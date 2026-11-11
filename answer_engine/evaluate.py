"""make eval: measures each stage, so a wrong answer can be traced to extraction, retrieval or generation.

1. Extraction, against gold we typed by hand (evals/gold/):
   - OCR text: CER / WER per page, for the scanned patent and the EV-BMS-100 design doc (ocr/<doc>.docx);
   - tables: cell accuracy (a cell is right if the same row and column hold the same text);
   - figures (figures.json): found on the right page, right figure number, Docling's own caption link, numerals read with their labels.
2. Retrieval + answers, on the dev set (dev_set/questions.json; 4 gold pages corrected, see README),
   or on any questions file in the same format: make eval QUESTIONS=path/to/questions.json
   - recall at K: a gold page is among the K units shown to the model (a SQL result unit counts);
   - judge correct: an LLM judge finds our answer states the same facts as the reference;
   - citation precision: share of our cited pages that are gold pages;
   - said not found: on unanswerable questions this should be 1, on all others 0;
   - figure cited: for figure questions, a cited unit is a piece of the asked figure.
Writes results/: <set>_answers.json (the brief's output shape), <set>_per_question.json (scores + what each step did),
one CSV per table; <set> = "dev" for the dev set, else the questions file's name.
"""
import argparse
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import docx
import jiwer
import pandas as pd
from docling_core.types.doc import DoclingDocument, ListItem, TableItem, TextItem
from docx.table import Table
from pydantic import BaseModel
from tqdm import tqdm

from . import llm
from .ask import answer_all
from .config import CORPUS, EXTRACTED, GOLD, JUDGE, K, MODEL, RESULTS, WORKERS
from .engine import brief_output, index, tokenize

# Dev-set gold pages we checked against the source pages and corrected (README: "Dev-set gold page corrections").
AUDITED = {"q02": ["US2988237A_programmed_article_transfer p1"],                         # answer only on p1 (scan)
           "q05": ["US20170320570A1_uav_vtol p1", "US20170320570A1_uav_vtol p2"],        # supported on both pages
           "q07": ["EV-BMS-100_design_document p2"],                                    # IP67 row is on p2
           "q16": ["EV-BMS-100_design_document p2", "EV-BMS-100_design_document p3"]}   # image p2, caption p3


# ---------- 1. Extraction ----------
def read_gold(path):
    """A gold docx -> {page: text}, {page: [table rows]}. Tables are flattened row by row.
    Skipped: [PAGE ...] markers, note lines ("Figure 1 diagram text ...", "Caption", "Figure 1 caption"),
    and the text inside drawings (a "[PAGE n | figure]" section, or the lines after "Figure N diagram text")."""
    pages, tables, page, skipping = {}, defaultdict(list), None, False
    for block in docx.Document(path).iter_inner_content():   # paragraphs and tables, in document order
        if isinstance(block, Table):
            rows = [[" ".join(cell.text.split()) for cell in r.cells] for r in block.rows]
            tables[page].append(rows)
            pages[page] += [" ".join(r) for r in rows]
            continue
        line = block.text.strip()
        marker = re.match(r"\[PAGE (\d+)(.*)\]$", line)
        if marker:
            page, skipping = int(marker.group(1)), "figure" in marker.group(2).lower()
            pages.setdefault(page, [])
        elif re.match(r"Figure \d+ diagram text", line):
            skipping = True
        elif line == "Caption" or re.match(r"Figure \d+ caption$", line):
            skipping = False
        elif line and not skipping:
            pages[page].append(line)
    return {p: " ".join(" ".join(lines).split()) for p, lines in pages.items()}, tables


def extracted_pages(doc):
    """Our extraction in the gold's form: text per page in reading order (tables flattened row by row), and the tables."""
    pages, tables = defaultdict(list), defaultdict(list)
    for item, _ in doc.iterate_items():           # body items in reading order (text inside figures is skipped)
        if not getattr(item, "prov", None):
            continue
        page = item.prov[0].page_no
        if isinstance(item, TableItem):
            rows = [[" ".join(cell.text.split()) for cell in row] for row in item.data.grid]
            tables[page].append(rows)
            pages[page] += [" ".join(r) for r in rows]
        elif isinstance(item, TextItem):
            marker = item.marker + " " if isinstance(item, ListItem) and item.marker else ""   # claims: put "1." back
            pages[page].append(marker + item.text)
    return {p: " ".join(" ".join(lines).split()) for p, lines in pages.items()}, tables


def cell_accuracy(gold_rows, rows):
    cells = [(r, c, cell) for r, row in enumerate(gold_rows) for c, cell in enumerate(row)]
    hits = sum(r < len(rows) and c < len(rows[r]) and rows[r][c] == cell for r, c, cell in cells)
    return hits, len(cells)


def ocr_and_tables():
    ocr, tables, refs, hyps = [], [], [], []
    for gold_path in sorted((GOLD / "ocr").glob("*.docx")):
        gold_text, gold_tables = read_gold(gold_path)
        ours, our_tables = extracted_pages(DoclingDocument.load_from_json(EXTRACTED / f"{gold_path.stem}.json"))
        for p, ref in sorted(gold_text.items()):
            hyp = ours.get(p, "")
            ocr.append({"doc": gold_path.stem, "page": p, "CER": jiwer.cer(ref, hyp), "WER": jiwer.wer(ref, hyp)})
            refs.append(ref)
            hyps.append(hyp)
            for i, g in enumerate(gold_tables.get(p, [])):      # gold table i on a page vs our table i on that page
                t = our_tables[p][i] if i < len(our_tables[p]) else []
                hits, total = cell_accuracy(g, t)
                tables.append({"doc": gold_path.stem, "page": p, "table": i + 1, "gold shape": f"{len(g)} x {len(g[0])}",
                               "our shape": f"{len(t)} x {len(t[0])}" if t else "missing", "cells right": f"{hits}/{total}",
                               "accuracy": hits / total})
    ocr.append({"doc": "all pages", "page": "", "CER": jiwer.cer(refs, hyps), "WER": jiwer.wer(refs, hyps)})   # all edits / all gold
    return pd.DataFrame(ocr), pd.DataFrame(tables)


def fig_key(s):                                   # "FIG. 3", "Figure 3", "fig 3" -> "fig 3"
    m = re.search(r"\b(?:fig\.?|figure)\s*(\d+[a-z]?)", s or "", re.I)
    return m and "fig " + m.group(1).lower()


def figures():
    rows = []
    for g in json.loads((GOLD / "figures.json").read_text()):
        doc = DoclingDocument.load_from_json(EXTRACTED / f"{g['doc']}.json")
        pics = [p for p in doc.pictures if p.prov[0].page_no == g["page"]]
        desc = pics[0].meta.description.text if pics and pics[0].meta and pics[0].meta.description else ""
        pieces = [set(tokenize(line)) for line in desc.split("\n")]
        read = [n for n, label in g["numerals"].items() if any(n in p and set(tokenize(label)) <= p for p in pieces)]
        same = lambda a, b: " ".join(a.replace("—", "-").split()).lower() == " ".join(b.replace("—", "-").split()).lower()
        rows.append({"doc": g["doc"], "page": g["page"], "figure": g["figure"], "found": bool(pics),
                     "figure number right": bool(desc) and fig_key(desc.split(":")[0]) == fig_key(g["figure"]),
                     "docling caption right": bool(pics) and same(pics[0].caption_text(doc), g["caption"]),
                     "numerals read": f"{len(read)}/{len(g['numerals'])}" if g["numerals"] else "",
                     "numerals missed": ", ".join(f"{n} {label}" for n, label in g["numerals"].items() if n not in read)})
    return pd.DataFrame(rows)


# ---------- 2. Retrieval + answers ----------
class Judgement(BaseModel):
    correct: bool


def judge(question, reference, ours):
    try:
        verdict = llm.parse(MODEL, JUDGE, f"Question: {question}\nReference answer: {reference}\nOur answer: {ours}", Judgement)
        return "correct" if verdict.correct else "incorrect"
    except Exception as e:                        # API or parsing failure: record it instead of crashing
        print("judge failed:", e)
        return "error raised"


def figure_cited(question, gold_doc, unit_ids):
    """A cited unit is a figure piece of the gold document that names the figure the question asks about."""
    units = index()[0].set_index("unit_id")
    asked = fig_key(question)
    return any(u in units.index and units.loc[u, "type"] == "figure" and units.loc[u, "doc"] == gold_doc
               and asked in {fig_key(m) for m in re.findall(r"\b(?:fig\.?|figure)\s*\d+[a-z]?", units.loc[u, "text"], re.I)}
               for u in unit_ids)


def question_set(path, corrections):
    """Answer, judge and score every question in `path`; `corrections` = gold pages to use instead of the file's (by id)."""
    dev = json.loads(path.read_text())
    runs = answer_all(dev)
    with ThreadPoolExecutor(WORKERS) as pool:
        verdicts = pool.map(lambda qr: judge(qr[0]["question"], qr[0]["reference_answer"], qr[1][0]["answer"]), zip(dev, runs))
        verdicts = list(tqdm(verdicts, total=len(dev), desc="judging", unit="question"))
    rows, answers = [], []
    for q, (final, trace), verdict in zip(dev, runs, verdicts):
        gold = set(corrections.get(q["id"], [f"{Path(e['doc']).stem} p{e['page']}" for e in q["evidence"]]))
        shown = [s.split(" ", 1)[1] for s in trace["shown"]]      # "U012 <doc> p2" -> "<doc> p2", in rank order
        cited = sorted({f"{c['doc']} p{c['page']}" for c in final["citations"]})
        answers.append({"id": q["id"], **brief_output(final)})
        rows.append({
            "id": q["id"], "type": q["type"], "question": q["question"], "reference answer": q["reference_answer"],
            "our answer": final["answer"], "judge": verdict,
            "recall at K": bool(gold & set(shown[:K])) if gold else None,
            "judge correct": verdict == "correct",
            "citation precision": len(gold & set(cited)) / len(cited) if cited else None,
            "said not found": not final["citations"],
            "figure cited": figure_cited(q["question"], next(iter(gold)).rsplit(" p", 1)[0], [c["unit_id"] for c in final["citations"]])
                            if q["type"] == "figure" else None,
            "gold pages": sorted(gold), "cited": [f"{c['unit_id']} {c['doc']} p{c['page']}: {c['quote']}" for c in final["citations"]],
            **trace})
    return pd.DataFrame(rows), answers


def main():
    dev_path = CORPUS / "dev_set" / "questions.json"
    parser = argparse.ArgumentParser(description="Extraction, retrieval and answer scores.")
    parser.add_argument("questions", nargs="?", type=Path, default=dev_path, help="questions file (default: the dev set)")
    path = parser.parse_args().questions.resolve()
    is_dev = path == dev_path.resolve()
    name = "dev" if is_dev else path.stem
    RESULTS.mkdir(exist_ok=True)
    pd.set_option("display.width", 250, "display.max_columns", 20, "display.max_colwidth", 60)

    print("Scoring the extraction against the hand-typed gold...")
    ocr, tables = ocr_and_tables()
    figs = figures()
    print("\n=== Extraction: OCR text vs hand-typed gold (lower is better)\n", ocr.round(3).to_string(index=False))
    print("\n=== Extraction: table cells vs hand-typed gold\n", tables.round(3).to_string(index=False))
    print("\n=== Extraction: figures vs hand-typed gold\n", figs.to_string(index=False))

    print(f"\nRunning {path.name} ({WORKERS} questions at a time)...")
    results, answers = question_set(path, AUDITED if is_dev else {})     # our page corrections are for the dev set only
    metrics = ["recall at K", "judge correct", "citation precision", "said not found", "figure cited"]
    scores = results[["type"] + metrics].assign(**{m: results[m].astype(float) for m in metrics})
    by_type = scores.groupby("type").mean()
    by_type.loc["all"] = scores[metrics].mean()
    by_type = by_type.T.rename(index={"recall at K": f"recall at {K}"})
    print(f"\n=== {name} ({len(results)} questions): mean per question type\n", by_type.round(2).to_string())

    ocr.to_csv(RESULTS / "extraction_ocr.csv", index=False)
    tables.to_csv(RESULTS / "extraction_tables.csv", index=False)
    figs.to_csv(RESULTS / "extraction_figures.csv", index=False)
    by_type.to_csv(RESULTS / f"{name}_by_type.csv")
    (RESULTS / f"{name}_answers.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False))
    (RESULTS / f"{name}_per_question.json").write_text(results.to_json(orient="records", indent=1, force_ascii=False))
    print(f"\nWritten to {RESULTS}/")


if __name__ == "__main__":
    main()
