# Each command installs the pinned dependencies (uv.lock) into .venv on first use.
RUN = uv run --frozen python -m

.PHONY: setup ingest ask answer eval

setup:    ## install the pinned dependencies (optional: every command below does it on first use)
	uv sync --frozen

ingest:   ## extract every document in the corpus + describe its figures -> extracted/
	$(RUN) answer_engine.ingest

ask:      ## make ask Q="What is the ingress protection rating of the EV-BMS-100?"
	$(RUN) answer_engine.ask "$(Q)"

answer:   ## make answer QUESTIONS=path/to/questions.json OUT=answers.json   (e.g. a hidden test set)
	$(RUN) answer_engine.ask --questions "$(QUESTIONS)" --out "$(or $(OUT),answers.json)"

eval:     ## extraction, retrieval and answer scores on the dev set -> results/   (or: make eval QUESTIONS=other_questions.json)
	$(RUN) answer_engine.evaluate $(QUESTIONS)
