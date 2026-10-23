"""vLLM servers on Modal for the study's open-weight models (Llama-3.1-8B, Qwen2.5-7B).

Deployed and checked through the study CLI, not by hand:

    python -m sting modal deploy     # build the image, deploy, record the endpoints locally
    python -m sting modal warm       # wake the servers and verify exactly what they serve
    python -m sting modal stop       # stop the app when the study is done

Follows Modal's official vLLM example (modal-labs/modal-examples,
06_gpu_and_ml/llm-serving/vllm_inference.py as of October 2026: Modal Server API, CUDA 12.9 image,
vllm==0.21.0). Study-specific choices, all verified by the client before its first call
(/v1/models, /version) and recorded with the data:

* bf16 weights at a pinned Hugging Face revision, served under the study's model key;
* --max-model-len 8192: study prompts stay under ~3k tokens; vLLM's default (the model's 128k
  window) reserves memory for nothing and does not fit a 24 GB GPU;
* --generation-config vllm: sampling is exactly what the study client sends (the harness's
  settings, Zeng & Rudzicz Table 10), never the model repo's generation_config.json defaults;
* one container per model (max_containers=1, target_concurrency=128): the study's 30-60
  concurrent requests are batched by vLLM on one GPU instead of Modal starting more GPUs;
  scale to zero after 15 idle minutes, so nothing is billed between stages;
* a bearer key (VLLM_API_KEY), generated at deploy time, protects the public endpoint.

Keep this file self-contained: Modal imports it inside the container, where the sting package is
not installed. Deploy-time settings reach the container through `env=` and the secret, so the
container's import reproduces the same definitions.
"""
from __future__ import annotations

import os
import subprocess

import modal

APP_NAME = "sting-vllm"
PORT = 8000
MINUTES = 60
MAX_MODEL_LEN = 8192
VLLM_VERSION = "0.21.0"
CUDA_IMAGE = "nvidia/cuda:12.9.0-devel-ubuntu22.04"

# model key -> Modal server name, Hugging Face repo and pinned revision (commit SHA, checked
# against the Hugging Face API on 2026-10-23).
OPEN_MODELS = {
    "llama-3.1-8b": dict(server="LlamaServer", repo="meta-llama/Llama-3.1-8B-Instruct",
                         revision="0e9e39f249a16976918f6564b8830bc894c89659", gated=True),
    "qwen2.5-7b": dict(server="QwenServer", repo="Qwen/Qwen2.5-7B-Instruct",
                       revision="a09a35458c702b33eeacc393d103063234e8bc28", gated=False),
}
# Fallback only if Meta's (manually approved) access request is still pending: an ungated copy
# whose weights and configs are byte-identical to Meta's repo (sha256 of every safetensors shard,
# config.json, generation_config.json, tokenizer.json, special_tokens_map.json); only
# tokenizer_config.json differs. Using it is a deviation to log in DEVIATIONS.md.
LLAMA_MIRROR = dict(repo="NousResearch/Meta-Llama-3.1-8B-Instruct",
                    revision="d10aef7999a2b5ba950ab3974312feeedbfe0b77", gated=False)

GPU = os.environ.get("STING_MODAL_GPU", "H100")
LLAMA_SOURCE = os.environ.get("STING_LLAMA_SOURCE", "official")      # "official" | "mirror"
if LLAMA_SOURCE == "mirror":
    OPEN_MODELS["llama-3.1-8b"].update(LLAMA_MIRROR)


def vllm_command(model_key: str) -> list:
    m = OPEN_MODELS[model_key]
    return ["vllm", "serve", m["repo"], "--revision", m["revision"],
            "--served-model-name", model_key,
            "--host", "0.0.0.0", "--port", str(PORT),
            "--dtype", "bfloat16",
            "--max-model-len", str(MAX_MODEL_LEN),
            "--generation-config", "vllm",
            "--uvicorn-log-level", "warning"]


image = (
    modal.Image.from_registry(CUDA_IMAGE, add_python="3.12")
    .entrypoint([])
    .uv_pip_install(f"vllm=={VLLM_VERSION}")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)
hf_cache = modal.Volume.from_name("sting-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("sting-vllm-cache", create_if_missing=True)
# vLLM reads VLLM_API_KEY itself (no key on the command line); HF_TOKEN downloads gated weights.
_secret_values = {k: os.environ[k] for k in ("VLLM_API_KEY", "HF_TOKEN") if os.environ.get(k)}
secret = modal.Secret.from_dict(_secret_values)

app = modal.App(APP_NAME)

SERVER_OPTIONS = dict(
    image=image,
    gpu=GPU,
    port=PORT,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[secret],
    env={"STING_MODAL_GPU": GPU, "STING_LLAMA_SOURCE": LLAMA_SOURCE},
    min_containers=0,
    max_containers=1,
    target_concurrency=128,
    scaledown_window=15 * MINUTES,
    startup_timeout=20 * MINUTES,
    unauthenticated=True,          # the vLLM bearer key is the authentication
)


@app.server(**SERVER_OPTIONS)
class LlamaServer:
    @modal.enter()
    def start(self):
        self.proc = subprocess.Popen(vllm_command("llama-3.1-8b"))

    @modal.exit()
    def stop(self):
        self.proc.terminate()


@app.server(**SERVER_OPTIONS)
class QwenServer:
    @modal.enter()
    def start(self):
        self.proc = subprocess.Popen(vllm_command("qwen2.5-7b"))

    @modal.exit()
    def stop(self):
        self.proc.terminate()
