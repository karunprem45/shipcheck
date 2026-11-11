"""Parse a unified git diff into per-file changes with added line numbers."""
from dataclasses import dataclass, field
import re

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
DEF_RE = re.compile(r"^\s*(?:def|func|function)\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)")


@dataclass
class FileChange:
    path: str
    added: list = field(default_factory=list)    # (line_no, text)
    removed: int = 0

    @property
    def changed_functions(self):
        names = []
        for _, text in self.added:
            m = DEF_RE.match(text)
            if m and m.group(1) not in names:
                names.append(m.group(1))
        return names

    @property
    def is_test(self):
        p = self.path.lower()
        return "test" in p.split("/")[-1] or "/tests/" in "/" + p

    @property
    def is_doc(self):
        return self.path.lower().endswith((".md", ".rst", ".txt"))


def parse_diff(text):
    files, cur, new_line = [], None, 0
    for raw in text.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path == "/dev/null":
                cur = None
                continue
            path = path[2:] if path.startswith("b/") else path
            cur = FileChange(path)
            files.append(cur)
        elif raw.startswith("--- ") or raw.startswith("diff --git"):
            continue
        elif cur is None:
            continue
        elif (m := HUNK_RE.match(raw)):
            new_line = int(m.group(1))
        elif raw.startswith("+"):
            cur.added.append((new_line, raw[1:]))
            new_line += 1
        elif raw.startswith("-"):
            cur.removed += 1
        else:
            new_line += 1
    return files
