"""The real-API code path of StudyClient, tested against a fake OpenAI-compatible client (no network)."""
from types import SimpleNamespace

import pytest

from sting.client import StudyClient


class AuthenticationError(Exception):
    pass


class FakeAPI:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))],
                               usage=SimpleNamespace(prompt_tokens=120, completion_tokens=7))


def make(model, script, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    api = FakeAPI(script)

    class C(StudyClient):
        def _build_api_client(self):
            return api
    return C(model), api


def test_sampling_cleanup_and_usage(monkeypatch):
    c, api = make("llama-3.1-8b", ['```json\n{"was_challenged": true, "challenge_reason": "x"}\n```'], monkeypatch)
    out, _ = c.chat([{"role": "user", "content": "hi"}])
    assert out.startswith("{") and '"was_challenged": true' in out          # harness clean-up applied
    kw = api.calls[0]
    assert kw["temperature"] == 0.8 and kw["top_p"] == 0.95 and kw["max_tokens"] == 256
    assert kw["extra_body"] == {"top_k": 40, "repetition_penalty": 1.1}
    assert c.tokens_in == 120 and c.tokens_out == 7


def test_transient_errors_retried_then_empty(monkeypatch):
    c, api = make("qwen2.5-7b", [RuntimeError("503"), RuntimeError("503"), "ok"], monkeypatch)
    assert c.chat([{"role": "user", "content": "hi"}])[0] == "ok" and len(api.calls) == 3
    c2, api2 = make("qwen2.5-7b", [RuntimeError("503")] * 3, monkeypatch)
    assert c2.chat([{"role": "user", "content": "hi"}])[0] == "" and c2.n_errors == 1 and c2.n_empty == 1


def test_fatal_errors_raise(monkeypatch):
    c, _ = make("llama-3.1-8b", [AuthenticationError("bad key")], monkeypatch)
    with pytest.raises(AuthenticationError):
        c.chat([{"role": "user", "content": "hi"}])


def test_closed_model_uses_provider_defaults(monkeypatch):
    c, api = make("gpt-4.1-mini", ["ACCEPT"], monkeypatch)
    c.chat([{"role": "user", "content": "hi"}], max_new_tokens=80)
    kw = api.calls[0]
    assert kw["model"] == "openai/gpt-4.1-mini" and "temperature" not in kw and kw["max_tokens"] == 80


def test_openrouter_only_model_needs_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("poseidon_compute.llm_config._load", lambda: None)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        StudyClient("gpt-4.1-mini")
