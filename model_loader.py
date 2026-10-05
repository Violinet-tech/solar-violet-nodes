# Violet model loaders. Four nodes over one loader:
#   Violet Checkpoint Loader / Violet Diffusion Loader / Violet GGUF Loader  - one per type
#   Violet Model Loader                                                        - shared, any of the three, AIO too
# What gets loaded is decided from the file's own contents (GGUF header, safetensors tensor names), not from
# the folder it sits in. A missing VAE / text encoder is never an error here: the output is simply None and the
# info panel says what to connect. Fresh Violet code.

import os

from .nodes import register_node
from . import model_catalog as mc
from . import model_advice as adv
from . import gguf_compat

try:
    import folder_paths
    import comfy.sd
    import nodes as comfy_nodes
    from server import PromptServer
except ImportError:
    folder_paths = None
    PromptServer = None

gguf_compat.apply()
_NONE = "none"
_AUTO = "auto"
_WEIGHT = ["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"]
_CLIP_FALLBACK = ["stable_diffusion", "stable_cascade", "sd3", "stable_audio", "mochi", "ltxv", "pixart", "cosmos",
                  "lumina2", "wan", "hidream", "chroma", "ace", "omnigen2", "qwen_image", "hunyuan_image", "flux", "flux2"]


def _clip_types():
    # Ask this ComfyUI which text-encoder types it knows, so newer ones (krea2, boogu, ...) show up without a pack update.
    try:
        got = list(comfy_nodes.CLIPLoader.INPUT_TYPES()["required"]["type"][0])
        if got:
            return [_AUTO] + got
    except Exception:
        pass
    return [_AUTO] + _CLIP_FALLBACK


_CLIP_TYPES = _clip_types()


def _ids(*kinds):
    ids = []
    for k in kinds:
        ids += [m["id"] for m in mc.list_models(k)]
    return ids or [_NONE]


def _names(kind):
    return [_NONE] + [m["id"] for m in mc.list_models(kind)]


def _load_gguf(path):
    cls = comfy_nodes.NODE_CLASS_MAPPINGS.get("UnetLoaderGGUF")
    if cls is None:
        raise RuntimeError("GGUF model selected but the ComfyUI-GGUF pack is not installed")
    gguf_compat.apply()
    orig = folder_paths.get_full_path

    def patched(kind, name):
        return name if os.path.isabs(name) else orig(kind, name)
    folder_paths.get_full_path = patched
    try:
        return cls().load_unet(path)[0]
    finally:
        folder_paths.get_full_path = orig


def _dtype_opts(weight_dtype):
    torch = comfy_nodes.torch
    if weight_dtype == "fp8_e4m3fn":
        return {"dtype": torch.float8_e4m3fn}
    if weight_dtype == "fp8_e4m3fn_fast":
        return {"dtype": torch.float8_e4m3fn, "fp8_optimizations": True}
    if weight_dtype == "fp8_e5m2":
        return {"dtype": torch.float8_e5m2}
    return {}


def _auto_clip_type(advice):
    want = advice.get("clip_type") or "stable_diffusion"
    if advice.get("arch") == "krea2" and "krea2" in _CLIP_TYPES:
        return "krea2"
    return want


def load_any(model_name, weight_dtype="default", vae_name=_NONE, clip_name=_NONE, clip_type=_AUTO, unique_id=None):
    """Load by content. Returns (model, clip, vae, info_text). Never raises for a missing VAE / text encoder."""
    path = mc.full_path(model_name)
    if not path:
        raise ValueError(f"Violet loader: model not found: {model_name}")
    advice = adv.advise(model_name) or {}
    kind = advice.get("kind") or "diffusion"
    model = clip = vae = None
    if kind == "gguf":
        model = _load_gguf(path)
    elif kind == "aio":
        out = comfy.sd.load_checkpoint_guess_config(
            path, output_vae=True, output_clip=True, embedding_directory=folder_paths.get_folder_paths("embeddings"))
        model, clip, vae = out[0], out[1], out[2]
    else:
        model = comfy.sd.load_diffusion_model(path, model_options=_dtype_opts(weight_dtype))

    notes = []
    if vae_name and vae_name != _NONE:
        vae = comfy_nodes.VAELoader().load_vae(vae_name.partition("::")[2])[0]
        notes.append("VAE from vae_name")
    if clip_name and clip_name != _NONE:
        cn = clip_name.partition("::")[2]
        ctype = _auto_clip_type(advice) if clip_type == _AUTO else clip_type
        if cn.lower().endswith(".gguf") and comfy_nodes.NODE_CLASS_MAPPINGS.get("CLIPLoaderGGUF"):
            clip = comfy_nodes.NODE_CLASS_MAPPINGS["CLIPLoaderGGUF"]().load_clip(cn, ctype)[0]
        else:
            clip = comfy_nodes.CLIPLoader().load_clip(cn, ctype)[0]
        notes.append(f"text encoder from clip_name ({ctype})")

    lines = list(advice.get("lines") or [])
    have_vae, have_clip = vae is not None, clip is not None
    status = []
    if not have_vae:
        status.append("VAE output is empty")
    if not have_clip:
        status.append("CLIP output is empty")
    if status:
        lines.append("Right now: " + " and ".join(status) + " – connect what the lines above suggest before using them.")
    if notes:
        lines.append("Applied: " + "; ".join(notes) + ".")
    text = "\n".join(lines)
    if PromptServer is not None and unique_id is not None:
        try:
            PromptServer.instance.send_sync("violet.model_info", {"node": str(unique_id), "advice": advice, "text": text,
                                                                   "has_vae": have_vae, "has_clip": have_clip})
        except Exception:
            pass
    return model, clip, vae, text


class _LoaderBase:
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "info")
    FUNCTION = "load"
    CATEGORY = "Solar Violet"
    KINDS = ("checkpoints", "diffusion", "gguf")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"model_name": (_ids(*cls.KINDS),), "weight_dtype": (_WEIGHT,)},
            "optional": {
                "vae_name": (_names("vae"),),
                "clip_name": (_names("text_encoders"),),
                "clip_type": (_CLIP_TYPES, {"default": _AUTO}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, model_name, **kw):
        return True

    def load(self, model_name, weight_dtype="default", vae_name=_NONE, clip_name=_NONE, clip_type=_AUTO, unique_id=None):
        return load_any(model_name, weight_dtype, vae_name, clip_name, clip_type, unique_id)


@register_node
class SolarVioletModelLoader(_LoaderBase):
    """Shared loader: checkpoint, all-in-one, diffusion model or GGUF, decided from the file's metadata."""
    DISPLAY_NAME = "Violet Model Loader"


@register_node
class SolarVioletCheckpointLoader(_LoaderBase):
    """Checkpoints (all-in-one or not). Missing VAE / text encoder is reported, never an error."""
    DISPLAY_NAME = "Violet Checkpoint Loader"
    KINDS = ("checkpoints",)


@register_node
class SolarVioletDiffusionLoader(_LoaderBase):
    """Diffusion-model-only files. Wire a VAE and text encoder, or pick them here."""
    DISPLAY_NAME = "Violet Diffusion Loader"
    KINDS = ("diffusion",)


@register_node
class SolarVioletGGUFLoader(_LoaderBase):
    """GGUF quantised diffusion models (needs the ComfyUI-GGUF pack)."""
    DISPLAY_NAME = "Violet GGUF Loader"
    KINDS = ("gguf",)
