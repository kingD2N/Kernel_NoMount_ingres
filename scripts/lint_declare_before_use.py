#!/usr/bin/env python3
"""
Lightweight, compiler-free lint for the exact bug class hit in susfs4ksu's
SUS_KSTAT/statfs.c refactor (github.com/Numbersf/Action-Build#269): an
`extern` forward declaration for a cross-TU susfs helper placed AFTER the
first call site in the same file, which -Werror rejects as an implicit
declaration.

This is a heuristic, not a C parser or a compiler -- it only flags:
for each `extern ... name(...)` declaration in a file, does any earlier
line already call `name(`? That is precisely the ordering upstream shipped
by mistake, so it is enough to catch a repeat without needing a full
kernel build in CI.

Usage: python3 lint_declare_before_use.py <file.c> [<file.c> ...]
Exit: 1 if any file has a hit, 0 otherwise.
"""
import re
import sys
import pathlib

EXTERN_RE = re.compile(r'^\s*extern\b[^;{]*?\b(\w+)\s*\(', re.MULTILINE)


def check_file(path):
    text = pathlib.Path(path).read_text()
    lines = text.splitlines()
    problems = []
    for m in EXTERN_RE.finditer(text):
        name = m.group(1)
        decl_line = text.count('\n', 0, m.start()) + 1
        call_re = re.compile(r'\b' + re.escape(name) + r'\s*\(')
        for i, line in enumerate(lines[:decl_line - 1], start=1):
            if call_re.search(line) and not re.match(r'^\s*extern\b', line):
                problems.append((name, i, decl_line))
                break
    return problems


def main(argv):
    if len(argv) < 2:
        print("usage: lint_declare_before_use.py <file.c> [<file.c> ...]", file=sys.stderr)
        return 2
    any_hit = False
    for path in argv[1:]:
        problems = check_file(path)
        if not problems:
            print(f"::notice::{path}: OK, no declare-after-use pattern for extern symbols")
            continue
        for name, call_line, decl_line in problems:
            print(f"::error file={path},line={call_line}::'{name}' called on line {call_line} "
                  f"but its extern declaration is on line {decl_line} -- declare-after-use, "
                  f"will fail as implicit-declaration under -Werror")
            any_hit = True
    return 1 if any_hit else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
