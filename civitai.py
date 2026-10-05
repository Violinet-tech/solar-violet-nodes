# CivitAI lookup for the Violet LoRA loader: full page text (model + version description),
# tags, trigger words, precision, per-image generation settings, preview download.
# Fresh Violet code. Results are cached next to the LoRA as <name>.violet.json.

import os
import re
import json
import time
import hashlib
import html
import urllib.request
import urllib.error
import ssl
from html.parser import HTMLParser

API = "https://civitai.com/api/v1"
UA = "Mozilla/5.0 (ViolinetOS ComfyUI Violet LoRA Loader)"
IMG_EXTS = {".jpeg": ".jpeg", ".jpg": ".jpg", ".png": ".png", ".webp": ".webp"}


def sidecar_path(lora_path):
    return os.path.splitext(lora_path)[0] + ".violet.json"


def load_sidecar(lora_path):
    try:
        with open(sidecar_path(lora_path), "r", encoding="utf8") as f:
            return json.load(f)
    except Exception:
        return None


class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "pre", "blockquote", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.href = None

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag == "li":
            self.out.append("- ")
        if tag == "a":
            self.href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag == "a":
            self.href = None

    def handle_data(self, data):
        self.out.append(data)
        if self.href and self.href not in data:
            self.out.append(f" ({self.href})")
            self.href = None


def html_to_text(src):
    if not src:
        return ""
    p = _Text()
    try:
        p.feed(str(src))
    except Exception:
        return html.unescape(re.sub(r"<[^>]+>", " ", str(src))).strip()
    text = "".join(p.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ssl_ctx():
    # The Windows store on this PC has an expired root that breaks the default context; certifi's bundle is current.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url, key=None, timeout=25):
    headers = {"User-Agent": UA}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        return r.read()


def _get_json(url, key=None):
    return json.loads(_get(url, key).decode("utf8"))


def file_sha256(path, cache_file=None):
    """SHA256 of the file, cached in the sidecar keyed by size+mtime."""
    st = os.stat(path)
    sig = f"{st.st_size}:{int(st.st_mtime)}"
    side = load_sidecar(path) or {}
    if side.get("sha256") and side.get("hash_sig") == sig:
        return side["sha256"]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 24)
            if not b:
                break
            h.update(b)
    return h.hexdigest(), sig


def _comfy_sampler(meta):
    """Pull sampler/cfg/steps out of an embedded ComfyUI graph when the plain fields are missing."""
    raw = meta.get("comfy")
    try:
        g = json.loads(raw) if isinstance(raw, str) else raw
        nodes = (g or {}).get("prompt", g) or {}
        for n in nodes.values():
            if not isinstance(n, dict):
                continue
            inp = n.get("inputs", {})
            if "sampler_name" in inp and "steps" in inp:
                return {"sampler": inp.get("sampler_name"), "cfg": inp.get("cfg"), "steps": inp.get("steps"),
                        "scheduler": inp.get("scheduler")}
    except Exception:
        pass
    return {}


def _norm_image(im):
    meta = im.get("meta") or {}
    comfy = _comfy_sampler(meta)
    return {
        "url": im.get("url"),
        "type": im.get("type", "image"),
        "nsfw": im.get("nsfwLevel"),
        "width": im.get("width"),
        "height": im.get("height"),
        "prompt": meta.get("prompt") or "",
        "negative": meta.get("negativePrompt") or "",
        "sampler": meta.get("sampler") or comfy.get("sampler") or "",
        "scheduler": meta.get("Schedule type") or meta.get("scheduler") or comfy.get("scheduler") or "",
        "cfg": meta.get("cfgScale", comfy.get("cfg")),
        "steps": meta.get("steps", comfy.get("steps")),
        "seed": meta.get("seed"),
        "model": meta.get("Model") or "",
        "clip_skip": meta.get("clipSkip"),
    }


def _summarise(images):
    """Most-used sampler / cfg / steps across the example images."""
    def top(key):
        tally = {}
        for im in images:
            v = im.get(key)
            if v not in (None, ""):
                tally[v] = tally.get(v, 0) + 1
        return sorted(tally.items(), key=lambda x: -x[1])
    out = {}
    for key in ("sampler", "scheduler", "cfg", "steps"):
        t = top(key)
        out[key] = t[0][0] if t else None
        out[key + "_all"] = [v for v, _ in t[:4]]
    return out


def _fp_from_versions(version):
    for f in version.get("files", []) or []:
        fp = (f.get("metadata") or {}).get("fp")
        if fp:
            return str(fp)
    return ""


def fetch(lora_path, api_key=None, force=False):
    side = load_sidecar(lora_path) or {}
    if side.get("civitai") and not force:
        return side["civitai"]
    got = file_sha256(lora_path)
    if isinstance(got, tuple):
        sha, sig = got
    else:
        sha, sig = got, side.get("hash_sig")
    try:
        ver = _get_json(f"{API}/model-versions/by-hash/{sha}", api_key)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            side.update(sha256=sha, hash_sig=sig, civitai={"found": False, "fetched_at": int(time.time())})
            _write(lora_path, side)
            return side["civitai"]
        raise
    model = {}
    try:
        model = _get_json(f"{API}/models/{ver.get('modelId')}", api_key)
    except Exception:
        pass
    images = [_norm_image(i) for i in (ver.get("images") or [])]
    still = [i for i in images if i["type"] == "image"]
    data = {
        "found": True,
        "fetched_at": int(time.time()),
        "model_id": ver.get("modelId"),
        "version_id": ver.get("id"),
        "model_name": (ver.get("model") or {}).get("name") or model.get("name") or "",
        "version_name": ver.get("name") or "",
        "creator": (model.get("creator") or {}).get("username", ""),
        "page_url": f"https://civitai.com/models/{ver.get('modelId')}?modelVersionId={ver.get('id')}",
        "model_description": html_to_text(model.get("description")),
        "version_description": html_to_text(ver.get("description")),
        "tags": model.get("tags") or [],
        "trained_words": [w for w in (ver.get("trainedWords") or []) if str(w).strip()],
        "base_model": ver.get("baseModel") or "",
        "published_at": ver.get("publishedAt") or "",
        "fp": _fp_from_versions(ver),
        "images": images,
        "gen": _summarise(still),
        "video_count": len(images) - len(still),
    }
    side.update(sha256=sha, hash_sig=sig, civitai=data)
    _write(lora_path, side)
    return data


def _write(lora_path, side):
    with open(sidecar_path(lora_path), "w", encoding="utf8") as f:
        json.dump(side, f, indent=1)


def _ext(url):
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    return IMG_EXTS.get(ext, ".jpeg")


def ensure_preview(lora_path, data):
    """If the LoRA has no preview image yet, save the first CivitAI still as <name>.preview.<ext>."""
    base = os.path.splitext(lora_path)[0]
    for suf in (".preview.png", ".preview.jpeg", ".preview.jpg", ".preview.webp", ".png", ".jpeg", ".jpg", ".webp"):
        if os.path.isfile(base + suf):
            return False
    for im in data.get("images", []):
        if im.get("type") == "image" and im.get("url"):
            try:
                blob = _get(im["url"], timeout=40)
                with open(base + ".preview" + _ext(im["url"]), "wb") as f:
                    f.write(blob)
                return True
            except Exception:
                continue
    return False


def download_previews(lora_path, data, limit=60):
    """Save every example image and its prompt as <name>.previews/NN.jpeg + NN.txt (+ NN.json params)."""
    folder = os.path.splitext(lora_path)[0] + ".previews"
    os.makedirs(folder, exist_ok=True)
    saved, failed = 0, 0
    for i, im in enumerate([x for x in data.get("images", []) if x.get("type") == "image"][:limit], 1):
        stem = os.path.join(folder, f"{i:02d}")
        try:
            blob = _get(im["url"], timeout=40)
            with open(stem + _ext(im["url"]), "wb") as f:
                f.write(blob)
            with open(stem + ".txt", "w", encoding="utf8") as f:
                f.write(im.get("prompt", ""))
            params = {k: im.get(k) for k in ("negative", "sampler", "scheduler", "cfg", "steps", "seed", "model", "width", "height")}
            with open(stem + ".json", "w", encoding="utf8") as f:
                json.dump(params, f, indent=1)
            saved += 1
        except Exception:
            failed += 1
    return {"folder": folder, "saved": saved, "failed": failed}
