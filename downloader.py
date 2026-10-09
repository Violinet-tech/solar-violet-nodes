# Download queue behind the Violet browser extension and the standalone page: given a CivitAI model page (or version
# link) it resolves the file, saves it into the right ComfyUI model folder, and adds the CivitAI info and preview.
# Routes (registered from __init__.py):
#   GET  /violet/ping         identifies this server, so the extension can find it
#   POST /violet/download     {url, host?, kind?, subfolder?, api_key?, file_id?}  -> {job}
#   GET  /violet/downloads    every job with progress
#   POST /violet/download_cancel {id}
# Deliberately no CORS headers and POST only: web pages cannot call these, the extension can (it has host access).

import os
import re
import json
import time
import queue
import hashlib
import threading
import urllib.request
import urllib.error
import urllib.parse

from . import civitai
from . import lora_catalog as lc

try:
    import folder_paths
except ImportError:
    folder_paths = None

VERSION = "1.1.0"
# CivitAI model type (lower case) -> ComfyUI folder key
TYPE_FOLDER = {
    "lora": "loras", "locon": "loras", "dora": "loras",
    "checkpoint": "checkpoints", "textualinversion": "embeddings", "hypernetwork": "hypernetworks",
    "controlnet": "controlnet", "vae": "vae", "upscaler": "upscale_models",
    "motionmodule": "animatediff_models", "poses": "poses",
}
MODEL_EXTS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".sft")
_jobs = {}
_order = []
_q = queue.Queue()
_lock = threading.Lock()
_worker = None
MODE = "comfyui"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _open(url, key=None, rng=0, hops=6):
    """GET with the CivitAI key only on CivitAI's own hosts: the CDN link it redirects to must not get it."""
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=civitai._ssl_ctx()))
    for _ in range(hops):
        headers = {"User-Agent": civitai.UA}
        if key and re.search(r"(^|\.)civitai\.(com|red|blue)$", urllib.parse.urlparse(url).hostname or ""):
            headers["Authorization"] = f"Bearer {key}"
        if rng:
            headers["Range"] = f"bytes={rng}-"
        try:
            return opener.open(urllib.request.Request(url, headers=headers), timeout=60)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
            raise
    raise OSError("too many redirects")


def parse_link(url):
    """(model_id, version_id) from a CivitAI page or API link."""
    url = str(url or "")
    m = re.search(r"modelVersionId=(\d+)", url) or re.search(r"/(?:model-versions|download/models)/(\d+)", url)
    v = m.group(1) if m else None
    m = re.search(r"/models/(\d+)", url)
    return (m.group(1) if m else None), v


def _api_bases(host):
    out = []
    host = (host or "").strip().lower()
    if re.fullmatch(r"(www\.)?civitai\.(com|red|blue)", host):
        out.append("https://" + host.replace("www.", "") + "/api/v1")
    out.append(civitai.API)
    return list(dict.fromkeys(out))


def resolve(url, host=None, key=None, file_id=None):
    """The version JSON and the file to save for a CivitAI link."""
    mid, vid = parse_link(url)
    if not (mid or vid):
        raise ValueError("This is not a CivitAI model link")
    last = None
    for base in _api_bases(host or urllib.parse.urlparse(str(url)).hostname):
        try:
            if not vid:
                model = civitai._get_json(f"{base}/models/{mid}", key)
                vers = model.get("modelVersions") or []
                if not vers:
                    raise ValueError("That model has no published versions")
                vid = str(vers[0]["id"])
            ver = civitai._get_json(f"{base}/model-versions/{vid}", key)
            break
        except Exception as e:  # try the next host
            last = e
    else:
        raise last
    files = [f for f in ver.get("files", []) if f.get("downloadUrl")]
    pick = None
    if file_id:
        pick = next((f for f in files if str(f.get("id")) == str(file_id)), None)
    pick = pick or next((f for f in files if f.get("primary")), None) \
        or next((f for f in files if str(f.get("name", "")).lower().endswith(MODEL_EXTS)), None) or (files[0] if files else None)
    if not pick:
        raise ValueError("That version has no downloadable file")
    return ver, pick


def _dest_dir(key, subfolder=""):
    dirs = []
    if folder_paths is not None and key in folder_paths.folder_names_and_paths:
        dirs = [d for d in folder_paths.folder_names_and_paths[key][0] if d]
    if not dirs:
        raise ValueError(f"No '{key}' folder is set up on this computer")
    base = next((d for d in dirs if os.path.isdir(d)), dirs[0])
    sub = re.sub(r"[<>:\"|?*]", "_", str(subfolder or "")).strip().strip("/\\")
    if ".." in sub.replace("\\", "/").split("/"):
        raise ValueError("Bad subfolder")
    out = os.path.join(base, sub) if sub else base
    os.makedirs(out, exist_ok=True)
    return out


def _safe_name(name):
    name = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", str(name or "")).strip(" .")
    return name or "model.safetensors"


def _api_key(given):
    if given:
        return str(given).strip()
    try:
        from . import llm_backends
        return llm_backends.llm_settings().get("civitai_key") or None
    except Exception:
        return None


def _set(job, **kw):
    with _lock:
        job.update(kw)


def _run(job):
    key = job["_key"]
    try:
        _set(job, status="resolving")
        ver, f = resolve(job["url"], job.get("host"), key, job.get("file_id"))
        mtype = str((ver.get("model") or {}).get("type") or "").lower().replace(" ", "")
        folder = job.get("kind") or TYPE_FOLDER.get(mtype) or "checkpoints"
        name = _safe_name(f.get("name"))
        dest = os.path.join(_dest_dir(folder, job.get("subfolder")), name)
        size = int(float(f.get("sizeKB") or 0) * 1024)
        _set(job, name=name, model=(ver.get("model") or {}).get("name", ""), version=ver.get("name", ""), folder=folder,
             path=dest, total=size, base_model=ver.get("baseModel", ""))
        if os.path.isfile(dest) and (not size or abs(os.path.getsize(dest) - size) < 4096):
            _set(job, status="exists", done=os.path.getsize(dest))
            return
        part = dest + ".part"
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        _set(job, status="downloading", done=have)
        try:
            r = _open(f["downloadUrl"], key, have)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise PermissionError("CivitAI wants an API key for this file. Add it in the extension options or the Violet settings.")
            raise
        if have and r.status != 206:
            have = 0
        total = have + int(r.headers.get("Content-Length") or 0) or size
        _set(job, total=total, done=have)
        with open(part, "ab" if have else "wb") as out:
            while True:
                if job.get("_cancel"):
                    raise InterruptedError("Cancelled")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                have += len(chunk)
                _set(job, done=have)
        r.close()
        want = ((f.get("hashes") or {}).get("SHA256") or "").lower()
        if want:
            _set(job, status="checking")
            h = hashlib.sha256()
            with open(part, "rb") as fh:
                for blk in iter(lambda: fh.read(1 << 22), b""):
                    h.update(blk)
            if h.hexdigest() != want:
                os.remove(part)
                raise ValueError("The file did not match CivitAI's checksum, so it was deleted. Try again.")
        os.replace(part, dest)
        _set(job, status="saving info")
        try:
            data = civitai.fetch(dest, key, True)
            if data.get("found"):
                civitai.ensure_preview(dest, data)
        except Exception:
            pass  # the file is saved; the browser's Fetch CivitAI can retry the info
        lc._invalidate()
        try:
            if folder_paths is not None:
                folder_paths.filename_list_cache.pop(folder, None)
            from . import model_catalog
            model_catalog._cache.clear()
        except Exception:
            pass
        _set(job, status="done", done=job.get("total") or have)
    except InterruptedError as e:
        _set(job, status="cancelled", error=str(e))
    except Exception as e:
        _set(job, status="error", error=str(e) or e.__class__.__name__)
    finally:
        _set(job, finished=time.time())


def _loop():
    while True:
        job = _q.get()
        if not job.get("_cancel"):
            _run(job)
        _q.task_done()


def submit(body):
    global _worker
    url = str(body.get("url", "")).strip()
    mid, vid = parse_link(url)
    if not (mid or vid):
        raise ValueError("That is not a CivitAI model link")
    job = {"id": os.urandom(5).hex(), "url": url, "host": str(body.get("host", "")), "kind": str(body.get("kind", "")),
           "subfolder": str(body.get("subfolder", "")), "file_id": body.get("file_id"), "status": "queued",
           "name": "", "model": "", "done": 0, "total": 0, "error": "", "created": time.time(),
           "_key": _api_key(body.get("api_key")), "_cancel": False}
    with _lock:
        _jobs[job["id"]] = job
        _order.append(job["id"])
        for old in _order[:-60]:
            if _jobs.get(old, {}).get("status") in ("done", "error", "exists", "cancelled"):
                _jobs.pop(old, None)
        _order[:] = [i for i in _order if i in _jobs]
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_loop, daemon=True, name="violet-downloads")
        _worker.start()
    _q.put(job)
    return public(job)


def public(job):
    return {k: v for k, v in job.items() if not k.startswith("_")}


def listing():
    with _lock:
        return [public(_jobs[i]) for i in reversed(_order) if i in _jobs]


def cancel(jid):
    job = _jobs.get(jid)
    if job:
        job["_cancel"] = True
    return bool(job)


def ping():
    folders = {}
    if folder_paths is not None:
        for k in ("loras", "checkpoints", "vae", "embeddings", "controlnet", "upscale_models"):
            if k in folder_paths.folder_names_and_paths:
                folders[k] = (folder_paths.folder_names_and_paths[k][0] or [""])[0]
    return {"app": "violet", "name": "Solar Violet", "version": VERSION, "mode": MODE, "folders": folders,
            "has_key": bool(_api_key(None))}


def register(routes, web, mode="comfyui"):
    global MODE
    MODE = mode

    @routes.get("/violet/ping")
    async def violet_ping(request):
        return web.json_response(ping())

    @routes.post("/violet/download")
    async def violet_download(request):
        try:
            return web.json_response({"ok": True, "job": submit(await request.json())})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)

    @routes.get("/violet/downloads")
    async def violet_downloads(request):
        return web.json_response({"jobs": listing()})

    @routes.post("/violet/download_cancel")
    async def violet_download_cancel(request):
        body = await request.json()
        return web.json_response({"ok": cancel(str(body.get("id", "")))})
