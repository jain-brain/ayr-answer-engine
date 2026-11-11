"""All settings in one place: paths, models, retrieval, citation check and prompts.
Paths, models and the API key can be overridden in .env (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
load_dotenv(REPO / ".env", override=True)          # values in .env win over the shell's

# --- Paths ---
CORPUS = (REPO / os.getenv("CORPUS_DIR", "swe-coding-exercise")).resolve()   # the exercise package: patents/, design_docs/, structured/, dev_set/
EXTRACTED = REPO / "extracted"                     # make ingest writes one <doc>.json (+ .md) per document here, figure crops in figures/
RESULTS = REPO / "results"                         # make eval writes its tables here
GOLD = REPO / "evals" / "gold"                     # hand-typed gold for the extraction eval

# --- Models (any OpenAI-compatible model; set OPENAI_BASE_URL in .env for another provider) ---
MODEL = os.getenv("ANSWER_MODEL", "gpt-5-nano")    # router, answer and judge
FIGURE_MODEL = os.getenv("FIGURE_MODEL", MODEL)    # describes each figure, so it must accept images
WORKERS = 8                                        # questions answered in parallel by make answer / make eval

# --- Retrieval ---
K = 10                           # units BM25 returns and the model sees
BM25_K1 = 1.5                    # how fast repeats of a word stop adding score (rank_bm25 default)
BM25_B = 0.75                    # how much long units are penalised: 0 = not at all, 1 = fully (rank_bm25 default)

# --- Citation check ---
QUOTE_MIN_SIMILARITY = 0.9       # a quote must be at least this similar (word by word, 0-1) to some stretch of the cited unit

# --- Router ---
SCHEMA_MAX_DISTINCT = 20         # the router sees every value of a text column that has at most this many distinct values

# --- Prompts ---
SYSTEM = """You answer questions about engineering documents using only the evidence units provided.
Each unit starts with [unit_id] followed by its document, page and type.
Cite every unit you use, with a short quote copied exactly from that unit's text without changing even a single word (since otherwise it would unnecessarily be rejected later).
If the evidence does not contain the answer, set answerable to false, answer "not found", and give no citations."""

# {schema} is filled in with the table description (engine.database()).
ROUTER = """You route questions about a set of engineering documents (design documents and patents) and two data tables.
The tables are in SQLite:

{schema}

What each source holds:
- test_log: results of individual test runs (measured values, PASS/FAIL, operators, dates, serial numbers).
- bill_of_materials: parts, quantities and costs.
- The documents: product specifications and ratings (e.g. rated current, temperature range, IP rating), descriptions, figures, patent claims.
A question about a product's specification or rating goes to the documents, even if test_log has a similar test_type.

If the question is about test runs, tested units, parts or costs, set use_sql to true and write one SQLite SELECT query that answers it.
Otherwise set use_sql to false and sql to ""."""

FIGURE_PROMPT = """You describe one figure cropped from an engineering document (a patent drawing, block diagram, photo or rendering).
title: the figure's title as printed in the image (e.g. "FIG. 3"), or "" if none.
components: every component drawn, with its label text exactly as printed and the reference numeral printed next to it ("" if none).
A numeral belongs to the component whose box or outline it sits at or points to.
arrows: every arrow or connecting line, from the component it starts at to the component its arrowhead points to, as drawn.
Name components by their label text and numeral.
other_text: any other text printed in the figure, exactly as printed.
summary: one or two sentences on what the figure shows, including counts of repeated elements (e.g. 4 connector ports).
Describe only what you can see. Never guess a numeral or a label.
units: the same description split into small self-contained pieces for a search index.
Each piece is 1-2 full sentences (about 40 words at most) about one thing: one component with its numeral and what it connects to,
or one group of related arrows, or the summary. Example: "Component 18 is the left thrust device, connected to the left wing 14."
Every component, numeral and arrow must appear in at least one piece. Do not mention the figure number; it is added to each piece for you."""

JUDGE = """You compare an answer to a reference answer for a question about engineering documents.
Mark it correct if it states the same facts as the reference (same values and units; wording may differ).
Mark it incorrect if a fact is wrong or missing, or if one says "not found" and the other doesn't."""
