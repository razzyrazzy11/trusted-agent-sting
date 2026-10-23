"""Protocol freeze: fix the pre-registration and the protocol code before any real data, then check
every later run against it.

    python -m sting freeze            write sting/FREEZE.json (sha256 of each protocol file, the
                                      protocol hash, UTC time) and print the commit/tag commands
    python -m sting freeze --check    recompute and compare with FREEZE.json (exit 1 on mismatch)

The protocol hash is the sha256 of a `sha256sum`-style listing ("<sha256>  sting/<file>" per line, in
PROTOCOL_FILES order), so a reader can verify it without this code, from Collusion_Liars_Bar/:

    sha256sum sting/PREREG.md sting/config.py ... | sha256sum      # files in PROTOCOL_FILES order

FREEZE.json is outside the hashed set, so recording the hash never changes it. Every real stage run
records the protocol hash it ran under (RUN_INFO.json / meta.json); the analysis reports whether all
data were collected under the frozen hash, and the checkpoint applies PREREG section 9 (pilot data
collected under a different protocol are excluded and rerun).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent

# Everything that defines what the agents see, how decisions are parsed into DVs, which data are
# collected, and how they are analysed. Tooling that cannot change results (status, smoke, stub,
# simulate, figures) is deliberately left out.
PROTOCOL_FILES = (
    "PREREG.md", "config.py", "texts.py", "parsing.py", "client.py", "players.py", "game.py", "offers.py",
    "probes.py", "sequence.py", "stage_a.py", "stage_s.py", "checkpoint.py", "judge.py",
    "analysis/load.py", "analysis/analyze.py", "analysis/stats.py",
)
FREEZE_NAME = "FREEZE.json"


def file_hashes(root: Path = ROOT) -> Dict[str, str]:
    return {f"sting/{f}": hashlib.sha256((root / f).read_bytes()).hexdigest() for f in PROTOCOL_FILES}


def protocol_hash(hashes: Dict[str, str]) -> str:
    listing = "".join(f"{h}  {name}\n" for name, h in hashes.items())
    return hashlib.sha256(listing.encode()).hexdigest()


def status(root: Path = ROOT) -> dict:
    cur = file_hashes(root)
    st = dict(protocol_hash=protocol_hash(cur), frozen=False, match=False, frozen_hash=None,
              frozen_at_utc=None, changed=[])
    path = root / FREEZE_NAME
    if path.exists():
        fz = json.loads(path.read_text())
        st.update(frozen=True, frozen_hash=fz["protocol_hash"], frozen_at_utc=fz.get("frozen_at_utc"),
                  match=st["protocol_hash"] == fz["protocol_hash"],
                  changed=sorted(n for n in set(cur) | set(fz["files"]) if cur.get(n) != fz["files"].get(n)))
    return st


def record(root: Path = ROOT) -> dict:
    """What a data folder stores about the protocol it was collected under."""
    st = status(root)
    return {k: st[k] for k in ("protocol_hash", "frozen", "match")}


_announced = set()


def announce(stage: str, *, stub: bool, root: Path = ROOT) -> dict:
    """Warn (once per stage and process) when real data are collected outside the frozen protocol."""
    rec = record(root)
    if stub or stage in _announced:
        return rec
    _announced.add(stage)
    if not rec["frozen"]:
        print(f"WARNING [stage {stage}]: the protocol is not frozen. Run `python -m sting freeze`, commit and tag "
              f"before collecting real data (PREREG.md, freeze procedure); data collected now are exploratory.",
              file=sys.stderr, flush=True)
    elif not rec["match"]:
        changed = ", ".join(status(root)["changed"])
        print(f"WARNING [stage {stage}]: protocol files changed since the freeze ({changed}). Log the change in "
              f"DEVIATIONS.md section D before using these data.", file=sys.stderr, flush=True)
    return rec


def write_freeze(root: Path = ROOT, force: bool = False) -> int:
    path = root / FREEZE_NAME
    st = status(root)
    if st["frozen"] and not force:
        if st["match"]:
            print(f"Already frozen at {st['frozen_at_utc']}, protocol unchanged: {st['frozen_hash']}")
            return 0
        print("FREEZE.json exists and these protocol files changed since: " + ", ".join(st["changed"]) +
              "\nRe-freezing after real data is a deviation: log it in DEVIATIONS.md section D, then rerun "
              "with --force.")
        return 1
    hashes = file_hashes(root)
    ph = protocol_hash(hashes)
    out = dict(protocol_hash=ph, frozen_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), files=hashes,
               verify="from Collusion_Liars_Bar/: sha256sum " + " ".join(hashes) + " | sha256sum")
    path.write_text(json.dumps(out, indent=2) + "\n")
    for name, h in hashes.items():
        print(f"{h[:16]}  {name}")
    print(f"\nprotocol hash: {ph}\nwritten to {path}\n\nNow commit and tag (an annotated tag carries the hash "
          f"and a timestamp; pushing it makes the timestamp public):\n"
          f"  git add -A && git commit -m \"Freeze protocol {ph[:12]}\"\n"
          f"  git tag -a prereg-v1 -m \"protocol hash {ph}\"\n"
          f"  git push origin prereg-v1        # optional")
    return 0


def check(root: Path = ROOT) -> int:
    st = status(root)
    if not st["frozen"]:
        print(f"Not frozen. Current protocol hash: {st['protocol_hash']}")
        return 1
    if st["match"]:
        print(f"MATCH: protocol unchanged since {st['frozen_at_utc']} ({st['frozen_hash']})")
        return 0
    print(f"MISMATCH: frozen {st['frozen_hash']}\n          current {st['protocol_hash']}\nchanged: " +
          ", ".join(st["changed"]))
    return 1


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare the current files with FREEZE.json")
    ap.add_argument("--force", action="store_true", help="re-freeze after a logged deviation")
    a = ap.parse_args(argv)
    return check() if a.check else write_freeze(force=a.force)


if __name__ == "__main__":
    sys.exit(main())
