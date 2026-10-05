# GGUF compatibility shim. Some GGUF diffusion files carry no `general.architecture` (stable-diffusion.cpp style),
# and the GGUF pack then guesses the model from its tensor names. That guess list has no Qwen-Image 2.1, so those
# files die with "Unknown model architecture". This adds the missing signature at runtime, from our side, without
# editing the GGUF pack: it survives that pack being updated. Fresh Violet code.

import importlib
import sys

_MARK = "_violet_patched"


def _qwen21_keys(keys):
    return ("txt_in.text_norm.weight" in keys or "modulation.1.weight" in keys) and \
        any(k.endswith("transformer_blocks.0.img_mlp.gate_up.weight") or k.endswith("transformer_blocks.0.img_mlp.proj.weight")
            for k in keys) and "img_in.weight" in keys and "proj_out.weight" in keys


def apply():
    """Patch the GGUF pack's detect_arch if that pack is loaded. Returns True when patched (or already)."""
    mod = None
    try:
        import nodes as comfy_nodes
        cls = comfy_nodes.NODE_CLASS_MAPPINGS.get("UnetLoaderGGUF")
        if cls is not None:
            pkg = sys.modules[cls.__module__].__package__ or cls.__module__.rpartition(".")[0]
            mod = importlib.import_module(pkg + ".tools.convert")
    except Exception:
        mod = None
    if mod is None:
        return False
    if getattr(mod, _MARK, False):
        return True
    orig = mod.detect_arch

    class ModelQwenImage21(mod.ModelTemplate):
        arch = "qwen_image"
        keys_detect = []

    def detect_arch(state_dict):
        try:
            return orig(state_dict)
        except AssertionError:
            if _qwen21_keys(set(state_dict)):
                return ModelQwenImage21()
            raise
    mod.detect_arch = detect_arch
    setattr(mod, _MARK, True)
    return True
