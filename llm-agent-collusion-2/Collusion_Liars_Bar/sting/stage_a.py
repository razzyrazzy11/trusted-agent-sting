"""Stage A: single-call offer battery (voluntary-adoption measurement, Zeng & Rudzicz protocol:
5 batches per cell per model; 100 offers per batch here, see config.STAGE_A_PER_BATCH_BY_MODEL).

Items are PAIRED across cells and models: item (batch b, index i) always uses the same names
and the same target/sting assignment, so cells differ only in the offer they test.

    python -m sting stage-a --models llama-3.1-8b qwen2.5-7b claude-haiku-5.5 --workers 32
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, List, Optional

from .client import ClientPool, JsonlSink
from .config import NAMES, STAGE_A_BATCHES, STAGE_A_CELLS, STAGE_A_MODELS, stage_a_per_batch
from .offers import run_offer
from .rng import stream
from .runinfo import record_client, write_run_info


def item_names(batch: int, item: int):
    names = list(NAMES)
    stream("stageA_item", batch, item).shuffle(names)
    return names[0], names[1], names                  # target, sting, all four


def _done_keys(path: Path):
    keys = set()
    if path.exists():
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            keys.add((r["cell"], r["batch"], r["item"]))
    return keys


def run_stage_a(models: List[str], cells: List[str], out_root: Path, stub_factory: Optional[Callable] = None,
                batches: int = STAGE_A_BATCHES, per_batch: Optional[int] = None, workers: int = 8) -> dict:
    out_root = Path(out_root)
    summary = {}
    for model in models:
        d = out_root / model
        d.mkdir(parents=True, exist_ok=True)
        write_run_info(d, stub=stub_factory is not None, stage="A")
        resp = JsonlSink(d / "responses.jsonl")
        done = _done_keys(d / "responses.jsonl")
        pool = ClientPool(JsonlSink(d / "calls.jsonl.gz"), stub_factory=stub_factory,
                          context={"stage": "A", "model": model})
        client = pool.get(model)
        n_per_batch = per_batch or stage_a_per_batch(model)
        jobs = [(c, b, i) for c in cells for b in range(batches) for i in range(n_per_batch) if (c, b, i) not in done]

        def one(job):
            cell, b, i = job
            spec = STAGE_A_CELLS[cell]
            target, sting, names = item_names(b, i)
            players = sorted(names) if spec["offer"] == "zeng_v0" else sorted(n for n in names if n != target)
            res = run_offer(client, spec["offer"], target=target, sting=sting, players=players, n_games=6, game=3,
                            suffix_keys=spec["suffix"], meta={"cell": cell, "batch": b, "item": i})
            resp.write(dict(stage="A", model=model, cell=cell, batch=b, item=i, **res))
            return res["decision_strict"]

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(one, jobs))
        summary[model] = dict(new_items=len(jobs), **client.stats())
        record_client(d, client.stats())
    return summary


def load_stage_a(root: Path, model: str) -> List[dict]:
    p = Path(root) / model / "responses.jsonl"
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=STAGE_A_MODELS)
    ap.add_argument("--cells", nargs="+", default=list(STAGE_A_CELLS))
    ap.add_argument("--out", default=None, help="default: sting_runs/stageA (sting_runs_stub/... with --stub)")
    ap.add_argument("--batches", type=int, default=STAGE_A_BATCHES)
    ap.add_argument("--per-batch", type=int, default=None, help="default: 100 for open 7-8B models, 20 for API models")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--stub", action="store_true", help="use the stub model (no API calls)")
    a = ap.parse_args(argv)
    if a.out is None:
        a.out = "sting_runs/stageA".replace("sting_runs/", "sting_runs_stub/") if a.stub else "sting_runs/stageA"
    from .client import prepare_backends
    from .stub import stub_factory
    prepare_backends(a.models, stub=a.stub)
    s = run_stage_a(a.models, a.cells, Path(a.out), stub_factory=stub_factory(0) if a.stub else None,
                    batches=a.batches, per_batch=a.per_batch, workers=a.workers)
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
