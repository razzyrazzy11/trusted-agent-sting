"""Recording LLM client with the harness's contract: chat(messages, model) -> (content, "").

* Real calls use the harness's sampling (src/llm/llm_client.py, Zeng Table 10) and its exact
  response clean-up, through the starter repo's routing (poseidon_compute: Nebius default,
  OpenRouter fallback). OpenRouter-only models (gpt-4.1-mini) get their own OpenRouter
  client, because make_client() points every call at one provider.
* Transient errors are retried 3 times with exponential backoff from 1 s (Zeng App. D);
  after that the call returns "" and the harness's own 5-attempt loop / fallback applies.
  The harness's fallbacks are logged, never hidden.
* Every call is recorded (purpose, prompt, reply, tokens, latency, errors) to a JSONL sink.
* `track()` collects the calls made inside a block on the current thread, so the game can log
  attempts, raw replies and fallbacks per decision even when reflections run in parallel.
"""
from __future__ import annotations

import contextlib
import gzip
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .config import MODELS

_FATAL_NAMES = ("AuthenticationError", "NotFoundError", "BadRequestError", "PermissionDeniedError")


class JsonlSink:
    """Thread-safe JSONL writer (gzip when the path ends in .gz)."""

    def __init__(self, path: Optional[Path]):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        if not self.path:
            return
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            if self.path.suffix == ".gz":
                with gzip.open(self.path, "at", encoding="utf-8") as f:
                    f.write(line)
            else:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line)


class _Tracker:
    def __init__(self):
        self.calls: List[dict] = []

    def summary(self) -> dict:
        first = self.calls[0] if self.calls else {}
        return {
            "n_calls": len(self.calls),
            "first_prompt": (first.get("messages") or [{}])[-1].get("content", "") if first else "",
            "raw_responses": [c.get("response", "") for c in self.calls],
            "errors": [c.get("error") for c in self.calls if c.get("error")],
            "empty_responses": sum(1 for c in self.calls if not c.get("response")),
        }


class StudyClient:
    """One client per model key. Thread-safe."""

    def __init__(self, model_key: str, sink: Optional[JsonlSink] = None, stub=None,
                 context: Optional[dict] = None, log_prompts: bool = True):
        if model_key not in MODELS:
            raise ValueError(f"unknown model {model_key!r}; add it to sting.config.MODELS")
        self.model_key = model_key
        self.spec = MODELS[model_key]
        self.sink = sink or JsonlSink(None)
        self.stub = stub
        self.context = dict(context or {})
        self.log_prompts = log_prompts
        self._tls = threading.local()
        self._lock = threading.Lock()
        self._api = None
        self.n_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.n_errors = 0
        self.n_empty = 0
        if stub is None:
            self._api = self._build_api_client()
            from src.llm.llm_client import LLMClient   # harness clean-up, reused verbatim
            self._cleaner = LLMClient.__new__(LLMClient)

    # -- tracking ---------------------------------------------------------
    @contextlib.contextmanager
    def track(self, purpose: str, **meta):
        stack = getattr(self._tls, "stack", None)
        if stack is None:
            stack = self._tls.stack = []
        tracker = _Tracker()
        stack.append((tracker, purpose, meta))
        try:
            yield tracker
        finally:
            stack.pop()

    def _current(self):
        stack = getattr(self._tls, "stack", None) or []
        return stack[-1] if stack else (None, "untracked", {})

    # -- the harness contract ------------------------------------------------
    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
             max_new_tokens: int = 4096):
        model = model or self.model_key
        if model != self.model_key:
            raise ValueError(f"client for {self.model_key} asked to call {model}")
        tracker, purpose, meta = self._current()
        t0 = time.time()
        error = None
        usage = {}
        if self.stub is not None:
            content = self.stub.respond(messages, model=model, purpose=purpose, meta=meta)
        else:
            content, usage, error = self._real_chat(messages, max_new_tokens)
        latency = time.time() - t0
        record = {
            "ts": round(t0, 3), "model": model, "purpose": purpose, **self.context,
            **{f"meta_{k}": v for k, v in meta.items()},
            "messages": messages if self.log_prompts else None,
            "response": content, "latency_s": round(latency, 3), "error": error,
            "tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens"),
            "max_new_tokens": max_new_tokens,
        }
        with self._lock:
            self.n_calls += 1
            self.tokens_in += usage.get("prompt_tokens") or _approx_tokens(messages)
            self.tokens_out += usage.get("completion_tokens") or _approx_tokens([{"content": content}])
            self.n_errors += 1 if error else 0
            self.n_empty += 0 if content else 1
        self.sink.write(record)
        stack = getattr(self._tls, "stack", None) or []
        for trk, _, _ in stack:
            trk.calls.append(record)
        return content, ""

    # -- real API ---------------------------------------------------------------
    def _build_api_client(self):
        from poseidon_compute import llm_config, make_client
        llm_config._load()
        if self.spec["provider"] == "openrouter":
            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                raise RuntimeError(f"{self.model_key} is served only by OpenRouter; set OPENROUTER_API_KEY "
                                   f"in the repo-root compute.env")
            from openai import OpenAI
            return OpenAI(base_url=llm_config.OPENROUTER_BASE_URL, api_key=key)
        return make_client()

    def _sampling(self) -> dict:
        fam = self.spec["family"]
        if fam == "llama":
            return dict(max_tokens=256, temperature=0.8, top_p=0.95, top_k=40, repetition_penalty=1.1)
        if fam == "qwen":
            return dict(max_tokens=256, temperature=0.8, top_p=0.9, top_k=50, repetition_penalty=1.05)
        if fam == "openai":
            return dict(max_tokens=1024)          # provider-default sampling (Zeng: API models)
        return dict(max_tokens=512, temperature=0.7, top_p=0.9, top_k=50, repetition_penalty=1.02)

    def _real_chat(self, messages, max_new_tokens):
        from poseidon_compute import resolve_model
        params = self._sampling()
        kwargs = dict(messages=messages, max_tokens=min(max_new_tokens, params["max_tokens"]))
        if self.spec["provider"] == "openrouter":
            kwargs["model"] = self.spec["model_id"]
        else:
            kwargs["model"] = resolve_model(self.spec["model_id"])
        if "temperature" in params:
            kwargs.update(temperature=params["temperature"], top_p=params["top_p"],
                          extra_body={"top_k": params["top_k"], "repetition_penalty": params["repetition_penalty"]})
        last_error = None
        for attempt in range(3):
            try:
                completion = self._api.chat.completions.create(**kwargs)
                raw = completion.choices[0].message.content or ""
                usage = {}
                if getattr(completion, "usage", None) is not None:
                    usage = {"prompt_tokens": completion.usage.prompt_tokens,
                             "completion_tokens": completion.usage.completion_tokens}
                return self._cleaner._clean_response(raw, self.model_key), usage, None
            except Exception as e:  # noqa: BLE001
                if type(e).__name__ in _FATAL_NAMES:
                    raise
                last_error = f"{type(e).__name__}: {e}"
                if attempt < 2:
                    time.sleep(2 ** attempt)   # 1 s, then 2 s
        return "", {}, last_error

    # -- accounting -------------------------------------------------------------
    def cost_usd(self) -> float:
        return (self.tokens_in * self.spec["price_in"] + self.tokens_out * self.spec["price_out"]) / 1e6

    def stats(self) -> dict:
        return {"model": self.model_key, "n_calls": self.n_calls, "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out, "n_errors": self.n_errors, "n_empty": self.n_empty,
                "cost_usd_estimate": round(self.cost_usd(), 4)}


def _approx_tokens(messages) -> int:
    return sum(len((m or {}).get("content") or "") for m in messages) // 4


class ClientPool:
    """One StudyClient per model, sharing a call sink. `factory(model_key)` builds the stub (or None)."""

    def __init__(self, sink: JsonlSink, stub_factory: Optional[Callable[[str], object]] = None,
                 context: Optional[dict] = None):
        self.sink = sink
        self.stub_factory = stub_factory
        self.context = context or {}
        self._clients: Dict[str, StudyClient] = {}

    def get(self, model_key: str) -> StudyClient:
        if model_key not in self._clients:
            stub = self.stub_factory(model_key) if self.stub_factory else None
            self._clients[model_key] = StudyClient(model_key, self.sink, stub=stub, context=self.context)
        return self._clients[model_key]

    def stats(self) -> List[dict]:
        return [c.stats() for c in self._clients.values()]
