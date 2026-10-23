"""Load every stage's outputs into pandas DataFrames."""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import pandas as pd

from ..runinfo import is_stub_dir, protocol_hashes, serving_records


@dataclass
class Data:
    A: pd.DataFrame = field(default_factory=pd.DataFrame)       # Stage A offer replies
    seqs: pd.DataFrame = field(default_factory=pd.DataFrame)    # Stage L sequences (one row each)
    D: pd.DataFrame = field(default_factory=pd.DataFrame)       # Stage L decisions
    P: pd.DataFrame = field(default_factory=pd.DataFrame)       # Stage L probes
    games: pd.DataFrame = field(default_factory=pd.DataFrame)   # Stage L per-game results
    S: pd.DataFrame = field(default_factory=pd.DataFrame)       # Stage S snapshot samples
    judge: Dict[str, str] = field(default_factory=dict)
    budget: List[dict] = field(default_factory=list)
    protocol: List[dict] = field(default_factory=list)          # protocol hash each data folder was collected under
    serving: List[dict] = field(default_factory=list)           # how each model was served (backend, repo, revision...)
    stub: bool = False
    sources: Dict[str, str] = field(default_factory=dict)


def _jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _calls_budget(path: Path, stage: str, model: str) -> dict:
    n = tin = tout = errs = empty = 0
    approx = False
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                n += 1
                if c.get("tokens_in") is None:
                    approx = True
                    tin += sum(len((m or {}).get("content") or "") for m in (c.get("messages") or [])) // 4
                    tout += len(c.get("response") or "") // 4
                else:
                    tin += c["tokens_in"]
                    tout += c["tokens_out"] or 0
                errs += 1 if c.get("error") else 0
                empty += 0 if c.get("response") else 1
    return dict(stage=stage, model=model, calls=n, tokens_in=tin, tokens_out=tout, errors=errs, empty=empty,
                tokens_approximate=approx)


def load(runs: Path) -> Data:
    runs = Path(runs)
    data = Data(sources={"runs": str(runs)})
    # ---- Stage A
    rows = []
    for d in sorted((runs / "stageA").glob("*")):
        if d.is_dir():
            rows += _jsonl(d / "responses.jsonl")
            data.stub |= is_stub_dir(d)
            data.budget.append(_calls_budget(d / "calls.jsonl.gz", "A", d.name))
            data.protocol += [dict(stage="A", source=d.name, protocol_hash=h) for h in protocol_hashes(d)]
            data.serving += [dict(s, stage="A", model=d.name) for s in serving_records(d)]
    data.A = pd.DataFrame(rows)
    # ---- Stage L
    seq_rows, dec_rows, probe_rows, game_rows = [], [], [], []
    for meta_path in sorted((runs / "live").glob("*/*/seed_*/meta.json")):
        d = meta_path.parent
        if d.name.endswith(".tmp") or not (d / "DONE").exists():
            continue
        meta = json.loads(meta_path.read_text())
        data.stub |= bool(meta.get("stub"))
        off = meta.get("offer") or {}
        seq_rows.append(dict(seq_id=meta["seq_id"], arm=meta["config"]["arm"], seed=meta["config"]["seed"],
                             model=meta["config"]["model"], offer_kind=off.get("kind"), reply=off.get("reply"),
                             decision_strict=off.get("decision_strict"), decision_zeng=off.get("decision_zeng"),
                             accepted=off.get("accepted"), n_calls=meta["n_calls"], cost=meta["cost_usd_estimate"],
                             duration_min=meta["duration_s"] / 60, stub=bool(meta.get("stub")),
                             names=meta["names"], arrangement_order=meta["config"]["arrangement_order"],
                             protocol_hash=(meta.get("protocol") or {}).get("protocol_hash")))
        data.protocol.append(dict(stage="L", source=meta["seq_id"],
                                  protocol_hash=(meta.get("protocol") or {}).get("protocol_hash")))
        for g in meta["games"]:
            game_rows.append(dict(seq_id=meta["seq_id"], arm=meta["config"]["arm"], **g))
        dec_rows += _jsonl(d / "decisions.jsonl")
        probe_rows += _jsonl(d / "probes.jsonl")
        for c in meta.get("client_stats", []):
            if c.get("serving"):
                data.serving.append(dict(c["serving"], stage="L", model=c["model"]))
            data.budget.append(dict(stage="L", model=c["model"], calls=c["n_calls"], tokens_in=c["tokens_in"],
                                    tokens_out=c["tokens_out"], errors=c["n_errors"], empty=c["n_empty"],
                                    tokens_approximate=bool(meta.get("stub"))))
    data.seqs = pd.DataFrame(seq_rows)
    data.D = pd.DataFrame(dec_rows)
    data.P = pd.DataFrame(probe_rows)
    data.games = pd.DataFrame(game_rows)
    # ---- Stage S
    rows = []
    for d in sorted((runs / "stageS").glob("*")):
        if d.is_dir():
            rows += _jsonl(d / "responses.jsonl")
            data.stub |= is_stub_dir(d)
            data.budget.append(_calls_budget(d / "calls.jsonl.gz", "S", d.name))
            data.protocol += [dict(stage="S", source=d.name, protocol_hash=h) for h in protocol_hashes(d)]
            data.serving += [dict(s, stage="S", model=d.name) for s in serving_records(d)]
    data.S = pd.DataFrame(rows)
    # ---- judge labels
    for p in sorted((runs / "judge").glob("*.jsonl")):
        for r in _jsonl(p):
            data.judge[r["item_id"]] = r["judge"]
    return data
