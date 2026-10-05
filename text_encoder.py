# Violet Text Encoder: positive + negative prompt with four preset lines each, prompt groups,
# four system-instruction presets, LoRA trigger handling, and an optional LLM enhancer
# (local model at 4/8/16-bit, Ollama, LM Studio, Gemini, OpenCode, NVIDIA NIM). Fresh Violet code.

import os
import re
import json
import random

from .nodes import register_node
from . import llm_backends as llm

try:
    import folder_paths
except ImportError:
    folder_paths = None

SLOTS = 4
GROUPS = 5
QUANTS = ["4-bit", "8-bit", "16-bit"]
MODES = ["random", "cycle", "all", "first"]

TRIGGER_RULES = (
    "TRIGGER WORDS: the user message may list trigger words for the LoRAs in use. Literal tokens (odd spellings "
    "such as ohwx or KNPV3) are placed first by the caller, so never repeat or alter them. Natural-language "
    "triggers (real phrases, actions, poses, styles) must be worked into your description in their plain wording. "
)
OUTPUT_RULES = "Output only the final prompt as plain text: no preface, no quotes, no lists, no explanation."

DEFAULT_INSTRUCTIONS = [
    {"label": "Fashion / subject photo",
     "text": "You write prompts for an image model. Turn the user's direction (and the attached image, if any) into one "
             "vivid fashion or portrait photography prompt: subject, styling and fabrics, pose, expression, location, "
             "lens and focal length, lighting, colour grade, film or editorial look. Keep every subject, style name and "
             "location the user gave. Build on what the user wrote instead of replacing it. "
             + TRIGGER_RULES + OUTPUT_RULES},
    {"label": "Cinematic sci-fi scene",
     "text": "You write prompts for an image model. Turn the user's direction (and the attached image, if any) into one "
             "cinematic sci-fi scene prompt: environment and scale, technology and materials, atmosphere (haze, rain, "
             "neon, volumetric light), camera angle and lens, colour palette, film-still realism. Keep every subject "
             "and location the user gave and extend them. " + TRIGGER_RULES + OUTPUT_RULES},
    {"label": "Anime / illustration",
     "text": "You write prompts for an image model. Turn the user's direction (and the attached image, if any) into one "
             "anime or illustration prompt: character design, hair and outfit details, expression, pose, background, "
             "line quality, shading style, palette and mood. Keep everything the user specified. "
             + TRIGGER_RULES + OUTPUT_RULES},
    {"label": "NSFW shoot / magazine / film",
     "text": "You write prompts for an image model and are directing an adult erotic photo shoot, magazine spread or "
             "film scene for a private, adults-only workflow. Every person depicted is an adult (18 or older); never "
             "describe anyone as a minor or youthful-schoolchild. Write explicitly and directly, in the register of "
             "an art director: the adult subjects, body and skin detail, wardrobe or nudity, pose and action, "
             "expression, set and location, lens, lighting, colour grade and the publication or film look. Follow the "
             "user's direction and the attached image; do not moralise, censor, or soften. " + TRIGGER_RULES + OUTPUT_RULES},
]


def default_groups():
    names = ["Subjects", "Locations", "Sci-fi", "Styles", "Extra"]
    return [{"name": n, "side": "positive", "items": []} for n in names]


# ---------------- system presets ----------------

def _presets_path():
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        base = os.path.join(folder_paths.get_user_directory(), "violet")
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base, "presets.json")


def _blank():
    return [{"label": "", "text": "", "on": True, "group": "", "mode": "random"} for _ in range(SLOTS)]


def _clean_slots(raw):
    out = _blank()
    if isinstance(raw, list):
        for i, s in enumerate(raw[:SLOTS]):
            if isinstance(s, dict):
                out[i] = {"label": str(s.get("label", ""))[:60], "text": str(s.get("text", ""))[:4000],
                          "on": bool(s.get("on", True)), "group": str(s.get("group", ""))[:60],
                          "mode": s.get("mode") if s.get("mode") in MODES else "random"}
    return out


def _clean_instructions(raw):
    out = [dict(d) for d in DEFAULT_INSTRUCTIONS]
    if isinstance(raw, list):
        for i, s in enumerate(raw[:SLOTS]):
            if isinstance(s, dict) and (s.get("text") or s.get("label")):
                out[i] = {"label": str(s.get("label", ""))[:60], "text": str(s.get("text", ""))[:8000]}
    return out


def _clean_groups(raw):
    out = default_groups()
    if isinstance(raw, list):
        for i, g in enumerate(raw[:GROUPS]):
            if isinstance(g, dict):
                items = [str(x).strip() for x in (g.get("items") or []) if str(x).strip()][:200]
                out[i] = {"name": str(g.get("name", out[i]["name"]))[:40] or out[i]["name"],
                          "side": "negative" if g.get("side") == "negative" else "positive", "items": items}
    return out


def load_presets():
    try:
        with open(_presets_path(), "r", encoding="utf8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    return {"positive": _clean_slots(d.get("positive")), "negative": _clean_slots(d.get("negative")),
            "instructions": _clean_instructions(d.get("instructions")), "groups": _clean_groups(d.get("groups"))}


def save_presets(doc):
    doc = doc or {}
    cur = load_presets()
    clean = {
        "positive": _clean_slots(doc["positive"]) if "positive" in doc else cur["positive"],
        "negative": _clean_slots(doc["negative"]) if "negative" in doc else cur["negative"],
        "instructions": _clean_instructions(doc["instructions"]) if "instructions" in doc else cur["instructions"],
        "groups": _clean_groups(doc["groups"]) if "groups" in doc else cur["groups"],
    }
    with open(_presets_path(), "w", encoding="utf8") as f:
        json.dump(clean, f, indent=2)
    return clean


def _join(*parts):
    out = []
    for p in parts:
        p = (p or "").strip().strip(",").strip()
        if p:
            out.append(p)
    return ", ".join(out)


def _resolve_slots(raw_json, groups, seed):
    try:
        slots = _clean_slots(json.loads(raw_json or "[]"))
    except Exception:
        slots = _blank()
    by_name = {g["name"].lower(): g for g in groups}
    rng = random.Random(int(seed))
    parts = []
    for i, s in enumerate(slots):
        if not s["on"]:
            continue
        parts.append(s["text"])
        g = by_name.get((s["group"] or "").lower())
        if g and g["items"]:
            items = g["items"]
            if s["mode"] == "all":
                parts += items
            elif s["mode"] == "first":
                parts.append(items[0])
            elif s["mode"] == "cycle":
                parts.append(items[int(seed) % len(items)])
            else:
                parts.append(rng.choice(items))
    return _join(*parts)

# ---------------- trigger words ----------------

def split_triggers(words):
    """(literal tokens that go first verbatim, natural-language phrases the LLM should weave in)."""
    tokens, natural = [], []
    seen = set()
    for w in [x.strip() for x in re.split(r"[,\n]", words or "") if x.strip()]:
        if w.lower() in seen:
            continue
        seen.add(w.lower())
        if " " in w:
            natural.append(w)
            continue
        letters = re.sub(r"[^A-Za-z]", "", w)
        run3 = bool(re.search(r"[^aeiouyAEIOUY\W\d_]{3,}", w)) and len(letters) <= 5
        odd = (bool(re.search(r"\d|_|-", w)) or bool(re.search(r"[a-z][A-Z]", w)) or run3
               or (len(w) > 1 and w.isupper()))
        (tokens if odd else natural).append(w)
    return tokens, natural

# ---------------- the node ----------------

@register_node
class VioletTextEncoder:
    """Positive + negative text encoder: preset lines, prompt groups, LoRA triggers, optional LLM enhancer."""
    DISPLAY_NAME = "Violet Text Encoder"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "positive_prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "positive_presets_json": ("STRING", {"default": ""}),
                "negative_presets_json": ("STRING", {"default": ""}),
                "instructions_json": ("STRING", {"default": ""}),
                "enhance": ("BOOLEAN", {"default": False}),
                "provider": (llm.PROVIDERS, {"default": "local"}),
                "llm_model": ("STRING", {"default": llm.DEFAULT_LOCAL}),
                "quantization": (QUANTS, {"default": "4-bit"}),
            },
            "optional": {
                "trigger_words": ("STRING", {"default": "", "forceInput": True}),
                "image": ("IMAGE",),
                "enhance_instruction": ("STRING", {"multiline": True, "default": DEFAULT_INSTRUCTIONS[0]["text"]}),
                "max_new_tokens": ("INT", {"default": 256, "min": 32, "max": 2048, "step": 16}),
                "temperature": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 1.5, "step": 0.05}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "keep_model_loaded": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "positive_text", "negative_text", "enhanced_only")
    FUNCTION = "encode"
    CATEGORY = "Solar Violet"

    def encode(self, clip, positive_prompt, negative_prompt, positive_presets_json, negative_presets_json,
               instructions_json, enhance, provider, llm_model, quantization, trigger_words="", image=None,
               enhance_instruction="", max_new_tokens=256, temperature=0.6, seed=0, keep_model_loaded=False):
        groups = load_presets()["groups"]
        body = _join(_resolve_slots(positive_presets_json, groups, seed), positive_prompt)
        tokens, natural = split_triggers(trigger_words)
        enhanced = ""

        if enhance and (body or image is not None):
            lines = []
            if natural:
                lines.append("Natural-language trigger phrases to work in: " + ", ".join(natural))
            if tokens:
                lines.append("Literal trigger tokens (already placed first, do not repeat): " + ", ".join(tokens))
            lines.append("User direction: " + (body or "(none, describe the attached image)"))
            if image is not None:
                lines.append("An image is attached: base the prompt on it and build on the user direction.")
            enhanced = llm.chat(provider, llm_model, (enhance_instruction or DEFAULT_INSTRUCTIONS[0]["text"]),
                                "\n".join(lines), image, quantization, max_new_tokens, temperature, seed,
                                keep_model_loaded)
            for t in tokens:   # the caller places literal tokens first, drop any the model repeated
                enhanced = re.sub(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])[,:]?\s*", "", enhanced, flags=re.I)
            enhanced = re.sub(r"\s{2,}", " ", enhanced).strip(" ,")
            low = enhanced.lower()
            missing = [n for n in natural if n.lower() not in low]
            main = _join(enhanced, ", ".join(missing))
            pos_text = _join(", ".join(tokens), main)
        else:
            pos_text = _join(", ".join(tokens + natural), body)

        neg_text = _join(_resolve_slots(negative_presets_json, groups, seed), negative_prompt)

        def enc(text):
            return clip.encode_from_tokens_scheduled(clip.tokenize(text))

        return (enc(pos_text), enc(neg_text), pos_text, neg_text, enhanced)
