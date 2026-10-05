# Model advice for the Violet loaders: from the file alone (safetensors header / GGUF header / name / CivitAI
# example data) decide what kind of file it is, what it still needs (VAE, text encoder, CLIP type) and what
# sampler settings to start from. No torch, no model load. Fresh Violet code.

import os
import re
import json
import struct

from . import lora_catalog as lc
from . import civitai

_cache = {}

# arch -> label, CLIP loader type, sampler defaults, name hints for the VAE / text encoders that fit it
ARCHS = {
    "sd15": dict(label="SD 1.5", clip_type="stable_diffusion", sampler="euler_ancestral", scheduler="normal", steps=25, cfg=7.0,
                 vae=["vae-ft-mse", "sd15", "sd1"], te=["clip_l"], te_note="CLIP-L (inside a full checkpoint)"),
    "sdxl": dict(label="SDXL / Pony / Illustrious", clip_type="stable_diffusion", sampler="dpmpp_2m", scheduler="karras", steps=30, cfg=6.0,
                 vae=["sdxl_vae", "sdxl"], te=["clip_l", "clip_g"], te_note="CLIP-L + CLIP-G (inside a full checkpoint)"),
    "sd3": dict(label="Stable Diffusion 3.x", clip_type="sd3", sampler="dpmpp_2m", scheduler="sgm_uniform", steps=28, cfg=4.5,
                vae=["sd3", "ae"], te=["clip_l", "clip_g", "t5xxl"], te_note="CLIP-L + CLIP-G + T5-XXL (Triple CLIP)"),
    "flux": dict(label="FLUX.1", clip_type="flux", sampler="euler", scheduler="simple", steps=20, cfg=1.0,
                 vae=["ae.safetensors", "flux", "ae"], te=["clip_l", "t5xxl"], te_note="CLIP-L + T5-XXL (Dual CLIP, type flux); use FluxGuidance ~3.5",),
    "z_image": dict(label="Z-Image / Turbo", clip_type="lumina2", sampler="res_multistep", scheduler="simple", steps=8, cfg=1.0,
                    vae=["ae.safetensors", "flux", "ae"], te=["qwen3_4b", "qwen_3_4b", "qwen3-4b"], te_note="Qwen3-4B text encoder (CLIP type lumina2)"),
    "krea2": dict(label="Krea 2 / Turbo", clip_type="qwen_image", sampler="euler", scheduler="simple", steps=8, cfg=1.0,
                  vae=["krea", "qwen_image_vae", "ae"], te=["krea"], te_note="Krea 2 / Qwen3-VL text encoder"),
    "ernie_image": dict(label="ERNIE-Image", clip_type="stable_diffusion", sampler="euler", scheduler="simple", steps=8, cfg=3.5,
                        vae=["ernie", "ae"], te=["ernie"], te_note="ERNIE text encoder"),
    "qwen_image": dict(label="Qwen-Image", clip_type="qwen_image", sampler="euler", scheduler="simple", steps=25, cfg=1.0,
                       vae=["qwen_image_vae", "qwen_image"], te=["qwen_2.5_vl", "qwen2.5_vl", "qwen3vl", "qwen_image"], te_note="Qwen2.5-VL / Qwen3-VL text encoder (CLIP type qwen_image)"),
    "ming_image": dict(label="Ming-Image", clip_type="lumina2", sampler="euler", scheduler="simple", steps=12, cfg=1.0,
                       vae=["ae.safetensors", "ae"], te=["ming"], te_note="Ming text encoder (CLIP type lumina2)"),
    "wan": dict(label="Wan video", clip_type="wan", sampler="euler", scheduler="simple", steps=20, cfg=5.0,
                vae=["wan"], te=["umt5"], te_note="UMT5-XXL text encoder (CLIP type wan)"),
    "ltx": dict(label="LTX video", clip_type="ltxv", sampler="euler", scheduler="normal", steps=30, cfg=3.0,
                vae=["ltx"], te=["t5xxl", "gemma"], te_note="T5-XXL / Gemma text encoder (CLIP type ltxv)"),
}
NAME_ARCH = [(r"qwen[-_ ]?image", "qwen_image"), (r"ming[-_ ]?image", "ming_image"), (r"z[-_ ]?image", "z_image"),
             (r"krea", "krea2"), (r"ernie", "ernie_image"), (r"flux", "flux"), (r"sd3|stable[-_ ]?diffusion[-_ ]?3", "sd3"),
             (r"sdxl|pony|illustrious|noobai", "sdxl"), (r"wan[-_ ]?2|wan2|wan_", "wan"), (r"ltx", "ltx"), (r"sd[-_ ]?1[._]?5", "sd15")]
FAST = re.compile(r"turbo|lightning|lcm|hyper|distill|schnell|\b4step|\b8step|_4s|_8s", re.I)


# ---------------- header reading ----------------

def _gguf_meta(path):
    """general.architecture and friends from a GGUF header (first few scalar/string KVs)."""
    out = {}
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return out
            f.read(4)
            f.read(8)
            (kvn,) = struct.unpack("<Q", f.read(8))
            sizes = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
            for _ in range(min(kvn, 12)):
                (kl,) = struct.unpack("<Q", f.read(8))
                key = f.read(kl).decode("utf8", "replace")
                (t,) = struct.unpack("<I", f.read(4))
                if t == 8:
                    (sl,) = struct.unpack("<Q", f.read(8))
                    out[key] = f.read(min(sl, 256)).decode("utf8", "replace")
                    f.seek(max(0, sl - 256), 1)
                elif t in sizes:
                    f.read(sizes[t])
                else:
                    break
    except Exception:
        pass
    return out


def _classify(path):
    """-> (kind, keys, meta). kind: gguf | aio | diffusion."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gguf":
        return "gguf", [], _gguf_meta(path)
    header = lc._read_header(path) if ext in (".safetensors", ".sft") else {}
    keys = [k for k in header if k != "__metadata__"]
    meta = header.get("__metadata__", {}) or {}
    has_vae = any(k.startswith(("first_stage_model.", "vae.")) or ".first_stage_model." in k for k in keys)
    has_clip = any(k.startswith(("text_encoders.", "cond_stage_model.", "conditioner.", "text_model.", "clip_l.", "clip_g.", "t5xxl."))
                   or k.startswith("model.text_model") for k in keys)
    kind = "aio" if (has_vae or has_clip) else "diffusion"
    return kind, keys, {**meta, "_has_vae": has_vae, "_has_clip": has_clip}


def _top(keys):
    out = set()
    for k in keys:
        for p in ("model.diffusion_model.", "diffusion_model.", "model."):
            if k.startswith(p):
                k = k[len(p):]
                break
        out.add(k.split(".")[0])
    return out


def _arch_from_keys(keys):
    top = _top(keys)
    joined = " ".join(keys[:1500])
    if {"txtfusion", "tproj"} <= top:
        return "krea2"
    if {"text_proj", "final_linear"} <= top:
        return "ernie_image"
    if {"noise_refiner", "context_refiner"} <= top:
        return "z_image"
    if {"double_blocks", "single_blocks"} <= top:
        return "flux"
    if "joint_blocks" in top:
        return "sd3"
    if "patch_embedding" in top and "blocks" in top and "head" in top:
        return "wan"
    if "adaln_single" in top or "caption_projection" in top:
        return "ltx"
    if {"input_blocks", "output_blocks"} <= top:
        if "conditioner.embedders.1" in joined or "cond_stage_model.1" in joined or "clip_g" in joined:
            return "sdxl"
        if "cond_stage_model.transformer.text_model" in joined:
            return "sd15"
        return "sdxl"
    if {"img_in", "txt_in", "transformer_blocks", "proj_out"} <= top:
        return "qwen_image"
    return None


def _arch_from_name(text):
    for rx, a in NAME_ARCH:
        if re.search(rx, text, re.I):
            return a
    return None


def _installed(kind, hints, limit=3):
    from . import model_catalog as mc
    hits = []
    for m in mc.list_models(kind):
        n = m["name"].lower()
        score = sum(1 for h in hints if h.lower() in n)
        if score:
            hits.append((score, m["id"]))
    hits.sort(key=lambda x: -x[0])
    return [i for _, i in hits[:limit]]


# ---------------- public ----------------

def advise(mid):
    from . import model_catalog as mc
    path = mc.full_path(mid)
    if not path or not os.path.isfile(path):
        return None
    sig = (path, os.path.getmtime(path))
    hit = _cache.get(mid)
    if hit and hit[0] == sig:
        return hit[1]
    kind, keys, meta = _classify(path)
    name = os.path.basename(path)
    arch = None
    if keys:
        arch = _arch_from_keys(keys)
    if not arch:
        arch = _arch_from_name(name + " " + str(meta.get("general.architecture", "")) + " " + str(meta.get("modelspec.architecture", "")))
    if not arch and meta.get("general.architecture"):
        arch = _arch_from_name(str(meta["general.architecture"]))
    a = ARCHS.get(arch or "", None)

    has_vae = bool(meta.get("_has_vae"))
    has_clip = bool(meta.get("_has_clip"))
    needs_vae = kind != "aio" or not has_vae
    needs_clip = kind != "aio" or not has_clip
    vae_sug = _installed("vae", a["vae"]) if (a and needs_vae) else []
    clip_sug = _installed("text_encoders", a["te"]) if (a and needs_clip) else []

    sampler = None
    if a:
        sampler = dict(sampler=a["sampler"], scheduler=a["scheduler"], steps=a["steps"], cfg=a["cfg"], source=a["label"] + " defaults")
        if FAST.search(name) and arch in ("sdxl", "sd15", "sd3", "flux"):
            sampler.update(steps=8 if arch != "flux" else 4, cfg=1.5 if arch in ("sdxl", "sd15") else 1.0, source="fast/distilled name")
        elif FAST.search(name):
            sampler.update(cfg=1.0, source=a["label"] + " defaults, distilled name")
    civ = mc._civitai_gen(path)
    if civ:
        sampler = dict(sampler or {}, **civ, source="CivitAI example images")

    lines = []
    kind_label = {"gguf": "GGUF quant", "aio": "All-in-one checkpoint", "diffusion": "Diffusion model only (no VAE, no text encoder)"}[kind]
    lines.append(f"Type: {kind_label}" + (f" · {a['label']}" if a else " · architecture not recognised"))
    if kind == "aio":
        parts = [("VAE", has_vae), ("text encoder", has_clip)]
        missing = [n for n, ok in parts if not ok]
        lines.append("Carries " + " and ".join(n for n, ok in parts if ok) + " inside." if not missing else
                     "Carries " + (" and ".join(n for n, ok in parts if ok) or "the denoiser only") + "; missing " + " and ".join(missing) + ".")
    if needs_vae:
        lines.append("VAE: connect a Load VAE node (or pick vae_name here)" + (f" – installed match: {rel(vae_sug[0])}" if vae_sug else "") + ".")
    else:
        lines.append("VAE: included, nothing to connect.")
    if needs_clip:
        lines.append("Text encoder: connect a text encoder / CLIP loader (or pick clip_name here)" +
                     (f" – {a['te_note']}" if a else "") + (f"; installed match: {rel(clip_sug[0])}" if clip_sug else "") +
                     (f"; CLIP type '{a['clip_type']}'" if a else "") + ".")
    else:
        lines.append("Text encoder: included, nothing to connect.")
    if sampler:
        lines.append(f"Suggested: {sampler['sampler']} / {sampler['scheduler']}, {sampler['steps']} steps, CFG {sampler['cfg']}  ({sampler['source']})")
    out = {"id": mid, "kind": kind, "arch": arch, "arch_label": a["label"] if a else "", "has_vae": has_vae, "has_clip": has_clip,
           "needs_vae": needs_vae, "needs_clip": needs_clip, "clip_type": a["clip_type"] if a else "", "vae_suggestions": vae_sug,
           "clip_suggestions": clip_sug, "sampler": sampler, "lines": lines, "text": "\n".join(lines)}
    _cache[mid] = (sig, out)
    return out


def rel(mid):
    return mid.split("::", 1)[-1]
