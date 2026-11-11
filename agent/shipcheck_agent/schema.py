"""Fixed output schema for the LLM, plus a strict validator."""
SEVERITIES = {"info", "minor", "major", "blocker"}

SCHEMA_TEXT = """Return ONLY a JSON object, no prose, no markdown fences:
{
  "findings": [{"file": str, "line": int, "severity": "info|minor|major|blocker",
                "message": str}],
  "suggested_tests": [{"function": str, "test_name": str, "reason": str}],
  "changelog": str
}"""


class SchemaError(ValueError):
    pass


def validate(obj, changed_files):
    if not isinstance(obj, dict):
        raise SchemaError("top level must be an object")
    for key in ("findings", "suggested_tests", "changelog"):
        if key not in obj:
            raise SchemaError(f"missing key: {key}")
    if not isinstance(obj["changelog"], str):
        raise SchemaError("changelog must be a string")
    clean = []
    for f in obj["findings"]:
        if not isinstance(f, dict):
            raise SchemaError("finding must be an object")
        if f.get("severity") not in SEVERITIES:
            raise SchemaError(f"bad severity: {f.get('severity')}")
        if not isinstance(f.get("line"), int) or not isinstance(f.get("message"), str):
            raise SchemaError("finding needs int line and str message")
        # Drop findings that point at files the PR did not touch (made-up paths).
        if f.get("file") in changed_files:
            clean.append(f)
    for t in obj["suggested_tests"]:
        if not all(isinstance(t.get(k), str) for k in ("function", "test_name", "reason")):
            raise SchemaError("suggested test needs function, test_name, reason")
    obj["findings"] = clean
    return obj
