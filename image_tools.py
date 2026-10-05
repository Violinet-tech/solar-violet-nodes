# Violet image tools: Save Image (with destinations), Image Compare, Size + Resize (presets + batch), Pipe In / Pipe Out.
# Fresh Violet code.

import json
import os
import re
import time

import numpy as np
import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .nodes import register_node

try:
    import folder_paths
    from comfy.cli_args import args
    import comfy.utils
except ImportError:
    folder_paths = None
    args = None

CATEGORY = "Solar Violet"


def _to_pil(t):
    arr = np.clip(255.0 * t.cpu().numpy(), 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


# ------------------------------------------------------------------ Save Image
_DESTS = ["output", "output / dated folder", "input", "custom folder", "temp (preview only)"]
_FORMATS = ["png", "jpg", "webp"]


def _next_counter(folder, prefix, ext):
    pat = re.compile("^" + re.escape(prefix) + r"_(\d+)_?\." + re.escape(ext) + "$")
    best = 0
    try:
        for f in os.listdir(folder):
            m = pat.match(f)
            if m:
                best = max(best, int(m.group(1)))
    except OSError:
        pass
    return best + 1


@register_node
class VioletSaveImage:
    """Save images to a chosen destination: output, a dated folder, input, any custom folder, or temp preview only."""
    DISPLAY_NAME = "Violet Save Image"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "saved_paths")
    FUNCTION = "save"
    CATEGORY = CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "violet", "tooltip": "strftime codes work: %Y-%m-%d, %H%M"}),
                "destination": (_DESTS, {"default": "output"}),
                "format": (_FORMATS, {"default": "png"}),
            },
            "optional": {
                "subfolder": ("STRING", {"default": "", "tooltip": "Folder inside the destination (strftime codes work)"}),
                "custom_folder": ("STRING", {"default": "", "tooltip": "Used when destination is 'custom folder'"}),
                "extra_copy_folder": ("STRING", {"default": "", "tooltip": "Optional second folder that also gets a copy"}),
                "quality": ("INT", {"default": 95, "min": 1, "max": 100, "tooltip": "jpg / webp only"}),
                "embed_workflow": ("BOOLEAN", {"default": True, "tooltip": "png: store the workflow so it can be dragged back in"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    def _base(self, destination, custom_folder):
        if destination == "input":
            return folder_paths.get_input_directory(), "input"
        if destination == "temp (preview only)":
            return folder_paths.get_temp_directory(), "temp"
        if destination == "custom folder":
            if not custom_folder.strip():
                raise ValueError("Violet Save Image: destination is 'custom folder' but custom_folder is empty")
            return os.path.expanduser(time.strftime(custom_folder.strip())), None
        return folder_paths.get_output_directory(), "output"

    def save(self, images, filename_prefix="violet", destination="output", format="png", subfolder="",
             custom_folder="", extra_copy_folder="", quality=95, embed_workflow=True, prompt=None, extra_pnginfo=None):
        base, ui_type = self._base(destination, custom_folder)
        sub = time.strftime(subfolder.strip()).strip("/\\") if subfolder else ""
        if destination == "output / dated folder":
            sub = os.path.join(time.strftime("%Y-%m-%d"), sub) if sub else time.strftime("%Y-%m-%d")
        sub = sub.replace("..", "")
        folder = os.path.join(base, sub) if sub else base
        os.makedirs(folder, exist_ok=True)
        prefix = time.strftime(filename_prefix.strip() or "violet")
        prefix = re.sub(r'[<>:"|?*]', "_", prefix).replace("\\", "/").split("/")[-1]
        ext = format
        counter = _next_counter(folder, prefix, ext)

        meta = None
        if format == "png" and embed_workflow and args is not None and not args.disable_metadata:
            meta = PngInfo()
            if prompt is not None:
                meta.add_text("prompt", json.dumps(prompt))
            for k, v in (extra_pnginfo or {}).items():
                meta.add_text(k, json.dumps(v))

        extras = []
        if extra_copy_folder.strip():
            ef = os.path.expanduser(time.strftime(extra_copy_folder.strip()))
            os.makedirs(ef, exist_ok=True)
            extras.append(ef)

        results, paths = [], []
        for i in range(images.shape[0]):
            img = _to_pil(images[i])
            name = f"{prefix}_{counter + i:05}_.{ext}"
            path = os.path.join(folder, name)
            for target in [path] + [os.path.join(e, name) for e in extras]:
                if format == "png":
                    img.save(target, pnginfo=meta, compress_level=4)
                elif format == "jpg":
                    img.convert("RGB").save(target, quality=quality)
                else:
                    img.save(target, format="WEBP", quality=quality)
            paths.append(path)
            if ui_type:
                results.append({"filename": name, "subfolder": sub, "type": ui_type})
            else:
                # custom folder: the UI can only show files under output/input/temp, so drop a temp preview
                tmp = folder_paths.get_temp_directory()
                pname = f"violet_prev_{int(time.time() * 1000)}_{i}.png"
                img.save(os.path.join(tmp, pname), compress_level=1)
                results.append({"filename": pname, "subfolder": "", "type": "temp"})
        return {"ui": {"images": results}, "result": (images, "\n".join(paths))}


# ------------------------------------------------------------------ Image Compare
def _temp_preview(images, tag):
    out = []
    tmp = folder_paths.get_temp_directory()
    stamp = int(time.time() * 1000)
    for i in range(images.shape[0]):
        name = f"violet_cmp_{tag}_{stamp}_{i}.png"
        _to_pil(images[i]).save(os.path.join(tmp, name), compress_level=1)
        out.append({"filename": name, "subfolder": "", "type": "temp"})
    return out


@register_node
class VioletImageCompare:
    """Compare two images with a left/right slider or side by side. Pass-through outputs, shows in the node."""
    DISPLAY_NAME = "Violet Image Compare"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("image_a", "image_b")
    FUNCTION = "compare"
    CATEGORY = CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {"image_a": ("IMAGE",), "image_b": ("IMAGE",)}}

    def compare(self, image_a=None, image_b=None):
        ui = {"a_images": _temp_preview(image_a, "a") if image_a is not None else [],
              "b_images": _temp_preview(image_b, "b") if image_b is not None else []}
        return {"ui": ui, "result": (image_a, image_b)}


# ------------------------------------------------------------------ Size + Resize
_PRESETS = {
    "Custom": None,
    "From image (multiple of 8)": "image",
    "512 x 512  (1:1, SD 1.5)": (512, 512),
    "512 x 768  (2:3, SD 1.5)": (512, 768),
    "768 x 512  (3:2, SD 1.5)": (768, 512),
    "768 x 768  (1:1)": (768, 768),
    "832 x 1216 (2:3, SDXL)": (832, 1216),
    "1216 x 832 (3:2, SDXL)": (1216, 832),
    "896 x 1152 (7:9, SDXL)": (896, 1152),
    "1152 x 896 (9:7, SDXL)": (1152, 896),
    "1024 x 1024 (1:1, 1MP)": (1024, 1024),
    "1024 x 1280 (4:5)": (1024, 1280),
    "1280 x 1024 (5:4)": (1280, 1024),
    "1024 x 1536 (2:3)": (1024, 1536),
    "1536 x 1024 (3:2)": (1536, 1024),
    "960 x 1280 (3:4)": (960, 1280),
    "1280 x 960 (4:3)": (1280, 960),
    "720 x 1280 (9:16)": (720, 1280),
    "1280 x 720 (16:9, 720p)": (1280, 720),
    "1088 x 1920 (9:16)": (1088, 1920),
    "1920 x 1088 (16:9, 1080p)": (1920, 1088),
    "1536 x 1536 (1:1, 2.3MP)": (1536, 1536),
    "2048 x 2048 (1:1, 4MP)": (2048, 2048),
    "1536 x 640 (12:5, wide)": (1536, 640),
    "640 x 1536 (5:12, tall)": (640, 1536),
    "2560 x 1088 (21:9)": (2560, 1088),
}
_MODES = ["stretch", "fit (pad)", "crop (fill)"]
_METHODS = ["lanczos", "bicubic", "bilinear", "area", "nearest-exact"]


def _snap(v, m):
    return max(m, int(round(v / m)) * m)


@register_node
class VioletSizeResize:
    """Get size + resize in one: pick a size preset (or take it from the image), resize, and set the batch size."""
    DISPLAY_NAME = "Violet Size + Resize"
    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height", "batch_size")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (list(_PRESETS.keys()), {"default": "1024 x 1024 (1:1, 1MP)"}),
                "orientation": (["as listed", "swap (rotate 90)"], {"default": "as listed"}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64, "tooltip": "How many images to generate; the image output is repeated this many times"}),
                "resize_mode": (_MODES, {"default": "crop (fill)"}),
                "method": (_METHODS, {"default": "lanczos"}),
            },
            "optional": {
                "image": ("IMAGE",),
                "custom_width": ("INT", {"default": 1024, "min": 16, "max": 16384, "step": 8}),
                "custom_height": ("INT", {"default": 1024, "min": 16, "max": 16384, "step": 8}),
                "multiple_of": ("INT", {"default": 8, "min": 1, "max": 128}),
                "pad_color": ("STRING", {"default": "0,0,0", "tooltip": "r,g,b 0-255, used by 'fit (pad)'"}),
            },
        }

    def run(self, preset, orientation, batch_size, resize_mode, method, image=None, custom_width=1024,
            custom_height=1024, multiple_of=8, pad_color="0,0,0"):
        p = _PRESETS.get(preset)
        if p == "image":
            if image is None:
                raise ValueError("Violet Size + Resize: preset 'From image' needs an image connected")
            h0, w0 = image.shape[1], image.shape[2]
            w, h = _snap(w0, multiple_of), _snap(h0, multiple_of)
        elif p is None:
            w, h = custom_width, custom_height
        else:
            w, h = p
        if orientation.startswith("swap") and p not in (None, "image"):
            w, h = h, w
        m = max(1, multiple_of)
        w, h = _snap(w, m), _snap(h, m)

        if image is None:
            return (torch.zeros((batch_size, h, w, 3)), w, h, batch_size)
        out = self._resize(image, w, h, resize_mode, method, pad_color)
        if batch_size > 1 and out.shape[0] == 1:
            out = out.repeat(batch_size, 1, 1, 1)
        return (out, w, h, batch_size)

    @staticmethod
    def _scale(img, w, h, method):
        x = img.movedim(-1, 1)
        if method == "lanczos":
            x = comfy.utils.lanczos(x, w, h)
        elif method in ("area", "nearest-exact"):
            x = torch.nn.functional.interpolate(x, size=(h, w), mode=method)
        else:
            x = torch.nn.functional.interpolate(x, size=(h, w), mode=method, align_corners=False)
        return x.movedim(1, -1).clamp(0, 1)

    def _resize(self, image, w, h, mode, method, pad_color):
        H, W = image.shape[1], image.shape[2]
        if W == w and H == h:
            return image
        if mode == "stretch":
            return self._scale(image, w, h, method)
        s = max(w / W, h / H) if mode.startswith("crop") else min(w / W, h / H)
        nw, nh = max(1, round(W * s)), max(1, round(H * s))
        x = self._scale(image, nw, nh, method)
        if mode.startswith("crop"):
            top, left = (nh - h) // 2, (nw - w) // 2
            return x[:, top:top + h, left:left + w, :]
        try:
            rgb = [int(v) / 255.0 for v in pad_color.split(",")][:3]
        except ValueError:
            rgb = [0, 0, 0]
        rgb = (rgb + [0, 0, 0])[:3]
        canvas = torch.tensor(rgb, dtype=x.dtype, device=x.device).view(1, 1, 1, 3).repeat(x.shape[0], h, w, 1)
        if x.shape[-1] == 4:
            canvas = torch.cat([canvas, torch.ones_like(canvas[..., :1])], dim=-1)
        top, left = (h - nh) // 2, (w - nw) // 2
        canvas[:, top:top + nh, left:left + nw, :] = x
        return canvas


# ------------------------------------------------------------------ Pipe In / Out (multi set / multi get)
_PIPE_KEYS = [("model", "MODEL"), ("clip", "CLIP"), ("vae", "VAE"), ("positive", "CONDITIONING"),
              ("negative", "CONDITIONING"), ("latent", "LATENT"), ("image", "IMAGE")]


@register_node
class VioletPipeIn:
    """Bundle model / clip / vae / conditioning / latent / image into one wire. Feed a pipe in to update part of it."""
    DISPLAY_NAME = "Violet Pipe In"
    RETURN_TYPES = ("VIOLET_PIPE",)
    RETURN_NAMES = ("pipe",)
    FUNCTION = "pack"
    CATEGORY = CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        opt = {"pipe": ("VIOLET_PIPE",)}
        opt.update({k: (t,) for k, t in _PIPE_KEYS})
        return {"required": {}, "optional": opt}

    def pack(self, pipe=None, **kw):
        out = dict(pipe or {})
        out.update({k: v for k, v in kw.items() if v is not None})
        return (out,)


@register_node
class VioletPipeOut:
    """Unpack a Violet pipe back into its parts. Anything the pipe does not hold comes out empty."""
    DISPLAY_NAME = "Violet Pipe Out"
    RETURN_TYPES = ("VIOLET_PIPE",) + tuple(t for _, t in _PIPE_KEYS)
    RETURN_NAMES = ("pipe",) + tuple(k for k, _ in _PIPE_KEYS)
    FUNCTION = "unpack"
    CATEGORY = CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"pipe": ("VIOLET_PIPE",)}}

    def unpack(self, pipe):
        return (pipe,) + tuple(pipe.get(k) for k, _ in _PIPE_KEYS)
