"""RUN_INFO.json next to every stage's outputs: was it the stub, when, which code version.

The analysis refuses to present stub-derived numbers as results: every output it writes from
stub data carries a "STUB DATA - NOT RESULTS" banner.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import STUDY_VERSION


def write_run_info(directory: Path, *, stub: bool, stage: str) -> None:
    from .sequence import git_commit
    path = Path(directory) / "RUN_INFO.json"
    info = json.loads(path.read_text()) if path.exists() else {"runs": []}
    previous = {r["stub"] for r in info["runs"]}
    if previous and previous != {stub}:
        raise RuntimeError(f"{directory} already holds {'stub' if True in previous else 'real'} data; refusing to "
                           f"mix in {'stub' if stub else 'real'} data. Use a different --out directory.")
    info["runs"].append(dict(stage=stage, stub=stub, study_version=STUDY_VERSION, git_commit=git_commit(),
                             started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    info["stub_any"] = any(r["stub"] for r in info["runs"])
    path.write_text(json.dumps(info, indent=2))


def is_stub_dir(directory: Path) -> bool:
    path = Path(directory) / "RUN_INFO.json"
    return bool(path.exists() and json.loads(path.read_text()).get("stub_any"))
