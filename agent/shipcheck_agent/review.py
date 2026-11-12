"""Agent workflow: diff -> static checks -> LLM review -> validated report."""
import json

from .diff import parse_diff
from .llm import parse_json
from .schema import SCHEMA_TEXT, SchemaError, validate

SYSTEM = ("You review pull requests. Point only at lines that were added. "
          "Be specific and short. " + SCHEMA_TEXT)

MAX_DIFF_CHARS = 60_000
SEV_ORDER = ["blocker", "major", "minor", "info"]


def static_checks(files):
    """Cheap rule checks that still run when the LLM is down."""
    notes = []
    for f in files:
        for line_no, text in f.added:
            low = text.lower()
            if "todo" in low or "fixme" in low:
                notes.append({"file": f.path, "line": line_no, "severity": "minor",
                              "message": "TODO/FIXME left in new code"})
            if any(k in low.replace(" ", "") for k in ("api_key=", "password=", "secret=")) \
                    and ('"' in text or "'" in text):
                notes.append({"file": f.path, "line": line_no, "severity": "blocker",
                              "message": "Possible hard-coded secret"})
    return notes


def build_prompt(files, diff_text):
    summary = [{"file": f.path, "functions": f.changed_functions,
                "added": len(f.added), "removed": f.removed} for f in files]
    return ("Changed files:\n" + json.dumps(summary, indent=1) +
            "\n\nDiff:\n" + diff_text[:MAX_DIFF_CHARS])


def review(diff_text, llm, max_attempts=2):
    files = parse_diff(diff_text)
    changed = {f.path for f in files}
    code_files = [f for f in files if not f.is_test and not f.is_doc]
    report = {
        "files_changed": len(files),
        "tests_changed": any(f.is_test for f in files),
        "docs_changed": any(f.is_doc for f in files),
        "changed_functions": sorted({n for f in code_files for n in f.changed_functions}),
        "static_findings": static_checks(files),
        "llm_status": "skipped",
        "findings": [], "suggested_tests": [], "changelog": "",
    }
    if llm is None or not files:
        return report

    prompt = build_prompt(files, diff_text)
    error = None
    for _ in range(max_attempts):
        try:
            ask = prompt if error is None else \
                prompt + f"\n\nYour last answer was invalid: {error}. Fix it."
            out = validate(parse_json(llm.complete(SYSTEM, ask)), changed)
            report.update(out)
            report["llm_status"] = "ok"
            return report
        except ValueError as exc:   # covers JSONDecodeError and SchemaError
            error = str(exc)
        except Exception as exc:    # API/network failure: keep the static checks
            report["llm_status"] = f"error: {type(exc).__name__}"
            return report
    report["llm_status"] = f"invalid_output: {error}"
    return report


def to_markdown(report):
    lines = ["## ShipCheck review", ""]
    allf = report["static_findings"] + report["findings"]
    if allf:
        lines += ["| Severity | Location | Note |", "|---|---|---|"]
        for f in sorted(allf, key=lambda x: SEV_ORDER.index(x["severity"])):
            lines.append(f"| {f['severity']} | `{f['file']}:{f['line']}` | {f['message']} |")
    else:
        lines.append("No findings.")
    if report["suggested_tests"]:
        lines += ["", "**Suggested tests**"]
        lines += [f"- `{t['test_name']}` for `{t['function']}`: {t['reason']}"
                  for t in report["suggested_tests"]]
    if report["changelog"]:
        lines += ["", "**Changelog draft**", report["changelog"]]
    lines += ["", f"_LLM status: {report['llm_status']}_"]
    return "\n".join(lines)
