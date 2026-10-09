# ComfyViolet Custom Nodes for ComfyUI
# Violet LoRA Loader, Model Selector, Prompt Enhancer, Image Describer, and managers

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from . import text_encoder  # registers VioletTextEncoder
from . import model_loader  # registers SolarVioletModelLoader
from . import image_tools  # Save Image, Image Compare, Size + Resize, Pipe In/Out

# HTTP endpoints for the frontend: LoRA catalog (with trigger words), previews from
# any configured directory, and runtime-editable extra LoRA directories.
try:
    import os
    import server
    from aiohttp import web
    from . import lora_catalog

    lora_catalog.init_from_config()
    _routes = server.PromptServer.instance.routes

    @_routes.get("/violet/lora_catalog")
    async def violet_models(request):
        return web.json_response(lora_catalog.list_loras())

    @_routes.get("/violet/lora_info")
    async def violet_lora_info(request):
        info = lora_catalog.lora_info(request.query.get("name", ""))
        return web.json_response(info or {}, status=200 if info else 404)

    @_routes.get("/violet/preview")
    async def violet_preview(request):
        f = lora_catalog.preview_file(request.query.get("name", ""))
        if not f:
            return web.Response(status=404)
        return web.FileResponse(f)

    @_routes.get("/violet/settings")
    async def violet_settings_get(request):
        return web.json_response(lora_catalog.get_settings())

    @_routes.post("/violet/settings")
    async def violet_settings_post(request):
        body = await request.json()
        dirs = body.get("lora_dirs", [])
        if not isinstance(dirs, list):
            return web.json_response({"error": "lora_dirs must be a list"}, status=400)
        lora_catalog.save_dirs([str(d) for d in dirs])
        return web.json_response(lora_catalog.get_settings())

    @_routes.get("/violet/presets")
    async def violet_presets_get(request):
        return web.json_response(text_encoder.load_presets())

    @_routes.post("/violet/presets")
    async def violet_presets_post(request):
        return web.json_response(text_encoder.save_presets(await request.json()))

    import asyncio
    from . import civitai, duplicates, llm_backends

    def _lora_path(name):
        import folder_paths
        return folder_paths.get_full_path("loras", name)

    async def _off(fn, *a):
        return await asyncio.get_event_loop().run_in_executor(None, lambda: fn(*a))

    @_routes.post("/violet/lora_fetch")
    async def violet_lora_fetch(request):
        body = await request.json()
        name, path = body.get("name", ""), _lora_path(body.get("name", ""))
        if not path:
            return web.json_response({"error": "unknown LoRA"}, status=404)
        key = llm_backends.llm_settings().get("civitai_key") or None
        try:
            data = await _off(civitai.fetch, path, key, bool(body.get("force")))
            if data.get("found"):
                await _off(civitai.ensure_preview, path, data)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=502)
        lora_catalog._meta_cache.pop(name, None)
        return web.json_response(lora_catalog.lora_info(name) or {})

    @_routes.post("/violet/lora_previews")
    async def violet_lora_previews(request):
        body = await request.json()
        path = _lora_path(body.get("name", ""))
        side = civitai.load_sidecar(path) if path else None
        if not side or not (side.get("civitai") or {}).get("found"):
            return web.json_response({"error": "fetch CivitAI data for this LoRA first"}, status=400)
        return web.json_response(await _off(civitai.download_previews, path, side["civitai"]))

    @_routes.get("/violet/duplicates")
    async def violet_duplicates(request):
        return web.json_response(await _off(duplicates.find))

    @_routes.post("/violet/duplicates/quarantine")
    async def violet_quarantine(request):
        body = await request.json()
        return web.json_response({"moved": await _off(duplicates.quarantine, [str(n) for n in body.get("names", [])])})

    @_routes.get("/violet/llm/settings")
    async def violet_llm_settings(request):
        return web.json_response(llm_backends.public_settings())

    @_routes.post("/violet/llm/settings")
    async def violet_llm_settings_post(request):
        return web.json_response(llm_backends.save_llm_settings(await request.json()))

    @_routes.get("/violet/llm/models")
    async def violet_llm_models(request):
        try:
            return web.json_response(await _off(llm_backends.describe_models, request.query.get("provider", "local"), request.query.get("free", "") == "1"))
        except Exception as e:
            return web.json_response({"models": [], "error": str(e)})

    @_routes.post("/violet/llm/detect")
    async def violet_llm_detect(request):
        found = await _off(llm_backends.detect_local)
        return web.json_response({"found": found, "pick": llm_backends.attach_pick(found)})

    @_routes.post("/violet/lora_rename")
    async def violet_lora_rename(request):
        body = await request.json()
        name, mode, value = body.get("name", ""), body.get("mode", "display"), body.get("value", "")
        try:
            if mode == "file":
                new_name = lora_catalog.rename_file(name, value)
                return web.json_response({"name": new_name, "info": lora_catalog.lora_info(new_name) or {}})
            return web.json_response({"name": name, "info": lora_catalog.set_alias(name, value) or {}})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    @_routes.get("/violet/ui")
    async def violet_ui_get(request):
        return web.json_response(lora_catalog.get_ui())

    @_routes.post("/violet/ui")
    async def violet_ui_post(request):
        return web.json_response(lora_catalog.save_ui(await request.json()))
    def _has_node(name):
        import nodes as _n
        return name in _n.NODE_CLASS_MAPPINGS

    from . import model_catalog

    model_catalog.apply_dirs()
    from . import library

    library.apply()  # Stability Matrix / other model libraries the person set up

    @_routes.get("/violet/library")
    async def violet_library(request):
        return web.json_response(await _off(library.status))

    @_routes.post("/violet/library")
    async def violet_library_post(request):
        body = await request.json()
        out = await _off(library.save, body.get("libraries", []))
        await _off(model_catalog.refresh, "loras")
        return web.json_response(out)

    def _mid(body):
        return str(body.get("id", ""))

    @_routes.get("/violet/model_catalog")
    async def violet_model_catalog(request):
        kind = request.query.get("kind", "")
        if not kind:
            return web.json_response({"counts": await _off(model_catalog.counts), "kinds": model_catalog.KIND_LABEL,
                                      "gguf_node": _has_node("UnetLoaderGGUF"), "clip_gguf_node": _has_node("CLIPLoaderGGUF")})
        if request.query.get("refresh"):
            await _off(model_catalog.refresh, kind)
        return web.json_response(await _off(model_catalog.list_models, kind))

    @_routes.get("/violet/model_info")
    async def violet_model_info(request):
        i = model_catalog.info(request.query.get("id", ""))
        return web.json_response(i or {}, status=200 if i else 404)

    @_routes.get("/violet/model_preview")
    async def violet_model_preview(request):
        f = model_catalog.preview_file(request.query.get("id", ""))
        return web.FileResponse(f) if f else web.Response(status=404)

    @_routes.post("/violet/model_fetch")
    async def violet_model_fetch(request):
        body = await request.json()
        mid, path = _mid(body), model_catalog.full_path(_mid(body))
        if not path:
            return web.json_response({"error": "unknown model"}, status=404)
        key = llm_backends.llm_settings().get("civitai_key") or None
        try:
            data = await _off(civitai.fetch, path, key, bool(body.get("force")))
            if data.get("found"):
                await _off(civitai.ensure_preview, path, data)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=502)
        model_catalog.forget(mid)
        return web.json_response(model_catalog.info(mid) or {})

    @_routes.post("/violet/model_previews")
    async def violet_model_previews(request):
        path = model_catalog.full_path(_mid(await request.json()))
        side = civitai.load_sidecar(path) if path else None
        if not side or not (side.get("civitai") or {}).get("found"):
            return web.json_response({"error": "fetch CivitAI data for this model first"}, status=400)
        return web.json_response(await _off(civitai.download_previews, path, side["civitai"]))

    @_routes.post("/violet/model_rename")
    async def violet_model_rename(request):
        body = await request.json()
        mid, mode, value = _mid(body), body.get("mode", "display"), body.get("value", "")
        try:
            if mode == "file":
                new_id = model_catalog.rename_file(mid, value)
                return web.json_response({"id": new_id, "info": model_catalog.info(new_id) or {}})
            return web.json_response({"id": mid, "info": model_catalog.set_alias(mid, value) or {}})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    @_routes.get("/violet/model_duplicates")
    async def violet_model_dups(request):
        kind = request.query.get("kind", "checkpoints")
        return web.json_response(await _off(duplicates.find, None, kind))

    @_routes.post("/violet/model_duplicates/quarantine")
    async def violet_model_quarantine(request):
        body = await request.json()
        return web.json_response({"moved": await _off(duplicates.quarantine, [str(n) for n in body.get("ids", [])], str(body.get("kind", "checkpoints")))})

    from . import organize

    @_routes.get("/violet/organize_plan")
    async def violet_organize_plan(request):
        return web.json_response(await _off(organize.plan, request.query.get("kind", "loras")))

    @_routes.post("/violet/organize_apply")
    async def violet_organize_apply(request):
        body = await request.json()
        try:
            return web.json_response({"results": await _off(organize.move_to_folders, body.get("moves", []), str(body.get("kind", "loras")))})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    @_routes.post("/violet/organize_undo")
    async def violet_organize_undo(request):
        body = await request.json()
        return web.json_response(await _off(organize.undo_last, str(body.get("kind", "loras"))))

    @_routes.post("/violet/model_remove")
    async def violet_model_remove(request):
        body = await request.json()
        try:
            return web.json_response({"results": await _off(organize.remove, [str(i) for i in body.get("ids", [])], str(body.get("mode", "recycle")), str(body.get("kind", "loras")))})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    @_routes.get("/violet/model_advice")
    async def violet_model_advice(request):
        from . import model_advice
        a = await _off(model_advice.advise, request.query.get("id", ""))
        return web.json_response(a or {}, status=200 if a else 404)

    @_routes.post("/violet/canvas_push")
    async def violet_canvas_push(request):
        """Another app (Violinet OS) asks every open ComfyUI tab to add / fill a loader for a model file."""
        body = await request.json()
        want = os.path.normcase(os.path.realpath(str(body.get("path", "")))) if body.get("path") else None
        mid = str(body.get("id", ""))
        kinds = [body["kind"]] if body.get("kind") in model_catalog.KINDS else list(model_catalog.KINDS)
        if want:
            mid = ""
            for k in kinds:
                for m in await _off(model_catalog.list_models, k):
                    if os.path.normcase(os.path.realpath(m["path"])) == want:
                        mid, kind = m["id"], k
                        break
                if mid:
                    break
        if not mid:
            return web.json_response({"error": "ComfyUI does not see that file in any of its model folders"}, status=404)
        if not want:
            kind = body.get("kind", "checkpoints")
        server.PromptServer.instance.send_sync("violet.add_model", {"id": mid, "kind": kind, "loader": body.get("loader", "stock")})
        return web.json_response({"ok": True, "id": mid, "kind": kind})

    @_routes.post("/violet/open_workflow")
    async def violet_open_workflow(request):
        """Ask every open ComfyUI tab (the Desktop app included) to open a saved workflow by name."""
        body = await request.json()
        name = str(body.get("name", "")).strip()
        if not name:
            return web.json_response({"error": "name required"}, status=400)
        server.PromptServer.instance.send_sync("violet.open_workflow", {"name": name})
        return web.json_response({"ok": True, "name": name})

    @_routes.get("/violet/model_dirs")
    async def violet_model_dirs_get(request):
        return web.json_response(model_catalog.get_dirs())

    @_routes.post("/violet/model_dirs")
    async def violet_model_dirs_post(request):
        return web.json_response(model_catalog.save_dirs(await request.json()))

    from . import downloader

    downloader.register(_routes, web, "standalone" if getattr(server.PromptServer.instance, "standalone", False) else "comfyui")

    from . import network_sources

    @_routes.get("/violet/net/sources")
    async def violet_net_sources(request):
        return web.json_response({"sources": network_sources.sources(), "status": await _off(network_sources.status)})

    @_routes.post("/violet/net/sources")
    async def violet_net_sources_post(request):
        body = await request.json()
        return web.json_response({"sources": network_sources.save_sources(body.get("sources", []))})

    @_routes.get("/violet/net/catalog")
    async def violet_net_catalog(request):
        return web.json_response(await _off(network_sources.catalog, request.query.get("src", ""), request.query.get("kind", "")))

    @_routes.get("/violet/net/preview")
    async def violet_net_preview(request):
        q = request.query
        got = await _off(network_sources.preview, q.get("src", ""), q.get("folder", ""), q.get("name", ""), q.get("pi", 0))
        return web.Response(body=got[0], content_type=(got[1] or "image/webp").split(";")[0]) if got else web.Response(status=404)
except Exception as e:
    print(f"[ComfyViolet] HTTP routes not registered: {e}")

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']