# Answer Engine for Engineering Documents

**macOS only.** This code and these instructions were built and tested on macOS 15 (Apple Silicon). They have not been tested on Linux or Windows.

## Architecture

![Architecture](docs/architecture.svg)

## Setup and commands

### 1. System packages (install once, with [Homebrew](https://brew.sh))

```bash
brew install uv tesseract
brew install --cask libreoffice
```

- **uv** installs Python 3.12 and the pinned Python packages.
- **Tesseract 5** is the OCR engine.
- **LibreOffice** converts the DOCX to PDF so it has page numbers.
- **make** comes with the Xcode command-line tools (run `xcode-select --install` if it is missing).

### 2. Python packages

The versions are pinned in two files:
- `pyproject.toml` lists the 12 packages the code imports, with exact versions, and requires Python 3.12.
- `uv.lock` lists all 134 packages they pull in, with exact versions and file hashes. `requirements.txt` holds the same versions in pip's format, exported from the lock (`uv export --frozen --format requirements-txt --no-hashes -o requirements.txt`).

**With uv (recommended):** nothing to do. Every `make` command runs `uv run --frozen`, which creates `.venv/` and installs exactly what `uv.lock` lists on first use. To install up front, run `make setup` (`uv sync --frozen`).

**With pip instead:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

then run the commands without `make`:

```bash
python -m answer_engine.ingest
python -m answer_engine.ask "What is the IP rating of the EV-BMS-100?"
python -m answer_engine.ask --questions questions.json --out answers.json
python -m answer_engine.evaluate                    # dev set
python -m answer_engine.evaluate questions.json     # another questions file
```

The first `ingest` downloads Docling's layout and table models from Hugging Face.

### 3. Configuration

**Set your API key:**

```bash
export OPENAI_API_KEY=sk-...
```

**Corpus:** put the exercise folder (`patents/`, `design_docs/`, `structured/`, `dev_set/`) in the repo as `swe-coding-exercise/`.

**Optional settings** (in the shell, or in a `.env` file in the repo; `.env.example` lists them):
- `ANSWER_MODEL` / `FIGURE_MODEL` change the models (default `gpt-5-nano`).
- `OPENAI_BASE_URL` points to another OpenAI-compatible endpoint.
- `CORPUS_DIR` points to the exercise folder if it's somewhere else.

### 4. Commands

| Command | What it does |
|---|---|
| `make ingest` | Extracts every PDF / DOCX in the corpus and describes its figures → `extracted/` |
| `make ask Q="What is the IP rating of the EV-BMS-100?"` | One answer, as JSON in the brief's shape |
| `make answer QUESTIONS=questions.json OUT=answers.json` | Answers for a whole questions file (`[{"id", "question"}]`), e.g. a hidden test set |
| `make eval` | Extraction, retrieval and answer scores on the dev set → `results/` |
| `make eval QUESTIONS=questions.json` | The same scores on another questions file in the dev set's format (`id`, `type`, `question`, `reference_answer`, `evidence`) |

## Model and library choices

**Model: OpenAI `gpt-5-nano`** for all four model calls: figure descriptions, the SQL router, answers, and the judge.
- It was the cheapest model on OpenAI's pricing page. We chose the weakest, cheapest model on purpose, so the results show what the architecture does (extraction, search, SQL, the citation check) rather than what a strong model can make up for. Switching to a stronger model later is a one-line change.
- It is configurable: `ANSWER_MODEL` (router, answers, judge) and `FIGURE_MODEL` (figures, must accept images) take any OpenAI model, and `OPENAI_BASE_URL` takes any OpenAI-compatible endpoint. Every call returns a fixed JSON shape (Pydantic structured output), so a reply that doesn't fit is rejected rather than half-parsed.

**Libraries** (open source, all run locally):

| Library | What it does here | Why |
|---|---|---|
| Docling 2.146 | Layout, reading order, tables, figure boxes | One pipeline for text PDFs, the scan and the DOCX, and every item keeps its doc, page and box. Details in [HOW_EXTRACTION_WORKS.md](HOW_EXTRACTION_WORKS.md) |
| Tesseract 5 (pinned inside Docling) | OCR | Lowest error on the hand-typed scan: CER 0.016 / 0 (p1 / p2) vs 0.033 / 0.185 for RapidOCR |
| LibreOffice | DOCX → PDF | A Word file has no fixed pages; the render gives the page numbers we cite |
| pypdfium2 | Renders pages | Crops each figure for the VLM |
| rank-bm25 | Keyword search | See below |
| SQLite (Python built-in) + pandas / openpyxl | The CSV and XLSX as SQL tables | See below |
| jiwer, python-docx | Evaluation | CER / WER, and reading the hand-typed gold pages |

**Why BM25 + SQL for this corpus:**
- **Units, not chunks.** Each paragraph, table row and figure piece is one unit (188 in all), with its section heading in front and its doc and page attached. A table row keeps its cells (`Peak current per ESC channel | 60 A | 10 s max`), so "the value in row X, column Y" stays answerable.
- **BM25 over the units.** The questions name exact things: product names, part numbers, reference numerals, spec names. BM25 needs no model, and every score can be explained word by word, which is how the failures below were traced. Its weakness, needing the question's exact words, is in Known limitations, and hybrid search is in Future work.
- **SQL for the spreadsheets.** Counting, summing and filtering 109 test runs and 25 BOM lines must be exact. Rows as text units only answer single-row lookups, and pasting whole tables into the prompt leaves the model counting 109 rows by reading, which is unreliable, especially for a small model. So the router writes one read-only SELECT, and its result becomes one more unit the answer can cite (the file, page 1). The documents are always searched as well, so if the SQL step fails, the answer still comes from the documents.
- **Citations come from our code, not the model.** The model cites unit IDs with a quote. A citation is kept only if its quote is found in that unit (≥ 0.9 word similarity), and the doc and page come from the unit. An answer with no surviving citation becomes "not found".

## Results

All results in one table. The question columns are the 22 dev-set questions, scored against the audited gold pages (see the next section). Scores are the share of questions, from 0 to 1.

| Stage | Metric | Factual (5) | Table (7) | Figure (4) | Structured (4) | Unanswerable (2) | All |
|---|---|---|---|---|---|---|---|
| Extraction | OCR error rate, CER / WER (5 hand-typed pages: the scanned patent + EV-BMS-100) | | | | | | 0.022 / 0.028 |
| Extraction | Table cells in the right row and column (2 EV-BMS-100 tables) | | | | | | 48 / 48 |
| Extraction | Figures found | | | | | | 9 / 9 |
| Extraction | Figure number on the figure's pieces | | | | | | 8 / 9 |
| Extraction | Caption linked by Docling | | | | | | 4 / 9 |
| Extraction | Numerals read and linked in the patent figures | | | | | | 28 / 28 |
| Retrieval | Recall@10: a gold page among the 10 units shown | 1.00 | 1.00 | 1.00 | 1.00 | | 1.00 |
| Answers | Correct (LLM judge) | 0.80 | 0.86 | 1.00 | 0.75 | 1.00 | 0.86 (19 / 22) |
| Answers | Numbers match (±1%) | 0.50 | 0.83 | | 0.50 | | 0.64 |
| Answers | Citation precision: cited pages that are gold pages | 1.00 | 0.86 | 1.00 | 1.00 | | 0.95 |
| Answers | Said "not found" (should be 1 for unanswerable, 0 elsewhere) | 0.00 | 0.00 | 0.00 | 0.25 | 1.00 | right declines 2 / 2, wrong declines 1 / 20 |
| Answers | Figure questions cite the asked figure | | | 1.00 | | | 1.00 |

Empty cells: the metric doesn't apply (e.g. no numbers in the reference, no gold page for unanswerable questions). The RJA-40 Figure 2 description came back empty in this ingest, hence 8 / 9 figure numbers. Per-question detail (answer, citations, judge verdict, trace) is in `results/dev_per_question.json`.

**How answers are judged:**
- **Free text: an LLM judge plus a manual check.** The judge (gpt-5-nano) compares our answer with the reference: correct if it states the same facts, incorrect if a fact is wrong or missing, or if only one of the two says "not found". The judge isn't reliable yet when an answer is incomplete or worded differently (e.g. the same "180.0" for q20 was marked incorrect in one run and correct in another), so we read every answer it marks incorrect. In this run: q05 and q09 left out part of the reference (the tail-sitting recharging pad; the 10 s limit), and q18 said "not found".
- **Numbers:** every number in the reference must appear in our answer within **±1%**. Numbers inside names (`RJA-40`, `IP67`) are ignored.
- **Citations:** precision = share of our cited pages that are gold pages.
- **"Not found":** counted when an answer has no surviving citation.

## Dev-set gold page corrections

Page-level scores (recall@k, citation precision) are reported against an **audited** copy of the dev set's evidence pages. Four questions were checked against the source pages. Two dev-set pages are wrong, and two leave out a second page that also holds the answer.

| q | Question (short) | Dev set says | Audited | Where the answer actually is |
|---|---|---|---|---|
| q02 | What reduces the transfer head's traverse rate before the stopping point? (US2,988,237) | p2 | **p1** | Scanned patent. Only page 1 mentions the function control anticipator 64: "…cooperate with a function control anticipator 64 so that fast traverse of the transfer head is reduced in advance of the required stopping point…" (right column, plus the FIG. 2 description and claims 1–2). Page 2 has only the end of claim 3 and claim 4. |
| q07 | Ingress protection rating of the EV-BMS-100 enclosure | p3 | **p2** | "Ingress protection \| IP67 \| connectors mated" is a row of the mechanical spec table on page 2. Page 3 has no IP67. |
| q05 | What recharges the UAV's battery, and what is the mechanism called? (US2017/0320570A1) | p2 | **p1, p2** | Page 2, claim 3: "wireless power transfer (WPT) circuitry 40 configured to inductively recharge the onboard power source…". Page 1, body text: "The battery or batteries 38 may be inductively recharged via wireless power transfer (WPT) circuitry 40 while the UAV is in a tail-sitting position on a recharging pad." |
| q16 | How many M12 connector ports are shown in Figure 2 of the EV-BMS-100 design document? | p3 | **p2, p3** | The figure itself, showing the four ports and labelled "M12 connector x4", is on page 2. Its caption ("…showing the four M12 connector ports…") is on page 3. |

## Failure analysis

Failures found on the dev set while building the system. Each one was traced through the steps: the units shown to the model, the route, and the model's raw reply.

| q | Question | What went wrong | Stage | What we did |
|---|---|---|---|---|
| q01 | In US8,485,576 B2 (Robotic Gripper), what provides the attractive force at the tip of pin 120 in the electromagnetic embodiment? | Answered "not found". BM25 needs exact words, and four things worked against the right unit: (1) the question says "electromagnetic", the claim says "electromagnet" (no stemming); (2) "attractive force" is the wording of the neighbouring suction claim, so it lifts the wrong units; (3) the patent number written with commas tokenizes to `us8`, which matches nothing, while its digits lift short metadata units; (4) the answer sits in a long unit (several claims merged into one list item), which BM25 scores down. At k=5 the right unit ranked 6th. At k=10 it was retrieved, but the exact quote check dropped the citation ("the distal end" vs "a distal end"). | Retrieval, then the citation check | Prompt asks for quotes copied word for word; k 5 → 10 (still failed); then quotes checked by fuzzy matching (≥ 0.9 similarity). Now correct, citing p2. |
| q15 | In FIG. 3 of US2017/0320570A1, what is component 18? | "Not found" in every run. The figure's numerals were lost in extraction: Tesseract read the label words but only "8", "8" and "4" of the nine numerals (12, 14, 16, 18, 20, 28, 34, 38, 46). The numerals touch the box outlines, and Tesseract treats a numeral joined to a line as part of the drawing. | Extraction (figure OCR) | Erasing the box lines before OCR read all 9, but it failed where an arrow runs through a numeral (74 and 76 in the scanned patent's FIG. 2). So a VLM now describes each figure (components with their numerals, arrows). One long description per figure ranked too low in BM25, so the VLM also splits its description into ~40-word pieces, each a search unit starting with the figure number. Now correct. |
| q05 | What recharges the UAV's battery in US2017/0320570A1, and what is the mechanism called? | The answer was right, but the model attached the same quote to two units: the paragraph that holds it, and an empty heading from the same patent ("CLAIMS: What is claimed is:") that was listed first. That second citation was made up. BM25 had filled 4 of the top 5 with that same heading from four patents: the question's "what" (×2) and "is" match these 4-word units strongly. | Generation (citation), with noisy retrieval | Added the citation check: a citation is kept only if it points to a unit the model was shown and its quote is found in that unit's text. The heading was dropped; the output cites only UAV p1. |
| q20 | What is the extended cost of the FVT-ESC-40A line item in the bill of materials? | SQL returned the right value and the model answered with it bare, "180.0" (no "$", no 8 × $22.50). The LLM judge marked it incorrect; in a later run the same answer was marked correct. | Generation (answer form) and evaluation (judge) | Not fixed. |

## Known limitations

**Search needs the question's exact words.** BM25 matches whole words, with no stemming or synonyms, so when the question's words differ from the extracted text, the right unit scores low or not at all. Examples from this corpus:
- word forms and synonyms: "electromagnetic" vs "electromagnet" (q01), "component 18" vs "device 18" (q15);
- OCR misreads on the scanned patent: "transter" for "transfer";
- identifiers written differently: "US8,485,576" in the question vs "US 8,485,576" in the patent.

## What we chose not to build

- **No embeddings or vector store.** BM25 alone found a gold page for every dev question at k = 10; hybrid search is the next step (Future work).
- **No UI or HTTP API.** A CLI with JSON output, as the brief allows.
- **No agent loop.** Each question is at most one router call, one SQL query and one answer call, so every step can be traced and scored.
- **No OCR by the VLM.** The VLM only describes figure crops; all page text comes from Docling + Tesseract, running locally.
- **No experiment tracker in the package.** MLflow was used while building; the package writes a per-question trace to `results/` instead.
- **No Docker image or Linux/Windows support yet** (macOS only, see the top).

## Future work

1. **Figure descriptions with function, not just geometry.** Today the VLM mostly describes what is drawn: shapes, positions and arrows (e.g. "Left thrust device 18 is a rectangular block located below the left wing"). Asking it for what each component does would let figure units answer questions about function.
2. **Hybrid search.** Keep BM25 for exact terms (part numbers, numerals, spec names), and for harder queries, or when BM25 leads to "not found", hand off to (or mix in) similarity search over LLM embeddings, so questions whose words differ from the text still reach the right units.

## AI coding tools

I built this with **Claude Code** (Anthropic's coding agent in the terminal).

- **How the work was split.** I delegated the implementation to Claude Code: the notebook cells, this package, the Makefile, the eval code, test runs, and the scripts that traced a failing question through each step. That left my time for research, design and analysis: comparing options (OCR engines, five ways of reading figure numerals, BM25 settings), weighing design choices, and reading per-question traces to find which stage caused each failure. Decisions such as pinning Tesseract, describing figures with a VLM, splitting the descriptions into pieces, and reverting a BM25 change that broke other questions were made after looking at results on this corpus.
- **Saving and resuming: a `CLAUDE.md` design log.** Claude Code reads a `CLAUDE.md` file at the start of every session. We used it as a running design log, updated as we worked: the brief condensed, verified facts about the corpus, every decision with its reasoning and who made it, experiment results, failure analyses, open questions, and a session log. The work ran over a week of sessions, and the log let each new session (or one cut short by context limits) resume exactly where the last one stopped, without redoing decisions.
- **Step by step, checked by hand.** The engine was built one notebook cell at a time, and I reviewed each step before the next. This repo is the package version of the notebook's final state. I typed the extraction gold pages myself, independently of any tool, verified the four dev-set gold corrections against the source pages, and read every answer the judge marks incorrect.
