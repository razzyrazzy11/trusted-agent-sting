"""Model backends without network: the Modal vLLM servers (definition, readiness, verification,
waiting through scale-up) and Claude through the native Anthropic SDK (fakes stand in for both)."""
import json
from types import SimpleNamespace

import pytest

from sting import client as client_mod
from sting import modal_cli
from sting.client import StudyClient, prepare_backends, to_anthropic
from sting.config import MODELS


# ----------------------------------------------------------------- Modal app definition
def test_modal_app_matches_the_protocol():
    from sting import modal_app
    assert modal_app.APP_NAME == modal_cli.APP_NAME
    for key in ("llama-3.1-8b", "qwen2.5-7b"):
        spec = modal_app.OPEN_MODELS[key]
        assert spec["repo"] == MODELS[key]["model_id"] and spec["revision"] == MODELS[key]["revision"]
        cmd = modal_app.vllm_command(key)
        flags = dict(zip(cmd[3::2], cmd[4::2]))
        assert cmd[:3] == ["vllm", "serve", spec["repo"]]
        assert flags["--revision"] == spec["revision"] and flags["--served-model-name"] == key
        assert flags["--max-model-len"] == "8192" and flags["--generation-config"] == "vllm"
        assert flags["--dtype"] == "bfloat16" and "--api-key" not in cmd       # key comes from VLLM_API_KEY
    opts = modal_app.SERVER_OPTIONS
    # one GPU per model, never scaled out: the study's peak concurrency stays under the target
    assert opts["max_containers"] == 1 and opts["min_containers"] == 0 and opts["target_concurrency"] >= 64
    assert opts["unauthenticated"] is True and opts["scaledown_window"] <= 30 * 60


def test_llama_mirror_is_explicit():
    specs = modal_cli.app_specs("mirror")
    assert specs["llama-3.1-8b"]["repo"] == "NousResearch/Meta-Llama-3.1-8B-Instruct"
    assert specs["qwen2.5-7b"]["repo"] == MODELS["qwen2.5-7b"]["model_id"]
    assert modal_cli.app_specs("official")["llama-3.1-8b"]["repo"] == MODELS["llama-3.1-8b"]["model_id"]


# ----------------------------------------------------------------- Modal client path
@pytest.fixture
def endpoints(tmp_path, monkeypatch):
    p = tmp_path / "endpoints.json"
    p.write_text(json.dumps(dict(app="sting-vllm", gpu="H100", llama_source="official", vllm_version="0.21.0",
                                 max_model_len=8192, api_key="k", deployed_at="t", models={
                                     "llama-3.1-8b": dict(server="LlamaServer", url="https://x.modal.run",
                                                          repo="meta-llama/Llama-3.1-8B-Instruct",
                                                          revision=MODELS["llama-3.1-8b"]["revision"])})))
    monkeypatch.setenv("STING_MODAL_ENDPOINTS", str(p))
    monkeypatch.setenv("STING_OPEN_BACKEND", "modal")
    monkeypatch.setattr("poseidon_compute.llm_config._load", lambda: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return p


def fake_server(monkeypatch, root="meta-llama/Llama-3.1-8B-Instruct", version="0.21.0", cold=2):
    calls = []

    def _get(url, key, timeout=30):
        calls.append(url)
        assert key == "k"
        if url.endswith("/v1/models"):
            if sum(u.endswith("/v1/models") for u in calls) <= cold:
                return 503, "scaling up"
            return 200, json.dumps({"data": [{"id": "llama-3.1-8b", "root": root, "max_model_len": 8192}]})
        return 200, json.dumps({"version": version})
    monkeypatch.setattr(modal_cli, "_get", _get)
    return calls


def test_modal_client_waits_for_scale_up_then_verifies(endpoints, monkeypatch, capsys):
    calls = fake_server(monkeypatch)
    c = StudyClient("llama-3.1-8b")
    assert sum(u.endswith("/v1/models") for u in calls) == 3          # two 503s, then ready
    assert c.serving["backend"] == "modal" and c.serving["vllm_version"] == "0.21.0"
    assert c.serving["revision"] == MODELS["llama-3.1-8b"]["revision"] and c.cost_usd() == 0.0
    assert str(c._api.base_url).rstrip("/") == "https://x.modal.run/v1"


@pytest.mark.parametrize("kw,msg", [(dict(root="NousResearch/Meta-Llama-3.1-8B-Instruct"), "root"),
                                    (dict(version="0.20.0"), "vLLM")])
def test_modal_client_refuses_a_server_that_serves_something_else(endpoints, monkeypatch, kw, msg):
    fake_server(monkeypatch, cold=0, **kw)
    with pytest.raises(RuntimeError, match=msg):
        StudyClient("llama-3.1-8b")


def test_no_deployment_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("STING_MODAL_ENDPOINTS", str(tmp_path / "missing.json"))
    monkeypatch.setenv("STING_OPEN_BACKEND", "modal")
    monkeypatch.setattr("poseidon_compute.llm_config._load", lambda: None)
    with pytest.raises(RuntimeError, match="modal deploy"):
        StudyClient("qwen2.5-7b")


class Unavailable(Exception):
    status_code = 503


class FakeOpenAI:
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(model="llama-3.1-8b", usage=SimpleNamespace(prompt_tokens=11, completion_tokens=3),
                               choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=item))])


def test_modal_restart_is_waited_out_without_spending_attempts(endpoints, monkeypatch):
    fake_server(monkeypatch, cold=0)
    c = StudyClient("llama-3.1-8b")
    c._api = FakeOpenAI([Unavailable("503")] * 4 + ["CHALLENGE"])
    out, _ = c.chat([{"role": "user", "content": "x"}])
    kw = c._api.calls[-1]
    assert out == "CHALLENGE" and len(c._api.calls) == 5 and c.n_errors == 0
    assert kw["model"] == "llama-3.1-8b" and kw["temperature"] == 0.8
    assert kw["extra_body"] == {"top_k": 40, "repetition_penalty": 1.1}


def test_forced_llm_model_is_refused(monkeypatch):
    monkeypatch.setenv("STING_OPEN_BACKEND", "poseidon")
    monkeypatch.setenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    monkeypatch.setattr("poseidon_compute.llm_config._load", lambda: None)
    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        StudyClient("llama-3.1-8b")


def test_prepare_backends_is_a_no_op_for_stub_api_and_poseidon(monkeypatch):
    def boom(models):
        raise AssertionError("should not wake servers")
    monkeypatch.setattr(modal_cli, "ensure_ready", boom)
    monkeypatch.setenv("STING_OPEN_BACKEND", "modal")
    prepare_backends(["llama-3.1-8b"], stub=True)
    prepare_backends(["claude-haiku-5.5"])
    monkeypatch.setenv("STING_OPEN_BACKEND", "poseidon")
    prepare_backends(["llama-3.1-8b"])


# ----------------------------------------------------------------- Claude path
def test_to_anthropic_hoists_system_and_merges_turns():
    sys_text, msgs = to_anthropic([{"role": "system", "content": "rules"}, {"role": "user", "content": "a"},
                                   {"role": "user", "content": "b"}, {"role": "assistant", "content": "c"},
                                   {"role": "user", "content": "d"}])
    assert sys_text == "rules"
    assert msgs == [{"role": "user", "content": "a\n\nb"}, {"role": "assistant", "content": "c"},
                    {"role": "user", "content": "d"}]


class FakeAnthropic:
    instances = []

    def __init__(self, **kw):
        self.kw, self.calls = kw, []
        self.messages = SimpleNamespace(create=self._create)
        FakeAnthropic.instances.append(self)

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(model="claude-haiku-5-5", stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=200, output_tokens=4),
                               content=[SimpleNamespace(type="text", text="REFUSE. I play fair.")])


def test_claude_call_disables_thinking_and_keeps_provider_sampling(monkeypatch, tmp_path):
    import anthropic
    from sting.client import JsonlSink
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr("poseidon_compute.llm_config._load", lambda: None)
    sink = JsonlSink(tmp_path / "calls.jsonl")
    c = StudyClient("claude-haiku-5.5", sink=sink)
    out, _ = c.chat([{"role": "system", "content": "rules"}, {"role": "user", "content": "offer"},
                     {"role": "user", "content": "reply now"}], max_new_tokens=80)
    api = FakeAnthropic.instances[-1]
    kw = api.calls[0]
    assert out == "REFUSE. I play fair." and api.kw["max_retries"] >= 5
    assert kw["model"] == "claude-haiku-5-5" and kw["thinking"] == {"type": "disabled"}
    assert kw["max_tokens"] == 80 and kw["system"] == "rules"
    assert not {"temperature", "top_p", "top_k"} & set(kw)
    assert kw["messages"] == [{"role": "user", "content": "offer\n\nreply now"}]
    rec = json.loads((tmp_path / "calls.jsonl").read_text().splitlines()[0])
    assert rec["finish"] == "end_turn" and rec["served_model"] == "claude-haiku-5-5" and rec["tokens_in"] == 200
    assert c.serving["thinking"] == "disabled" and c.cost_usd() == pytest.approx((200 * 0.10 + 4 * 0.50) / 1e6)


def test_claude_needs_its_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("poseidon_compute.llm_config._load", lambda: None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        StudyClient("claude-haiku-5.5")
