# Node reference

One ComfyUI custom-node pack, one `custom_nodes/` folder, many nodes registered from it. This is the correct ComfyUI shape: a pack is a folder with `__init__.py` exporting `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS` and `WEB_DIRECTORY`; the nodes inside it are organized by concern across separate `.py` files, not by separate folders. ComfyUI does not require (or support) "sub-packs" nested inside one pack — what breaks is two *different* custom-node folders registering a node with the *same class name*, which then collide in ComfyUI's single global node registry regardless of which folder either one lives in. That collision, not folder layout, is the actual cause of the "can't run two packs together" problem.

## Folder structure

```
solar-violet-nodes/
  __init__.py            registers routes, imports NODE_CLASS_MAPPINGS from nodes.py, exports WEB_DIRECTORY
  nodes.py                LoRA loader/stack, LoRA scan/symlink/duplicates, model selector, prompt enhancer, image describer
  model_loader.py          typed checkpoint / diffusion / GGUF loaders (shared base class)
  image_tools.py           Save Image, Image Compare, Size + Resize, Pipe In/Out
  text_encoder.py          Violet Text Encoder (positive/negative, presets, LLM enhance)
  llm_backends.py          local / LM Studio / OpenCode / OpenRouter backends for the text encoder's LLM enhancer
  lora_catalog.py          LoRA directory list, trigger words, base-model + preview lookup (backs the loader and browser)
  model_catalog.py         checkpoint/diffusion/GGUF/VAE/etc. directory scanning (backs the loaders and browser)
  model_advice.py          "what LoRA/model goes with this" heuristics
  civitai.py               CivitAI metadata lookup for catalog entries
  duplicates.py            duplicate-file detection shared by the Scan/Duplicates nodes and the browser
  gguf_compat.py           GGUF quant/format compatibility checks
  library.py               model libraries: use Stability Matrix (or any folder tree) as-is, no moving or symlinks
  network_sources.py       browse-only listing of another computer's ComfyUI models over its stock /experiment/models API
  web/
    violet_theme.js         node color palette (Violet Diffusion site palette)
    violet_overlay.js, solar_overlay.js   node-canvas overlays (preview thumbnails etc.)
    violet_model_browser.js  the model/LoRA browser dialog (This PC + network sources)
    violet_lora_detail.js    per-LoRA detail panel (trigger words, base model, CivitAI info)
    violet_text_encoder.js   settings dialog + auto-attach-to-local-LLM for the text encoder node
    violet_image_compare.js  fills the Image Compare node's preview from onExecuted UI data
```

Every `.py` file above is one concern, imported by whichever node needs it — not copy-pasted per node. A node with 15+ inputs is a signal several jobs got merged into one.

## Conventions every node here follows

1. **Typed, not mode-switched.** `SolarVioletCheckpointLoader` / `DiffusionLoader` / `GGUFLoader` are separate node classes sharing one `_LoaderBase`, rather than one loader with a dropdown that changes which inputs matter.
2. **Backend renders, frontend only displays.** `VioletSaveImage` / `VioletImageCompare` / `VioletSizeResize` are `OUTPUT_NODE`s that write files server-side and return `{"ui": {"images": [...]}, "result": (...)}`; their JS widgets (`violet_image_compare.js`) fill themselves from `onExecuted`, never from `node.getInputData()` in the browser.
3. **DOM widgets via `node.addDOMWidget`**, registered through `app.registerExtension` — never `LiteGraph.registerWidgetType`.
4. **`WEB_DIRECTORY` exported from `__init__.py`**, always, or the `web/` JS silently never loads.
5. **Never name or credit any third-party node pack this was inspired by** — not in code, comments, docs, or node text.

## Node reference

### Loaders (`model_loader.py`) — category `Solar Violet`

| Node | Returns | Notes |
|---|---|---|
| **Violet Model Loader** (`SolarVioletModelLoader`) | `MODEL, CLIP, VAE, STRING(info)` | Shared loader — decides checkpoint / all-in-one / diffusion / GGUF from the file's own metadata, not a dropdown. |
| **Violet Checkpoint Loader** (`SolarVioletCheckpointLoader`) | same | Checkpoints only. |
| **Violet Diffusion Loader** (`SolarVioletDiffusionLoader`) | same | Diffusion-only (UNET) files. |
| **Violet GGUF Loader** (`SolarVioletGGUFLoader`) | same | GGUF-quantized models; uses `gguf_compat.py` for format checks. |

Shared inputs: `model_name` (from the matching catalog folder), `weight_dtype`; optional `vae_name`, `clip_name`, `clip_type` (auto-detected by default).

### LoRAs (`nodes.py`) — category `Solar Violet` / `Solar LoRA`

- **Solar Violet LoRA Loader** (`SolarVioletLoraLoader`) — stacks up to 30 LoRAs on one `model`+`clip`, each with its own preview card. Inputs: `lora_stack_json` (the slot list — name/strength/preview/trigger_words, edited from the node's own widget, not typed by hand), `auto_strength`, `step_increment`; optional `max_loras`, `prompt` (forced input, so trigger words can feed a text encoder), `apply_triggers`. Returns `model, clip, applied_names, trigger_words, prompt`. Multiple instances on one graph keep independent state.
- **Solar LoRA Scan** (`SolarLoraScanNode`) — scans the configured LoRA directories, returns a JSON list (name, size, base model guess, trigger words if known).
- **Solar LoRA Symlink** (`SolarLoraSymlinkNode`) — symlinks LoRAs from an external/network folder into ComfyUI's own `loras` search path without copying the files.
- **Solar LoRA Duplicates** (`SolarLoraDuplicatesNode`) — hashes and groups duplicate LoRA files (via `duplicates.py`) so the same weights under different names don't silently double up.

### Model utilities (`nodes.py`) — category `Solar`

- **Solar Model Selector** (`SolarModelSelector`) — picks a model file by a short natural-language description (uses `model_advice.py`'s heuristics), returns the resolved filename.
- **Solar Prompt Enhancer** (`SolarPromptEnhancer`) — expands a short prompt into a fuller one via the same LLM backends as the text encoder.
- **Solar Image Describer** (`SolarImageDescriber`) — captions an input image via a local/remote vision-capable LLM.

### Text encoding (`text_encoder.py`) — category `Solar Violet`

- **Violet Text Encoder** (`VioletTextEncoder`) — one node for both positive and negative conditioning. Inputs: `clip`, `positive_prompt`, `negative_prompt`, `positive_presets_json` / `negative_presets_json` (saved preset lines), `instructions_json`, `enhance` (turns on the LLM pass), `provider` (`local` / LM Studio / OpenCode / OpenRouter, from `llm_backends.py`), `llm_model`, `quantization`; optional `trigger_words` (forced input from a LoRA loader), `image` (for vision-aware enhancement), `enhance_instruction`, `max_new_tokens`, `temperature`, `seed`, `keep_model_loaded`. Returns `positive, negative` conditioning plus the raw/enhanced text. When `provider` is left on `local` or unset, the node's JS auto-attaches to whatever LLM server is already running on the machine — no manual URL entry needed.

`llm_backends.py` supplies the provider list and per-provider auth: local (no key), LM Studio, OpenCode, and OpenRouter (`OPENROUTER_API_KEY` env var or the settings-dialog field, with `HTTP-Referer`/`X-Title` headers set).

### Image tools (`image_tools.py`) — category `Solar Violet`

- **Violet Save Image** (`VioletSaveImage`) — `OUTPUT_NODE`; saves to output / a dated subfolder / Pictures / a custom folder, as PNG/JPG/WebP with a name prefix. Returns the image straight through plus the saved path.
- **Violet Image Compare** (`VioletImageCompare`) — `OUTPUT_NODE`; takes two images, renders a slider or side-by-side compare in the node itself (via `onExecuted` UI data, not client-side tensor reads).
- **Violet Size + Resize** (`VioletSizeResize`) — reports an input image's width/height and optionally resizes/crops it to a target size or named preset.
- **Violet Pipe In / Pipe Out** (`VioletPipeIn` / `VioletPipeOut`) — bundles several values into one `VIOLET_PIPE` wire and back out again, to cut down on long noodle runs between distant nodes.

### Violet Model Browser (`violet_model_browser.js` + `model_catalog.py`/`lora_catalog.py`)

Not a node — the floating ✦ menu (or Ctrl+Alt+M) that lists every checkpoint, diffusion model, GGUF, VAE, text encoder and LoRA ComfyUI can see: preview, precision/quant, base model, size, CivitAI details, rename, a duplicate finder (quarantines into a reversible `_violet_duplicates` folder rather than deleting), and extra-folder support. "Add as …" buttons drop the matching loader node straight into the open workflow. Another app can trigger the same push via `POST /violet/canvas_push` (this is how VIOLINET OS's own Model Browser does it). A missing VAE or text encoder on a loader is never a hard error — the node's info output says what to connect, plus suggested sampler/scheduler/steps/CFG (from CivitAI example images when available, else per-architecture defaults).

### Network sources (`network_sources.py`)

Not a node — a browser-side feature (`violet_model_browser.js`'s network-source picker) that lists the models/LoRAs another computer's ComfyUI can see, over that machine's own stock `/experiment/models` HTTP API. Nothing needs installing on the other machine. Browsing only: files stay where they are. To actually *use* a remote model in a graph, share its folder and add the UNC path under Folders/Settings, or run the graph on that machine directly.

## Using the pack

1. Load a checkpoint/diffusion/GGUF model with the matching **Violet …Loader** node.
2. Stack LoRAs with **Solar Violet LoRA Loader**, wire its `trigger_words` output into **Violet Text Encoder**'s `trigger_words` input so trigger words apply automatically.
3. Write prompts in **Violet Text Encoder**; turn on `enhance` if you want an LLM pass first.
4. Sample and decode as normal, then finish with **Violet Save Image** and, if comparing two takes, **Violet Image Compare**.
5. Use the model/LoRA browser (toolbar button) to manage local files, preview LoRAs, and — via **Network** — browse what another paired computer's ComfyUI has, without leaving this one.

### Model libraries (`library.py`)

Have a Stability Matrix install, or models kept somewhere else? Open the Violet Model Browser or LoRA Browser and press **Library**.
The pack looks for Stability Matrix in its usual places (`STABILITY_MATRIX_HOME`, the app data folder, the home folder, or the install a running ComfyUI was started from) and offers it with one click; otherwise type its folder. Two layouts are understood:

- **Stability Matrix**: its shared `Models` folder (`StableDiffusion`, `Lora`, `LyCORIS`, `VAE`, `TextEncoders`, `DiffusionModels`, `ControlNet`, `ESRGAN`, ...) is mapped onto ComfyUI's own folder names.
- **ComfyUI-style folders**: a tree named `checkpoints`, `loras`, `vae`, ...

Nothing is moved, renamed or symlinked, so the other program keeps working. The folders are added to ComfyUI's search lists at start-up and when you press Save, so every loader, the stock nodes and both browsers see the files. Libraries are saved per person in the pack's config file; none are built in.

### Browsers

- **Violet Model Browser** (Ctrl+Alt+M): checkpoints, diffusion models, GGUF, VAE, text encoders. **Violet LoRA Browser** (Ctrl+Alt+L): LoRAs only.
- A folder list on the left follows the folders the files sit in (a `KREA2` folder, an `ANIMA` folder, ...), with counts; a folder includes its sub-folders.
- **Rescan**, **Fetch CivitAI** (every file shown), **Duplicates**, rename (display name or the file), **Network** (browse ComfyUI on another computer, add its address yourself), **Folders / settings**, **Library**.
- On a Violet loader node, **Browse models / VAE / text encoders** open the browser aimed at that node: **Use in this node** fills it.

### Text encoder: choosing the LLM

The model is never typed. Pick a provider and the **LLM** row fills a dropdown from that provider; the raw `llm_model` text field is hidden and follows the dropdown. Switching provider moves to a model that provider really has.

- **NVIDIA NIM**: chat models available to your key (embedding, rerank and safety models are left out). Add the key once under **Settings**; NIM does not need to be open.
- **OpenRouter / OpenCode Zen**: a **Free only** box (on by default) keeps only free models.
- **Ollama**: read from Ollama's own model folder when Ollama is not running, and Ollama is started in the background when the graph runs.
- **LM Studio, Gemini, local**: listed from the running server, the API, or the text encoder folders.
- If a provider has no key or is unreachable, the row says what to do instead of asking for a name.

**Local provider (Qwen3-VL).** The dropdown lists Qwen3-VL 2B, 4B and 8B in Instruct and Thinking versions, marked *installed* or *downloads on first run*, followed by any other model folders found under the text encoder folders. Picking one that is not on disk downloads it on the first run. Thinking versions get extra room to reason before they answer, and their reasoning is stripped from the reply. This LLM is separate from the text encoder file that the loader uses to run the image model. A fresh node stays on Local; it no longer switches itself to whatever server is running (the **Attach to local process** button still does that on request).

### Example workflows

`example_workflows/` ships with the pack, so both show up in ComfyUI's Templates browser under this pack: **Violet image to image** (Violet Model Loader: checkpoint, diffusion or GGUF chosen from the file) and **Violet image to image (low VRAM)** (the same graph with the Violet GGUF Loader hooked up). Pick a model in the loader after opening; no model or image of anyone's is baked in.

### Selecting, grouping and cleaning up (both browsers)

- **Click a card to select it** (a tick appears); Shift-click selects everything between two clicks; **Select all shown** and **Clear** are in the bar that appears once something is selected. Hover a card for its details (preview, base model, trigger words, sampler, tags); the **i** button opens the full card, one at a time.
- **Add N to LoRA loader** puts every selected LoRA into the loader already in the workflow (a new one is only made when there is none).
- **Move to folder...** moves the selected files into an existing or new folder inside the library folder they are already in, with their previews and info files. **Undo** puts the last batch back.
- **Organize** reads each loose file's metadata (CivitAI base model, training base model, architecture, layer names) and proposes a folder such as `Krea2`, `Qwen`, `Anima`, `SDXL`, reusing a folder you already have. You review and edit the list before anything moves. After **Fetch CivitAI** finishes the browser offers it too.
- **Recycle bin** and **Delete permanently** act on the selection (with a confirmation); a file's preview and info files go with it.
- **Duplicates**: tick rows (Shift-click for a range), hover a row for its card, then **Recycle bin**, **Set aside** (a reversible `_violet_duplicates` folder) or **Delete permanently**. It refuses to remove every copy in a group. Fingerprints are remembered per file, so a second scan is fast.
