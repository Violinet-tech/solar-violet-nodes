# Roadmap

What is planned after 1.0.0: the remaining nodes from our earlier 58-node Violet
pack, and the standalone versions of the model and LoRA manager. Nothing here is
released yet; this is the plan.

## Remaining nodes

The earlier pack is folded into this one rather than installed beside it. Several
class names would collide (`SolarVioletLoraLoader`, `VioletLoraLoader`,
`VioletImageCompare`, `VioletSaveImage`, `VioletLoadImage`), so the two should never
be loaded in one ComfyUI.

**Already covered here, dropped from the old pack:** the LoRA loader, model
selector, save image, image compare and load image nodes, and the LoRA scan /
symlink / duplicates, prompt enhancer and image describer duplicates.

**Port (a real job, nothing equivalent in this pack yet):** auto resize,
resolution selector, resize / upscale latent, load image plus, RTX upscale, GGUF
switch, all-in-one model loader, gallery, image captioner, VAE encode / decode,
LoRA trigger prompt.

**Collapse into fewer nodes with explicit modes:**

| Old cluster | Becomes |
|---|---|
| Six VRAM free / HUD / offload nodes | A free / HUD node and one typed offload node (`vram_tools.py`) |
| Four per-family LoRA stack nodes | One stack node parameterised by model family (`lora_stack.py`) |
| Six conditioning nodes | One conditioning node with a mode input (`conditioning.py`) |

**Split before porting:** about ten nodes with 17 to 28 inputs each. They bundle
several jobs and become several single-purpose nodes.

**New:** samplers (`sampling.py`), RunPod and ComfyUI API nodes
(`api_backends.py`), pose conditioning and detection (`pose.py`), timer /
countdown / get-set / group bypass utilities (`utils.py`).

**Sidebar.** A docked Violet sidebar (ping / status, catalog, one-click
replace-a-LoRA), rebuilt cleanly with ComfyUI's sidebar API, together with the
server route it calls.

## Rules every ported node follows

1. One node, one job, typed inputs.
2. The backend renders and writes files; the frontend only displays what
   `onExecuted` hands it.
3. Widgets are DOM widgets registered through `app.registerExtension`.
4. `WEB_DIRECTORY` is exported so the pack's JS actually loads.
5. One extension file per concern.
6. Shared catalog and helper modules instead of logic copied into each node.
7. Routes live under `/violet/...` and every route a widget calls exists.

## Order

1. Port the simple nodes (images, loaders, VAE).
2. Sidebar and its replace route.
3. Collapse the VRAM, LoRA-stack and conditioning clusters.
4. Split and port the large nodes, then sampling, pose and utilities.
5. API nodes last, since they need a live pod to verify.

## Standalone versions

- **Desktop app.** The Electron model manager catches up to this pack (typed
  loaders, model libraries, Organize, Recycle bin, duplicate panel), preferably by
  calling the pack's `/violet/*` routes when ComfyUI is running.
- **VIOLINET OS.** The model browser, LoRA browser and duplicate finder inside the
  OS, with a ComfyUI instance picker. This is the main standalone home; there will
  not be a second Electron app for it.
- **Browser extension.** Send-to-app buttons on CivitAI and TensorArt pages, kept
  working with the app above.
- **ComfyUI-Manager listing.** Registry metadata so the pack installs from
  Manager's own browser.
