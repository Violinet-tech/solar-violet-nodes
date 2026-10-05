# LLM backends for the Violet Text Encoder: local transformers models (4/8/16-bit),
# Ollama, LM Studio, OpenRouter, Gemini, OpenCode Zen and NVIDIA NIM (free chat models only),
# plus detection of LLM servers already running on this machine. Fresh Violet code.

import os
import re
import json
import base64
import gc
import io
import sys
import time
import shutil
import subprocess
import urllib.request
import urllib.error

from . import lora_catalog as lc
from .civitai import _ssl_ctx

try:
    import folder_paths
except ImportError:
    folder_paths = None

PROVIDERS = ["local", "ollama", "lmstudio", "openrouter", "opencode", "gemini", "nvidia_nim"]
DEFAULT_URLS = {
    "ollama": "http://127.0.0.1:11434",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "opencode": "https://opencode.ai/zen/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
}
# Qwen3-VL models the enhancer can run on this PC. One that is not on disk yet is downloaded on first use.
LOCAL_CATALOG = {
    "Qwen3-VL-2B-Instruct": "Qwen/Qwen3-VL-2B-Instruct",
    "Qwen3-VL-2B-Thinking": "Qwen/Qwen3-VL-2B-Thinking",
    "Qwen3-VL-4B-Instruct": "Qwen/Qwen3-VL-4B-Instruct",
    "Qwen3-VL-4B-Thinking": "Qwen/Qwen3-VL-4B-Thinking",
    "Qwen3-VL-8B-Instruct": "Qwen/Qwen3-VL-8B-Instruct",
    "Qwen3-VL-8B-Thinking": "Qwen/Qwen3-VL-8B-Thinking",
}
DEFAULT_LOCAL = "Qwen3-VL-2B-Instruct"
LOCAL_REPO = LOCAL_CATALOG[DEFAULT_LOCAL]

# NIM lists embedding/rerank/safety/vision-encoder models next to chat models; keep chat only.
_NIM_SKIP = re.compile(r"embed|rerank|guard|safety|nemoguard|parse|clip|retriev|riva|paddle|ocr|"
                       r"reward|topic-control|content-safety|jailbreak|nv-yolox|cosmos|deplot|"
                       r"vista|maxine|fuyu|kosmos|neva|streampetr|bge|arctic-embed|snowflake", re.I)


# ---------------- settings ----------------

def llm_settings():
    cfg = lc.load_config().get("llm", {})
    return {"keys": cfg.get("keys", {}), "urls": cfg.get("urls", {}), "local_dirs": cfg.get("local_dirs", []),
            "civitai_key": lc.load_config().get("civitai_key", "")}


def save_llm_settings(body):
    cfg = lc.load_config()
    cur = cfg.get("llm", {})
    if isinstance(body.get("keys"), dict):
        keys = cur.get("keys", {})
        for k, v in body["keys"].items():
            if v is None:
                continue
            if v == "":
                keys.pop(k, None)
            elif not str(v).startswith("•"):   # masked placeholder from the UI means "unchanged"
                keys[k] = str(v).strip()
        cur["keys"] = keys
    if isinstance(body.get("urls"), dict):
        cur["urls"] = {k: str(v).strip() for k, v in body["urls"].items() if str(v).strip()}
    if isinstance(body.get("local_dirs"), list):
        cur["local_dirs"] = [str(d).strip() for d in body["local_dirs"] if str(d).strip()]
    cfg["llm"] = cur
    if "civitai_key" in body and not str(body["civitai_key"]).startswith("•"):
        cfg["civitai_key"] = str(body["civitai_key"]).strip()
    with open(lc._config_path(), "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=2)
    return public_settings()


def public_settings():
    """Same as llm_settings but with keys masked so they never travel back to the browser."""
    s = llm_settings()
    mask = lambda v: ("•" * 8 + v[-4:]) if v else ""
    return {"keys": {k: mask(v) for k, v in s["keys"].items()}, "urls": s["urls"], "local_dirs": s["local_dirs"],
            "civitai_key": mask(s["civitai_key"]), "defaults": DEFAULT_URLS, "providers": PROVIDERS}


def _key(provider):
    env = {"gemini": "GEMINI_API_KEY", "nvidia_nim": "NVIDIA_API_KEY", "opencode": "OPENCODE_API_KEY", "openrouter": "OPENROUTER_API_KEY",
           "lmstudio": "LMSTUDIO_API_KEY", "ollama": "OLLAMA_API_KEY"}.get(provider)
    return llm_settings()["keys"].get(provider) or (os.environ.get(env) if env else None) or ""


def _url(provider):
    return (llm_settings()["urls"].get(provider) or DEFAULT_URLS.get(provider, "")).rstrip("/")


# ---------------- http helpers ----------------

def _http(url, body=None, headers=None, timeout=120, method=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", "User-Agent": "ViolinetOS-Violet"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            return json.loads(r.read().decode("utf8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf8", "ignore")[:300]
        raise RuntimeError(f"{e.code} from {url.split('?')[0]}: {detail}")


def _bearer(provider):
    k = _key(provider)
    h = {"Authorization": f"Bearer {k}"} if k else {}
    if provider == "openrouter":
        h.update({"HTTP-Referer": "https://violinettech.ai", "X-Title": "Violet"})
    return h


def _image_b64(image):
    from PIL import Image
    arr = image[0].cpu().numpy()
    im = Image.fromarray((arr.clip(0, 1) * 255).astype("uint8")).convert("RGB")
    if max(im.size) > 1280:
        im.thumbnail((1280, 1280))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


# ---------------- model listing ----------------

def local_model_dirs():
    roots = []
    if folder_paths is not None:
        try:
            roots += folder_paths.get_folder_paths("text_encoders")
        except Exception:
            pass
    roots += llm_settings()["local_dirs"]
    out, seen = [], set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        cands = [root] + [os.path.join(root, d) for d in sorted(os.listdir(root))]
        for c in cands:
            if os.path.isfile(os.path.join(c, "config.json")) and c.lower() not in seen:
                try:
                    if any(f.endswith((".safetensors", ".bin")) for f in os.listdir(c)):
                        seen.add(c.lower())
                        out.append(c)
                except OSError:
                    pass
    return out


def _ollama_disk_models():
    """Ollama's own model store, read from disk, so the list works even when Ollama is not running."""
    roots = [os.environ.get("OLLAMA_MODELS", ""), os.path.join(os.path.expanduser("~"), ".ollama", "models")]
    for r in roots:
        man = os.path.join(r, "manifests") if r else ""
        if not os.path.isdir(man):
            continue
        out = set()
        for dp, _dn, fn in os.walk(man):
            for f in fn:
                rel = os.path.relpath(os.path.join(dp, f), man).replace("\\", "/").split("/")
                if len(rel) < 4:
                    continue
                reg, ns, model, tag = rel[0], rel[1], "/".join(rel[2:-1]), rel[-1]
                if reg == "registry.ollama.ai":
                    base = model if ns == "library" else f"{ns}/{model}"
                else:
                    base = f"{reg}/{ns}/{model}"
                out.add(f"{base}:{tag}")
        if out:
            return sorted(out)
    return []


def _ollama_exe():
    exe = shutil.which("ollama")
    if exe:
        return exe
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")):
        p = os.path.join(base, "Programs", "Ollama", "ollama.exe") if base else ""
        if p and os.path.isfile(p):
            return p
    return None


def ensure_ollama():
    """Make sure a local Ollama answers, starting it in the background when it is installed but not running."""
    url = _url("ollama")
    try:
        _http(url + "/api/tags", timeout=2)
        return True
    except Exception:
        pass
    if not url.startswith(("http://127.0.0.1", "http://localhost")):
        return False
    exe = _ollama_exe()
    if not exe:
        return False
    flags = (0x08000000 | 0x00000008) if sys.platform == "win32" else 0
    try:
        subprocess.Popen([exe, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    except Exception:
        return False
    end = time.time() + 25
    while time.time() < end:
        time.sleep(1)
        try:
            _http(url + "/api/tags", timeout=2)
            return True
        except Exception:
            continue
    return False


def _is_free(provider, m):
    if provider == "openrouter":
        p = m.get("pricing") or {}
        try:
            return float(p.get("prompt", 1)) == 0 and float(p.get("completion", 1)) == 0
        except (TypeError, ValueError):
            return False
    if provider == "opencode":
        return "free" in str(m.get("id", "")).lower()
    return True


NEEDS_KEY = {"gemini": "Gemini", "nvidia_nim": "NVIDIA", "opencode": "OpenCode Zen"}


def describe_models(provider, free_only=False):
    """{models, note, free_filter}: the dropdown contents plus a line telling the person what they are looking at."""
    if provider in NEEDS_KEY and not _key(provider):
        raise RuntimeError(f"Add your {NEEDS_KEY[provider]} API key under Settings and the models you can use will list here.")
    if provider == "ollama":
        note = ""
        try:
            names = [m["name"] for m in _http(_url("ollama") + "/api/tags", timeout=4).get("models", [])]
        except Exception:
            names = _ollama_disk_models()
            note = "Ollama is not running: listed from its model folder. It is started for you when the graph runs."
        return {"models": names, "note": note, "free_filter": False}
    if provider in ("openrouter", "opencode"):
        d = _http(_url(provider) + "/models", headers=_bearer(provider), timeout=15)
        rows = d.get("data", [])
        note = ""
        if free_only:
            rows = [m for m in rows if _is_free(provider, m)]
            note = "Free models only."
        return {"models": sorted(m["id"] for m in rows), "note": note, "free_filter": True}
    names = list_models(provider)
    if provider == "local":
        have = {os.path.basename(d).lower() for d in local_model_dirs()}
        return {"models": names, "installed": [n for n in names if n.lower() in have], "free_filter": False,
                "note": "Not installed yet? Pick it and the first run downloads it. Quantization applies to local models."}
    note = {"nvidia_nim": "Free NIM chat models only."}.get(provider, "")
    return {"models": names, "note": note, "free_filter": False}


def list_models(provider):
    if provider == "local":
        names = list(LOCAL_CATALOG)
        names += [b for b in (os.path.basename(d) for d in local_model_dirs()) if b not in names]
        return names
    if provider == "ollama":
        d = _http(_url("ollama") + "/api/tags", timeout=6)
        return [m["name"] for m in d.get("models", [])]
    if provider in ("lmstudio", "opencode", "openrouter"):
        d = _http(_url(provider) + "/models", headers=_bearer(provider), timeout=10)
        return [m["id"] for m in d.get("data", [])]
    if provider == "gemini":
        d = _http(f"{_url('gemini')}/models?key={_key('gemini')}&pageSize=200", timeout=15)
        return [m["name"].split("/", 1)[1] for m in d.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])]
    if provider == "nvidia_nim":
        d = _http(_url("nvidia_nim") + "/models", headers=_bearer("nvidia_nim"), timeout=15)
        return sorted(m["id"] for m in d.get("data", []) if not _NIM_SKIP.search(m["id"]))
    return []


# ---------------- detect what is already running ----------------

_PROBES = [
    ("ollama", "http://127.0.0.1:11434", "/api/tags"),
    ("lmstudio", "http://127.0.0.1:1234/v1", "/models"),
    ("llamacpp", "http://127.0.0.1:8080/v1", "/models"),
    ("koboldcpp", "http://127.0.0.1:5001/v1", "/models"),
    ("vllm", "http://127.0.0.1:8000/v1", "/models"),
    ("jan", "http://127.0.0.1:1337/v1", "/models"),
    ("openwebui-api", "http://127.0.0.1:5000/v1", "/models"),
]


def _probe(item):
    name, base, path = item
    try:
        d = _http(base + path, timeout=1.5)
    except Exception:
        return None
    models = [m.get("name") or m.get("id") for m in (d.get("models") or d.get("data") or [])]
    loaded = []
    if name == "ollama":
        try:
            loaded = [m["name"] for m in _http(base + "/api/ps", timeout=1.5).get("models", [])]
        except Exception:
            pass
    return {"process": name, "base_url": base, "models": [m for m in models if m], "loaded": loaded}


def detect_local():
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(len(_PROBES)) as ex:
        return [r for r in ex.map(_probe, _PROBES) if r]


def attach_pick(found):
    """Choose provider/url/model from detect_local() output: prefer a model that is already loaded."""
    order = {"ollama": "ollama", "lmstudio": "lmstudio"}
    for f in found:
        if f["loaded"]:
            return {"provider": "ollama", "base_url": f["base_url"], "model": f["loaded"][0], "process": f["process"]}
    for f in found:
        if f["models"]:
            prov = order.get(f["process"], "lmstudio")   # llama.cpp / vLLM / Jan / Kobold speak the LM Studio dialect
            return {"provider": prov, "base_url": f["base_url"], "model": f["models"][0], "process": f["process"]}
    return None


# ---------------- chat calls ----------------

def _openai_chat(provider, model, system, text, image, max_tokens, temperature, base_override=None):
    content = [{"type": "text", "text": text}]
    if image is not None:
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _image_b64(image)}})
    body = {"model": model, "max_tokens": int(max_tokens), "temperature": float(temperature),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": content if image is not None else text}]}
    d = _http((base_override or _url(provider)) + "/chat/completions", body, _bearer(provider), timeout=180)
    return d["choices"][0]["message"]["content"]


def _ollama_chat(model, system, text, image, max_tokens, temperature):
    ensure_ollama()
    msg = {"role": "user", "content": text}
    if image is not None:
        msg["images"] = [_image_b64(image)]
    body = {"model": model, "stream": False, "think": False, "messages": [{"role": "system", "content": system}, msg],
            "options": {"temperature": float(temperature), "num_predict": int(max_tokens)}}
    return _http(_url("ollama") + "/api/chat", body, _bearer("ollama"), timeout=300)["message"]["content"]


def _gemini_chat(model, system, text, image, max_tokens, temperature):
    parts = [{"text": text}]
    if image is not None:
        parts.insert(0, {"inline_data": {"mime_type": "image/jpeg", "data": _image_b64(image)}})
    body = {"system_instruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": float(temperature), "maxOutputTokens": int(max_tokens)}}
    d = _http(f"{_url('gemini')}/models/{model}:generateContent?key={_key('gemini')}", body, timeout=180)
    return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])


# ---------------- local transformers ----------------

_local = {"key": None, "model": None, "processor": None, "vl": False}


def unload_local():
    if _local["model"] is not None:
        _local.update(key=None, model=None, processor=None)
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass


def resolve_local_dir(name):
    """`name` may be a full path, the folder name of a model under text_encoders, or the default Qwen3-VL."""
    if name and os.path.isabs(name) and os.path.isdir(name):
        return name
    for d in local_model_dirs():
        if os.path.basename(d).lower() == (name or DEFAULT_LOCAL).lower():
            return d
    want = name or DEFAULT_LOCAL
    repo = next((r for k, r in LOCAL_CATALOG.items() if k.lower() == want.lower()), None)
    if repo:
        want = next(k for k in LOCAL_CATALOG if k.lower() == want.lower())
        root = None
        try:
            paths = folder_paths.get_folder_paths("text_encoders")
            install = os.path.normcase(getattr(folder_paths, "base_path", ""))
            outside = [p for p in paths if not os.path.normcase(p).startswith(install)]
            root = (outside or paths)[0]
        except Exception:
            root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        d = os.path.join(root, want)
        if not os.path.isfile(os.path.join(d, "config.json")):
            from huggingface_hub import snapshot_download
            print(f"[Violet] downloading {repo} to {d} (first use only)")
            snapshot_download(repo_id=repo, local_dir=d)
        return d
    raise RuntimeError(f"Local model '{name}' not found. Use a folder name under text_encoders or a full path.")


def _load_local(name, quant):
    path = resolve_local_dir(name)
    key = (path, quant)
    if _local["key"] == key and _local["model"] is not None:
        return _local
    unload_local()
    import torch
    from transformers import AutoProcessor, AutoTokenizer, BitsAndBytesConfig
    cfg = json.load(open(os.path.join(path, "config.json"), encoding="utf8"))
    archs = " ".join(cfg.get("architectures", []))
    vl = bool(re.search(r"VL|Vision|ImageText|LLaVA|Llava|Gemma3|Idefics|Pixtral|Mistral3", archs)) or "vision_config" in cfg
    kwargs = {"dtype": torch.bfloat16}
    if quant == "4-bit":
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16)
    elif quant == "8-bit":
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    if torch.cuda.is_available():
        kwargs["device_map"] = {"": 0}
    print(f"[Violet] loading local model {os.path.basename(path)} ({quant})")
    if vl:
        from transformers import AutoModelForImageTextToText
        model = AutoModelForImageTextToText.from_pretrained(path, **kwargs).eval()
        proc = AutoProcessor.from_pretrained(path)
    else:
        from transformers import AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained(path, **kwargs).eval()
        proc = AutoTokenizer.from_pretrained(path)
    _local.update(key=key, model=model, processor=proc, vl=vl)
    return _local


def _local_chat(name, quant, system, text, image, max_tokens, temperature, seed, keep):
    import torch
    st = _load_local(name, quant)
    model, proc, vl = st["model"], st["processor"], st["vl"]
    if "thinking" in (name or "").lower():
        max_tokens = int(max_tokens) + 2048
    try:
        if vl:
            user = [{"type": "text", "text": text}]
            if image is not None:
                from PIL import Image
                arr = image[0].cpu().numpy()
                user.insert(0, {"type": "image", "image": Image.fromarray((arr.clip(0, 1) * 255).astype("uint8")).convert("RGB")})
            msgs = [{"role": "system", "content": [{"type": "text", "text": system}]}, {"role": "user", "content": user}]
            inputs = proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True,
                                              return_dict=True, return_tensors="pt").to(model.device)
        else:
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": text}]
            ids = proc.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True)
            inputs = ids.to(model.device)
        if seed is not None:
            torch.manual_seed(int(seed) % (2 ** 63))
        gen = {"max_new_tokens": int(max_tokens)}
        if temperature > 0:
            gen.update(do_sample=True, temperature=float(temperature), top_p=0.9)
        else:
            gen.update(do_sample=False)
        with torch.inference_mode():
            out = model.generate(**inputs, **gen)
        return proc.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
    finally:
        if not keep:
            unload_local()


# ---------------- entry point ----------------

def clean_reply(text):
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    if "</think>" in t:   # the opening tag is part of the prompt on some thinking models
        t = t.split("</think>")[-1].strip()
    for pre in ("Prompt:", "prompt:", "Enhanced prompt:", "Final prompt:", "Here is the prompt:"):
        if t.startswith(pre):
            t = t[len(pre):].strip()
    if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'":
        t = t[1:-1].strip()
    return t


def chat(provider, model, system, text, image=None, quant="4-bit", max_tokens=256, temperature=0.6,
         seed=0, keep_loaded=False):
    if provider == "local":
        out = _local_chat(model, quant, system, text, image, max_tokens, temperature, seed, keep_loaded)
    elif provider == "ollama":
        out = _ollama_chat(model, system, text, image, max_tokens, temperature)
    elif provider == "gemini":
        out = _gemini_chat(model, system, text, image, max_tokens, temperature)
    elif provider in ("lmstudio", "opencode", "openrouter", "nvidia_nim"):
        if provider == "nvidia_nim" and _NIM_SKIP.search(model or ""):
            raise RuntimeError(f"{model} is not a free chat model on NVIDIA NIM")
        out = _openai_chat(provider, model, system, text, image, max_tokens, temperature)
    else:
        raise RuntimeError(f"Unknown provider {provider}")
    out = clean_reply(out)
    if not out:
        raise RuntimeError(f"{provider} model '{model}' returned an empty reply (thinking models can spend the whole "
                           "token budget on reasoning; raise max_new_tokens or pick another model)")
    return out
