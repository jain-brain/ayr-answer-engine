"""The answer engine: units -> BM25 search -> (router + SQL) -> answer with citations -> citation check.

ask(question) returns our final answer plus a trace of each step (units shown, route, the model's raw reply),
so a wrong answer can be traced to retrieval or generation.
"""
import re
import sqlite3
import sys
import threading
from difflib import SequenceMatcher
from functools import cache

import pandas as pd
from docling_core.types.doc import DoclingDocument, PictureItem, SectionHeaderItem, TableItem, TextItem
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from . import llm
from .config import (BM25_B, BM25_K1, CORPUS, EXTRACTED, K, MODEL, QUOTE_MIN_SIMILARITY, ROUTER, SCHEMA_MAX_DISTINCT,
                     SYSTEM)


# ---------- Units: the pieces the engine searches and cites; each keeps its doc and page ----------
def make_units(json_path):
    doc = DoclingDocument.load_from_json(json_path)
    units, section = [], ""
    for item, _ in doc.iterate_items():                  # body items in reading order (text inside figures is skipped)
        page = item.prov[0].page_no if item.prov else None
        if isinstance(item, SectionHeaderItem):
            section = item.text                          # remember the current heading, don't make it a unit
        elif isinstance(item, TableItem):
            for row in item.data.grid:                   # one unit per table row
                cells = " | ".join(cell.text for cell in row)
                units.append({"doc": json_path.stem, "page": page, "type": "table row", "text": f"{section}: {cells}"})
        elif isinstance(item, PictureItem):              # one unit per piece of the figure's VLM description (one line each)
            if item.meta and item.meta.description:
                for piece in filter(str.strip, item.meta.description.text.split("\n")):   # skip blank lines
                    units.append({"doc": json_path.stem, "page": page, "type": "figure", "text": f"{section}: {piece}"})
        elif isinstance(item, TextItem):                 # paragraphs, captions, list items, ...
            units.append({"doc": json_path.stem, "page": page, "type": item.label.value, "text": f"{section}: {item.text}"})
    return units


def tokenize(s):
    return re.findall(r"[a-z0-9]+", s.lower())           # lowercase words and numbers: "RJA-40" -> ["rja", "40"]


@cache
def index():
    """All units + the BM25 index over them (built once)."""
    paths = sorted(EXTRACTED.glob("*.json"))
    if not paths:
        raise SystemExit("No extracted documents in extracted/. Run `make ingest` first.")
    units = pd.DataFrame([u for path in paths for u in make_units(path)])
    units.insert(0, "unit_id", [f"U{i:03d}" for i in range(len(units))])
    # Search reads doc name + text, so a product name in the question matches that product's units.
    bm25 = BM25Okapi([tokenize(d + " " + t) for d, t in zip(units.doc, units.text)], k1=BM25_K1, b=BM25_B)
    return units, bm25


def search(question, k=K):
    units, bm25 = index()
    return units.assign(score=bm25.get_scores(tokenize(question))).sort_values("score", ascending=False).head(k)


# ---------- Structured files: every CSV / XLSX becomes one SQLite table ----------
@cache
def database():
    """In-memory SQLite with one table per CSV / XLSX, the schema text the router sees, and table -> source file stem."""
    files = sorted(p for p in CORPUS.glob("*/*") if p.suffix.lower() in {".csv", ".xlsx"} and not p.name.startswith((".", "~$")))
    db = sqlite3.connect(":memory:", check_same_thread=False)
    schema, table_doc = [], {}
    for path in files:
        name = re.sub(r"\W+", "_", path.stem).lower()     # test_log.csv -> test_log
        df = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
        df.to_sql(name, db, index=False)
        table_doc[name] = path.stem
        # What the router is shown: name, row count, columns with types, 3 example rows, and every value of the
        # text columns with few distinct values (e.g. unit_type, result), so it writes exact literals like result='FAIL'.
        lines = [f"Table {name} ({len(df)} rows, from {path.name})",
                 f"Columns: {', '.join(f'{col} ({dtype})' for col, dtype in df.dtypes.astype(str).items())}"]
        for col in df.columns:
            values = df[col].dropna().unique()
            if not pd.api.types.is_numeric_dtype(df[col]) and len(values) <= SCHEMA_MAX_DISTINCT:
                lines.append(f"Values of {col}: {', '.join(map(str, values))}")
        lines.append(f"Example rows:\n{df.head(3).to_csv(index=False)}")
        schema.append("\n".join(lines))
    return db, "\n\n".join(schema), table_doc


class Route(BaseModel):
    use_sql: bool                                 # True = the tables can help answer
    sql: str                                      # one SQLite SELECT query if use_sql, else ""


_db_lock = threading.Lock()                       # one SQLite connection, shared by the worker threads


def run_sql(sql):
    if not sql.strip().lower().startswith("select"):   # read-only: refuse anything that isn't a SELECT
        raise ValueError(f"not a SELECT query: {sql}")
    db, _, _ = database()
    with _db_lock:
        return pd.read_sql(sql, db)


# ---------- Answer + citation check ----------
class Citation(BaseModel):
    unit_id: str                                  # e.g. "U050"
    quote: str                                    # words copied from that unit (checked below)


class Answer(BaseModel):                          # the JSON shape the model must return
    answerable: bool
    answer: str
    citations: list[Citation]


def answer(question, hits):
    evidence = "\n\n".join(f"[{u.unit_id}] {u.doc} · p{u.page} · {u.type}\n{u.text}" for u in hits.itertuples())
    try:
        return llm.parse(MODEL, SYSTEM, f"Evidence:\n\n{evidence}\n\nQuestion: {question}", Answer)
    except Exception as e:                        # API or parsing failure: record it instead of crashing
        print("answer step failed:", e, file=sys.stderr)
        return Answer(answerable=False, answer="error raised", citations=[])


def find_quote(quote, text):
    """The stretch of `text` most similar to `quote` -> (similarity 0-1, that stretch in the unit's own words)."""
    q, words = " ".join(quote.split()).lower().split(), text.split()
    best = (0.0, "")
    for i in range(max(1, len(words) - len(q) + 1)):     # slide a window as long as the quote over the text
        window = words[i:i + len(q)]
        best = max(best, (SequenceMatcher(None, q, [w.lower() for w in window]).ratio(), " ".join(window)))
    return best


def check_citations(result, hits):
    """Keep a citation only if it points to a unit the model was shown and its quote is close enough to that unit's text.
    A kept citation gets doc + page from the unit and the unit's own words as its quote.
    If the model said "answerable" but no citation survives, the answer becomes "not found"."""
    shown = hits.set_index("unit_id")
    citations = []
    for c in result.citations:
        if c.unit_id not in shown.index:
            continue
        similarity, exact_quote = find_quote(c.quote, shown.loc[c.unit_id, "text"])
        if similarity >= QUOTE_MIN_SIMILARITY:
            unit = shown.loc[c.unit_id]
            citations.append({"doc": unit["doc"], "page": int(unit["page"]), "unit_id": c.unit_id, "quote": exact_quote})
    return {"answer": result.answer if citations or not result.answerable else "not found", "citations": citations}


# ---------- The full pipeline ----------
def ask(question):
    """Documents always, plus the SQL result when the router says the tables can help (a failed SQL step -> documents only).
    Returns (final, trace): final = {"answer", "citations": [{doc, page, unit_id, quote}]}; trace = what each step did."""
    hits = search(question)                       # top-K document units, always
    trace = {"route": None, "sql_error": None}
    try:
        _, schema, table_doc = database()
        route = llm.parse(MODEL, ROUTER.format(schema=schema), question, Route)
        trace["route"] = route.model_dump()
        if route.use_sql:
            rows = run_sql(route.sql)
            sql_units = pd.DataFrame([           # the SQL result becomes an extra unit, cited as the table's file, page 1
                {"unit_id": f"SQL_{table}", "doc": doc, "page": 1, "type": "sql result",
                 "text": f"Query: {route.sql}\nResult:\n{rows.to_csv(index=False)}"}
                for table, doc in table_doc.items() if table in route.sql])
            hits = pd.concat([sql_units, hits], ignore_index=True)
    except Exception as e:
        trace["sql_error"] = str(e)
        print("SQL step skipped:", e, file=sys.stderr)
    result = answer(question, hits)
    trace["shown"] = [f"{u.unit_id} {u.doc} p{u.page}" for u in hits.itertuples()]   # in rank order
    trace["raw answer"] = result.model_dump()
    return check_citations(result, hits), trace


@cache
def source_files():
    """doc stem -> original file name (e.g. RJA-40_actuator_design_document -> .docx, test_log -> .csv)."""
    return {p.stem: p.name for p in CORPUS.glob("*/*") if p.is_file()}


def brief_output(final):
    """The output shape the brief asks for: {"answer", "citations": [{"doc", "page"}], "not_found"}."""
    pages = dict.fromkeys((source_files().get(c["doc"], c["doc"]), c["page"]) for c in final["citations"])   # unique, in order
    return {"answer": final["answer"], "citations": [{"doc": d, "page": p} for d, p in pages], "not_found": not final["citations"]}
