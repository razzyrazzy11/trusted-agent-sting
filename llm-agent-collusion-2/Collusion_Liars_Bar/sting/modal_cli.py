"""Deploy, warm up, inspect and stop the study's vLLM servers on Modal (definitions: modal_app.py).

    python -m sting modal deploy [--gpu H100] [--llama-mirror]
    python -m sting modal warm   [--models llama-3.1-8b qwen2.5-7b] [--timeout 1500]
    python -m sting modal status
    python -m sting modal stop

`deploy` records the endpoint URLs and the endpoint key in ~/.sting/modal_endpoints.json (outside
the repo; override the path with STING_MODAL_ENDPOINTS). With OPEN_MODEL_BACKEND = "modal" (config.py;
override with STING_OPEN_BACKEND), the study client reads that file and, before its first call,
checks that each server serves the expected model key, repository, context length and vLLM
version. It never falls back to another model or provider.

Prerequisites: `pip install -r sting/requirements.txt`, `python -m modal setup` (once, in the same
environment, e.g. WSL), and for Llama an approved access request on Hugging Face plus HF_TOKEN in
compute.env (or the environment).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

APP_FILE = Path(__file__).with_name("modal_app.py")
APP_NAME = "sting-vllm"            # = modal_app.APP_NAME (a test checks)
DEFAULT_TIMEOUT_S = 1500           # first boot downloads ~16 GB of weights and compiles CUDA graphs


# ------------------------------------------------------------------ endpoints file
def endpoints_path() -> Path:
    return Path(os.environ.get("STING_MODAL_ENDPOINTS") or Path.home() / ".sting" / "modal_endpoints.json")


def load_endpoints() -> dict:
    p = endpoints_path()
    if not p.exists():
        raise RuntimeError(f"No Modal deployment recorded at {p}. Run `python -m sting modal deploy` first, or "
                           f"set STING_OPEN_BACKEND=poseidon to use Nebius/OpenRouter instead.")
    return json.loads(p.read_text())


def save_endpoints(d: dict) -> Path:
    p = endpoints_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n")
    try:
        os.chmod(p, 0o600)       # holds the endpoint key
    except OSError:
        pass
    return p


# ------------------------------------------------------------------ helpers
def _env_loaded() -> None:
    """compute.env (repo root) -> os.environ, as the rest of the study does (HF_TOKEN, ANTHROPIC_API_KEY)."""
    try:
        from poseidon_compute import llm_config
        llm_config._load()
    except Exception:  # noqa: BLE001 - the starter package is optional for these commands
        pass


def hf_token() -> Optional[str]:
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var].strip()
    home = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
    try:
        return (home / "token").read_text().strip() or None
    except OSError:
        return None


def hf_access(repo: str, revision: str, token: Optional[str]) -> Optional[int]:
    """HTTP status of the repo's config.json at the pinned revision (None if the check itself failed)."""
    req = urllib.request.Request(f"https://huggingface.co/{repo}/resolve/{revision}/config.json", method="HEAD")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001 - network hiccup: do not block, the server boot will surface it
        return None


def app_specs(llama_source: str = "official") -> Dict[str, dict]:
    """OPEN_MODELS as modal_app.py defines them for this Llama source (needs the modal package)."""
    old = os.environ.get("STING_LLAMA_SOURCE")
    os.environ["STING_LLAMA_SOURCE"] = llama_source
    try:
        spec = importlib.util.spec_from_file_location("sting_modal_app", APP_FILE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if old is None:
            os.environ.pop("STING_LLAMA_SOURCE", None)
        else:
            os.environ["STING_LLAMA_SOURCE"] = old
    return {k: dict(v) for k, v in mod.OPEN_MODELS.items()} | {"_meta": dict(
        vllm_version=mod.VLLM_VERSION, max_model_len=mod.MAX_MODEL_LEN, app=mod.APP_NAME)}


def _require_modal():
    try:
        import modal  # noqa: F401
    except ImportError:
        raise SystemExit("The modal package is not installed in this environment: "
                         "pip install -r sting/requirements.txt") from None


def _get(url: str, key: str, timeout: float = 30) -> Tuple[Optional[int], str]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa: BLE001 - connection refused / reset / timeout while scaling up
        return None, f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------ readiness + verification
def server_info(model_key: str, timeout: float = DEFAULT_TIMEOUT_S, verbose: bool = True) -> dict:
    """Wait until the model's server answers (Modal returns 503 while it scales up from zero), then
    verify it serves exactly what was deployed. Returns the provenance record the client logs."""
    ep = load_endpoints()
    m = ep.get("models", {}).get(model_key)
    if m is None:
        raise RuntimeError(f"{model_key} is not in the Modal deployment ({endpoints_path()}); redeploy with "
                           f"`python -m sting modal deploy`.")
    key, url = ep["api_key"], m["url"].rstrip("/")
    t0, last_note, status, body = time.time(), 0.0, None, ""
    while True:
        status, body = _get(url + "/v1/models", key)
        if status == 200:
            break
        if status in (401, 403):
            raise RuntimeError(f"The {model_key} server rejected the endpoint key; redeploy with "
                               f"`python -m sting modal deploy` (it reuses or renews the key).")
        if status == 404:          # vLLM always serves /v1/models: a 404 comes from Modal (no such app)
            raise RuntimeError(f"No Modal server at {url}: the app may have been stopped. Redeploy with "
                               f"`python -m sting modal deploy`.")
        waited = time.time() - t0
        if waited > timeout:
            raise TimeoutError(
                f"{model_key}: Modal server not ready after {int(waited)} s (last: {status} {body[:120]}). Check "
                f"`python -m modal app logs {APP_NAME}`; for Llama, a 401/403 from Hugging Face there means the "
                f"access request is not approved yet (or HF_TOKEN was missing at deploy).")
        if verbose and time.time() - last_note > 30:
            print(f"[modal] {model_key}: waiting for the server ({int(waited)} s; {status or body[:60]}). "
                  f"A cold start takes ~2-4 min, the first boot ~5-10 min.", flush=True)
            last_note = time.time()
        time.sleep(5)
    data = (json.loads(body).get("data") or [{}])[0]
    vstatus, vbody = _get(url + "/version", key)
    version = json.loads(vbody).get("version") if vstatus == 200 else None
    root = str(data.get("root") or "")
    problems = []
    if data.get("id") != model_key:
        problems.append(f"served id {data.get('id')!r} != {model_key!r}")
    if not (root == m["repo"] or (m["repo"].replace("/", "--") in root and m["revision"] in root)):
        problems.append(f"root {root!r} != {m['repo']!r}")
    if data.get("max_model_len") != ep["max_model_len"]:
        problems.append(f"max_model_len {data.get('max_model_len')} != {ep['max_model_len']}")
    if version != ep["vllm_version"]:
        problems.append(f"vLLM {version} != {ep['vllm_version']}")
    if problems:
        raise RuntimeError(f"The Modal server for {model_key} does not serve what the study expects: "
                           + "; ".join(problems) + ". Redeploy with `python -m sting modal deploy`.")
    if verbose:
        print(f"[modal] {model_key}: ready ({int(time.time() - t0)} s) - {m['repo']}@{m['revision'][:10]}, "
              f"vLLM {version}, {ep['gpu']}", flush=True)
    return dict(backend="modal", url=url, repo=m["repo"], revision=m["revision"], served_id=data.get("id"),
                root=root, max_model_len=data.get("max_model_len"), vllm_version=version, gpu=ep["gpu"],
                llama_source=ep.get("llama_source"), deployed_at=ep.get("deployed_at"))


def open_model_client(model_key: str, timeout: float = DEFAULT_TIMEOUT_S):
    """(OpenAI-compatible client, provenance) for an open model served on Modal."""
    info = server_info(model_key, timeout=timeout, verbose=True)
    from openai import OpenAI
    api = OpenAI(base_url=info["url"] + "/v1", api_key=load_endpoints()["api_key"], timeout=120.0, max_retries=0)
    return api, info


def ensure_ready(models: List[str], timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, dict]:
    """Wake several servers in parallel (cold starts overlap) and verify each."""
    out, errors = {}, {}

    def one(mk):
        try:
            out[mk] = server_info(mk, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            errors[mk] = e
    threads = [threading.Thread(target=one, args=(mk,)) for mk in models]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise RuntimeError("; ".join(f"{k}: {v}" for k, v in errors.items()))
    return out


# ------------------------------------------------------------------ commands
def deploy(gpu: str, llama_mirror: bool) -> int:
    _require_modal()
    _env_loaded()
    source = "mirror" if llama_mirror else "official"
    specs = app_specs(source)
    meta = specs.pop("_meta")
    token = hf_token()
    llama = specs["llama-3.1-8b"]
    if llama["gated"]:
        status = hf_access(llama["repo"], llama["revision"], token) if token else 401
        if status in (401, 403):
            print(f"Cannot deploy: {llama['repo']} is gated on Hugging Face and "
                  f"{'no HF token was found' if not token else 'this token has no access yet'}.\n"
                  f"  1. Request access at https://huggingface.co/{llama['repo']} (Meta approves manually;\n"
                  f"     usually minutes to hours).\n"
                  f"  2. Create a read token at https://huggingface.co/settings/tokens and add HF_TOKEN=hf_... to\n"
                  f"     the repo-root compute.env.\n"
                  f"  3. Rerun `python -m sting modal deploy`.\n"
                  f"If approval is slow, `--llama-mirror` serves {app_specs('mirror')['llama-3.1-8b']['repo']}, an\n"
                  f"ungated copy with byte-identical weights (only tokenizer_config.json differs); log it in\n"
                  f"DEVIATIONS.md.")
            return 2
    prev = json.loads(endpoints_path().read_text()) if endpoints_path().exists() else {}
    key = prev.get("api_key") or secrets.token_urlsafe(32)
    env = dict(os.environ, STING_MODAL_GPU=gpu, STING_LLAMA_SOURCE=source, VLLM_API_KEY=key)
    if token:
        env["HF_TOKEN"] = token
    else:
        env.pop("HF_TOKEN", None)
    print(f"Deploying {APP_NAME}: Llama {llama['repo']}@{llama['revision'][:10]} and "
          f"{specs['qwen2.5-7b']['repo']}, vLLM {meta['vllm_version']} on {gpu} (scale to zero when idle).", flush=True)
    rc = subprocess.run([sys.executable, "-m", "modal", "deploy", str(APP_FILE)], env=env).returncode
    if rc:
        print("`modal deploy` failed (output above). If it says you are not authenticated, run "
              "`python -m modal setup` in this environment.")
        return rc
    import modal
    models = {}
    for mk, s in specs.items():
        url = modal.Server.from_name(APP_NAME, s["server"]).get_url()
        if not url:
            print(f"Deployed, but Modal returned no URL for {s['server']}; rerun `python -m sting modal deploy`.")
            return 1
        models[mk] = dict(server=s["server"], url=str(url).rstrip("/"), repo=s["repo"], revision=s["revision"])
    p = save_endpoints(dict(app=APP_NAME, deployed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), gpu=gpu,
                            llama_source=source, vllm_version=meta["vllm_version"],
                            max_model_len=meta["max_model_len"], api_key=key, models=models))
    for mk, m in models.items():
        print(f"  {mk:14s} {m['url']}")
    print(f"Endpoints recorded in {p}.\nNext: `python -m sting modal warm` (the first boot downloads the weights).")
    return 0


def warm(models: List[str], timeout: float) -> int:
    ensure_ready(models, timeout=timeout)
    return 0


def status() -> int:
    ep = load_endpoints()
    shown = {k: v for k, v in ep.items() if k != "api_key"}
    print(json.dumps(shown, indent=2))
    print("Servers scale to zero after 15 idle minutes; any request (including `warm`) starts a GPU. "
          "GPU spend: Modal dashboard -> Usage.")
    return 0


def stop() -> int:
    _require_modal()
    rc = subprocess.run([sys.executable, "-m", "modal", "app", "stop", APP_NAME, "-y"]).returncode
    if rc == 0:
        print(f"Stopped {APP_NAME}. `python -m sting modal deploy` brings it back (same endpoint key).")
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("deploy")
    d.add_argument("--gpu", default=os.environ.get("STING_MODAL_GPU", "H100"),
                   help="Modal GPU type (H100 default; A100-80GB or L40S are cheaper and slower)")
    d.add_argument("--llama-mirror", action="store_true", help="serve the ungated byte-identical Llama copy")
    w = sub.add_parser("warm")
    w.add_argument("--models", nargs="+", default=["llama-3.1-8b", "qwen2.5-7b"])
    w.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    sub.add_parser("status")
    sub.add_parser("stop")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "deploy":
            return deploy(a.gpu, a.llama_mirror)
        if a.cmd == "warm":
            return warm(a.models, a.timeout)
        if a.cmd == "status":
            return status()
        return stop()
    except (RuntimeError, TimeoutError) as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
