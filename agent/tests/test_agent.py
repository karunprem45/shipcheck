import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "metrics"))

from shipcheck_agent.collect import bandit_summary, build_evidence, junit_summary  # noqa: E402
from shipcheck_agent.diff import parse_diff  # noqa: E402
from shipcheck_agent.llm import FakeLLM, parse_json  # noqa: E402
from shipcheck_agent.review import review, to_markdown  # noqa: E402
import prmetrics  # noqa: E402

DIFF = open(os.path.join(HERE, "..", "..", "examples", "sample.diff")).read()

GOOD = json.dumps({
    "findings": [
        {"file": "app/rates.py", "line": 12, "severity": "major",
         "message": "Division by zero when window is 0"},
        {"file": "made/up/path.py", "line": 1, "severity": "blocker", "message": "x"},
    ],
    "suggested_tests": [{"function": "rolling_rate", "test_name": "test_rolling_rate_zero_window",
                         "reason": "window=0 path is untested"}],
    "changelog": "Add rolling_rate helper for request metrics.",
})


class DiffTests(unittest.TestCase):
    def test_parses_files_and_line_numbers(self):
        files = {f.path: f for f in parse_diff(DIFF)}
        self.assertEqual(set(files), {"app/rates.py", "README.md"})
        first_line, _ = files["app/rates.py"].added[0]
        self.assertEqual(first_line, 10)

    def test_finds_changed_functions(self):
        f = [x for x in parse_diff(DIFF) if x.path == "app/rates.py"][0]
        self.assertEqual(f.changed_functions, ["rolling_rate"])

    def test_go_func_with_receiver(self):
        d = "+++ b/x.go\n@@ -0,0 +1,1 @@\n+func (s *Server) Handle(w int) {\n"
        self.assertEqual(parse_diff(d)[0].changed_functions, ["Handle"])


class ReviewTests(unittest.TestCase):
    def test_static_checks_without_llm(self):
        rep = review(DIFF, None)
        sev = sorted(f["severity"] for f in rep["static_findings"])
        self.assertEqual(sev, ["blocker", "minor"])
        self.assertEqual(rep["llm_status"], "skipped")
        self.assertFalse(rep["tests_changed"])
        self.assertTrue(rep["docs_changed"])

    def test_valid_llm_output_and_drops_unknown_files(self):
        rep = review(DIFF, FakeLLM([GOOD]))
        self.assertEqual(rep["llm_status"], "ok")
        self.assertEqual([f["file"] for f in rep["findings"]], ["app/rates.py"])

    def test_retries_once_on_bad_json(self):
        llm = FakeLLM(["not json", GOOD])
        rep = review(DIFF, llm)
        self.assertEqual(rep["llm_status"], "ok")
        self.assertIn("invalid", llm.calls[1])

    def test_gives_up_after_two_bad_answers(self):
        bad = json.dumps({"findings": [{"file": "app/rates.py", "line": 1,
                                        "severity": "huge", "message": "x"}],
                          "suggested_tests": [], "changelog": ""})
        rep = review(DIFF, FakeLLM([bad, bad]))
        self.assertTrue(rep["llm_status"].startswith("invalid_output"))
        self.assertEqual(len(rep["static_findings"]), 2)   # static checks survive

    def test_strips_code_fences(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_markdown_orders_by_severity(self):
        md = to_markdown(review(DIFF, FakeLLM([GOOD])))
        self.assertLess(md.index("blocker"), md.index("major"))
        self.assertIn("test_rolling_rate_zero_window", md)


class CollectTests(unittest.TestCase):
    def test_evidence_merges_sources(self):
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "j.xml")
            open(j, "w").write('<testsuites><testsuite tests="5" failures="1" errors="0" '
                               'skipped="1"/></testsuites>')
            b = os.path.join(d, "b.json")
            open(b, "w").write(json.dumps({"results": [{"issue_severity": "HIGH"},
                                                       {"issue_severity": "LOW"}]}))
            self.assertEqual(junit_summary(j), {"total": 5, "failed": 1, "skipped": 1})
            self.assertEqual(bandit_summary(b)["high"], 1)
            ev = build_evidence(review(DIFF, None), j, b)
            self.assertEqual(ev["review"]["blocker"], 1)
            self.assertEqual(ev["security"]["high"], 1)


class MetricsTests(unittest.TestCase):
    def test_cycle_time_and_acceptance(self):
        rows = [
            {"number": 1, "created_at": "2026-11-01T00:00:00Z", "first_review_at": "2026-11-01T02:00:00Z",
             "merged_at": "2026-11-01T10:00:00Z", "shipcheck": {"findings": 4, "accepted": 3}},
            {"number": 2, "created_at": "2026-11-02T00:00:00Z", "first_review_at": None,
             "merged_at": "2026-11-02T20:00:00Z", "shipcheck": None},
            {"number": 3, "created_at": "2026-11-03T00:00:00Z", "first_review_at": "2026-11-03T04:00:00Z",
             "merged_at": None, "shipcheck": {"findings": 0, "accepted": 0}},
        ]
        m = prmetrics.compute(rows)
        self.assertEqual(m["merged"], 2)
        self.assertEqual(m["median_cycle_hours"], 15.0)
        self.assertEqual(m["median_first_review_hours"], 3.0)
        self.assertEqual(m["ai_finding_acceptance"], 0.75)


if __name__ == "__main__":
    unittest.main()
