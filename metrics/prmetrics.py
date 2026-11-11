"""Engineering productivity metrics from a JSONL export of merged PRs.

Each line: {"number": int, "created_at": iso, "first_review_at": iso|null,
            "merged_at": iso|null, "shipcheck": {"findings": int, "accepted": int}|null}
Fetch it with scripts in README (GitHub REST: /repos/{o}/{r}/pulls?state=closed).
"""
import json
import statistics
import sys
from datetime import datetime


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _hours(a, b):
    return (b - a).total_seconds() / 3600


def compute(rows):
    cycle, first_review = [], []
    found = accepted = with_ai = 0
    for r in rows:
        c, fr, m = _ts(r["created_at"]), _ts(r.get("first_review_at")), _ts(r.get("merged_at"))
        if m:
            cycle.append(_hours(c, m))
        if fr:
            first_review.append(_hours(c, fr))
        sc = r.get("shipcheck")
        if sc:
            with_ai += 1
            found += sc["findings"]
            accepted += sc["accepted"]
    med = lambda xs: round(statistics.median(xs), 2) if xs else None
    return {
        "prs": len(rows),
        "merged": len(cycle),
        "median_cycle_hours": med(cycle),
        "median_first_review_hours": med(first_review),
        "prs_reviewed_by_shipcheck": with_ai,
        "ai_finding_acceptance": round(accepted / found, 3) if found else None,
    }


def load(path):
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


if __name__ == "__main__":
    print(json.dumps(compute(load(sys.argv[1])), indent=2))
