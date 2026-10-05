// Violet Model Browser: an external browser for checkpoints, diffusion models, GGUF, VAE and text encoders.
// Cards mirror the LoRA loader (preview, precision, base model, CivitAI info, rename); each card has
// "add as ..." buttons that drop the right loader node into the open graph (or fill the selected one).

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import "./violet_lora_detail.js";

const css = document.createElement("style");
css.textContent = `
  .mb-back { position:fixed; inset:0; background:rgba(0,0,0,.6); z-index:99990; display:flex; align-items:center; justify-content:center; }
  .mb { width:min(1100px,94vw); height:86vh; background:#14101C; color:#F4F1FA; border:1px solid #2A2140; border-radius:10px; display:flex; flex-direction:column; overflow:hidden; font:12px sans-serif; }
  .mb-head { display:flex; align-items:center; gap:8px; padding:10px 14px; border-bottom:1px solid #2A2140; flex-wrap:wrap; }
  .mb-head h3 { margin:0; color:#A855F7; font-size:14px; }
  .mb-tabs { display:flex; gap:4px; flex-wrap:wrap; }
  .mb-tab { background:#1E1830; color:#D9D0EC; border:1px solid #2A2140; border-radius:14px; padding:3px 11px; cursor:pointer; font-size:11px; }
  .mb-tab.on { background:#2A2140; color:#fff; border-color:#6D28D9; }
  .mb-tab small { color:#B8ADCF; margin-left:4px; }
  .mb-search { flex:1; min-width:140px; padding:5px 8px; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:4px; }
  .mb-grid { flex:1; overflow-y:auto; padding:12px; display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:10px; align-content:start; grid-auto-rows:max-content; }
  .mb-card { background:#1E1830; border:1px solid #2A2140; border-radius:8px; overflow:hidden; display:flex; flex-direction:column; }
  .mb-thumb { width:100%; height:170px; object-fit:cover; background:#0A0710; cursor:pointer; display:block; }
  .mb-nothumb { display:flex; align-items:center; justify-content:center; color:#3A2D5C; font-size:11px; }
  .mb-body { padding:7px 9px; display:flex; flex-direction:column; gap:5px; }
  .mb-name { font-size:12px; font-weight:600; word-break:break-word; }
  .mb-sub { color:#B8ADCF; font-size:10px; word-break:break-all; }
  .mb-pills { display:flex; gap:4px; flex-wrap:wrap; }
  .mb-pill { font-size:9px; padding:1px 6px; border-radius:8px; background:#2a2140; color:#C89BF5; }
  .mb-pill.g { background:#10303A; color:#A5F0FB; }
  .mb-acts { display:flex; gap:4px; flex-wrap:wrap; margin-top:2px; }
  .mb-b { background:#2A2140; color:#F4F1FA; border:1px solid #3A2D5C; border-radius:4px; font-size:10px; padding:3px 7px; cursor:pointer; }
  .mb-b:hover { border-color:#A855F7; } .mb-b.pri { background:#A855F7; border-color:#A855F7; } .mb-b:disabled { opacity:.45; cursor:default; }
  .mb-msg { padding:6px 14px; color:#B8ADCF; font-size:11px; border-top:1px solid #2A2140; min-height:16px; }
  .mb-main { flex:1; display:flex; min-height:0; }
  .mb-main .mb-grid { min-width:0; }
  .mb-side { width:190px; flex:none; overflow-y:auto; border-right:1px solid #2A2140; padding:6px 4px; font-size:11px; }
  .mb-fold { display:flex; justify-content:space-between; gap:6px; padding:3px 6px; border-radius:4px; cursor:pointer; color:#D9D0EC; word-break:break-all; }
  .mb-fold:hover { background:#1E1830; } .mb-fold.on { background:#2A2140; color:#fff; }
  .mb-fold small { color:#B8ADCF; flex:none; }
  .mb-more { background:#1E1830; color:#D9D0EC; border:1px solid #2A2140; border-radius:14px; padding:3px 8px; font-size:11px; max-width:190px; }
  .mb-more.on { background:#2A2140; color:#fff; border-color:#6D28D9; }
  .mb-src, .mb-sort { background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:4px; padding:4px; font-size:11px; max-width:150px; }
  .mb-card { position:relative; cursor:pointer; }
  .mb-card.sel { outline:2px solid #A855F7; outline-offset:-2px; background:#241A3C; }
  .mb-chk { position:absolute; top:6px; left:6px; width:22px; height:22px; border-radius:5px; background:rgba(10,7,16,.8); border:2px solid #6D28D9; color:transparent; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:700; z-index:2; opacity:0; transition:opacity .1s; }
  .mb-card:hover .mb-chk, .mb-grid.picking .mb-chk { opacity:1; }
  .mb-card.sel .mb-chk { background:#A855F7; border-color:#A855F7; color:#fff; opacity:1; }
  .mb-tools { position:absolute; top:6px; right:6px; display:flex; gap:4px; z-index:2; opacity:0; transition:opacity .1s; }
  .mb-card:hover .mb-tools { opacity:1; }
  .mb-selbar { display:flex; align-items:center; gap:6px; flex-wrap:wrap; padding:7px 14px; border-top:1px solid #6D28D9; background:#1A1330; }
  .mb-hover { position:fixed; width:340px; max-height:80vh; overflow:hidden; background:#14101C; color:#F4F1FA; border:1px solid #6D28D9; border-radius:10px; z-index:100020; box-shadow:0 12px 40px rgba(0,0,0,.65); font:12px sans-serif; pointer-events:none; }
  .mbh-img { width:100%; max-height:260px; object-fit:cover; display:block; background:#0A0710; }
  .mbh-body { padding:8px 10px; display:flex; flex-direction:column; gap:5px; }
  .mbh-title { font-size:13px; font-weight:600; color:#C89BF5; word-break:break-word; }
  .mbh-sub { font-size:10px; color:#B8ADCF; word-break:break-all; }
  .mbh-sec { font-size:10px; text-transform:uppercase; letter-spacing:.06em; color:#B8ADCF; }
  .mbh-row { display:flex; gap:4px; flex-wrap:wrap; }
  .mb-pill.tw { background:#2A1A4A; border:1px solid #6D28D9; }
  .mb-dirs textarea { width:100%; min-height:44px; box-sizing:border-box; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:4px; font-size:11px; padding:5px; }
`;
document.head.appendChild(css);

const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const post = async (url, body) => {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
};
const mb = (n) => (n >= 1073741824 ? (n / 1073741824).toFixed(1) + " GB" : (n / 1048576).toFixed(0) + " MB");
const rel = (id) => id.slice(id.indexOf("::") + 2);

// kind -> the stock loader that "add as ..." creates
const ADD = {
  loras: [{ label: "Add to LoRA loader", lora: true }],
  checkpoints: [{ label: "Add as checkpoint", node: "CheckpointLoaderSimple", widget: "ckpt_name" }],
  diffusion: [{ label: "Add as diffusion model", node: "UNETLoader", widget: "unet_name" }],
  gguf: [{ label: "Add as GGUF", node: "UnetLoaderGGUF", widget: "unet_name", needs: "gguf_node" }],
  vae: [{ label: "Add VAE", node: "VAELoader", widget: "vae_name" }],
  text_encoders: [{ label: "Add as text encoder", node: "CLIPLoader", widget: "clip_name", gguf: ["CLIPLoaderGGUF", "clip_name"] }],
};

function slotInto(spec, m, flags) {
  if (spec.lora) return window.VioletLoraLoader.add(m);
  let node = spec.node, widget = spec.widget;
  if (spec.gguf && m.name.toLowerCase().endsWith(".gguf")) {
    if (!flags.clip_gguf_node) throw new Error("GGUF text encoder needs the ComfyUI-GGUF pack (CLIPLoaderGGUF)");
    [node, widget] = spec.gguf;
  }
  if (spec.needs && !flags[spec.needs]) throw new Error("GGUF loading needs the ComfyUI-GGUF pack installed");
  return place(node, widget, rel(m.id));
}

// Fill the selected node when it is the right type, otherwise drop a new one at the middle of the canvas.
function place(type, widget, value, extra) {
  const g = app.graph, canvas = app.canvas;
  const sel = Object.values(canvas.selected_nodes || {})[0];
  const tgt = target && app.graph.getNodeById(target.id) && (target.widgets || []).some((x) => x.name === widget) ? target : null;
  let node = tgt || (sel && sel.type === type ? sel : null);
  let created = false;
  if (!node) {
    node = LiteGraph.createNode(type);
    if (!node) throw new Error("node type not available: " + type);
    const ds = canvas.ds, cw = canvas.canvas.width, ch = canvas.canvas.height;
    node.pos = [(cw / 2 - ds.offset[0] * ds.scale) / ds.scale - 100, (ch / 2 - ds.offset[1] * ds.scale) / ds.scale - 60];
    g.add(node);
    created = true;
  }
  const set = (name, v) => {
    const w = (node.widgets || []).find((x) => x.name === name);
    if (!w) return;
    w.value = v;
    if (w.callback) w.callback(v, canvas, node, node.pos, null);
  };
  set(widget, value);
  Object.entries(extra || {}).forEach(([k, v]) => set(k, v));
  canvas.selectNode(node);
  g.setDirtyCanvas(true, true);
  return created ? "Added " + type : "Set " + widget + " on the selected " + type;
}

let root = null;
let detailPop = null; // the one open "full details" card
let target = null; // a loader node the browser was opened from: "Use in this node" fills it
function close() { hideHover(); if (detailPop) { detailPop.remove(); detailPop = null; } if (root) { root.remove(); root = null; } target = null; }

// ---------- hover card, small dialogs ----------
let hoverEl = null, hoverTimer = null;
function hideHover() { clearTimeout(hoverTimer); if (hoverEl) { hoverEl.remove(); hoverEl = null; } }
const infoCache = new Map();
async function modelInfo(id) {
  if (infoCache.has(id)) return infoCache.get(id);
  try { const r = await fetch("/violet/model_info?id=" + encodeURIComponent(id)); if (r.ok) { const d = await r.json(); infoCache.set(id, d); return d; } } catch (e) { /* offline */ }
  return null;
}
function hoverHtml(m) {
  const c = m.civitai || {}, g = c.gen || {};
  const words = (m.trigger_words || []).slice(0, 14);
  const pills = [m.base_model, m.precision, c.version_name, c.creator && "by " + c.creator, m.size && mb(m.size)].filter(Boolean);
  return (m.preview ? '<img class="mbh-img" src="' + esc(m.preview) + '">' : "") +
    '<div class="mbh-body"><div class="mbh-title">' + esc(m.alias || c.model_name || rel(m.id).replace(/^.*[\\/]/, "")) + "</div>" +
    '<div class="mbh-sub">' + esc(m.rel || rel(m.id)) + "</div>" +
    '<div class="mbh-row">' + pills.map((t, i) => '<span class="mb-pill' + (i === 1 ? " g" : "") + '">' + esc(t) + "</span>").join("") + "</div>" +
    (g.sampler || g.cfg != null || g.steps != null ? '<div class="mbh-row">' + [g.sampler && g.sampler + (g.scheduler ? " / " + g.scheduler : ""), g.cfg != null && "CFG " + g.cfg, g.steps != null && g.steps + " steps"].filter(Boolean).map((t) => '<span class="mb-pill g">' + esc(t) + "</span>").join("") + "</div>" : "") +
    (words.length ? '<div class="mbh-sec">Trigger words</div><div class="mbh-row">' + words.map((w) => '<span class="mb-pill tw">' + esc(w) + "</span>").join("") + "</div>" : "") +
    ((c.tags || []).length ? '<div class="mbh-sec">Tags</div><div class="mbh-row">' + c.tags.slice(0, 10).map((t) => '<span class="mb-pill">' + esc(t) + "</span>").join("") + "</div>" : "") +
    (m.path ? '<div class="mbh-sub" style="margin-top:4px">' + esc(m.path) + "</div>" : "") + "</div>";
}
function showHover(anchor, m) {
  hideHover();
  hoverEl = document.createElement("div");
  hoverEl.className = "mb-hover";
  hoverEl.innerHTML = hoverHtml(m);
  document.body.appendChild(hoverEl);
  const r = anchor.getBoundingClientRect(), w = hoverEl.offsetWidth, h = hoverEl.offsetHeight;
  let x = r.right + 10;
  if (x + w > window.innerWidth - 8) x = Math.max(8, r.left - w - 10);
  let y = Math.min(Math.max(8, r.top), Math.max(8, window.innerHeight - h - 8));
  hoverEl.style.left = x + "px"; hoverEl.style.top = y + "px";
}
// Rest the mouse on an element for a moment and its card pops out beside it; leave and it goes away.
function attachHover(el, getModel) {
  el.addEventListener("mouseenter", () => {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(async () => { const m = await getModel(); if (m && el.isConnected && el.matches(":hover")) showHover(el, m); }, 350);
  });
  el.addEventListener("mouseleave", hideHover);
  el.addEventListener("mousedown", hideHover);
}

// In-page yes/no (the browser's own confirm() steals focus in some hosts).
function askDlg(text, okLabel, danger) {
  return new Promise((done) => {
    const back = document.createElement("div");
    back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100010;display:flex;align-items:center;justify-content:center";
    back.innerHTML = '<div style="width:min(460px,92vw);background:#14101C;color:#F4F1FA;border:1px solid ' + (danger ? "#DC2626" : "#6D28D9") + ';border-radius:10px;padding:14px;font:12px sans-serif">' +
      '<div style="white-space:pre-wrap;line-height:1.5;margin-bottom:10px">' + esc(text) + '</div><div class="vd-row"><button class="vd-btn' + (danger ? "" : " pri") + '" data-r="1" style="' + (danger ? "background:#DC2626;border-color:#DC2626" : "") + '">' + esc(okLabel || "OK") + '</button><button class="vd-btn" data-r="0">Cancel</button></div></div>';
    document.body.appendChild(back);
    const fin = (v) => { back.remove(); done(v); };
    back.querySelectorAll("[data-r]").forEach((b) => b.onclick = () => fin(b.dataset.r === "1"));
    back.addEventListener("mousedown", (e) => { if (e.target === back) fin(false); });
  });
}

const SORTS = { name: "Name", big: "Largest", base: "Base model", new: "Newest (CivitAI date)" };

async function open(startKind, opts) {
  const keepTarget = opts && opts.target;
  close();
  target = keepTarget || null;
  const mode = (opts && opts.mode) || (startKind === "loras" ? "loras" : "models");
  root = document.createElement("div");
  root.className = "mb-back";
  root.innerHTML = '<div class="mb"><div class="mb-head"><h3>' + (mode === "loras" ? "Violet LoRA Browser" : "Violet Model Browser") + '</h3><div class="mb-tabs"></div>' +
    '<select class="mb-src" title="Where to browse: this PC or another computer on the network"><option value="">This PC</option></select><input class="mb-search" placeholder="' + (mode === "loras" ? "Search LoRAs or trigger words..." : "Search models...") + '">' +
    '<select class="mb-sort" title="Sort">' + Object.entries(SORTS).map(([k, l]) => '<option value="' + k + '">' + l + "</option>").join("") + "</select>" +
    '<button class="mb-b" data-a="rescan" title="Scan the folders again">Rescan</button><button class="mb-b" data-a="fetchall" title="Look up every file shown on CivitAI for previews, base model and trigger words">Fetch CivitAI</button>' +
    '<button class="mb-b" data-a="org" title="Group loose files into folders by what their metadata says they are">Organize</button>' +
    '<button class="mb-b" data-a="dups" title="Find duplicate files in this category">Duplicates</button><button class="mb-b" data-a="net" title="Other computers to browse (ComfyUI URLs)">Network</button><button class="mb-b" data-a="dirs" title="Extra folders and settings for this category">Folders / settings</button>' +
    '<button class="mb-b" data-a="lib" title="Use another program\'s model folders, for example Stability Matrix">Library</button>' +
    '<button class="mb-b" data-a="x">✕</button></div><div class="mb-main"><div class="mb-side" style="display:none"></div><div class="mb-grid"></div></div>' +
    '<div class="mb-selbar" style="display:none"></div><div class="mb-msg"></div></div>';
  document.body.appendChild(root);
  root.addEventListener("mousedown", (e) => { if (e.target === root) close(); });
  const q = (s) => root.querySelector(s);
  const msg = (t, undo) => { const el = q(".mb-msg"); el.textContent = t; if (undo) { const b = document.createElement("button"); b.className = "mb-b"; b.textContent = "Undo"; b.style.marginLeft = "8px"; b.onclick = async () => { b.disabled = true; try { const r = await post("/violet/organize_undo", { kind }); forceScan = true; await load(); msg(r.note); } catch (e) { msg("Failed: " + e.message); } }; el.appendChild(b); } };
  q("[data-a=x]").onclick = close;
  const overview = await (await fetch("/violet/model_catalog")).json();
  const flags = overview;
  // LoRAs get their own browser: it lists only LoRAs, the model browser lists everything else.
  const kinds = Object.fromEntries(Object.entries(overview.kinds).filter(([k]) => (mode === "loras") === (k === "loras")));
  let src = "", kind = typeof startKind === "string" && kinds[startKind] ? startKind : Object.keys(kinds)[0], list = [], filter = "", folder = "", forceScan = false, sort = "name";
  const selected = new Map();   // id -> model: what the next action applies to
  let lastId = null, shown = [];
  const relOf = (m) => m.rel || rel(m.id);
  const dirOf = (m) => { const r = relOf(m).replace(/\\/g, "/"); const i = r.lastIndexOf("/"); return i < 0 ? "" : r.slice(0, i); };
  const TOP = "\u0000top";
  const inFolder = (m) => { if (!folder) return true; const d = dirOf(m); return folder === TOP ? d === "" : d === folder || d.startsWith(folder + "/"); };
  const tabs = q(".mb-tabs");
  const drawTabs = () => {
    tabs.style.display = Object.keys(kinds).length > 1 ? "" : "none";
    // The main model types are tabs; every other ComfyUI model folder (controlnet, clip_vision, upscale_models, ...) is in the "More folders" list.
    const main = Object.entries(kinds).filter(([k]) => ADD[k]), more = Object.entries(kinds).filter(([k]) => !ADD[k]);
    tabs.innerHTML = main.map(([k, l]) =>
      '<button class="mb-tab' + (k === kind ? " on" : "") + '" data-k="' + k + '">' + esc(l) + "<small>" + (overview.counts[k] ?? 0) + "</small></button>").join("") +
      (more.length ? '<select class="mb-more' + (!ADD[kind] ? " on" : "") + '" title="Every other ComfyUI model folder"><option value="">' + (!ADD[kind] ? "More folders" : "More ComfyUI folders...") + "</option>" +
        more.map(([k, l]) => '<option value="' + k + '"' + (k === kind ? " selected" : "") + ">" + esc(l) + " (" + (overview.counts[k] ?? 0) + ")</option>").join("") + "</select>" : "");
    tabs.querySelectorAll(".mb-tab").forEach((b) => b.onclick = () => { kind = b.dataset.k; folder = ""; selected.clear(); load(); });
    const sel = tabs.querySelector(".mb-more");
    if (sel) sel.onchange = () => { if (sel.value) { kind = sel.value; folder = ""; selected.clear(); load(); } };
  };
  // Folder list: every folder the files sit in (KREA2, ANIMA, ...) with counts; a folder includes its sub-folders.
  const allDirs = () => { const s = new Set(); list.forEach((m) => { const d = dirOf(m); if (d) d.split("/").reduce((acc, seg) => { const p = acc ? acc + "/" + seg : seg; s.add(p); return p; }, ""); }); return [...s].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())); };
  const drawFolders = () => {
    const side = q(".mb-side");
    const counts = new Map(); let top = 0;
    list.forEach((m) => {
      const d = dirOf(m);
      if (!d) { top++; return; }
      d.split("/").reduce((acc, seg) => { const p = acc ? acc + "/" + seg : seg; counts.set(p, (counts.get(p) || 0) + 1); return p; }, "");
    });
    if (!counts.size) { side.style.display = "none"; folder = ""; return; }
    side.style.display = "";
    const rows = [["", "All", list.length, 0]];
    allDirs().forEach((p) => rows.push([p, p.split("/").pop(), counts.get(p), p.split("/").length - 1]));
    if (top) rows.push([TOP, "(top level)", top, 0]);
    side.innerHTML = rows.map(([p, label, n, depth]) => '<div class="mb-fold' + (p === folder ? " on" : "") + '" data-p="' + esc(p) + '" style="padding-left:' + (6 + depth * 12) + 'px" title="' + esc(p || "All") + '"><span>' + esc(label) + "</span><small>" + n + "</small></div>").join("");
    side.querySelectorAll(".mb-fold").forEach((el) => el.onclick = () => { folder = el.dataset.p; draw(); });
  };

  // ---- selection bar: what you can do with the ticked files ----
  const listOrder = () => list.filter((m) => selected.has(m.id));
  const drawSel = () => {
    const bar = q(".mb-selbar");
    const n = selected.size;
    root.querySelectorAll(".mb-card").forEach((c) => c.classList.toggle("sel", selected.has(c.dataset.id)));
    root.querySelector(".mb-grid").classList.toggle("picking", n > 0);
    if (!n) { bar.style.display = "none"; return; }
    const one = n === 1 ? listOrder()[0] : null;
    bar.style.display = "flex";
    bar.innerHTML = '<b>' + n + " selected</b>" +
      (kind === "loras" ? '<button class="mb-b pri" data-s="add">Add ' + n + " to LoRA loader</button>" :
        one ? (ADD[kind] || []).map((s, j) => '<button class="mb-b pri" data-s="addk" data-j="' + j + '">' + esc(s.label) + "</button>").join("") + (ADD[kind] ? '<button class="mb-b' + (target ? " pri" : "") + '" data-s="violet">' + (target ? "Use in this node" : "Violet loader") + "</button>" : "") : '<span class="mb-sub">Pick one file to put it in a loader</span>') +
      '<button class="mb-b" data-s="move">Move to folder...</button>' + (one ? '<button class="mb-b" data-s="ren">Rename</button>' : "") +
      '<button class="mb-b" data-s="recycle">Recycle bin</button><button class="mb-b" data-s="delete" style="border-color:#DC2626">Delete permanently</button>' +
      '<span style="flex:1"></span><button class="mb-b" data-s="all">Select all shown</button><button class="mb-b" data-s="clear">Clear</button>';
    bar.querySelectorAll("[data-s]").forEach((b) => b.onclick = () => act(b.dataset.s, b.dataset.j));
  };
  const afterChange = async (text, withUndo) => { selected.clear(); forceScan = true; await load(); msg(text, withUndo); try { await app.refreshComboInNodes(); } catch (e) { /* older frontend */ } };
  const act = async (a, j) => {
    const items = listOrder();
    try {
      if (a === "clear") { selected.clear(); drawSel(); return; }
      if (a === "all") { shown.forEach((m) => selected.set(m.id, m)); drawSel(); return; }
      if (!items.length) return;
      if (a === "add") {
        let last = "";
        for (const m of items) last = window.VioletLoraLoader.add(m);
        selected.clear(); drawSel(); msg("Added " + items.length + " LoRA(s) to the LoRA loader. " + (items.length > 1 ? "" : last)); return;
      }
      if (a === "addk") { msg(slotInto(ADD[kind][+j], items[0], flags)); selected.clear(); drawSel(); return; }
      if (a === "violet") { msg(violetLoader(items[0], kind)); selected.clear(); drawSel(); return; }
      if (a === "ren") return renameDlg(items[0], () => afterChange("Renamed."));
      if (a === "move") return moveDlg(items, allDirs(), kind, (r) => afterChange(r));
      if (a === "recycle" || a === "delete") {
        const text = a === "recycle" ? "Move " + items.length + " file(s) and their preview / info files to the Recycle Bin?" : "DELETE " + items.length + " file(s) and their preview / info files permanently?\n\nThis cannot be undone.";
        if (!(await askDlg(text, a === "recycle" ? "Move to Recycle Bin" : "Delete permanently", a === "delete"))) return;
        const r = await post("/violet/model_remove", { ids: items.map((m) => m.id), mode: a, kind });
        const ok = r.results.filter((x) => x.ok).length, bad = r.results.filter((x) => !x.ok);
        await afterChange((a === "recycle" ? "Moved " : "Deleted ") + ok + " file(s)." + (bad.length ? " " + bad.length + " failed: " + bad[0].error : ""));
      }
    } catch (e) { msg("Failed: " + e.message); }
  };

  const sortFn = {
    name: (a, b) => (a.alias || relOf(a)).toLowerCase().localeCompare((b.alias || relOf(b)).toLowerCase()),
    big: (a, b) => (b.size || 0) - (a.size || 0),
    base: (a, b) => String(a.base_model || "~").toLowerCase().localeCompare(String(b.base_model || "~").toLowerCase()) || sortFn.name(a, b),
    new: (a, b) => String((b.civitai || {}).published_at || "").localeCompare(String((a.civitai || {}).published_at || "")) || sortFn.name(a, b),
  };
  const draw = () => {
    const grid = q(".mb-grid");
    const f = filter.toLowerCase();
    drawFolders();
    shown = list.filter((m) => inFolder(m) && (!f || (m.name + " " + m.alias + " " + m.base_model + " " + (m.trigger_words || []).join(" ") + " " + ((m.civitai || {}).model_name || "")).toLowerCase().includes(f))).sort(sortFn[sort]);
    grid.innerHTML = shown.map((m, i) =>
      '<div class="mb-card' + (selected.has(m.id) ? " sel" : "") + '" data-i="' + i + '" data-id="' + esc(m.id) + '">' +
      (m.remote ? "" : '<div class="mb-chk" title="Select">✓</div>') +
      '<div class="mb-tools"><button class="mb-b" data-a="info" title="Full details">ⓘ</button>' + (m.remote ? "" : '<button class="mb-b" data-a="ren" title="Rename">✎</button>') + "</div>" +
      (m.preview ? '<img class="mb-thumb" loading="lazy" src="' + m.preview + '">' : '<div class="mb-thumb mb-nothumb">no preview</div>') +
      '<div class="mb-body"><div class="mb-name">' + esc(m.alias || (m.civitai || {}).model_name || relOf(m).replace(/^.*[\\/]/, "")) + "</div>" +
      '<div class="mb-sub">' + esc(relOf(m)) + "</div>" +
      '<div class="mb-pills">' + (m.precision ? '<span class="mb-pill g">' + esc(m.precision) + "</span>" : "") +
      (m.base_model ? '<span class="mb-pill">' + esc(m.base_model) + "</span>" : "") +
      '<span class="mb-pill">' + mb(m.size) + "</span>" + (m.remote ? '<span class="mb-pill">on ' + esc(m.source) + "</span>" : "") + "</div></div></div>").join("") ||
      '<div class="mb-sub">Nothing here. Use Folders / settings or Library to add a directory.</div>';
    grid.querySelectorAll(".mb-card").forEach((card) => {
      const m = shown[+card.dataset.i];
      attachHover(card, async () => m);
      card.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-a]");
        if (btn) {
          e.stopPropagation();
          if (btn.dataset.a === "info") m.remote ? msg(m.path + "  ·  " + mb(m.size)) : detail(m, (u) => { const i = list.findIndex((x) => x.id === m.id); if (i >= 0) list[i] = u; draw(); });
          else if (btn.dataset.a === "ren") renameDlg(m, () => afterChange("Renamed."));
          return;
        }
        if (m.remote) return;
        // click selects; shift-click selects everything between this and the last one clicked
        if (e.shiftKey && lastId && lastId !== m.id) {
          const a = shown.findIndex((x) => x.id === lastId), b = +card.dataset.i;
          if (a >= 0) shown.slice(Math.min(a, b), Math.max(a, b) + 1).forEach((x) => selected.set(x.id, x));
        } else if (selected.has(m.id)) selected.delete(m.id);
        else selected.set(m.id, m);
        lastId = m.id;
        drawSel();
      });
    });
    drawSel();
  };
  const load = async () => {
    hideHover();
    drawTabs(); msg("Loading " + kinds[kind] + "...");
    q(".mb-grid").innerHTML = "";
    if (src) {
      try { list = await (await fetch("/violet/net/catalog?src=" + encodeURIComponent(src) + "&kind=" + kind)).json(); } catch (e) { list = []; }
      msg(list.length + " on " + src + ". Browse only: these files live on that computer. Share its folder and add the network path as a Library to load them here, or run the graph over there.");
      draw(); return;
    }
    list = await (await fetch("/violet/model_catalog?kind=" + kind + (forceScan ? "&refresh=1" : ""))).json();
    forceScan = false;
    overview.counts[kind] = list.length; drawTabs();
    for (const id of [...selected.keys()]) if (!list.some((m) => m.id === id)) selected.delete(id);
    msg(list.length + " " + (kind === "loras" ? "LoRAs" : "models") + ". Click to select (Shift-click for a range), hover for details.");
    draw();
  };
  const srcSel = q(".mb-src");
  const loadSources = async () => {
    let d = { sources: [] };
    try { d = await (await fetch("/violet/net/sources")).json(); } catch (e) { /* older backend */ }
    const up = Object.fromEntries((d.status || []).map((s) => [s.name, s]));
    srcSel.innerHTML = '<option value="">This PC</option>' + d.sources.map((s) => '<option value="' + esc(s.name) + '">' + esc(s.name) + (up[s.name] && up[s.name].up ? " (online)" : " (offline)") + "</option>").join("");
    srcSel.value = src;
  };
  srcSel.onchange = () => { src = srcSel.value; selected.clear(); load(); };
  q("[data-a=net]").onclick = () => netDialog(loadSources);
  loadSources();
  q(".mb-search").oninput = (e) => { filter = e.target.value; draw(); };
  q(".mb-sort").onchange = (e) => { sort = e.target.value; draw(); };
  q("[data-a=rescan]").onclick = () => { forceScan = true; load(); };
  q("[data-a=lib]").onclick = () => libraryDialog(() => { forceScan = true; load(); });
  let fetching = false;
  q("[data-a=fetchall]").onclick = async (ev) => {
    if (src) return msg("Fetching is for files on this PC.");
    if (fetching) { fetching = false; return; }
    const todo = list.filter((m) => inFolder(m) && !m.has_fetch);
    if (!todo.length) return msg("Everything shown already has CivitAI data.");
    fetching = true; ev.target.textContent = "Stop";
    let done = 0, hit = 0;
    for (const m of todo) {
      if (!fetching) break;
      msg("Fetching " + (++done) + "/" + todo.length + ": " + rel(m.id));
      try { const d = await post("/violet/model_fetch", { id: m.id }); if (d.has_fetch) hit++; const i = list.findIndex((x) => x.id === m.id); if (i >= 0) list[i] = d; } catch (e) { /* keep going */ }
    }
    fetching = false; ev.target.textContent = "Fetch CivitAI";
    draw(); msg("Done. " + hit + " of " + done + " found on CivitAI.");
    // the scan just learned more base models: offer to group the loose files
    try {
      const p = await (await fetch("/violet/organize_plan?kind=" + kind)).json();
      const n = p.groups.reduce((a, g) => a + g.files.length, 0);
      if (n && await askDlg(n + " loose file(s) are not in a folder and their metadata says what they are (for example " + p.groups.slice(0, 3).map((g) => g.folder).join(", ") + ").\n\nGroup them into folders now? You will see the list first.", "Show me", false)) orgDlg(kind, (r) => afterChange(r, true));
    } catch (e) { /* plan unavailable */ }
  };
  q("[data-a=org]").onclick = () => orgDlg(kind, (r) => afterChange(r, true));
  q("[data-a=dirs]").onclick = () => (kind === "loras" && window.VioletLoraLoader ? window.VioletLoraLoader.folders() : dirsDialog(kind));
  q("[data-a=dups]").onclick = () => dupDialog(kind, kinds[kind], () => { forceScan = true; load(); });
  load();
}

// Move the ticked files into a folder (an existing one, or a new name).
function moveDlg(items, dirs, kind, done) {
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  back.innerHTML = '<div style="width:min(460px,92vw);background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif">' +
    '<div style="font-size:13px;color:#C89BF5;margin-bottom:8px">Move ' + items.length + " file(s) to a folder</div>" +
    '<select class="mv-pick" style="width:100%;box-sizing:border-box;background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:4px;padding:6px;margin-bottom:6px"><option value="">Pick an existing folder...</option>' + dirs.map((d) => '<option value="' + esc(d) + '">' + esc(d) + "</option>").join("") + "</select>" +
    '<input class="mv-new" placeholder="or type a new folder name" style="width:100%;box-sizing:border-box;background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:4px;padding:6px">' +
    '<div class="vd-msg" style="margin:8px 0">The folder is made inside the library folder each file is already in. Previews and info files go with them. A saved workflow that names a moved file needs re-pointing. You get an Undo afterwards.</div>' +
    '<div class="vd-row"><button class="vd-btn pri" data-a="go">Move</button><button class="vd-btn" data-a="x">Cancel</button></div><div class="vd-msg st" style="margin-top:6px"></div></div>';
  document.body.appendChild(back);
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  const st = back.querySelector(".st");
  back.querySelector("[data-a=x]").onclick = () => back.remove();
  back.querySelector("[data-a=go]").onclick = async () => {
    const f = back.querySelector(".mv-new").value.trim() || back.querySelector(".mv-pick").value;
    if (!f) { st.textContent = "Pick a folder or type a name."; return; }
    st.textContent = "Moving...";
    try {
      const r = await post("/violet/organize_apply", { kind, moves: items.map((m) => ({ id: m.id, folder: f })) });
      const ok = r.results.filter((x) => x.ok).length, bad = r.results.filter((x) => !x.ok);
      back.remove(); done("Moved " + ok + " file(s) to " + f + "." + (bad.length ? " " + bad.length + " not moved: " + bad[0].error : ""), true);
    } catch (e) { st.textContent = "Failed: " + e.message; }
  };
}

// Organize: loose files grouped by the base model in their metadata. Review, edit the folder names, then move.
async function orgDlg(kind, done) {
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  back.innerHTML = '<div style="width:min(760px,94vw);max-height:84vh;display:flex;flex-direction:column;background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif">' +
    '<div style="font-size:13px;color:#C89BF5;margin-bottom:4px">Organize loose files into folders</div><div class="vd-msg st">Reading metadata...</div>' +
    '<div class="body" style="overflow-y:auto;flex:1;margin:8px 0"></div><div class="vd-row"><button class="vd-btn pri" data-a="go" disabled>Move checked files</button><button class="vd-btn" data-a="undo" title="Put back the last batch that was moved">Undo last move</button><button class="vd-btn" data-a="x">Close</button></div></div>';
  document.body.appendChild(back);
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  back.querySelector("[data-a=x]").onclick = () => back.remove();
  const st = back.querySelector(".st"), body = back.querySelector(".body"), go = back.querySelector("[data-a=go]");
  back.querySelector("[data-a=undo]").onclick = async () => { try { const r = await post("/violet/organize_undo", { kind }); back.remove(); done(r.note); } catch (e) { st.textContent = "Failed: " + e.message; } };
  let plan;
  try { plan = await (await fetch("/violet/organize_plan?kind=" + kind)).json(); } catch (e) { st.textContent = "Could not read the library: " + e; return; }
  const total = plan.groups.reduce((a, g) => a + g.files.length, 0);
  st.textContent = plan.loose ? total + " file(s) can be grouped" + (plan.unknown.length ? "; " + plan.unknown.length + " have no base model in their metadata and are left alone (select them in the browser and use Move to folder...)." : ".") : "Nothing loose: every file is already in a folder.";
  plan.groups.forEach((g, gi) => {
    const box = document.createElement("div");
    box.style.cssText = "border:1px solid #2A2140;border-radius:6px;padding:6px 8px;margin:6px 0";
    box.innerHTML = '<div style="display:flex;gap:6px;align-items:center;margin-bottom:4px"><input type="checkbox" class="gall" checked><b>Folder</b><input class="gname" value="' + esc(g.folder) + '" style="background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:4px;padding:3px 6px"><span class="vd-msg">' + g.files.length + " file(s)</span></div>" +
      g.files.map((f, fi) => '<label style="display:flex;gap:6px;align-items:center;padding:1px 0"><input type="checkbox" class="gf" data-g="' + gi + '" data-f="' + fi + '" checked><span style="flex:1;word-break:break-all">' + esc(f.name) + '</span><small style="color:#B8ADCF">' + esc(f.why) + "</small></label>").join("");
    box.querySelector(".gall").onchange = (e) => { box.querySelectorAll(".gf").forEach((c) => c.checked = e.target.checked); recount(); };
    body.appendChild(box);
  });
  const recount = () => { const n = body.querySelectorAll(".gf:checked").length; go.disabled = !n; go.textContent = "Move " + n + " checked file(s)"; };
  body.addEventListener("change", recount); recount();
  go.onclick = async () => {
    const moves = [];
    body.querySelectorAll(".gf:checked").forEach((c) => { const g = plan.groups[+c.dataset.g]; const name = c.closest("div").querySelector(".gname").value.trim() || g.folder; moves.push({ id: g.files[+c.dataset.f].id, folder: name }); });
    if (!moves.length) return;
    if (!(await askDlg("Move " + moves.length + " file(s) into folders?\n\nTheir preview and info files go with them. Saved workflows that name a moved file need re-pointing. You can undo this right after.", "Move", false))) return;
    go.disabled = true; st.textContent = "Moving...";
    try {
      const r = await post("/violet/organize_apply", { kind, moves });
      const ok = r.results.filter((x) => x.ok).length, bad = r.results.filter((x) => !x.ok);
      back.remove(); done("Moved " + ok + " file(s) into folders." + (bad.length ? " " + bad.length + " not moved: " + bad[0].error : ""));
    } catch (e) { st.textContent = "Failed: " + e.message; go.disabled = false; }
  };
}

// Violet Model Loader node: model kinds set model_name, VAE / text encoders fill the optional inputs.
function violetLoader(m, kind) {
  const canvas = app.canvas;
  const sel = Object.values(canvas.selected_nodes || {})[0];
  const isViolet = sel && sel.type === "SolarVioletModelLoader";
  if (kind === "vae") return place("SolarVioletModelLoader", "vae_name", m.id);
  if (kind === "text_encoders") return place("SolarVioletModelLoader", "clip_name", m.id);
  return place("SolarVioletModelLoader", "model_name", m.id) + (isViolet ? "" : "");
}

async function detail(m, changed) {
  const V = window.VioletLoraDetail;
  V.closePop();
  if (detailPop) { detailPop.remove(); detailPop = null; }   // one card at a time, so closing it never reveals an older one
  const pop = document.createElement("div");
  pop.className = "vd-pop"; pop.style.zIndex = 100001;
  document.body.appendChild(pop);
  detailPop = pop;
  const kill = () => { pop.remove(); if (detailPop === pop) detailPop = null; document.removeEventListener("keydown", onEsc, true); };
  const onEsc = (e) => { if (e.key === "Escape") kill(); };
  document.addEventListener("keydown", onEsc, true);
  const draw = (info) => {
    const c = info.civitai || {}, g = c.gen || {};
    const imgs = (c.images || []).filter((i) => i.type !== "video");
    pop.innerHTML = '<header><h4>' + esc(info.alias || c.model_name || rel(info.id)) + '</h4><button class="vd-x">✕</button></header><div class="vd-body">' +
      (info.preview ? '<img class="vd-hero" src="' + info.preview + '">' : "") +
      '<div class="vd-row">' + [info.base_model, info.precision, c.version_name, c.creator && "by " + c.creator, mb(info.size), c.published_at && String(c.published_at).slice(0, 10)]
        .filter(Boolean).map((t, i) => '<span class="vd-pill' + (i === 1 ? " g" : "") + '">' + esc(t) + "</span>").join("") + "</div>" +
      '<div class="vd-msg">' + esc(info.path) + "</div>" +
      (g.sampler || g.cfg != null || g.steps != null ? '<div class="vd-row">' + [g.sampler && g.sampler + (g.scheduler ? " / " + g.scheduler : ""), g.cfg != null && "CFG " + g.cfg, g.steps != null && g.steps + " steps"].filter(Boolean).map((t) => '<span class="vd-pill g">' + esc(t) + "</span>").join("") + "</div>" : "") +
      (c.version_description ? '<div class="vd-sec">Version notes</div><div class="vd-text">' + esc(c.version_description) + "</div>" : "") +
      (c.model_description ? '<div class="vd-sec">Model page description</div><div class="vd-text">' + esc(c.model_description) + "</div>" : "") +
      ((c.tags || []).length ? '<div class="vd-sec">Tags</div><div class="vd-row">' + c.tags.map((t) => '<span class="vd-pill">' + esc(t) + "</span>").join("") + "</div>" : "") +
      (imgs.length ? '<div class="vd-sec">Example images (' + imgs.length + ')</div><div class="vd-gal">' + imgs.slice(0, 40).map((im, i) => '<img data-i="' + i + '" loading="lazy" src="' + esc(im.url) + '">').join("") + '</div><div class="vd-text ex" style="display:none"></div>' : "") +
      '<div class="vd-row"><button class="vd-btn pri" data-a="fetch">' + (info.has_fetch ? "Refresh from CivitAI" : "Fetch from CivitAI") + "</button>" +
      (info.has_fetch ? '<button class="vd-btn" data-a="dl">Download all preview images + captions</button>' : "") +
      (c.page_url ? '<a class="vd-btn" target="_blank" rel="noopener" href="' + esc(c.page_url) + '" style="text-decoration:none">Open page</a>' : "") +
      '</div><div class="vd-msg st"></div></div>';
    pop.querySelector(".vd-x").onclick = kill;
    const st = pop.querySelector(".st"), ex = pop.querySelector(".ex");
    pop.querySelectorAll(".vd-gal img").forEach((el) => el.onclick = () => {
      const im = imgs[+el.dataset.i]; ex.style.display = "block";
      ex.textContent = (im.prompt ? "Prompt:\n" + im.prompt : "(no prompt published)") + (im.negative ? "\n\nNegative:\n" + im.negative : "");
    });
    pop.querySelector("[data-a=fetch]").onclick = async (e) => {
      e.target.disabled = true; st.textContent = "Contacting CivitAI (large files are hashed first, this can take a few minutes)...";
      try { const d = await post("/violet/model_fetch", { id: info.id, force: true }); draw(d); changed && changed(d);
        if (!d.has_fetch) pop.querySelector(".st").textContent = "Not found on CivitAI."; }
      catch (err) { st.textContent = "Failed: " + err.message; e.target.disabled = false; }
    };
    const dl = pop.querySelector("[data-a=dl]");
    if (dl) dl.onclick = async () => {
      dl.disabled = true; st.textContent = "Downloading...";
      try { const r = await post("/violet/model_previews", { id: info.id }); st.textContent = "Saved " + r.saved + " images + captions to " + r.folder; }
      catch (err) { st.textContent = "Failed: " + err.message; }
      dl.disabled = false;
    };
  };
  const first = await (await fetch("/violet/model_info?id=" + encodeURIComponent(m.id))).json();
  draw(first);
}

function renameDlg(m, done) {
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  const stem = rel(m.id).replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, "");
  back.innerHTML = '<div style="width:min(460px,92vw);background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif">' +
    '<div style="font-size:13px;color:#C89BF5;margin-bottom:6px">Rename model</div><input class="rn" style="width:100%;box-sizing:border-box;background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:4px;padding:6px">' +
    '<div class="vd-msg" style="margin:8px 0">Display name only changes how it looks in Violet UIs. Renaming the file also renames its preview and info files; workflows naming the old file need re-pointing.</div>' +
    '<div class="vd-row"><button class="vd-btn pri" data-m="display">Change display name</button><button class="vd-btn" data-m="file">Rename file on disk</button><button class="vd-btn" data-m="x">Cancel</button></div><div class="vd-msg st"></div></div>';
  document.body.appendChild(back);
  const inp = back.querySelector(".rn"); inp.value = m.alias || stem; inp.focus(); inp.select();
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  back.querySelectorAll("[data-m]").forEach((b) => b.onclick = async () => {
    if (b.dataset.m === "x") return back.remove();
    if (b.dataset.m === "file" && !confirm("Rename the file on disk?")) return;
    try { const d = await post("/violet/model_rename", { id: m.id, mode: b.dataset.m, value: inp.value }); back.remove(); done(d.id); }
    catch (e) { back.querySelector(".st").textContent = "Failed: " + e.message; }
  });
  inp.addEventListener("keydown", (e) => { if (e.key === "Escape") back.remove(); e.stopPropagation(); });
}

// Duplicate finder: identical files, the same CivitAI model across versions, name families. Tick what to remove
// (Shift-click for a range), hover a row for its card, then send to the Recycle Bin, delete for good, or set aside.
async function dupDialog(kind, label, reload) {
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  back.innerHTML = '<div style="width:min(860px,95vw);max-height:86vh;display:flex;flex-direction:column;background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif">' +
    '<div style="font-size:13px;color:#C89BF5;margin-bottom:6px">Duplicate ' + esc(label) + '</div><div class="vd-msg st">Scanning (large files are sampled, not fully hashed)...</div>' +
    '<div class="vd-row" style="margin:6px 0"><button class="vd-btn" data-a="auto" title="Tick everything marked remove">Tick suggested</button><button class="vd-btn" data-a="none">Clear ticks</button></div>' +
    '<div class="body" style="overflow-y:auto;flex:1;margin:4px 0"></div>' +
    '<div class="vd-row"><button class="vd-btn pri" data-a="recycle">Recycle bin</button><button class="vd-btn" data-a="quarantine" title="Reversible: moved into a _violet_duplicates folder next to the file">Set aside (_violet_duplicates)</button><button class="vd-btn" data-a="delete" style="border-color:#DC2626">Delete permanently</button><span style="flex:1"></span><button class="vd-btn" data-a="x">Close</button></div><div class="vd-msg act" style="margin-top:6px"></div></div>';
  document.body.appendChild(back);
  back.addEventListener("mousedown", (e) => { if (e.target === back) { hideHover(); back.remove(); } });
  back.querySelector("[data-a=x]").onclick = () => { hideHover(); back.remove(); };
  const st = back.querySelector(".st"), body = back.querySelector(".body"), actMsg = back.querySelector(".act");
  let lastBox = null;
  const boxes = () => [...body.querySelectorAll("input[type=checkbox]")];
  const scan = async () => {
    hideHover(); body.innerHTML = ""; st.textContent = "Scanning (large files are sampled, not fully hashed)...";
    let res;
    try { res = await (await fetch("/violet/model_duplicates?kind=" + kind)).json(); } catch (e) { st.textContent = "Scan failed: " + e; return; }
    st.textContent = res.groups.length + " group(s) in " + res.scanned + " files. Reclaimable: " + mb(res.reclaimable_bytes) + ". Hover a row for its details. Nothing happens until you press a button below.";
    res.groups.forEach((g, gi) => {
      const box = document.createElement("div");
      box.style.cssText = "border:1px solid #2A2140;border-radius:6px;padding:6px 8px;margin:6px 0";
      box.innerHTML = "<b>" + esc(g.reason) + "</b> (" + esc(g.confidence) + " confidence)";
      g.members.forEach((m) => {
        const row = document.createElement("label");
        row.style.cssText = "display:flex;gap:6px;align-items:center;padding:3px 2px;border-radius:4px";
        row.onmouseenter = () => { row.style.background = "#1E1830"; }; row.onmouseleave = () => { row.style.background = ""; };
        row.innerHTML = '<input type="checkbox" data-id="' + esc(m.name) + '" data-g="' + gi + '" data-sug="' + (m.verdict === "remove" ? 1 : 0) + '">' +
          '<span class="vd-pill' + (m.verdict === "keep" ? " g" : "") + '">' + esc(m.verdict) + "</span>" +
          "<span style='flex:1;word-break:break-all'>" + esc(rel(m.name)) + "<br><small style='color:#8F84A8'>" + esc(m.where || "") + "</small></span><small style='color:#B8ADCF;text-align:right'>" +
          esc([m.version, m.published, m.precision, mb(m.size), m.note].filter(Boolean).join(" · ")) + "</small>";
        attachHover(row, () => modelInfo(m.name));
        const cb = row.querySelector("input");
        cb.addEventListener("click", (e) => {
          if (e.shiftKey && lastBox && lastBox !== cb) {
            const all = boxes(), a = all.indexOf(lastBox), b = all.indexOf(cb);
            all.slice(Math.min(a, b), Math.max(a, b) + 1).forEach((x) => { x.checked = cb.checked; });
          }
          lastBox = cb;
        });
        box.appendChild(row);
      });
      body.appendChild(box);
    });
  };
  const ticked = () => boxes().filter((c) => c.checked);
  back.querySelector("[data-a=auto]").onclick = () => boxes().forEach((c) => { c.checked = c.dataset.sug === "1"; });
  back.querySelector("[data-a=none]").onclick = () => boxes().forEach((c) => { c.checked = false; });
  ["recycle", "quarantine", "delete"].forEach((mode) => back.querySelector("[data-a=" + mode + "]").onclick = async () => {
    const t = ticked(), ids = t.map((c) => c.dataset.id);
    if (!ids.length) { actMsg.textContent = "Tick the files you want to remove first."; return; }
    // never remove every copy of something
    const per = {}; boxes().forEach((c) => { const g = c.dataset.g; per[g] = per[g] || { all: 0, on: 0 }; per[g].all++; if (c.checked) per[g].on++; });
    if (Object.values(per).some((p) => p.all > 0 && p.on === p.all)) { actMsg.textContent = "Every copy in a group is ticked. Leave at least one in each group."; return; }
    const text = mode === "recycle" ? "Move " + ids.length + " file(s) and their preview / info files to the Recycle Bin?" :
      mode === "quarantine" ? "Set aside " + ids.length + " file(s) in a _violet_duplicates folder next to them? You can move them back any time." :
        "DELETE " + ids.length + " file(s) and their preview / info files permanently?\n\nThis cannot be undone.";
    if (!(await askDlg(text, mode === "recycle" ? "Move to Recycle Bin" : mode === "quarantine" ? "Set aside" : "Delete permanently", mode === "delete"))) return;
    actMsg.textContent = "Working...";
    try {
      const r = await post("/violet/model_remove", { ids, mode, kind });
      const ok = r.results.filter((x) => x.ok).length, bad = r.results.filter((x) => !x.ok);
      actMsg.textContent = (mode === "delete" ? "Deleted " : mode === "recycle" ? "Moved to the Recycle Bin: " : "Set aside: ") + ok + " file(s)." + (bad.length ? " " + bad.length + " failed: " + bad[0].error : "");
      try { await app.refreshComboInNodes(); } catch (e) { /* older frontend */ }
      await scan(); reload && reload();
    } catch (e) { actMsg.textContent = "Failed: " + e.message; }
  });
  scan();
}

async function dirsDialog(startKind) {
  const cfg = await (await fetch("/violet/model_dirs")).json();
  const edits = {};   // kind -> text, kept while the category dropdown moves between kinds
  Object.keys(cfg.kinds).forEach((k) => { edits[k] = ((cfg.model_dirs || {})[k] || []).join("\n"); });
  let cur = cfg.kinds[startKind] ? startKind : Object.keys(cfg.kinds)[0];
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  back.innerHTML = '<div class="mb-dirs" style="width:min(560px,94vw);background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif">' +
    '<div style="font-size:13px;color:#C89BF5;margin-bottom:6px">Extra model folders (one path per line, all loaders see them)</div>' +
    '<select class="mb-src" data-a="kind" style="max-width:none;width:100%;margin-bottom:6px">' + Object.entries(cfg.kinds).map(([k, l]) => '<option value="' + k + '">' + esc(l) + "</option>").join("") + '</select>' +
    '<textarea data-a="text" style="width:100%;min-height:130px;box-sizing:border-box"></textarea>' +
    '<div class="vd-row" style="margin-top:8px"><button class="vd-btn pri" data-a="save">Save</button><button class="vd-btn" data-a="x">Cancel</button></div><div class="vd-msg st"></div></div>';
  document.body.appendChild(back);
  const sel = back.querySelector("[data-a=kind]"), ta = back.querySelector("[data-a=text]");
  const show = (k) => { edits[cur] = ta.value; cur = k; ta.value = edits[k] || ""; sel.value = k; };
  ta.value = edits[cur] || ""; sel.value = cur;
  sel.onchange = () => show(sel.value);
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  back.querySelector("[data-a=x]").onclick = () => back.remove();
  back.querySelector("[data-a=save]").onclick = async () => {
    edits[cur] = ta.value;
    const body = {};
    Object.entries(edits).forEach(([k, t]) => { body[k] = t.split("\n").map((s) => s.trim()).filter(Boolean); });
    try { await post("/violet/model_dirs", body); back.remove(); open(cur, { mode: "models" }); } catch (e) { back.querySelector(".st").textContent = "Failed: " + e.message; }
  };
}

const openModels = () => open("checkpoints", { mode: "models" });
const openLoras = () => open("loras", { mode: "loras" });
window.VioletModelBrowser = { open, close, openModels, openLoras };

app.registerExtension({
  name: "SolarViolet.ModelBrowser",
  commands: [
    { id: "Violet.ModelBrowser", label: "Violet Model Browser", function: openModels },
    { id: "Violet.LoraBrowser", label: "Violet LoRA Browser", function: openLoras },
  ],
  keybindings: [
    { combo: { key: "m", ctrl: true, alt: true }, commandId: "Violet.ModelBrowser" },
    { combo: { key: "l", ctrl: true, alt: true }, commandId: "Violet.LoraBrowser" },
  ],
  menuCommands: [{ path: ["Extensions"], commands: ["Violet.ModelBrowser", "Violet.LoraBrowser"] }],
  // top bar, beside the VRAM / temperature readouts
  actionBarButtons: [
    { icon: "pi pi-images", label: "LoRAs", tooltip: "Violet LoRA Browser (Ctrl+Alt+L)", onClick: openLoras },
    { icon: "pi pi-box", label: "Models", tooltip: "Violet Model Browser (Ctrl+Alt+M)", onClick: openModels },
  ],
});

// ---- the Violet loader nodes: info panel (what to connect, suggested sampler settings) ----
const LOADERS = ["SolarVioletModelLoader", "SolarVioletCheckpointLoader", "SolarVioletDiffusionLoader", "SolarVioletGGUFLoader"];

function paintPanel(node, advice, text, live) {
  const el = node.__violetPanel;
  if (!el) return;
  const warn = [];
  const outLinked = (name) => { const o = (node.outputs || []).find((x) => x.name === name); return !!(o && o.links && o.links.length); };
  const wv = (n) => { const w = (node.widgets || []).find((x) => x.name === n); return w ? w.value : "none"; };
  if (advice && advice.needs_clip && wv("clip_name") === "none" && outLinked("clip")) warn.push("CLIP output is connected but nothing supplies a text encoder. Pick clip_name or use a text encoder / CLIP loader node.");
  if (advice && advice.needs_vae && wv("vae_name") === "none" && outLinked("vae")) warn.push("VAE output is connected but nothing supplies a VAE. Pick vae_name or use a Load VAE node.");
  const sm = advice && advice.sampler;
  el.innerHTML = '<div style="white-space:pre-wrap">' + esc(text || "Pick a model to see what it needs.") + "</div>" +
    (warn.length ? '<div style="color:#F5A524;margin-top:4px">' + warn.map(esc).join("<br>") + "</div>" : "") +
    (sm ? '<button class="mb-b" style="margin-top:4px" data-a="cp">Copy sampler settings</button>' : "");
  const b = el.querySelector("[data-a=cp]");
  if (b) b.onclick = () => { try { navigator.clipboard.writeText(`sampler ${sm.sampler}, scheduler ${sm.scheduler}, steps ${sm.steps}, cfg ${sm.cfg}`); } catch (e) {} };
  node.setDirtyCanvas(true, true);
}

async function refreshPanel(node) {
  const w = (node.widgets || []).find((x) => x.name === "model_name");
  if (!w || !w.value || w.value === "none") return paintPanel(node, null, "", false);
  try {
    const r = await fetch("/violet/model_advice?id=" + encodeURIComponent(w.value));
    const a = r.ok ? await r.json() : null;
    paintPanel(node, a, a ? a.text : "No information for this file.", false);
  } catch (e) { paintPanel(node, null, "Could not read model information.", false); }
}

app.registerExtension({
  name: "SolarViolet.ModelLoaderNode",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!LOADERS.includes(nodeData.name)) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = created ? created.apply(this, arguments) : undefined;
      const self = this;
      this.addWidget("button", "Browse models", null, () => open("checkpoints", { mode: "models", target: self }));
      this.addWidget("button", "Browse VAE", null, () => open("vae", { mode: "models", target: self }));
      this.addWidget("button", "Browse text encoders", null, () => open("text_encoders", { mode: "models", target: self }));
      const el = document.createElement("div");
      el.style.cssText = "font:11px sans-serif;color:#D9D0EC;background:#0A0710;border:1px solid #2A2140;border-radius:6px;padding:6px 8px;min-height:60px;overflow:auto;box-sizing:border-box";
      this.addDOMWidget("violet_model_info", "custom", el, { serialize: false, hideOnZoom: false });
      this.__violetPanel = el;
      const node = this;
      const watch = (name) => {
        const w = (node.widgets || []).find((x) => x.name === name);
        if (!w) return;
        const cb = w.callback;
        w.callback = function () { const rr = cb ? cb.apply(this, arguments) : undefined; refreshPanel(node); return rr; };
      };
      ["model_name", "vae_name", "clip_name"].forEach(watch);
      const conf = this.onConfigure;
      this.onConfigure = function () { const rr = conf ? conf.apply(this, arguments) : undefined; setTimeout(() => refreshPanel(node), 50); return rr; };
      const conn = this.onConnectionsChange;
      this.onConnectionsChange = function () { const rr = conn ? conn.apply(this, arguments) : undefined; refreshPanel(node); return rr; };
      setTimeout(() => refreshPanel(node), 100);
      return r;
    };
  },
  setup() {
    // After a run the node reports what it actually loaded (adds "right now" status).
    api.addEventListener("violet.model_info", (e) => {
      const d = e.detail || {};
      const node = app.graph.getNodeById(+d.node);
      if (node) paintPanel(node, d.advice, d.text, true);
    });
    // Ask this tab to open a saved workflow (POST /violet/open_workflow {name}).
    api.addEventListener("violet.open_workflow", async (e) => {
      const name = ((e.detail || {}).name || "").replace(/\.json$/i, "");
      try {
        const r = await fetch("/userdata/" + encodeURIComponent("workflows/" + name + ".json"));
        if (!r.ok) throw new Error("not found: " + name);
        await app.loadGraphData(await r.json(), true, true, name);
      } catch (err) { console.warn("[Violet] open_workflow failed", err); }
    });
    // Another app (Violinet OS) asks this tab to add / fill a loader for a model file.
    api.addEventListener("violet.add_model", async (e) => {
      const d = e.detail || {};
      try {
        const flags = await (await fetch("/violet/model_catalog")).json();
        const m = { id: d.id, name: rel(d.id) };
        if (d.loader === "violet") place("SolarVioletModelLoader", d.kind === "vae" ? "vae_name" : d.kind === "text_encoders" ? "clip_name" : "model_name", d.id);
        else slotInto(ADD[d.kind][0], m, flags);
        app.extensionManager?.toast?.add?.({ severity: "info", summary: "Violet", detail: "Added " + m.name, life: 3000 });
      } catch (err) { console.warn("[Violet] add_model failed", err); }
    });
  },
});


async function netDialog(done) {
  const d = await (await fetch("/violet/net/sources")).json();
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  back.innerHTML = '<div style="width:min(560px,94vw);background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif">' +
    '<div style="font-size:13px;color:#C89BF5;margin-bottom:6px">Other computers (their ComfyUI address, one per line: name = http://host:port)</div>' +
    '<textarea style="width:100%;height:90px;background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:5px;padding:5px">' + esc(d.sources.map((s) => s.name + " = " + s.url).join("\n")) + "</textarea>" +
    '<div class="vd-msg">The other computer must run ComfyUI with --listen so this PC can reach it. Nothing needs installing there to browse.</div>' +
    '<div class="vd-row" style="margin-top:8px"><button class="vd-btn pri" data-a="save">Save</button><button class="vd-btn" data-a="x">Cancel</button></div></div>';
  document.body.appendChild(back);
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  back.querySelector("[data-a=x]").onclick = () => back.remove();
  back.querySelector("[data-a=save]").onclick = async () => {
    const sources = back.querySelector("textarea").value.split("\n").map((l) => l.split("=")).filter((p) => p.length >= 2)
      .map((p) => ({ name: p[0].trim(), url: p.slice(1).join("=").trim() }));
    await post("/violet/net/sources", { sources }); back.remove(); done && done();
  };
}

// Model libraries: use another program's model folders (Stability Matrix, a shared drive, a plain folder) as they are.
async function libraryDialog(done) {
  let st = { libraries: [], detected: [], layouts: {} };
  try { st = await (await fetch("/violet/library")).json(); } catch (e) { /* older backend */ }
  let libs = st.libraries.map((l) => ({ layout: l.layout, path: l.path }));
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  back.innerHTML = '<div style="width:min(640px,94vw);max-height:86vh;overflow:auto;background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif">' +
    '<div style="font-size:13px;color:#C89BF5;margin-bottom:6px">Model libraries</div>' +
    '<div class="vd-msg">Point ComfyUI at model folders another program keeps, for example Stability Matrix. Nothing is moved, renamed or linked: the folders are added to the search lists, so every loader and both browsers see the files. Stability Matrix\'s own folder names (Lora, StableDiffusion, VAE, TextEncoders...) are understood.</div>' +
    '<div class="lib-detected" style="margin:8px 0"></div><div class="lib-list" style="margin:8px 0"></div>' +
    '<div style="display:flex;gap:6px;align-items:center"><select class="lib-layout" style="background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:4px;padding:5px"><option value="stability">Stability Matrix</option><option value="comfy">ComfyUI-style folders</option></select>' +
    '<input class="lib-path" placeholder="Folder (for Stability Matrix: its install folder or its Models folder)" style="flex:1;box-sizing:border-box;background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:4px;padding:6px"><button class="vd-btn" data-a="add">Add</button></div>' +
    '<div class="vd-row" style="margin-top:10px"><button class="vd-btn pri" data-a="save">Save and rescan</button><button class="vd-btn" data-a="x">Close</button></div><div class="vd-msg lib-st" style="margin-top:6px"></div></div>';
  document.body.appendChild(back);
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  const q = (s) => back.querySelector(s);
  q("[data-a=x]").onclick = () => back.remove();
  const said = (t) => { q(".lib-st").textContent = t; };
  const paint = () => {
    q(".lib-detected").innerHTML = st.detected.length
      ? "<div style='margin-bottom:4px'>Found on this computer:</div>" + st.detected.map((p, i) => '<div style="display:flex;gap:6px;align-items:center;margin:2px 0"><span style="flex:1;word-break:break-all">Stability Matrix: ' + esc(p) + '</span><button class="vd-btn" data-d="' + i + '">Use</button></div>').join("")
      : "<div>No Stability Matrix install found in the usual places. If you have one, type its folder below.</div>";
    q(".lib-list").innerHTML = libs.length
      ? libs.map((l, i) => '<div style="display:flex;gap:6px;align-items:center;margin:2px 0"><span class="mb-pill">' + esc((st.layouts || {})[l.layout] || l.layout) + '</span><span style="flex:1;word-break:break-all">' + esc(l.path) + '</span><button class="vd-btn" data-r="' + i + '">Remove</button></div>').join("")
      : "<div style='color:#B8ADCF'>No libraries added yet.</div>";
    back.querySelectorAll("[data-d]").forEach((b) => b.onclick = () => { const p = st.detected[+b.dataset.d]; if (!libs.some((l) => l.path === p)) libs.push({ layout: "stability", path: p }); paint(); });
    back.querySelectorAll("[data-r]").forEach((b) => b.onclick = () => { libs.splice(+b.dataset.r, 1); paint(); });
  };
  q("[data-a=add]").onclick = () => {
    const p = q(".lib-path").value.trim();
    if (!p) return said("Type a folder first.");
    libs.push({ layout: q(".lib-layout").value, path: p }); q(".lib-path").value = ""; paint();
  };
  q("[data-a=save]").onclick = async () => {
    try {
      const r = await post("/violet/library", { libraries: libs });
      st = r.status; libs = st.libraries.map((l) => ({ layout: l.layout, path: l.path })); paint();
      const bad = st.libraries.filter((l) => !l.exists).map((l) => l.path);
      const n = Object.values(r.added || {}).reduce((a, b) => a + b, 0);
      said(bad.length ? "Folder not found: " + bad.join(", ") : "Saved. " + n + " new folder(s) added to ComfyUI's search lists.");
      try { await app.refreshComboInNodes(); } catch (e) { /* older frontend */ }
      done && done();
    } catch (e) { said("Failed: " + e.message); }
  };
  paint();
}
