#!/usr/bin/env python
"""Solar Violet standalone: the model and LoRA browsers, duplicate finder and download queue without ComfyUI.

    python standalone.py                          # http://127.0.0.1:8765
    python standalone.py --port 9000 --listen     # reachable from other computers on your network
    python standalone.py --stability D:\\stability  # a Stability Matrix install (found automatically when this
                                                  # folder sits inside <install>\\Data\\Packages\\ComfyUI\\custom_nodes)
    python standalone.py --models E:\\models       # a plain ComfyUI-style folder tree (checkpoints, loras, ...)

It loads the same pack code ComfyUI loads, so every /violet route behaves the same; only the node graph is missing.
The Violet browser extension can send CivitAI downloads here, or to a running ComfyUI, from the same options page.
"""

import argparse
import importlib.util
import os
import sys
import types

PACK = os.path.dirname(os.path.abspath(__file__))
MODEL_EXTS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".sft", ".onnx", ".yaml", ".yml"}
KEYS = ["checkpoints", "loras", "vae", "vae_approx", "text_encoders", "clip", "clip_vision", "diffusion_models", "unet",
        "unet_gguf", "controlnet", "embeddings", "hypernetworks", "upscale_models", "gligen", "diffusers", "ipadapter",
        "style_models", "model_patches", "sams", "facerestore_models", "ultralytics", "ultralytics_bbox",
        "ultralytics_segm", "animatediff_models", "poses"]


def make_folder_paths(data_dir):
    fp = types.ModuleType("folder_paths")
    fp.base_path = data_dir
    fp.folder_names_and_paths = {k: ([], set(MODEL_EXTS)) for k in KEYS}
    fp.filename_list_cache = {}
    user = os.path.join(data_dir, "user")
    for sub in ("user", "input", "output", "temp"):
        os.makedirs(os.path.join(data_dir, sub), exist_ok=True)

    def get_folder_paths(key):
        return list(fp.folder_names_and_paths[key][0])

    def get_filename_list(key):
        if key in fp.filename_list_cache:
            return fp.filename_list_cache[key]
        out = []
        for root in fp.folder_names_and_paths.get(key, ([], None))[0]:
            for dp, dn, files in os.walk(root, followlinks=True):
                for f in files:
                    if os.path.splitext(f)[1].lower() in MODEL_EXTS:
                        out.append(os.path.relpath(os.path.join(dp, f), root))
        out = sorted(set(out))
        fp.filename_list_cache[key] = out
        return out

    def get_full_path(key, name):
        for root in fp.folder_names_and_paths.get(key, ([], None))[0]:
            p = os.path.join(root, name)
            if os.path.isfile(p):
                return p
        return None

    fp.get_folder_paths = get_folder_paths
    fp.get_filename_list = get_filename_list
    fp.get_full_path = get_full_path
    fp.get_user_directory = lambda: user
    fp.get_input_directory = lambda: os.path.join(data_dir, "input")
    fp.get_output_directory = lambda: os.path.join(data_dir, "output")
    fp.get_temp_directory = lambda: os.path.join(data_dir, "temp")
    return fp


def stub_missing():
    """The node classes import torch / numpy / PIL at the top; the browsers never run them, so stand-ins are fine."""
    from unittest import mock
    for name in ("numpy", "torch", "PIL", "PIL.Image", "PIL.ImageOps", "PIL.PngImagePlugin"):
        try:
            __import__(name)
        except Exception:
            sys.modules[name] = mock.MagicMock()


def find_stability_root():
    p = PACK
    while True:
        parent = os.path.dirname(p)
        if os.path.basename(parent).lower() == "packages" and os.path.basename(os.path.dirname(parent)).lower() == "data":
            return os.path.dirname(os.path.dirname(parent))
        if parent == p:
            return None
        p = parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--listen", action="store_true", help="listen on every network address, not just this computer")
    ap.add_argument("--stability", help="Stability Matrix install folder (or its Models folder)")
    ap.add_argument("--models", action="append", default=[], help="ComfyUI-style models folder (can repeat)")
    ap.add_argument("--data", default=os.path.join(PACK, "standalone_data"), help="where settings and CivitAI info are kept")
    args = ap.parse_args()

    from aiohttp import web

    fp = make_folder_paths(os.path.abspath(args.data))
    sys.modules["folder_paths"] = fp
    routes = web.RouteTableDef()
    instance = types.SimpleNamespace(routes=routes, standalone=True, send_sync=lambda *a, **k: None)
    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(instance=instance)
    sys.modules["server"] = server
    comfy_nodes = types.ModuleType("nodes")
    comfy_nodes.NODE_CLASS_MAPPINGS = {}
    sys.modules["nodes"] = comfy_nodes
    stub_missing()

    spec = importlib.util.spec_from_file_location("solar_violet_nodes", os.path.join(PACK, "__init__.py"),
                                                  submodule_search_locations=[PACK])
    pack = importlib.util.module_from_spec(spec)
    sys.modules["solar_violet_nodes"] = pack
    spec.loader.exec_module(pack)
    from solar_violet_nodes import library, lora_catalog as lc

    # model folders: whatever the person configured before, else this Stability Matrix install / the folders given
    libs = [x for x in lc.load_config().get("libraries", []) if isinstance(x, dict)]
    have = {os.path.normcase(x.get("path", "")) for x in libs}
    wanted = []
    if args.stability:
        wanted.append({"layout": "stability", "path": args.stability})
    elif not libs:
        root = find_stability_root()
        if root:
            wanted.append({"layout": "stability", "path": root})
        wanted += [{"layout": "stability", "path": m} for m in library.detect_stability()]
    wanted += [{"layout": "comfy", "path": m} for m in args.models]
    fresh = [w for w in wanted if os.path.normcase(os.path.normpath(w["path"])) not in have]
    if fresh:
        library.save(libs + fresh)
    else:
        library.apply()
    lc.init_from_config()
    from solar_violet_nodes import model_catalog
    model_catalog.apply_dirs()

    app = web.Application(client_max_size=64 * 1024 * 1024)
    app.add_routes(routes)

    async def index(request):
        return web.Response(text=INDEX, content_type="text/html")

    async def js_app(request):
        return web.Response(text=SHIM_APP, content_type="text/javascript")

    async def js_api(request):
        return web.Response(text=SHIM_API, content_type="text/javascript")

    app.router.add_get("/", index)
    app.router.add_get("/scripts/app.js", js_app)
    app.router.add_get("/scripts/api.js", js_api)
    app.router.add_static("/extensions/solar-violet-nodes", os.path.join(PACK, "web"))

    host = "0.0.0.0" if args.listen else "127.0.0.1"
    got = {k: v[0] for k, v in fp.folder_names_and_paths.items() if v[0]}
    print(f"Solar Violet standalone on http://{host if host != '0.0.0.0' else '127.0.0.1'}:{args.port}")
    print("Model folders:", ", ".join(f"{k}={len(v)}" for k, v in got.items()) or "none found - use --stability or --models")
    web.run_app(app, host=host, port=args.port, print=None)


# What the pack's browser scripts expect from ComfyUI's frontend, reduced to what they use outside a node graph.
SHIM_APP = """
const noop = () => {};
export const app = {
  extensions: [],
  registerExtension(e) { this.extensions.push(e); try { e.setup && e.setup(); } catch (err) { console.warn(err); } },
  graph: { _nodes: [], getNodeById: () => null, add: noop, setDirtyCanvas: noop },
  canvas: { selected_nodes: {}, selectNode: noop, ds: { offset: [0, 0], scale: 1 }, canvas: { width: 1, height: 1 } },
  refreshComboInNodes: async () => {},
  extensionManager: { toast: { add: noop } },
  loadGraphData: async () => {},
};
window.app = app;
"""
SHIM_API = """
export const api = {
  addEventListener() {}, removeEventListener() {},
  apiURL: (p) => p, fileURL: (p) => p,
  fetchApi: (p, o) => fetch(p, o),
};
"""

INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solar Violet</title>
<style>
:root{--void:#0A0710;--ink:#14101C;--slate:#1E1830;--line:#2A2140;--text:#F4F1FA;--dim:#B9AED0;--violet:#A855F7;--deep:#6D28D9;--ok:#34D399;--err:#F87171}
*{box-sizing:border-box}body{margin:0;background:var(--void);color:var(--text);font:14px/1.5 Inter,system-ui,sans-serif}
header{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:14px 20px;background:var(--ink);border-bottom:1px solid var(--line)}
h1{font-size:17px;margin:0 auto 0 0;color:#C89BF5;letter-spacing:.3px}
button{background:var(--deep);color:#fff;border:0;border-radius:7px;padding:8px 14px;font:inherit;cursor:pointer}button:hover{background:var(--violet)}
main{max-width:860px;margin:0 auto;padding:22px 20px}
.card{background:var(--ink);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px}
.card h2{font-size:14px;margin:0 0 10px;color:#C89BF5}
.row{display:flex;gap:8px;flex-wrap:wrap}input{flex:1;min-width:220px;background:var(--void);color:var(--text);border:1px solid var(--line);border-radius:7px;padding:8px 10px;font:inherit}
.job{padding:10px 0;border-top:1px solid var(--line)}.job:first-child{border-top:0}.bar{height:6px;background:var(--slate);border-radius:3px;margin-top:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--violet)}
.dim{color:var(--dim);font-size:12px}.ok{color:var(--ok)}.err{color:var(--err)}
</style></head><body>
<header><h1>Solar Violet</h1><button id="b-m">Models</button><button id="b-l">LoRAs</button></header>
<main>
<div class="card"><h2>Download from CivitAI</h2>
<div class="row"><input id="url" placeholder="Paste a CivitAI model link"><button id="go">Download</button></div>
<div class="dim" id="msg" style="margin-top:8px">Saved into the right model folder with its CivitAI info and preview. The Violet browser extension sends links here too.</div></div>
<div class="card"><h2>Downloads</h2><div id="jobs" class="dim">Nothing yet.</div></div>
<div class="card"><h2>This server</h2><div id="me" class="dim"></div></div>
</main>
<script type="module">
import "/scripts/app.js";
await import("/extensions/solar-violet-nodes/violet_model_browser.js");
const B = window.VioletModelBrowser;
document.getElementById("b-m").onclick = () => B.openModels();
document.getElementById("b-l").onclick = () => B.openLoras();
const $ = (id) => document.getElementById(id), esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
$("go").onclick = async () => {
  const url = $("url").value.trim(); if (!url) return;
  const r = await fetch("/violet/download", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({url})});
  const d = await r.json(); $("msg").textContent = d.ok ? "Queued." : (d.error || "Failed"); if (d.ok) $("url").value = "";
  poll();
};
const mb = (n) => (n / 1048576).toFixed(n > 1e8 ? 0 : 1) + " MB";
async function poll() {
  try {
    const jobs = (await (await fetch("/violet/downloads")).json()).jobs;
    $("jobs").innerHTML = jobs.length ? jobs.map((j) => {
      const pct = j.total ? Math.min(100, j.done / j.total * 100) : 0, live = ["downloading","resolving","checking","saving info","queued"].includes(j.status);
      return '<div class="job"><b>' + esc(j.name || j.url) + '</b> <span class="dim">' + esc(j.model) + (j.folder ? " \\u2192 " + esc(j.folder) : "") + '</span><br>' +
        '<span class="' + (j.status === "done" || j.status === "exists" ? "ok" : j.status === "error" ? "err" : "dim") + '">' + esc(j.status) + (j.error ? ": " + esc(j.error) : "") + '</span>' +
        (live && j.total ? ' <span class="dim">' + mb(j.done) + " / " + mb(j.total) + '</span><div class="bar"><i style="width:' + pct + '%"></i></div>' : "") + "</div>";
    }).join("") : "Nothing yet.";
  } catch (e) {}
}
async function me() { try { const d = await (await fetch("/violet/ping")).json(); $("me").innerHTML = "Version " + esc(d.version) + " &middot; " + Object.entries(d.folders).map(([k, v]) => esc(k) + ": " + esc(v)).join("<br>") + (d.has_key ? "" : "<br>No CivitAI API key set (only needed for some files)."); } catch (e) {} }
me(); poll(); setInterval(poll, 1500);
</script></body></html>
"""

if __name__ == "__main__":
    main()
