"""Check every number in the paper against the committed result files, without building the document.

Imports paper_numbers (which recomputes every number from sting_results/ and runs its assertions on
the paper's claims), resolves every placeholder in content.py, and compares each printed value with
paper/out/number_sources.md, the list written by the last committed build. Needs only pandas (no
python-docx, LibreOffice or poppler), so it runs in CI.

    python paper/check_numbers.py          # from the repository root

Exit status 0: every placeholder resolves and prints exactly what the committed paper prints.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import content  # noqa: E402
import paper_numbers as N  # noqa: E402


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, (list, tuple)):
        for o in obj:
            yield from strings(o)
    elif isinstance(obj, dict):
        for o in obj.values():
            yield from strings(o)


def main() -> int:
    for name, val in vars(content).items():
        if not name.startswith("_"):
            for s in strings(val):
                N.render(s)
    left = [s for name, v in vars(content).items() if not name.startswith("_")
            for s in strings(v) if "{{" in N.render(s)]
    committed = {}
    for line in (HERE / "out" / "number_sources.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| `([^`]+)` \| (.*) \|$", line)
        if m:
            committed[m.group(1)] = m.group(2)
    problems = [f"unresolved placeholder in: {s[:80]!r}" for s in left]
    problems += [f"{k}: now {v!r}, committed {committed.get(k)!r}"
                 for k, v in sorted(N.USED.items()) if committed.get(k) != v]
    problems += [f"{k}: in number_sources.md but no longer used" for k in sorted(set(committed) - set(N.USED))]
    if problems:
        print("\n".join(problems))
        print(f"FAILED: {len(problems)} problem(s)")
        return 1
    print(f"OK: {len(N.USED)} numbers recomputed from sting_results/ match the committed paper")
    return 0


if __name__ == "__main__":
    sys.exit(main())
