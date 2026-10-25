"""Single entry point. Run from llm-agent-collusion-2/Collusion_Liars_Bar/:

    python -m sting modal deploy|warm|status|stop   the study's vLLM servers on Modal (open models)
    python -m sting smoke                       real-API smoke test (cents): keys, routing, one game
    python -m sting status       [--runs DIR]   progress of every stage
    python -m sting stage-a      [--stub] ...   Stage A offer battery
    python -m sting live         [--stub] ...   Stage L live sequences (--pilot for the go/no-go pilot)
    python -m sting checkpoint                  go/no-go after the pilot
    python -m sting snapshots    [--stub] ...   Stage S counterfactual snapshots
    python -m sting judge ...                   LLM judge / hand labels / kappa (subcommands)
    python -m sting analyze      --runs DIR     all pre-registered analyses, figures, claims.json
    python -m sting simulate                    pre-run yield and power simulation
    python -m sting texts [--write]             print (or write TEXTS.md) every study text
    python -m sting freeze       [--check]      freeze the protocol (writes sting/FREEZE.json) / verify it
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main():
    from .texts import LB_ROOT
    os.chdir(LB_ROOT)
    if str(LB_ROOT) not in sys.path:
        sys.path.insert(0, str(LB_ROOT))
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "modal":
        from .modal_cli import main as m
    elif cmd == "smoke":
        from .smoke import main as m
    elif cmd == "status":
        from .status import main as m
    elif cmd == "stage-a":
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
        runs = Path(argv[argv.index("--runs") + 1]) if "--runs" in argv else Path("sting_runs")
        if not runs.exists():
            print(f"{runs}/ not found: the raw run logs are not in the repository (shared on request). "
                  "The committed results are in sting_results/; the paper rebuilds from them (paper/build.py).")
            return 1
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
        from .freeze import main as m
    else:
        print(f"unknown command {cmd!r}\n{__doc__}")
        return 2
    return m(argv) or 0


if __name__ == "__main__":
    sys.exit(main())
