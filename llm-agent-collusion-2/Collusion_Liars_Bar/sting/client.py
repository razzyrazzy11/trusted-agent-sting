"""Recording LLM client with the harness's contract: chat(messages, model) -> (content, "").

* Open models (Llama, Qwen) use the harness's sampling (src/llm/llm_client.py, Zeng Table 10) and
  its exact response clean-up. Backend (config.OPEN_MODEL_BACKEND, env STING_OPEN_BACKEND):
  "modal" = the study's own vLLM servers on Modal (modal_app.py; the client verifies the served
  repo, context length and vLLM version before its first call), or "poseidon" = the starter
  repo's routing (Nebius, OpenRouter fallback). A forced LLM_MODEL is refused, never applied.
* Claude (provider "anthropic") goes through the native Anthropic SDK with thinking disabled and
  provider-default sampling (current Claude models reject custom temperature/top_p), as Zeng ran
  API models. System text moves to the `system` field; consecutive same-role turns are merged.
* OpenRouter-only models (gpt-4.1-mini, optional) get their own OpenRouter client.
* Transient errors are retried 3 times with exponential backoff from 1 s (Zeng App. D); after
  that the call returns "" and the harness's own 5-attempt loop / fallback applies. A Modal server
  that is scaling up (503/502/504, connection errors) is waited for (up to MODAL_PATIENCE_S)
  without spending those attempts. The harness's fallbacks are logged, never hidden.
* Every call is recorded (purpose, prompt, reply, tokens, latency, errors, the model that
  answered, finish reason) to a JSONL sink; `stats()` carries the serving provenance.
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

from .config import MODELS, OPEN_MODEL_BACKEND

_FATAL_NAMES = ("AuthenticationError", "NotFoundError", "BadRequestError", "PermissionDeniedError")
MODAL_PATIENCE_S = 1200          # how long one call waits for a Modal server that is (re)starting
CLAUDE_MAX_TOKENS = 1024         # provider-default sampling and the same cap as the other API model


def open_backend() -> str:
    b = os.environ.get("STING_OPEN_BACKEND") or OPEN_MODEL_BACKEND
    if b not in ("modal", "poseidon"):
        raise ValueError(f"STING_OPEN_BACKEND must be 'modal' or 'poseidon', not {b!r}")
    return b


def is_open_model(model_key: str) -> bool:
    return MODELS[model_key]["provider"] == "default"


def prepare_backends(models, stub: bool = False) -> None:
    """Before a stage starts: wake and verify the Modal servers it will use (cold starts overlap and
    show progress here instead of stalling the first game call)."""
    open_models = sorted({m for m in models if is_open_model(m)})
    if stub or not open_models or open_backend() != "modal":
        return
    from .modal_cli import ensure_ready
    ensure_ready(open_models)


def _server_unavailable(e: Exception) -> bool:
    return getattr(e, "status_code", None) in (502, 503, 504) or \
        type(e).__name__ in ("APIConnectionError", "APITimeoutError")


def to_anthropic(messages: List[Dict[str, str]]):
    """OpenAI-style messages -> (system, messages) for the Messages API: system text hoisted (as the
    OpenAI-compatibility layer does), consecutive same-role turns merged into one."""
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    out: List[Dict[str, str]] = []
    for m in messages:
        if m.get("role") == "system":
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1] = {"role": m["role"], "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return system, out


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
        self.serving: dict = {"backend": "stub"} if stub is not None else {}
        self._modal = False
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
            "served_model": usage.get("served_model"), "finish": usage.get("finish"),
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
        from poseidon_compute import llm_config
        llm_config._load()                     # repo-root compute.env -> os.environ
        provider = self.spec["provider"]
        if provider == "anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError(f"{self.model_key} runs on the Claude API; set ANTHROPIC_API_KEY in the "
                                   f"repo-root compute.env")
            import anthropic
            self.serving = dict(backend="anthropic", model_id=self.spec["model_id"], thinking="disabled",
                                sampling="provider default", sdk=anthropic.__version__)
            # The SDK retries 429/529/5xx itself, honouring retry-after.
            return anthropic.Anthropic(api_key=key, max_retries=8, timeout=120.0)
        if provider == "openrouter":
            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                raise RuntimeError(f"{self.model_key} is served only by OpenRouter; set OPENROUTER_API_KEY "
                                   f"in the repo-root compute.env")
            from openai import OpenAI
            self.serving = dict(backend="openrouter", model_id=self.spec["model_id"])
            return OpenAI(base_url=llm_config.OPENROUTER_BASE_URL, api_key=key)
        if open_backend() == "modal":
            from .modal_cli import open_model_client
            api, self.serving = open_model_client(self.model_key)   # verified: repo, context, vLLM version
            self._modal = True
            return api
        forced = os.environ.get("LLM_MODEL")
        if forced and forced != self.spec["model_id"]:
            raise RuntimeError(f"LLM_MODEL={forced!r} would replace {self.spec['model_id']!r} in every call. "
                               f"Unset LLM_MODEL: the study never substitutes models.")
        from poseidon_compute import make_client
        self.serving = dict(backend="poseidon", model_id=self.spec["model_id"], endpoint=llm_config.base_url())
        return make_client()

    def _sampling(self) -> dict:
        fam = self.spec["family"]
        if fam == "llama":
            return dict(max_tokens=256, temperature=0.8, top_p=0.95, top_k=40, repetition_penalty=1.1)
        if fam == "qwen":
            return dict(max_tokens=256, temperature=0.8, top_p=0.9, top_k=50, repetition_penalty=1.05)
        if fam == "openai":
            return dict(max_tokens=1024)          # provider-default sampling (Zeng: API models)
        if fam == "claude":
            return dict(max_tokens=CLAUDE_MAX_TOKENS)
        return dict(max_tokens=512, temperature=0.7, top_p=0.9, top_k=50, repetition_penalty=1.02)

    def _real_chat(self, messages, max_new_tokens):
        if self.spec["provider"] == "anthropic":
            return self._anthropic_chat(messages, max_new_tokens)
        params = self._sampling()
        kwargs = dict(messages=messages, max_tokens=min(max_new_tokens, params["max_tokens"]))
        if self.spec["provider"] == "openrouter":
            kwargs["model"] = self.spec["model_id"]
        elif self._modal:
            kwargs["model"] = self.model_key       # served under the study key; repo/revision verified at build
        else:
            from poseidon_compute import resolve_model
            kwargs["model"] = resolve_model(self.spec["model_id"])
        if "temperature" in params:
            kwargs.update(temperature=params["temperature"], top_p=params["top_p"],
                          extra_body={"top_k": params["top_k"], "repetition_penalty": params["repetition_penalty"]})
        last_error = None
        attempt, unavailable_since = 0, None
        while True:
            try:
                completion = self._api.chat.completions.create(**kwargs)
                choice = completion.choices[0]
                raw = choice.message.content or ""
                usage = {"served_model": getattr(completion, "model", None),
                         "finish": getattr(choice, "finish_reason", None)}
                if getattr(completion, "usage", None) is not None:
                    usage.update(prompt_tokens=completion.usage.prompt_tokens,
                                 completion_tokens=completion.usage.completion_tokens)
                return self._cleaner._clean_response(raw, self.model_key), usage, None
            except Exception as e:  # noqa: BLE001
                if type(e).__name__ in _FATAL_NAMES:
                    raise
                last_error = f"{type(e).__name__}: {e}"
                if self._modal and _server_unavailable(e):
                    unavailable_since = unavailable_since or time.time()
                    if time.time() - unavailable_since < MODAL_PATIENCE_S:
                        time.sleep(10)         # server (re)starting: wait, do not spend an attempt
                        continue
                attempt += 1
                if attempt >= 3:
                    return "", {}, last_error
                time.sleep(2 ** (attempt - 1))   # 1 s, then 2 s

    def _anthropic_chat(self, messages, max_new_tokens):
        system, msgs = to_anthropic(messages)
        kwargs = dict(model=self.spec["model_id"], max_tokens=min(max_new_tokens, CLAUDE_MAX_TOKENS),
                      messages=msgs, thinking={"type": "disabled"})
        if system:
            kwargs["system"] = system
        last_error = None
        for attempt in range(3):
            try:
                msg = self._api.messages.create(**kwargs)
                raw = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
                usage = {"served_model": getattr(msg, "model", None), "finish": getattr(msg, "stop_reason", None)}
                if getattr(msg, "usage", None) is not None:
                    usage.update(prompt_tokens=msg.usage.input_tokens, completion_tokens=msg.usage.output_tokens)
                return self._cleaner._clean_response(raw, self.model_key), usage, None
            except Exception as e:  # noqa: BLE001
                if type(e).__name__ in _FATAL_NAMES:
                    raise
                last_error = f"{type(e).__name__}: {e}"
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return "", {}, last_error

    # -- accounting -------------------------------------------------------------
    def cost_usd(self) -> float:
        if self._modal:
            return 0.0       # billed as GPU time by Modal (dashboard), not per token
        return (self.tokens_in * self.spec["price_in"] + self.tokens_out * self.spec["price_out"]) / 1e6

    def stats(self) -> dict:
        return {"model": self.model_key, "n_calls": self.n_calls, "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out, "n_errors": self.n_errors, "n_empty": self.n_empty,
                "cost_usd_estimate": round(self.cost_usd(), 6), "serving": self.serving}


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
