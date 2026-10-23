"""Single entry point. Run from llm-agent-collusion-2/Collusion_Liars_Bar/:

    python -m sting stage-a      [--stub] ...   Stage A offer battery
    python -m sting live         [--stub] ...   Stage L live sequences (--pilot for the go/no-go pilot)
    python -m sting checkpoint                  go/no-go after the pilot
    python -m sting snapshots    [--stub] ...   Stage S counterfactual snapshots
    python -m sting judge ...                   LLM judge / hand labels / kappa (subcommands)
    python -m sting analyze      --runs DIR     all pre-registered analyses, figures, claims.json
    python -m sting simulate                    pre-run yield and power simulation
    python -m sting texts [--write]             print (or write TEXTS.md) every study text
    python -m sting freeze                      sha256 of the frozen protocol files (for PREREG)
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def _freeze():
    root = Path(__file__).resolve().parent
    files = ["PREREG.md", "config.py", "texts.py", "game.py", "players.py", "offers.py", "sequence.py",
             "probes.py", "stage_a.py", "stage_s.py", "analysis/analyze.py", "analysis/stats.py"]
    h = hashlib.sha256()
    for f in files:
        p = root / f
        if p.exists():
            data = p.read_bytes()
            h.update(f.encode() + b"\0" + data)
            print(f"{hashlib.sha256(data).hexdigest()[:16]}  sting/{f}")
    print(f"\nprotocol hash: {h.hexdigest()}")


def main():
    from .texts import LB_ROOT
    os.chdir(LB_ROOT)
    if str(LB_ROOT) not in sys.path:
        sys.path.insert(0, str(LB_ROOT))
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "stage-a":
        from .stage_a import main as m
    elif cmd == "live":
        from .run_live import main as m
    elif cmd == "checkpoint":
        from .checkpoint import main as m
    elif cmd == "snapshots":
        from .stage_s import main as m
    elif cmd in ("judge", "labels"):
        from .judge import main as m
        if cmd == "judge":
            argv = ["judge"] + argv
    elif cmd == "analyze":
        from .analysis.analyze import main as m
    elif cmd == "simulate":
        from .simulate import main as m
    elif cmd == "texts":
        from . import texts
        if "--write" in argv:
            out = Path(__file__).with_name("TEXTS.md")
            texts.write_texts_md(out)
            print(f"wrote {out}")
        else:
            for name, text in texts.all_texts().items():
                print(f"===== {name} =====\n{text}\n")
        return 0
    elif cmd == "freeze":
        _freeze()
        return 0
    else:
        print(f"unknown command {cmd!r}\n{__doc__}")
        return 2
    return m(argv) or 0


if __name__ == "__main__":
    sys.exit(main())
