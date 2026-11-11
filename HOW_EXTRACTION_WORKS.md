# How extraction works

**Docling 2.146** does layout, reading order and tables. It calls **Tesseract 5** for OCR, and a **VLM** describes what is inside each figure. A DOCX is first rendered to PDF by LibreOffice: a Word file has no fixed pages, and every answer must cite a page.

**Why Docling.** It is one open-source pipeline (MIT licence) that covers layout, reading order, tables, figure boxes and OCR, and it keeps the doc, page and box of every item, which is what our citations need. We looked at the alternatives:
- **PyMuPDF / pdfplumber** only read the PDF's text layer. They have no layout model and no OCR, and the scanned patent has no text layer at all.
- **Plain Tesseract** has no layout step. On the scanned patent, "one block" mode (psm 6) interleaved the two columns line by line (CER 0.37 on p1). Auto mode (psm 3) put the figure's words into the body text (CER 0.040).
- **Surya** (and Marker, which is built on it) we left out because of their licence.

## Text: layout and reading order
- Docling runs its layout model (Heron, an object detector) on each page image. Heron draws a box around each region and labels it: text, section header, list item, caption, table, picture, page header or footer. Headers and footers are treated as page furniture and kept out of the body.
- The text in each box comes from the PDF's text layer. OCR fills in only where there is none (see the next section).
- Reading order is rule-based, not learned, and there is **no column detector**. Docling links boxes stacked above each other, and links side-by-side boxes only when they line up almost exactly (≥ 80% vertical overlap, nothing in between). It then walks these links from the top down. A column's boxes are stacked, so each column is read top to bottom before the next one starts.
- On the scanned patent, Docling's layout followed by Tesseract on each region gave **CER 0.016** on page 1 and 0 on page 2. Over the 5 hand-typed gold pages, CER is 0.022 and WER 0.028.

## OCR: when it kicks in, which engine
- Layout runs first. A region is OCR'd if it has no text in the PDF's text layer or if it overlaps a bitmap image, e.g. the scanned patent, or labels inside a raster figure. Where both exist, the PDF text wins: an OCR word is kept only if no PDF text overlaps it.
- Docling's "auto" engine choice depends on the machine: ocrmac on macOS, Nemotron or RapidOCR elsewhere, and never Tesseract. We pin **Tesseract** (`TesseractCliOcrOptions(lang=["eng"])`) so every machine gets the same result. On the scan, Docling + Tesseract scored CER 0.016 / 0 (p1 / p2), against 0.033 / 0.185 for Docling + RapidOCR.
- Tesseract reads each region at 3× scale (about 216 dpi), checks its orientation first, and returns text lines with a confidence.

## Tables
- The layout model marks the table's box. TableFormer, Docling's table model (accurate mode), predicts the grid from the table image: rows, columns, merged cells, and which cells are headers. Each predicted cell is then filled with the PDF text that falls inside it, so the values themselves are not re-read by a model.
- We keep that structure: one search unit per row, cells joined by `|`, and the section heading in front. Example: `3. Electrical Specifications: Peak current per ESC channel | 60 A | 10 s max`.
- Against hand-typed gold, the EV-BMS-100 tables came out with every cell in the right row and column: electrical table 33/33, mechanical 15/15.

## Figures and images
- **Finding and cropping.** The layout model labels each picture region. Our code crops that box, plus a 10 pt margin, from the page rendered at 216 dpi (pypdfium2) and saves it to `extracted/figures/`.
- **Caption.** Docling links a caption only if the region is labelled "caption" and sits on the same page. That was right for only 4 of 9 figures here. In EV-BMS-100, for example, it linked the title printed inside the image, and the figure-2 caption is on the next page. So our code takes the figure number from the linked caption if that has one, else from the next text item if it starts with "FIG. n" / "Figure n", else from the title the VLM read.
- **Content.** A VLM (gpt-5-nano) lists the components with their label and numeral, the arrows (from → to), any other text, and a summary. It also splits all of this into pieces of about 40 words. Each piece, starting with the figure number (`FIG. 3: ...`), becomes a search unit with the figure's doc and page. It read 28/28 numerals on the four patent figures.
- **Tradeoff.** Captions alone are cheap but say nothing about what is inside. OCR of labels runs locally and gives the same result every run, but it loses numerals and arrows (see below). The VLM reads numerals and arrows, but it costs one call per figure and varies between runs: one fresh ingest missed 18 and 20 in UAV FIG. 3, and 74 and 76 in the scanned patent's FIG. 2.

## Where it breaks: numerals inside figures
- In UAV FIG. 3 (US2017/0320570A1), Docling + Tesseract read the label words but only "8", "8" and "4" of the nine numerals (12, 14, 16, 18, 20, 28, 34, 38, 46). So "what is component 18 in FIG. 3?" (dev q15) came back "not found".
- **Why.** The numerals sit on the corners of the boxes. A numeral touching a box line forms one connected shape with it, and Tesseract treats that as drawing, not text, so the first digit was lost (18 → "8", 14 → "4"). Neither resolution nor Docling was the cause: upscaling 2× or 3× did not help, and plain Tesseract on the embedded image did the same.
- **First fix: erase the boxes.** Removing horizontal and vertical lines before OCR read all 9 numerals in UAV FIG. 3.
- **Where that fix broke: arrows through numerals.** In the scanned patent's FIG. 2 (US2,988,237), an arrow runs along the top bar of the 7 in "74" and "76". Erasing the arrow also erases the bar, and none of the five pixel-based methods we tried read them.
- **What we did.** We switched to VLM descriptions, the only method that read 74 and 76 (7/7 on the scan). One long description per figure ranked too low in BM25, so the VLM also splits its description into the search-sized pieces described above.

**Other places it breaks on this corpus.**
- Caption linking: only 4 of 9 figures got the right caption.
- On the scan, "transfer" was read as "transter".
- The scan's page header ("United States Patent", the patent number and date) is labelled furniture and dropped.
