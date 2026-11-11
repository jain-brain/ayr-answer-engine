"""make ingest: every PDF / DOCX in the corpus -> extracted/<doc>.json (the Docling document) + <doc>.md (readable copy).

1. Extraction: Docling (layout, reading order, tables) with Tesseract as the OCR engine, pinned explicitly.
   A DOCX has no fixed pages, so LibreOffice first converts it to PDF (extracted/<doc>.pdf); page numbers come from that render.
2. Figures: for each picture Docling found, our code crops it from the rendered page and a VLM describes it
   (components + reference numerals, arrows, summary), split into small pieces. The pieces, each starting with the
   figure number ("FIG. 3: ..."), are stored in the picture's own entry (picture.meta.description), so they keep its doc and page.
The CSV / XLSX files are not ingested here: engine.database() loads them into SQLite when a question is asked.
"""
import base64
import io
import os
import re
import subprocess

import pypdfium2 as pdfium
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import TextItem
from docling_core.types.doc.document import DescriptionMetaField, PictureMeta
from pydantic import BaseModel
from tqdm import tqdm

from . import llm
from .config import CORPUS, EXTRACTED, FIGURE_MODEL, FIGURE_PROMPT

FIGURES = EXTRACTED / "figures"                   # the crops the VLM saw, to check by eye


class Component(BaseModel):
    numeral: str                                  # reference numeral next to it, "" if none
    text: str                                     # its label, exactly as printed


class Arrow(BaseModel):
    source: str                                   # component the arrow starts at
    target: str                                   # component the arrowhead points to


class FigureDescription(BaseModel):               # the JSON shape the VLM must return (prompt: FIGURE_PROMPT)
    title: str
    components: list[Component]
    arrows: list[Arrow]
    other_text: list[str]
    summary: str
    units: list[str]                              # the description split into search-sized pieces, without the figure number


FIG_NUMBER = re.compile(r"^\s*(fig\.?|figure)\s*\d+[a-z]?", re.I)   # "FIG. 3 ...", "FIG. 2A ...", "Figure 1 — ..."


def documents():
    """The PDFs and DOCXs one folder down in the corpus (patents/, design_docs/); skips hidden and Office lock files."""
    return sorted(p for p in CORPUS.glob("*/*") if p.suffix.lower() in {".pdf", ".docx"} and not p.name.startswith((".", "~$")))


def to_pdf(path):
    if path.suffix.lower() != ".docx":
        return path
    soffice = os.getenv("SOFFICE", "soffice")     # LibreOffice's command-line binary
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", EXTRACTED, path], check=True, capture_output=True)
    return EXTRACTED / f"{path.stem}.pdf"


def crop(pdf_path, picture, doc, scale=3):        # scale 3 = 216 dpi render
    prov = picture.prov[0]
    page = pdfium.PdfDocument(str(pdf_path))[prov.page_no - 1]
    box = prov.bbox.to_top_left_origin(doc.pages[prov.page_no].size.height)
    m = 10                                        # 10 pt margin, so labels on the figure's edge aren't cut off
    return page.render(scale=scale).to_pil().crop(((box.l - m) * scale, (box.t - m) * scale, (box.r + m) * scale, (box.b + m) * scale))


def describe(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    image = {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}
    return llm.parse(FIGURE_MODEL, FIGURE_PROMPT, [{"role": "user", "content": [image]}], FigureDescription)


def figure_label(doc, picture, f):
    # The figure's number (+ title), taken from the document so every piece says which figure it is:
    # 1) the caption Docling linked to the picture, 2) else the next text in reading order if it starts with "FIG. n" / "Figure n",
    # 3) else the title the VLM read in the image (the crop often leaves the title out).
    caption = picture.caption_text(doc)
    if FIG_NUMBER.match(caption):
        return caption
    items = [item for item, _ in doc.iterate_items()]
    i = next(i for i, item in enumerate(items) if item.self_ref == picture.self_ref)
    for item in items[i + 1:i + 3]:
        if isinstance(item, TextItem) and FIG_NUMBER.match(item.text):
            return item.text
    if not FIG_NUMBER.match(f.title):
        tqdm.write(f"  WARNING: no figure number found for {picture.self_ref}")
    return f.title


def describe_figures(doc, pdf_path):
    for n, picture in enumerate(tqdm(doc.pictures, desc="  figures", unit="figure", leave=False), 1):
        img = crop(pdf_path, picture, doc)
        img.save(FIGURES / f"{pdf_path.stem}_fig{n}_p{picture.prov[0].page_no}.png")
        f = describe(img)
        label = figure_label(doc, picture, f)
        number = FIG_NUMBER.match(label).group(0).strip() if FIG_NUMBER.match(label) else label   # "FIG. 3", not the whole caption
        picture.meta = picture.meta or PictureMeta()
        picture.meta.description = DescriptionMetaField(text="\n".join(f"{number}: {piece}" for piece in f.units), created_by=FIGURE_MODEL)
        tqdm.write(f"  figure {n} (page {picture.prov[0].page_no}, {number}): {len(f.units)} pieces")
        if not f.units:
            tqdm.write(f"  WARNING: the VLM returned no description for figure {n}; re-run `make ingest` to retry")


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    options = PdfPipelineOptions(do_ocr=True, ocr_options=TesseractCliOcrOptions(lang=["eng"]))
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    paths = documents()
    if not paths:
        raise SystemExit(f"No PDF or DOCX found under {CORPUS}. Set CORPUS_DIR in .env to the exercise folder.")
    bar = tqdm(paths, desc="documents", unit="doc")
    for path in bar:
        bar.set_postfix_str(path.name)
        pdf_path = to_pdf(path)
        doc = converter.convert(pdf_path).document
        tqdm.write(f"{path.name}: {doc.num_pages()} pages, {len(doc.pictures)} figures")
        describe_figures(doc, pdf_path)
        doc.save_as_json(EXTRACTED / f"{path.stem}.json")
        (EXTRACTED / f"{path.stem}.md").write_text(doc.export_to_markdown())


if __name__ == "__main__":
    main()
