# Library duplicate finder for the Violet LoRA loader. Nothing is deleted:
# it groups likely-same LoRAs, recommends which to keep, and can move the rest to a
# reversible _violet_duplicates folder.

import os
import re
import json
import shutil
import hashlib

from . import lora_catalog as lc

try:
    import folder_paths
except ImportError:
    folder_paths = None

_VERSION_RE = re.compile(r"(?:^|[\s_\-.])v(?:er(?:sion)?)?[\s_\-.]?(\d+(?:[._]\d+)*)(?=$|[\s_\-.])", re.I)
_NOISE = re.compile(
    r"(?:^|[\s_\-.])(?:v(?:er(?:sion)?)?[\s_\-.]?\d+(?:[._]\d+)*|epoch[\s_\-.]?\d+|e\d{1,3}|\d{6,9}|"
    r"fp(?:8|16|32)|bf16|f16|f32|fp8|final|pruned|converted|diffusers|comfy(?:ui)?|"
    r"rank[\s_\-.]?\d+|r\d{1,4}|dim[\s_\-.]?\d+|step[s]?[\s_\-.]?\d+|copy|\(\d+\))(?=$|[\s_\-.])", re.I)


def family_key(filename):
    """Name stripped of version/epoch/precision/rank tokens so V1/V2/fp16 variants collapse together."""
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    prev = None
    while prev != stem:
        prev = stem
        stem = _NOISE.sub(" ", stem)
    return re.sub(r"[^a-z0-9]+", "", stem)


def version_number(filename, civ_version_name=""):
    for text in (civ_version_name or "", os.path.splitext(os.path.basename(filename))[0]):
        m = _VERSION_RE.search(text)
        if m:
            try:
                return tuple(int(x) for x in re.split(r"[._]", m.group(1)))
            except ValueError:
                pass
    return None


_fp_cache = None


def _fp_file():
    return os.path.join(os.path.dirname(lc._config_path()), "fingerprints.json")


def _fp_load():
    global _fp_cache
    if _fp_cache is None:
        try:
            with open(_fp_file(), "r", encoding="utf8") as f:
                _fp_cache = json.load(f)
        except Exception:
            _fp_cache = {}
    return _fp_cache


def _fp_save():
    try:
        with open(_fp_file(), "w", encoding="utf8") as f:
            json.dump(_fp_cache or {}, f)
    except Exception:
        pass


def _header_fingerprint(path):
    """Content fingerprint: size + samples from the start, middle and end of the weights.
    (Header alone is not enough: LoRAs of the same rank share identical headers.)
    Remembered per file (path, size, modified time) so a second scan of a big library takes seconds, not minutes."""
    st = os.stat(path)
    key = f"{os.path.normcase(path)}|{st.st_size}|{int(st.st_mtime)}"
    cache = _fp_load()
    if key in cache:
        return cache[key]
    size = st.st_size
    h = hashlib.md5(str(size).encode())
    with open(path, "rb") as f:
        for pos in (0, size // 3, (2 * size) // 3, max(0, size - (1 << 20))):
            f.seek(pos)
            h.update(f.read(1 << 20))
    cache[key] = h.hexdigest()
    return cache[key]


def _path(name, kind):
    if kind:
        from . import model_catalog as mc
        return mc.full_path(name)
    return folder_paths.get_full_path("loras", name)


def _info(name, kind):
    if kind:
        from . import model_catalog as mc
        return mc.info(name) or {}
    return lc.lora_info(name) or {}


def _rec(name, kind=None):
    path = _path(name, kind)
    info = _info(name, kind)
    civ = info.get("civitai", {}) or {}
    st = os.stat(path)
    return {
        "name": name, "path": path, "size": st.st_size, "mtime": st.st_mtime,
        "model_id": str(civ.get("model_id") or "") or None,
        "version_id": str(civ.get("version_id") or "") or None,
        "version_name": civ.get("version_name") or "",
        "model_name": civ.get("model_name") or "",
        "published": civ.get("published_at") or "",
        "base_model": info.get("base_model", ""),
        "precision": info.get("precision", ""),
        "version_num": version_number(name, civ.get("version_name", "")),
        "family": family_key(name),
        "fp": _header_fingerprint(path) if path.lower().endswith((".safetensors", ".gguf", ".sft", ".ckpt")) else None,
    }


def _order_key(r):
    # newest first: publish date, then explicit version number, then file date
    return (r["published"] or "", r["version_num"] or (), r["mtime"])


def find(names=None, kind=None):
    """kind=None scans LoRAs; a model_catalog kind ("checkpoints", "diffusion", ...) scans those models (names are ids)."""
    if not names:
        if kind:
            from . import model_catalog as mc
            names = [m["id"] for m in mc.list_models(kind)]
        else:
            names = folder_paths.get_filename_list("loras") if folder_paths else []
    recs = []
    for n in names:
        try:
            recs.append(_rec(n, kind))
        except Exception:
            continue

    parent = list(range(len(recs)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[root(a)] = root(b)

    reasons = {}
    buckets = {}
    for i, r in enumerate(recs):
        for kind, key in (("identical file", r["fp"]),
                          ("same CivitAI model", ("m", r["model_id"], (r["base_model"] or "").lower()) if r["model_id"] else None),
                          ("similar name", ("f", r["family"], r["base_model"] or "") if len(r["family"]) >= 4 else None)):
            if key:
                buckets.setdefault((kind, key), []).append(i)
    for (kind, _), idxs in buckets.items():
        if len(idxs) > 1:
            for j in idxs[1:]:
                union(idxs[0], j)
            for j in idxs:
                reasons.setdefault(j, set()).add(kind)

    groups = {}
    for i in range(len(recs)):
        groups.setdefault(root(i), []).append(i)

    out, reclaim = [], 0
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        members = sorted((recs[i] for i in idxs), key=_order_key, reverse=True)
        kinds = set().union(*[reasons.get(i, set()) for i in idxs])
        identical = len({m["fp"] for m in members if m["fp"]}) == 1 and all(m["fp"] for m in members)
        strong = "same CivitAI model" in kinds or identical
        keep = members[0]
        rows = []
        for m in members:
            if m is keep:
                verdict = "keep"
            elif identical or m["fp"] == keep["fp"]:
                verdict = "remove"
            elif strong:
                verdict = "remove"
            else:
                verdict = "review"
            newer = m["published"] and keep["published"] and m["published"] < keep["published"]
            rows.append({
                "name": m["name"], "where": os.path.dirname(m["path"]), "size": m["size"], "version": m["version_name"] or (
                    "v" + ".".join(map(str, m["version_num"])) if m["version_num"] else ""),
                "published": m["published"][:10], "base_model": m["base_model"], "precision": m["precision"],
                "verdict": verdict,
                "note": ("identical file" if m["fp"] == keep["fp"] and m is not keep else
                         "older release of the same model" if strong and newer else
                         "same model, superseded" if strong and m is not keep else
                         "name looks the same, not confirmed" if m is not keep else "newest"),
            })
            if verdict == "remove":
                reclaim += m["size"]
        reason = ("Identical files" if identical else
                  "Same CivitAI model, different versions" if "same CivitAI model" in kinds else
                  "Names match after stripping version, epoch and precision tags")
        out.append({"reason": reason, "confidence": "high" if strong else "medium",
                    "family": members[0]["family"], "members": rows})
    out.sort(key=lambda g: (g["confidence"] != "high", g["family"]))
    _fp_save()
    return {"groups": out, "scanned": len(recs), "reclaimable_bytes": reclaim}


def quarantine(names, kind=None):
    """Move LoRAs (plus previews/sidecars) into <its folder>/_violet_duplicates. Reversible."""
    moved = []
    for n in names:
        path = _path(n, kind)
        if not path or not os.path.isfile(path):
            continue
        folder = os.path.join(os.path.dirname(path), "_violet_duplicates")
        os.makedirs(folder, exist_ok=True)
        stem = os.path.splitext(path)[0]
        extras = (".cminfo.json", ".metadata.json", ".violet.json", ".civitai.info", ".info", ".json",
                  ".preview.png", ".preview.jpeg", ".preview.jpg", ".preview.webp", ".png", ".jpeg", ".jpg",
                  ".webp", ".mp4", ".previews")
        for full in [path] + [stem + x for x in extras]:
            if os.path.exists(full):
                shutil.move(full, os.path.join(folder, os.path.basename(full)))
        moved.append(n)
    lc._invalidate()
    if kind:
        from . import model_catalog as mc
        mc._cache.clear()
    return moved
