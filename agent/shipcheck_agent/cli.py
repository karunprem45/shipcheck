"""python -m shipcheck_agent.cli --diff pr.diff [--junit j.xml] [--bandit b.json] [--no-llm]"""
import argparse
import json
import sys

from .collect import build_evidence
from .llm import ClaudeClient
from .review import review, to_markdown


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", required=True)
    ap.add_argument("--junit")
    ap.add_argument("--bandit")
    ap.add_argument("--out", default="evidence.json")
    ap.add_argument("--md", default="review.md")
    ap.add_argument("--no-llm", action="store_true", help="static checks only")
    a = ap.parse_args(argv)

    with open(a.diff) as fh:
        diff_text = fh.read()
    llm = None
    if not a.no_llm:
        try:
            llm = ClaudeClient()
        except (KeyError, ImportError) as exc:
            print(f"LLM unavailable ({exc}); static checks only", file=sys.stderr)
    rep = review(diff_text, llm)
    with open(a.out, "w") as fh:
        json.dump(build_evidence(rep, a.junit, a.bandit), fh, indent=2)
    with open(a.md, "w") as fh:
        fh.write(to_markdown(rep))
    print(f"wrote {a.out} and {a.md}")


if __name__ == "__main__":
    main()
