# LoRA catalog for the Violet loader: extra directories (runtime-editable),
# trigger words, base model and preview lookup. Fresh Violet code.

import os
import json
import struct

try:
    import folder_paths
except ImportError:
    folder_paths = None

PACK_DIR = os.path.dirname(os.path.abspath(__file__))
LORA_EXTS = (".safetensors", ".pt", ".ckpt", ".bin")
PREVIEW_SUFFIXES = (".preview.png", ".preview.jpeg", ".preview.jpg", ".preview.webp",
                    ".png", ".jpeg", ".jpg", ".webp")
SIDECARS = (".cminfo.json", ".metadata.json", ".civitai.info", ".info", ".json")

_extra_dirs = []
_meta_cache = {}


def _config_path():
    base = PACK_DIR
    try:
        user = folder_paths.get_user_directory()
        base = os.path.join(user, "violet")
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base, "config.json")


def _norm(p):
    return os.path.normpath(os.path.expanduser(str(p).strip().strip('"')))


def _loras_list():
    return folder_paths.folder_names_and_paths["loras"][0]


def _invalidate():
    try:
        folder_paths.filename_list_cache.pop("loras", None)
    except Exception:
        pass
    _meta_cache.clear()


def apply_dirs(dirs):
    """Make ComfyUI's global `loras` folder list = its own dirs + `dirs`.
    Every LoRA loader node sees the result, no restart needed."""
    global _extra_dirs
    lst = _loras_list()
    for old in _extra_dirs:
        if old in lst:
            lst.remove(old)
    clean, seen = [], set()
    for d in dirs:
        n = _norm(d)
        if n and n.lower() not in seen and os.path.isdir(n):
            seen.add(n.lower())
            clean.append(n)
    for n in clean:
        if n not in lst and n.lower() not in [x.lower() for x in lst]:
            lst.append(n)
    _extra_dirs = [n for n in clean if n in lst]
    _invalidate()
    return list(_extra_dirs)


def load_config():
    try:
        with open(_config_path(), "r", encoding="utf8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_dirs(dirs):
    applied = apply_dirs(dirs)
    cfg = load_config()
    cfg["lora_dirs"] = [_norm(d) for d in dirs if str(d).strip()]
    with open(_config_path(), "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=2)
    return applied


def get_settings():
    cfg = load_config()
    saved = cfg.get("lora_dirs", [])
    return {
        "lora_dirs": saved,
        "missing": [d for d in saved if not os.path.isdir(_norm(d))],
        "builtin": [p for p in _loras_list() if p not in _extra_dirs],
    }


def init_from_config():
    if folder_paths is None:
        return
    apply_dirs(load_config().get("lora_dirs", []))


def _read_json(path):
    try:
        with open(path, "r", encoding="utf8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_header(path):
    try:
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            if n > 50_000_000:
                return {}
            return json.loads(f.read(n))
    except Exception:
        return {}


def _safetensors_header(path):
    return _read_header(path).get("__metadata__", {}) or {}


_DTYPE_LABEL = {"F32": "FP32", "F16": "FP16", "BF16": "BF16", "F64": "FP64", "F8_E4M3": "FP8", "F8_E5M2": "FP8",
                "I8": "INT8", "U8": "UINT8"}


def _precision(header):
    tally = {}
    for k, v in header.items():
        if k == "__metadata__" or not isinstance(v, dict):
            continue
        d = v.get("dtype")
        if d:
            try:
                shape = v.get("shape") or [1]
                n = 1
                for x in shape:
                    n *= int(x)
            except Exception:
                n = 1
            tally[d] = tally.get(d, 0) + n
    if not tally:
        return ""
    return _DTYPE_LABEL.get(max(tally.items(), key=lambda x: x[1])[0], max(tally.items(), key=lambda x: x[1])[0])


def _words(v):
    if isinstance(v, str):
        v = [x for x in v.replace("\n", ",").split(",")]
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()]


def _dedupe(words):
    seen, out = set(), []
    for w in words:
        k = w.lower()
        if k not in seen:
            seen.add(k)
            out.append(w)
    return out


def lora_info(name):
    path = folder_paths.get_full_path("loras", name) if folder_paths else None
    if not path or not os.path.isfile(path):
        return None
    mtime = os.path.getmtime(path)
    hit = _meta_cache.get(name)
    if hit and hit[0] == mtime and hit[1] == path:
        return hit[2]

    base = os.path.splitext(path)[0]
    words, base_model, preview = [], "", None

    for suf in SIDECARS:
        d = _read_json(base + suf)
        if not isinstance(d, dict):
            continue
        civ = d.get("civitai") if isinstance(d.get("civitai"), dict) else {}
        words += _words(d.get("TrainedWords")) + _words(d.get("trainedWords")) + _words(civ.get("trainedWords"))
        base_model = base_model or d.get("BaseModel") or d.get("base_model") or civ.get("baseModel") or ""
        if words and base_model:
            break

    if path.lower().endswith(".safetensors"):
        md = _safetensors_header(path)
        if not words:
            words += _words(md.get("modelspec.trigger_phrase"))
        if not words and md.get("ss_tag_frequency"):
            try:
                freq = json.loads(md["ss_tag_frequency"])
                tally = {}
                for ds in freq.values():
                    for t, c in ds.items():
                        tally[t] = tally.get(t, 0) + c
                words += [t.strip() for t, _ in sorted(tally.items(), key=lambda x: -x[1])[:5] if t.strip()]
            except Exception:
                pass
        base_model = base_model or md.get("ss_base_model_version") or md.get("modelspec.architecture") or ""

    for suf in PREVIEW_SUFFIXES:
        if os.path.isfile(base + suf):
            preview = f"/violet/preview?name={_q(name)}"
            break

    header = _read_header(path) if path.lower().endswith(".safetensors") else {}
    precision = _precision(header)
    civ = _civitai_view(path, base)
    if not precision and civ.get("fp"):
        precision = str(civ["fp"]).upper().replace("BF16", "BF16")
    words = words + [w for w in civ.get("trained_words", [])]
    base_model = base_model or civ.get("base_model", "")
    from . import civitai as _cv
    alias = ((_cv.load_sidecar(path) or {}).get("alias")) or ""
    info = {"name": name, "alias": alias, "trigger_words": _dedupe(words), "base_model": str(base_model), "preview": preview,
            "precision": precision, "civitai": civ, "size": os.path.getsize(path),
            "has_fetch": bool(civ.get("fetched"))}
    _meta_cache[name] = (mtime, path, info)
    return info


def _civitai_view(path, base):
    """Merge the .violet.json fetch result (preferred) with whatever the .cminfo.json already holds."""
    from . import civitai
    view = {}
    cm = _read_json(base + ".cminfo.json")
    if isinstance(cm, dict):
        view.update(
            model_id=cm.get("ModelId"), version_id=cm.get("VersionId"), model_name=cm.get("ModelName", ""),
            version_name=cm.get("VersionName", ""), creator=cm.get("CreatorUsername", ""),
            model_description=civitai.html_to_text(cm.get("ModelDescription")),
            version_description=civitai.html_to_text(cm.get("VersionDescription")),
            tags=cm.get("Tags") if isinstance(cm.get("Tags"), list) else [],
            base_model=cm.get("BaseModel", ""), published_at=cm.get("VersionPublishedAt", ""),
            fp=(cm.get("FileMetadata") or {}).get("fp", "") if isinstance(cm.get("FileMetadata"), dict) else "",
            trained_words=_words(cm.get("TrainedWords")),
            page_url=(f"https://civitai.com/models/{cm.get('ModelId')}" if cm.get("ModelId") else ""),
            images=[], gen={}, fetched=False)
    side = civitai.load_sidecar(path)
    if side and isinstance(side.get("civitai"), dict) and side["civitai"].get("found"):
        c = side["civitai"]
        for k, v in c.items():
            if v not in (None, "", [], {}):
                view[k] = v
        view["fetched"] = True
    return view


def _q(s):
    from urllib.parse import quote
    return quote(s, safe="")


def preview_file(name):
    path = folder_paths.get_full_path("loras", name) if folder_paths else None
    if not path:
        return None
    base = os.path.splitext(path)[0]
    for suf in PREVIEW_SUFFIXES:
        if os.path.isfile(base + suf):
            return base + suf
    return None


def list_loras():
    if folder_paths is None:
        return []
    out = []
    for name in folder_paths.get_filename_list("loras"):
        info = lora_info(name)
        if info:
            out.append(info)
    return out


# ---------------- rename / alias / ui ----------------

_COMPANION = (".cminfo.json", ".metadata.json", ".violet.json", ".civitai.info", ".info", ".json",
              ".preview.png", ".preview.jpeg", ".preview.jpg", ".preview.webp", ".png", ".jpeg", ".jpg",
              ".webp", ".mp4", ".previews")
_BAD = set('<>:"|?*/') | {chr(92)}


def set_alias(name, alias):
    """Display-only name shown inside Violet UIs; the file on disk is untouched."""
    from . import civitai
    path = folder_paths.get_full_path("loras", name)
    if not path:
        raise ValueError("unknown LoRA")
    side = civitai.load_sidecar(path) or {}
    alias = (alias or "").strip()
    if alias:
        side["alias"] = alias[:120]
    else:
        side.pop("alias", None)
    civitai._write(path, side)
    _meta_cache.pop(name, None)
    return lora_info(name)


def rename_file(name, new_stem):
    """Rename the LoRA file and every companion (preview, sidecars, .previews) to a new stem.
    Returns the new name relative to the LoRA root, e.g. 'General/New Name.safetensors'."""
    path = folder_paths.get_full_path("loras", name)
    if not path:
        raise ValueError("unknown LoRA")
    new_stem = (new_stem or "").strip()
    ext = os.path.splitext(path)[1]
    if new_stem.lower().endswith(ext.lower()):
        new_stem = new_stem[: -len(ext)]
    if not new_stem or any(c in _BAD for c in new_stem) or new_stem in (".", ".."):
        raise ValueError("That name has characters a file name can't contain.")
    folder = os.path.dirname(path)
    old_stem = os.path.splitext(os.path.basename(path))[0]
    dst = os.path.join(folder, new_stem + ext)
    if os.path.normcase(dst) != os.path.normcase(path) and os.path.exists(dst):
        raise ValueError("A file with that name already exists.")
    moves = [(path, dst)]
    for suf in _COMPANION:
        a, b = os.path.join(folder, old_stem + suf), os.path.join(folder, new_stem + suf)
        if os.path.exists(a):
            if os.path.exists(b) and os.path.normcase(a) != os.path.normcase(b):
                raise ValueError(f"'{new_stem + suf}' already exists next to it.")
            moves.append((a, b))
    for a, b in moves:
        os.replace(a, b)
    cm = os.path.join(folder, new_stem + ".cminfo.json")
    d = _read_json(cm)
    if isinstance(d, dict) and "PrimaryFileName" in d:
        d["PrimaryFileName"] = new_stem + ext
        with open(cm, "w", encoding="utf8") as f:
            json.dump(d, f, indent=2)
    _invalidate()
    # name relative to the registered root: reuse the same prefix as the original name
    prefix = name[: len(name) - len(os.path.basename(name))]
    return prefix + new_stem + ext


def get_ui():
    d = load_config().get("ui", {})
    return {"thumb": int(d.get("thumb", 40)), "font": int(d.get("font", 11)), "pad": int(d.get("pad", 5)),
            "show_tags": bool(d.get("show_tags", True)), "show_meta": bool(d.get("show_meta", True))}


def save_ui(body):
    cur = get_ui()
    for k, lo, hi in (("thumb", 20, 220), ("font", 8, 22), ("pad", 1, 20)):
        if k in body:
            cur[k] = max(lo, min(hi, int(body[k])))
    for k in ("show_tags", "show_meta"):
        if k in body:
            cur[k] = bool(body[k])
    cfg = load_config()
    cfg["ui"] = cur
    with open(_config_path(), "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=2)
    return cur
