"""Merge JUnit XML, bandit JSON and the review report into evidence.json for the Go gate."""
import json
import xml.etree.ElementTree as ET


def junit_summary(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    total = failed = skipped = 0
    for s in suites:
        total += int(s.get("tests", 0))
        failed += int(s.get("failures", 0)) + int(s.get("errors", 0))
        skipped += int(s.get("skipped", 0))
    return {"total": total, "failed": failed, "skipped": skipped}


def bandit_summary(path):
    with open(path) as fh:
        data = json.load(fh)
    counts = {"low": 0, "medium": 0, "high": 0}
    for r in data.get("results", []):
        sev = r.get("issue_severity", "LOW").lower()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def build_evidence(review_report, junit_path=None, bandit_path=None):
    sev = [f["severity"] for f in review_report["static_findings"] + review_report["findings"]]
    return {
        "tests": junit_summary(junit_path) if junit_path else None,
        "security": bandit_summary(bandit_path) if bandit_path else None,
        "review": {s: sev.count(s) for s in ("blocker", "major", "minor", "info")},
        "tests_changed": review_report["tests_changed"],
        "docs_changed": review_report["docs_changed"],
        "changed_functions": len(review_report["changed_functions"]),
        "llm_status": review_report["llm_status"],
    }
