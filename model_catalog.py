# Model catalog for the Violet Model Browser: checkpoints, diffusion models, GGUF, VAE and text encoders
# found in every folder ComfyUI knows about (plus runtime-editable extra folders).
# Ids are "<folder_key>::<relative name>". Fresh Violet code; shares civitai.py with the LoRA loader.

import os
import re
import json

from . import lora_catalog as lc
from . import civitai

try:
    import folder_paths
except ImportError:
    folder_paths = None

# kind -> ComfyUI folder keys that can hold it
KINDS = {
    "loras": ["loras"],
    "checkpoints": ["checkpoints"],
    "diffusion": ["diffusion_models", "unet"],
    "gguf": ["unet_gguf", "diffusion_models", "unet"],
    "text_encoders": ["text_encoders", "clip"],
    "vae": ["vae"],
}
KIND_LABEL = {"loras": "LoRAs", "checkpoints": "Checkpoints", "diffusion": "Diffusion models", "gguf": "GGUF",
              "text_encoders": "Text encoders", "vae": "VAE"}
EXTS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".sft")
GENERIC_EXTS = EXTS + (".onnx", ".yaml", ".yml")
# Every other ComfyUI model folder (controlnet, clip_vision, upscale_models, ...) becomes a category of its own, added by sync_kinds().
# These are not models: folders ComfyUI keeps for nodes and datasets.
_NOT_MODELS = {"custom_nodes", "datasets", "model_paths"}
_QUANT = re.compile(r"(?:^|[\s_\-.])((?:i?q\d(?:_[a-z0-9]+)*)|f16|f32|bf16|fp8|fp16|fp32|nvfp4|mxfp8)(?=$|[\s_\-.])", re.I)

_cache = {}


_PRIMARY_KINDS = tuple(KINDS)
_PRIMARY_KEYS = {k for ks in KINDS.values() for k in ks}


def sync_kinds():
    """Add every ComfyUI folder name (including ones other node packs register) as its own category. True when new ones appeared."""
    if folder_paths is None:
        return False
    new = False
    for key in sorted(folder_paths.folder_names_and_paths):
        if key in KINDS or key in _PRIMARY_KEYS or key in _NOT_MODELS:
            continue
        KINDS[key] = [key]
        KIND_LABEL[key] = key
        new = True
    return new


def _folders(kind):
    if folder_paths is None:
        return []
    return [k for k in KINDS.get(kind, []) if k in folder_paths.folder_names_and_paths]


def _kind_of(kind, name):
    if kind not in _PRIMARY_KINDS:
        return True
    is_gguf = name.lower().endswith(".gguf")
    if kind == "gguf":
        return is_gguf
    if kind == "diffusion":
        return not is_gguf
    if kind == "text_encoders":
        return True
    return not is_gguf or kind == "text_encoders"


def _split(mid):
    folder, _, name = mid.partition("::")
    return folder, name


def full_path(mid):
    folder, name = _split(mid)
    if folder_paths is None or not name:
        return None
    return folder_paths.get_full_path(folder, name)


def _extra_dirs_cfg():
    d = lc.load_config().get("model_dirs", {})
    return d if isinstance(d, dict) else {}


def apply_dirs():
    """Append each kind's extra folders to ComfyUI's global folder lists (loaders see them at once)."""
    if folder_paths is None:
        return
    sync_kinds()
    for kind, dirs in _extra_dirs_cfg().items():
        if kind == "loras":  # LoRA folders have their own editor (lora_catalog)
            continue
        for key in _folders(kind)[:1]:
            lst = folder_paths.folder_names_and_paths[key][0]
            for d in dirs:
                n = lc._norm(d)
                if os.path.isdir(n) and n.lower() not in [x.lower() for x in lst]:
                    lst.append(n)
            folder_paths.filename_list_cache.pop(key, None)
    _cache.clear()


def get_dirs():
    sync_kinds()
    return {"model_dirs": {k: list(v) for k, v in _extra_dirs_cfg().items()},
            "kinds": {k: v for k, v in KIND_LABEL.items() if k != "loras"}}


def save_dirs(body):
    sync_kinds()
    clean = {}
    for kind, dirs in (body or {}).items():
        if kind in KINDS and kind != "loras" and isinstance(dirs, list):
            clean[kind] = [lc._norm(d) for d in dirs if str(d).strip()]
    cfg = lc.load_config()
    cfg["model_dirs"] = clean
    with open(lc._config_path(), "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=2)
    apply_dirs()
    return get_dirs()


def _preview_of(path):
    base = os.path.splitext(path)[0]
    for suf in lc.PREVIEW_SUFFIXES:
        if os.path.isfile(base + suf):
            return base + suf
    return None


def _quant_from_name(name):
    m = _QUANT.search(os.path.splitext(os.path.basename(name))[0])
    return m.group(1).upper() if m else ""


def _arch_guess(header):
    """Cheap architecture hint from tensor names when no metadata says so."""
    md = header.get("__metadata__", {}) or {}
    for k in ("modelspec.architecture", "modelspec.title", "architecture"):
        if md.get(k):
            return str(md[k])
    keys = [k for k in header if k != "__metadata__"][:4000]
    joined = " ".join(keys[:800])
    for needle, label in (("double_blocks", "Flux-style DiT"), ("joint_blocks", "SD3-style MMDiT"),
                          ("transformer_blocks", "DiT"), ("input_blocks", "SDXL/SD1 UNet"),
                          ("model.diffusion_model", "Checkpoint (UNet+VAE+CLIP)")):
        if needle in joined or any(needle in k for k in keys):
            return label
    return ""


def info(mid):
    path = full_path(mid)
    if not path or not os.path.isfile(path):
        return None
    st = os.stat(path)
    hit = _cache.get(mid)
    if hit and hit[0] == st.st_mtime and hit[1] == path:
        return hit[2]
    header = lc._read_header(path) if path.lower().endswith((".safetensors", ".sft")) else {}
    precision = lc._precision(header) if header else ""
    if not precision:
        precision = _quant_from_name(path)
    base = os.path.splitext(path)[0]
    civ = lc._civitai_view(path, base)
    md = header.get("__metadata__", {}) or {}
    side = civitai.load_sidecar(path) or {}
    folder, name = _split(mid)
    prev = _preview_of(path)
    out = {
        "id": mid, "name": name, "folder": folder, "alias": side.get("alias") or "", "size": st.st_size,
        "ext": os.path.splitext(path)[1].lower(), "precision": precision or (civ.get("fp") or "").upper(),
        "base_model": civ.get("base_model") or md.get("modelspec.architecture") or _arch_guess(header),
        "title": md.get("modelspec.title") or "", "civitai": civ, "has_fetch": bool(civ.get("fetched")),
        "trigger_words": lc._dedupe(civ.get("trained_words", [])),
        "preview": (f"/violet/model_preview?id={lc._q(mid)}&t={int(os.path.getmtime(prev))}" if prev else None),
        "path": path,
    }
    if folder == "loras":
        # LoRAs carry more than other models (trigger words from sidecars and training metadata): use the LoRA catalog's read of them
        try:
            li = lc.lora_info(name) or {}
            out["trigger_words"] = li.get("trigger_words") or out["trigger_words"]
            out["base_model"] = li.get("base_model") or out["base_model"]
            out["precision"] = li.get("precision") or out["precision"]
        except Exception:
            pass
    _cache[mid] = (st.st_mtime, path, out)
    return out


def list_models(kind):
    sync_kinds()
    if folder_paths is None or kind not in KINDS:
        return []
    exts = EXTS if kind in _PRIMARY_KINDS else GENERIC_EXTS
    seen, out = set(), []
    for key in _folders(kind):
        for name in folder_paths.get_filename_list(key):
            if not name.lower().endswith(exts) or not _kind_of(kind, name) or "_violet_duplicates" in name:
                continue
            path = folder_paths.get_full_path(key, name)
            real = os.path.normcase(os.path.realpath(path)) if path else None
            if not real or real in seen:
                continue
            seen.add(real)
            i = info(f"{key}::{name}")
            if i:
                out.append(i)
    out.sort(key=lambda x: (x["alias"] or x["name"]).lower())
    return out


def _count_names(kind):
    """File count without reading headers: the folder categories can hold thousands of files and a count is all the tab needs."""
    n = 0
    for key in _folders(kind):
        n += sum(1 for name in folder_paths.get_filename_list(key) if name.lower().endswith(GENERIC_EXTS) and "_violet_duplicates" not in name)
    return n


def counts():
    if sync_kinds():
        apply_dirs()  # a pack registered a folder after startup: its extra folders apply now
    return {k: (len(list_models(k)) if k in _PRIMARY_KINDS else _count_names(k)) for k in list(KINDS)}


def refresh(kind):
    """Rescan the disk for this kind: drop ComfyUI's cached file lists and our own info cache."""
    if folder_paths is not None:
        for key in _folders(kind):
            folder_paths.filename_list_cache.pop(key, None)
    if kind == "loras":
        lc._invalidate()
    _cache.clear()


def preview_file(mid):
    path = full_path(mid)
    return _preview_of(path) if path else None


def forget(mid):
    _cache.pop(mid, None)


# ---------------- rename ----------------

def set_alias(mid, alias):
    path = full_path(mid)
    if not path:
        raise ValueError("unknown model")
    side = civitai.load_sidecar(path) or {}
    if (alias or "").strip():
        side["alias"] = alias.strip()[:120]
    else:
        side.pop("alias", None)
    civitai._write(path, side)
    forget(mid)
    return info(mid)


def rename_file(mid, new_stem):
    path = full_path(mid)
    if not path:
        raise ValueError("unknown model")
    new_stem = (new_stem or "").strip()
    if not new_stem or any(c in lc._BAD for c in new_stem):
        raise ValueError("invalid file name")
    folder, name = _split(mid)
    ext = os.path.splitext(path)[1]
    new_path = os.path.join(os.path.dirname(path), new_stem + ext)
    if os.path.exists(new_path):
        raise ValueError("a file with that name already exists")
    os.rename(path, new_path)
    old_base, new_base = os.path.splitext(path)[0], os.path.splitext(new_path)[0]
    for suf in lc._COMPANION:
        if os.path.exists(old_base + suf):
            os.rename(old_base + suf, new_base + suf)
    prefix = name[: len(name) - len(os.path.basename(path))]
    if folder_paths is not None:
        folder_paths.filename_list_cache.pop(folder, None)
    forget(mid)
    return f"{folder}::{prefix}{new_stem}{ext}"


# ---------------- CivitAI example settings, as ComfyUI sampler names ----------------

_SAMPLERS = {"euler": "euler", "euler a": "euler_ancestral", "euler ancestral": "euler_ancestral", "heun": "heun", "lms": "lms",
             "dpm++ 2m": "dpmpp_2m", "dpm++ 2m karras": "dpmpp_2m", "dpm++ sde": "dpmpp_sde", "dpm++ 2m sde": "dpmpp_2m_sde",
             "dpm++ 3m sde": "dpmpp_3m_sde", "dpm++ 2s a": "dpmpp_2s_ancestral", "ddim": "ddim", "uni_pc": "uni_pc", "unipc": "uni_pc",
             "lcm": "lcm", "dpm2": "dpm_2", "dpm2 a": "dpm_2_ancestral"}


def _civitai_gen(path):
    g = ((civitai.load_sidecar(path) or {}).get("civitai") or {}).get("gen") or {}
    if not g or (g.get("sampler") is None and g.get("cfg") is None and g.get("steps") is None):
        return None
    out = {}
    if g.get("sampler"):
        raw = str(g["sampler"]).strip()
        out["sampler"] = _SAMPLERS.get(raw.lower(), raw.lower().replace(" ", "_").replace("+", "p"))
        if "karras" in raw.lower() and not g.get("scheduler"):
            out["scheduler"] = "karras"
    if g.get("scheduler"):
        out["scheduler"] = str(g["scheduler"]).lower().replace(" ", "_")
    if g.get("cfg") is not None:
        out["cfg"] = g["cfg"]
    if g.get("steps") is not None:
        out["steps"] = g["steps"]
    return out
