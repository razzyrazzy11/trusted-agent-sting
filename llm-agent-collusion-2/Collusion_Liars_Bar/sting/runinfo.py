"""RUN_INFO.json next to every stage's outputs: was it the stub, when, which code version.

The analysis refuses to present stub-derived numbers as results: every output it writes from
stub data carries a "STUB DATA - NOT RESULTS" banner.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import STUDY_VERSION


RAW_GITIGNORE = ("# Raw study data: not for git. The starter repo's .gitignore hides *.json but not *.jsonl,\n"
                 "# so `git add -A` would commit half of every folder. Publish as an archive instead\n"
                 "# (sting/README.md, 'What goes into git').\n*\n")


def keep_out_of_git(directory: Path) -> None:
    """Give the raw-data root (the nearest sting_runs* folder at or above `directory`) a catch-all .gitignore."""
    d = Path(directory).resolve()
    for p in (d, *d.parents):
        if p.name.startswith("sting_runs"):
            p.mkdir(parents=True, exist_ok=True)
            gi = p / ".gitignore"
            if not gi.exists():
                gi.write_text(RAW_GITIGNORE)
            return


def write_run_info(directory: Path, *, stub: bool, stage: str) -> None:
    from .freeze import announce
    from .sequence import git_commit
    keep_out_of_git(directory)
    path = Path(directory) / "RUN_INFO.json"
    info = json.loads(path.read_text()) if path.exists() else {"runs": []}
    previous = {r["stub"] for r in info["runs"]}
    if previous and previous != {stub}:
        raise RuntimeError(f"{directory} already holds {'stub' if True in previous else 'real'} data; refusing to "
                           f"mix in {'stub' if stub else 'real'} data. Use a different --out directory.")
    info["runs"].append(dict(stage=stage, stub=stub, study_version=STUDY_VERSION, git_commit=git_commit(),
                             protocol=announce(stage, stub=stub),
                             started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    info["stub_any"] = any(r["stub"] for r in info["runs"])
    path.write_text(json.dumps(info, indent=2))


def record_client(directory: Path, stats: dict) -> None:
    """Attach the client's call counts and serving provenance (backend, repo, revision, vLLM version,
    GPU, or Claude model id and thinking setting) to this folder's latest run entry."""
    path = Path(directory) / "RUN_INFO.json"
    if not path.exists():
        return
    info = json.loads(path.read_text())
    if info.get("runs"):
        info["runs"][-1]["client"] = stats
        path.write_text(json.dumps(info, indent=2))


def serving_records(directory: Path) -> list:
    path = Path(directory) / "RUN_INFO.json"
    if not path.exists():
        return []
    return [(r.get("client") or {}).get("serving") for r in json.loads(path.read_text())["runs"]
            if (r.get("client") or {}).get("serving")]


def protocol_hashes(directory: Path) -> list:
    """Protocol hash recorded by each run that wrote into this folder (None for pre-freeze-tooling runs)."""
    path = Path(directory) / "RUN_INFO.json"
    if not path.exists():
        return []
    return [(r.get("protocol") or {}).get("protocol_hash") for r in json.loads(path.read_text())["runs"]]


def is_stub_dir(directory: Path) -> bool:
    path = Path(directory) / "RUN_INFO.json"
    return bool(path.exists() and json.loads(path.read_text()).get("stub_any"))
