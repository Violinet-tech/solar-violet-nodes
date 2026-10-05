# Model libraries: point ComfyUI at model folders that another program keeps (Stability Matrix, a shared drive,
# a plain folder) without moving, renaming or symlinking anything. Each configured library is a folder plus a
# layout ("stability" or "comfy"); the folders that exist inside it are added to ComfyUI's own search lists, so
# every loader, the Violet browsers and the stock nodes all see the files at once. Fresh Violet code.
#
# Config (user/violet config, key "libraries"):
#   [{"layout": "stability", "path": "D:\\Some\\Path\\Data\\Models"}, {"layout": "comfy", "path": "E:\\models"}]
# Nothing here is specific to one machine: Stability Matrix is looked for in its usual places, and the person can
# type a path if theirs is elsewhere.

import os
import sys
import json

from . import lora_catalog as lc

try:
    import folder_paths
except ImportError:
    folder_paths = None

# ComfyUI folder key -> sub-folder names inside a library. Stability Matrix's shared "Models" folder uses the first
# spelling of each; plain ComfyUI trees use the last. Only folders that exist are added.
STABILITY = {
    "checkpoints": ["StableDiffusion"],
    "loras": ["Lora", "LyCORIS"],
    "vae": ["VAE"],
    "vae_approx": ["ApproxVAE"],
    "text_encoders": ["TextEncoders", "CLIP"],
    "clip": ["CLIP", "TextEncoders"],
    "clip_vision": ["ClipVision"],
    "diffusion_models": ["DiffusionModels"],
    "unet": ["DiffusionModels"],
    "controlnet": ["ControlNet", "T2IAdapter"],
    "embeddings": ["Embeddings"],
    "hypernetworks": ["Hypernetwork"],
    "upscale_models": ["ESRGAN", "RealESRGAN", "SwinIR", "BSRGAN", "LDSR", "ScuNET"],
    "gligen": ["GLIGEN"],
    "diffusers": ["Diffusers"],
    "ipadapter": ["IpAdapter", "IpAdapters15", "IpAdaptersXl"],
    "style_models": ["StyleModels"],
    "model_patches": ["ModelPatches"],
    "sams": ["Sams"],
    "facerestore_models": ["GFPGAN", "Codeformer"],
    "ultralytics": ["Ultralytics"],
    "ultralytics_bbox": [os.path.join("Ultralytics", "bbox")],
    "ultralytics_segm": [os.path.join("Ultralytics", "segm")],
}
COMFY = {k: [k] for k in STABILITY}
COMFY.update({"text_encoders": ["text_encoders", "clip"], "clip": ["clip", "text_encoders"],
              "diffusion_models": ["diffusion_models", "unet"], "unet": ["unet", "diffusion_models"],
              "upscale_models": ["upscale_models"], "controlnet": ["controlnet", "t2i_adapter"],
              "ultralytics_bbox": [os.path.join("ultralytics", "bbox")],
              "ultralytics_segm": [os.path.join("ultralytics", "segm")]})
LAYOUTS = {"stability": STABILITY, "comfy": COMFY}
LABEL = {"stability": "Stability Matrix", "comfy": "ComfyUI-style folders"}


def _configured():
    got = lc.load_config().get("libraries", [])
    return [x for x in got if isinstance(x, dict) and x.get("path")] if isinstance(got, list) else []


def _models_dir(root):
    """The 'Models' folder for a Stability Matrix install rooted at `root` (portable or not), or None."""
    if not root:
        return None
    root = os.path.expandvars(os.path.expanduser(str(root).strip().strip('"')))
    for sub in ("", "Models", os.path.join("Data", "Models")):
        p = os.path.join(root, sub) if sub else root
        if os.path.isdir(os.path.join(p, "StableDiffusion")) or os.path.isdir(os.path.join(p, "Lora")):
            return os.path.normpath(p)
    return None


def detect_stability():
    """Stability Matrix installs found in their usual places. Never guesses beyond these."""
    home = os.path.expanduser("~")
    roots = [os.environ.get("STABILITY_MATRIX_HOME", "")]
    if sys.platform == "win32":
        roots += [os.path.join(os.environ.get("APPDATA", ""), "StabilityMatrix"),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "StabilityMatrix"),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Stability Matrix")]
    else:
        roots += [os.path.join(home, ".config", "StabilityMatrix"), os.path.join(home, "StabilityMatrix")]
    roots.append(os.path.join(home, "StabilityMatrix"))
    # a running ComfyUI that Stability Matrix started lives under <install>\Data\Packages\<name>
    try:
        base = os.path.abspath(getattr(folder_paths, "base_path", ""))
        marker = os.path.join("Data", "Packages")
        i = base.find(marker)
        if i > 0:
            roots.append(base[:i].rstrip("\\/"))
    except Exception:
        pass
    out, seen = [], set()
    for r in roots:
        m = _models_dir(r) if r else None
        if m and m.lower() not in seen:
            seen.add(m.lower())
            out.append(m)
    return out


def _existing(root, names):
    out = []
    for n in names:
        p = os.path.join(root, n)
        if os.path.isdir(p):
            out.append(os.path.normpath(p))
    return out


def preview(layout, path):
    """What a library would add: {folder key: [folders that exist]}."""
    table = LAYOUTS.get(layout)
    if not table or not path or not os.path.isdir(path):
        return {}
    return {k: v for k, v in ((k, _existing(path, names)) for k, names in table.items()) if v}


def apply():
    """Add every configured library's folders to ComfyUI's search lists. Safe to call again."""
    if folder_paths is None:
        return {}
    added = {}
    for lib in _configured():
        for key, dirs in preview(lib.get("layout", "stability"), lib["path"]).items():
            if key not in folder_paths.folder_names_and_paths:
                continue
            lst = folder_paths.folder_names_and_paths[key][0]
            have = {os.path.normcase(os.path.normpath(x)) for x in lst}
            for d in dirs:
                if os.path.normcase(d) not in have:
                    lst.append(d)
                    have.add(os.path.normcase(d))
                    added.setdefault(key, []).append(d)
            folder_paths.filename_list_cache.pop(key, None)
    if added:
        lc._invalidate()
    return added


def status():
    libs = []
    for lib in _configured():
        p = lib["path"]
        libs.append({"layout": lib.get("layout", "stability"), "path": p, "exists": os.path.isdir(p),
                     "folders": {k: len(v) for k, v in preview(lib.get("layout", "stability"), p).items()}})
    return {"libraries": libs, "detected": detect_stability(), "layouts": LABEL}


def save(libraries):
    clean = []
    for x in libraries or []:
        layout = str(x.get("layout", "stability"))
        path = os.path.normpath(os.path.expandvars(os.path.expanduser(str(x.get("path", "")).strip().strip('"'))))
        if layout not in LAYOUTS or not str(x.get("path", "")).strip():
            continue
        if layout == "stability":
            path = _models_dir(path) or path  # accept the install folder or its Models folder
        clean.append({"layout": layout, "path": path})
    cfg = lc.load_config()
    cfg["libraries"] = clean
    with open(lc._config_path(), "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=2)
    added = apply()
    return {"status": status(), "added": {k: len(v) for k, v in added.items()}}
