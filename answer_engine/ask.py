"""make ask Q="..."                          -> one answer, printed as JSON in the brief's shape
make answer QUESTIONS=file.json OUT=out.json -> answers for a questions file ([{"id", "question"}, ...], e.g. a hidden test set),
                                                written as [{"id", "answer", "citations", "not_found"}, ...]"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tqdm import tqdm

from .config import WORKERS
from .engine import ask, brief_output, database, index


def answer_all(questions):
    """ask() for every question, WORKERS at a time -> list of (final, trace), in the input order."""
    index(), database()                           # build once, before the threads start
    with ThreadPoolExecutor(WORKERS) as pool:
        runs = pool.map(lambda q: ask(q["question"]), questions)
        return list(tqdm(runs, total=len(questions), desc="answering", unit="question"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question", nargs="?", help="one question")
    parser.add_argument("--questions", help="a JSON file with a list of {id, question}")
    parser.add_argument("--out", default="answers.json", help="where to write the answers for --questions")
    args = parser.parse_args()
    if args.questions:
        questions = json.loads(Path(args.questions).read_text())
        answers = [{"id": q["id"], **brief_output(final)} for q, (final, _) in zip(questions, answer_all(questions))]
        Path(args.out).write_text(json.dumps(answers, indent=1, ensure_ascii=False))
        print(f"{len(answers)} answers -> {args.out}")
    elif args.question:
        print("Answering: search, router, answer model (about 10-20 s)...", file=sys.stderr)
        final, _ = ask(args.question)
        print(json.dumps(brief_output(final), indent=1, ensure_ascii=False))
    else:
        parser.error('give a question (make ask Q="...") or a questions file (make answer QUESTIONS=...)')


if __name__ == "__main__":
    main()
