"""Real-API smoke test before any study run (cents): keys, routing, models, parsing, timing.

    python -m sting smoke            # 2 offers per Stage A model + one live game with the primary model
    python -m sting smoke --no-game  # offers only

Writes to sting_runs_smoke/ (never mixed with study data).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import time
from pathlib import Path

from .client import ClientPool, JsonlSink
from .config import PRIMARY_MODEL, STAGE_A_MODELS, SequenceConfig
from .offers import run_offer


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=STAGE_A_MODELS)
    ap.add_argument("--no-game", action="store_true")
    ap.add_argument("--out", default="sting_runs_smoke")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from .runinfo import keep_out_of_git
    keep_out_of_git(out)
    ok = True
    for model in a.models:
        try:
            client = ClientPool(JsonlSink(out / f"{model}.calls.jsonl.gz"), context={"stage": "smoke"}).get(model)
            for kind in ("zeng_v0", "direct"):
                t0 = time.time()
                r = run_offer(client, kind, target="Lily", sting="Mike",
                              players=["Luke", "Mike", "Quinn"] if kind != "zeng_v0" else ["Lily", "Luke", "Mike", "Quinn"],
                              n_games=6, game=3)
                print(f"[{model}] {kind:8s} {r['decision_strict']:8s} ({time.time() - t0:.1f}s) reply: {r['reply'][:90]!r}")
            st = client.stats()
            print(f"[{model}] calls {st['n_calls']}, tokens in/out {st['tokens_in']}/{st['tokens_out']}, "
                  f"errors {st['n_errors']}, est. ${st['cost_usd_estimate']:.5f}")
            if st["n_errors"] or st["n_empty"]:
                ok = False
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"[{model}] FAILED: {type(e).__name__}: {e}")
    if not a.no_game:
        from .sequence import run_sequence
        cfg = SequenceConfig(arm="B1", seed=999, model=PRIMARY_MODEL, n_games=1, offer_game=1, probes=False)
        t0 = time.time()
        with contextlib.redirect_stdout(io.StringIO()):
            meta = run_sequence(cfg, out / "live", overwrite=True)
        g = meta["games"][0]
        print(f"[game] 1 game with {PRIMARY_MODEL}: {meta['n_calls']} calls, {g['rounds']} rounds, "
              f"{(time.time() - t0) / 60:.1f} min, est. ${meta['cost_usd_estimate']:.4f}; offer reply "
              f"{meta['offer']['decision_strict']}")
        d = out / "live" / "B1" / PRIMARY_MODEL / "seed_999" / "decisions.jsonl"
        rows = [json.loads(l) for l in open(d)]
        fb = sum(r["fallback"] for r in rows if r["actor_role"] != "S")
        print(f"[game] decisions {len(rows)}, harness fallbacks {fb}")
        ok = ok and fb / max(1, len(rows)) < 0.05
    print("\nSMOKE TEST", "PASSED" if ok else "FAILED (fix before Stage A)")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
