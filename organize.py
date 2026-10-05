# Organise a model / LoRA library: group loose files into folders by what their metadata says they are
# (Krea 2, Qwen, Anima, SDXL, ...), move selected files into a folder, and remove files (Recycle Bin or for good).
# Every move keeps a file's preview and info files with it and is written to an undo log. Fresh Violet code.

import os
import re
import sys
import json
import shutil

from . import lora_catalog as lc
from . import model_catalog as mc

try:
    import folder_paths
except ImportError:
    folder_paths = None

QUARANTINE = "_violet_duplicates"

# folder name, pattern over the base-model / architecture text. Order matters: the first hit wins.
FAMILIES = [
    ("Krea2", r"krea[\s_.\-]*2"),
    ("Qwen", r"qwen"),
    ("Anima", r"anima"),
    ("ZImage", r"z[\s_.\-]*image"),
    ("Flux2", r"flux[\s_.\-]*2|klein"),
    ("Flux", r"flux"),
    ("Illustrious", r"illustrious|noob[\s_.\-]*ai"),
    ("Pony", r"pony"),
    ("SDXL", r"sdxl|stable[\s_\-]*diffusion[\s_\-]*xl|sd[\s_\-]*xl"),
    ("SD3", r"\bsd[\s_.\-]*3|stable[\s_\-]*diffusion[\s_\-]*3"),
    ("SD15", r"sd[\s_.\-]*1[\s_.\-]*5|\bsd[\s_.\-]*1\b|stable[\s_\-]*diffusion[\s_\-]*v?1"),
    ("Wan", r"\bwan"),
    ("LTX", r"\bltx"),
    ("Hunyuan", r"hunyuan"),
    ("HiDream", r"hidream"),
    ("Chroma", r"chroma"),
    ("Lumina", r"lumina"),
    ("Boogu", r"boogu"),
    ("Ernie", r"ernie"),
    ("Ming", r"\bming\b"),
    ("MiniMax", r"minimax"),
]
_FAM = [(n, re.compile(p, re.I)) for n, p in FAMILIES]
_MOVES_LOG = "moves.json"
_BADNAME = set('<>:"|?*\\') | {chr(0)}


def _key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def family_of(info):
    """(folder name, why) from the metadata the file carries, or (None, why not)."""
    civ = info.get("civitai") or {}
    md, keys = {}, []
    path = info.get("path") or ""
    if path.lower().endswith((".safetensors", ".sft")):
        header = lc._read_header(path)
        md = header.get("__metadata__", {}) or {}
        keys = [k for k in header if k != "__metadata__"][:400]
    bits = [info.get("base_model"), civ.get("base_model"), info.get("title"), md.get("ss_base_model_version"),
            md.get("modelspec.architecture"), md.get("modelspec.implementation"), md.get("ss_sd_model_name"), md.get("modelspec.title")]
    text = " ".join(str(b) for b in bits if b)
    for name, rx in _FAM:
        if rx.search(text):
            return name, f"base model: {(info.get('base_model') or civ.get('base_model') or md.get('ss_base_model_version') or text).strip()[:40]}"
    joined = " ".join(keys)
    if "double_blocks" in joined or "single_blocks" in joined:
        return "Flux", "layer names look like Flux"
    if "lora_te2" in joined:
        return "SDXL", "layer names look like SDXL"
    tags = " ".join(str(t) for t in (civ.get("tags") or []))
    for name, rx in _FAM:
        if tags and rx.search(tags):
            return name, "CivitAI tags"
    return None, "no base model in the file's metadata"


def _roots(folder_key):
    if folder_paths is None:
        return []
    try:
        return [os.path.normpath(p) for p in folder_paths.get_folder_paths(folder_key)]
    except Exception:
        return []


def _root_of(path, folder_key):
    p = os.path.normcase(os.path.normpath(path))
    best = None
    for r in _roots(folder_key):
        n = os.path.normcase(r)
        if p.startswith(n + os.sep) and (best is None or len(r) > len(best)):
            best = r
    return best


def _top_dirs(root):
    try:
        return [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and not d.startswith("_")]
    except OSError:
        return []


def _existing_folder(root, fam):
    """Reuse the folder the person already has for this family (KREA2, Minimax H3, ...) instead of making a second one."""
    want = _key(fam)
    for d in _top_dirs(root):
        k = _key(d)
        if k == want or k.startswith(want):
            return d
    return fam


def plan(kind="loras"):
    """Loose files (not in any folder yet) with the folder their metadata points to."""
    groups, unknown = {}, []
    for m in mc.list_models(kind):
        rel = m["id"].partition("::")[2].replace("\\", "/")
        if "/" in rel or QUARANTINE in rel:
            continue
        fam, why = family_of(m)
        folder_key = m["id"].partition("::")[0]
        root = _root_of(m["path"], folder_key)
        row = {"id": m["id"], "name": rel, "size": m.get("size", 0), "why": why, "base_model": m.get("base_model", "")}
        if not fam or not root:
            unknown.append(row)
            continue
        folder = _existing_folder(root, fam)
        groups.setdefault(folder, []).append(row)
    out = [{"folder": f, "files": rows} for f, rows in sorted(groups.items(), key=lambda kv: kv[0].lower())]
    return {"groups": out, "unknown": unknown, "loose": sum(len(g["files"]) for g in out) + len(unknown)}


# ---------------- moving ----------------

def _log_path():
    return os.path.join(os.path.dirname(lc._config_path()), _MOVES_LOG)


def _read_log():
    try:
        with open(_log_path(), "r", encoding="utf8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _write_log(batches):
    try:
        with open(_log_path(), "w", encoding="utf8") as f:
            json.dump(batches[-20:], f, indent=1)
    except Exception:
        pass


def _companions(path):
    stem = os.path.splitext(path)[0]
    return [stem + s for s in lc._COMPANION if os.path.exists(stem + s)]


def _clean_folder(folder):
    parts = [p.strip() for p in str(folder or "").replace("\\", "/").split("/") if p.strip()]
    if not parts or any(p in (".", "..") or any(c in _BADNAME for c in p) for p in parts):
        raise ValueError("That folder name has characters a folder can't contain.")
    return parts


def _invalidate(kind):
    lc._invalidate()
    mc._cache.clear()
    if folder_paths is not None:
        for key in mc._folders(kind):
            folder_paths.filename_list_cache.pop(key, None)


def move_to_folders(moves, kind="loras"):
    """moves: [{id, folder}]. The folder is created inside the library folder the file already lives in."""
    done, batch = [], []
    for mv in moves or []:
        mid, res = str(mv.get("id", "")), {"id": str(mv.get("id", ""))}
        try:
            path = mc.full_path(mid)
            if not path or not os.path.isfile(path):
                raise ValueError("file not found")
            folder_key, _, name = mid.partition("::")
            root = _root_of(path, folder_key)
            if not root:
                raise ValueError("not inside a known library folder")
            parts = _clean_folder(mv.get("folder"))
            dest_dir = os.path.join(root, *parts)
            dst = os.path.join(dest_dir, os.path.basename(path))
            if os.path.normcase(dst) == os.path.normcase(path):
                res["ok"] = True
                res["new_id"] = mid
                done.append(res)
                continue
            if os.path.exists(dst):
                raise ValueError("a file with that name is already in that folder")
            os.makedirs(dest_dir, exist_ok=True)
            pairs = [(path, dst)] + [(c, os.path.join(dest_dir, os.path.basename(c))) for c in _companions(path)]
            for a, b in pairs:
                if os.path.exists(b):
                    raise ValueError(f"{os.path.basename(b)} already exists there")
            for a, b in pairs:
                shutil.move(a, b)
                batch.append([a, b])
            res["ok"] = True
            res["new_id"] = f"{folder_key}::" + "/".join(parts) + "/" + os.path.basename(path)
        except Exception as e:
            res["ok"] = False
            res["error"] = str(e)
        done.append(res)
    if batch:
        log = _read_log()
        log.append(batch)
        _write_log(log)
    _invalidate(kind)
    return done


def undo_last(kind="loras"):
    log = _read_log()
    if not log:
        return {"restored": 0, "note": "Nothing to undo."}
    batch = log.pop()
    n = 0
    for a, b in reversed(batch):
        try:
            if os.path.exists(b) and not os.path.exists(a):
                os.makedirs(os.path.dirname(a), exist_ok=True)
                shutil.move(b, a)
                n += 1
        except Exception:
            pass
    # drop folders the move left empty
    for _a, b in batch:
        d = os.path.dirname(b)
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except OSError:
            pass
    _write_log(log)
    _invalidate(kind)
    return {"restored": n, "note": f"Moved {n} file(s) back."}


# ---------------- removing ----------------

def _recycle(path):
    """Send one file to the Recycle Bin / Trash. Raises if it could not be done (never deletes for good)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                        ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL), ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", wintypes.LPCWSTR)]
        # FO_DELETE | ALLOWUNDO | WANTNUKEWARNING: a file too big for the bin asks instead of vanishing
        op = SHFILEOPSTRUCTW(None, 3, os.path.abspath(path) + "\0\0", None, 0x40 | 0x4000 | 0x4 | 0x400, False, None, None)
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc != 0 or op.fAnyOperationsAborted or os.path.exists(path):
            raise RuntimeError("Windows did not move it to the Recycle Bin")
        return
    try:
        from send2trash import send2trash
        send2trash(path)
        return
    except ImportError:
        pass
    if shutil.which("gio"):
        import subprocess
        if subprocess.run(["gio", "trash", path], capture_output=True).returncode == 0:
            return
    raise RuntimeError("no Trash available here; use 'Move to _violet_duplicates' instead")


def remove(ids, mode="recycle", kind="loras"):
    """mode: recycle (Recycle Bin / Trash), delete (permanent), quarantine (_violet_duplicates, reversible)."""
    if mode not in ("recycle", "delete", "quarantine"):
        raise ValueError("unknown mode")
    if mode == "quarantine":
        from . import duplicates
        moved = duplicates.quarantine([str(i) for i in ids], kind)
        return [{"id": i, "ok": True} for i in moved]
    out = []
    for mid in ids:
        res = {"id": str(mid)}
        try:
            path = mc.full_path(str(mid))
            if not path or not os.path.isfile(path):
                raise ValueError("file not found")
            for full in [path] + _companions(path):
                if mode == "recycle":
                    _recycle(full)
                else:
                    os.remove(full)
            res["ok"] = True
        except Exception as e:
            res["ok"] = False
            res["error"] = str(e)
        out.append(res)
    _invalidate(kind)
    return out
