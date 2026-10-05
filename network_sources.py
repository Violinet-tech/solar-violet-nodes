# Network sources for the Violet Browser: read the model / LoRA lists of ComfyUI instances on OTHER computers
# (a second PC on the same network, or over a direct cable) and show them next to this PC's own. Uses only ComfyUI's stock
# /experiment/models API, so the other machine needs nothing installed. Browsing only: the files stay where they are.
# To actually load them, share their folder and add the UNC path in "Folders / settings", or run the graph over there.

import re
import json
import urllib.parse
import urllib.request

from . import lora_catalog as lc
from . import model_catalog as mc

DEFAULT_SOURCES = []  # each person adds their own other-computer ComfyUI addresses under Network
_QUANT = mc._QUANT


def sources():
    cfg = lc.load_config()
    return cfg.get("network_sources", DEFAULT_SOURCES)


def save_sources(items):
    cfg = lc.load_config()
    clean = []
    for s in items or []:
        name, url = str(s.get("name", "")).strip(), str(s.get("url", "")).strip().rstrip("/")
        if name and url.startswith(("http://", "https://")):
            clean.append({"name": name, "url": url})
    cfg["network_sources"] = clean
    with open(lc._config_path(), "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=2)
    return clean


def _url(name):
    for s in sources():
        if s["name"] == name:
            return s["url"]
    return None


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Violet"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def status():
    out = []
    for s in sources():
        try:
            body, _ = _get(s["url"] + "/system_stats", 4)
            d = json.loads(body)
            dev = (d.get("devices") or [{}])[0].get("name", "")
            out.append({**s, "up": True, "device": dev, "version": d.get("system", {}).get("comfyui_version", "")})
        except Exception as e:
            out.append({**s, "up": False, "error": str(e)[:120]})
    return out


def _entry(src, folder, m, kind):
    name = m["name"]
    base = re.split(r"[\\/]", name)[-1]
    quant = _QUANT.search(base.rsplit(".", 1)[0])
    mid = f"net:{src}::{folder}::{name}"
    q = urllib.parse.quote
    return {
        "id": mid, "name": base, "folder": folder, "alias": "", "size": m.get("size", 0),
        "ext": "." + base.rsplit(".", 1)[-1].lower() if "." in base else "",
        "precision": quant.group(1).upper() if quant else "", "base_model": "", "title": "", "civitai": {},
        "has_fetch": False, "trigger_words": [], "remote": True, "source": src, "rel": name,
        "path": f"{src}: {folder}/{name}",
        "preview": f"/violet/net/preview?src={q(src)}&folder={q(folder)}&name={q(name)}&pi={m.get('pathIndex', 0)}",
    }


def catalog(src, kind):
    base = _url(src)
    if not base or kind not in mc.KINDS:
        return []
    out, seen = [], set()
    for folder in mc.KINDS[kind]:
        try:
            body, _ = _get(f"{base}/experiment/models/{urllib.parse.quote(folder)}", 30)
            items = json.loads(body)
        except Exception:
            continue
        for m in items:
            name = m.get("name", "")
            if not name.lower().endswith(mc.EXTS) or not mc._kind_of(kind, name):
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(_entry(src, folder, m, kind))
    out.sort(key=lambda x: x["name"].lower())
    return out


def preview(src, folder, name, pi):
    base = _url(src)
    if not base:
        return None
    q = urllib.parse.quote
    try:
        return _get(f"{base}/experiment/models/preview/{q(folder)}/{int(pi)}/{q(name)}", 15)
    except Exception:
        return None
