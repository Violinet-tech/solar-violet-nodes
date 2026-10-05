// Violet Text Encoder frontend: four preset lines per side with prompt-group pickers, four system
// instruction presets, LLM provider / model picker with "attach to local process", trigger-word panel,
// and a settings dialog (API keys, local model folders, five prompt groups).

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const wget2 = (n, k) => (n.widgets || []).find((w) => w.name === k);
const SLOTS = 4;
const MODES = ["random", "cycle", "all", "first"];
const st = document.createElement("style");
st.textContent = `
  .vte { width:100%; display:flex; flex-direction:column; gap:6px; font-family:sans-serif; color:#F4F1FA; }
  .vte-side { border:1px solid #2A2140; border-radius:6px; padding:5px; background:#14101C; }
  .vte-head { display:flex; align-items:center; gap:6px; font-size:11px; font-weight:600; margin-bottom:4px; flex-wrap:wrap; }
  .vte-head.pos { color:#A5F0FB; } .vte-head.neg { color:#f0a7a7; } .vte-head.llm { color:#C89BF5; } .vte-head.trg { color:#C89BF5; }
  .vte-head span { flex:1; }
  .vte-btn { font-size:10px; padding:2px 7px; border-radius:4px; border:1px solid #2A2140; background:#1E1830; color:#F4F1FA; cursor:pointer; }
  .vte-btn:hover { background:#352A52; } .vte-btn.on { background:#6D28D9; border-color:#A855F7; }
  .vte-row { display:flex; gap:4px; align-items:flex-start; margin-bottom:4px; flex-wrap:wrap; }
  .vte-row.off { opacity:.45; }
  .vte-row input[type=text] { width:70px; font-size:10px; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:3px; padding:2px 3px; }
  .vte-row select, .vte-sel { font-size:10px; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:3px; max-width:118px; }
  .vte-row textarea { flex:1 1 150px; min-height:36px; resize:vertical; font-size:11px; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:3px; padding:3px; }
  .vte-msg { font-size:9px; color:#B8ADCF; min-height:11px; }
  .vte-chip { display:inline-block; font-size:10px; padding:2px 7px; margin:2px 3px 2px 0; border-radius:10px; background:#2A1A4A; color:#C89BF5; border:1px solid #6D28D9; }
  .vte-chip.tok { background:#10303A; border-color:#22D3EE; color:#A5F0FB; }
  .vte-modal { position:fixed; inset:0; background:rgba(0,0,0,.65); z-index:100001; display:flex; align-items:center; justify-content:center; }
  .vte-dlg { width:min(760px,94vw); max-height:88vh; overflow-y:auto; background:#14101C; color:#F4F1FA; border:1px solid #3A2D5C; border-radius:10px; padding:14px; font-family:sans-serif; font-size:12px; }
  .vte-dlg h3 { margin:0 0 8px; font-size:14px; color:#A855F7; } .vte-dlg h4 { margin:12px 0 4px; font-size:12px; color:#C89BF5; }
  .vte-dlg input[type=text], .vte-dlg input[type=password], .vte-dlg textarea { width:100%; box-sizing:border-box; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:4px; padding:4px 6px; font-size:11px; }
  .vte-dlg textarea { min-height:70px; }
  .vte-grid { display:grid; grid-template-columns:110px 1fr; gap:5px 8px; align-items:center; }
  .vte-grp { border:1px solid #2A2140; border-radius:6px; padding:6px; margin-bottom:6px; background:#14101C; }
`;
document.head.appendChild(st);

const blank = () => Array.from({ length: SLOTS }, () => ({ label: "", text: "", on: true, group: "", mode: "random" }));
const norm = (raw) => {
  const out = blank();
  if (Array.isArray(raw)) raw.slice(0, SLOTS).forEach((s, i) => { if (s && typeof s === "object") out[i] = { label: s.label || "", text: s.text || "", on: s.on !== false, group: s.group || "", mode: MODES.includes(s.mode) ? s.mode : "random" }; });
  return out;
};
const parse = (v) => { try { return norm(JSON.parse(v || "[]")); } catch { return blank(); } };
const hasContent = (slots) => slots.some((s) => s.text || s.label || s.group);
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const jget = async (url) => { try { const r = await api.fetchApi(url); return r.ok ? await r.json() : null; } catch { return null; } };
const jpost = async (url, body) => { try { const r = await api.fetchApi(url, { method: "POST", body: JSON.stringify(body) }); return r.ok ? await r.json() : null; } catch { return null; } };
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const btn = (label, tip, fn, cls = "") => { const b = el("button", "vte-btn " + cls, label); b.title = tip || ""; b.onclick = fn; return b; };
const stop = (e) => e.stopPropagation();

// ---------------- settings dialog ----------------
async function openSettings(onSaved) {
  const [cfg, pre] = await Promise.all([jget("/violet/llm/settings"), jget("/violet/presets")]);
  if (!cfg || !pre) { alert("Could not reach the Violet backend."); return; }
  const back = el("div", "vte-modal");
  const dlg = el("div", "vte-dlg");
  back.appendChild(dlg);
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  dlg.innerHTML = "<h3>Violet Text Encoder settings</h3>";
  const keyNames = [["gemini", "Gemini API key"], ["nvidia_nim", "NVIDIA NIM API key"], ["opencode", "OpenCode Zen API key"], ["openrouter", "OpenRouter API key"],
    ["lmstudio", "LM Studio API key (optional)"], ["ollama", "Ollama API key (optional)"]];
  dlg.insertAdjacentHTML("beforeend", "<h4>Providers</h4><div class='vte-msg'>Keys are stored on this PC in the Violet config and never sent back to the browser in full. Leave a masked key untouched to keep it. Environment variables GEMINI_API_KEY, NVIDIA_API_KEY and OPENCODE_API_KEY and OPENROUTER_API_KEY also work.</div>");
  const grid = el("div", "vte-grid");
  const inputs = {};
  keyNames.forEach(([k, label]) => {
    grid.appendChild(el("label", null, label));
    const i = el("input"); i.type = "password"; i.autocomplete = "off"; i.value = (cfg.keys || {})[k] || ""; inputs["key_" + k] = i; grid.appendChild(i);
  });
  ["ollama", "lmstudio", "openrouter", "opencode", "nvidia_nim", "gemini"].forEach((k) => {
    grid.appendChild(el("label", null, k + " URL"));
    const i = el("input"); i.type = "text"; i.placeholder = (cfg.defaults || {})[k] || ""; i.value = (cfg.urls || {})[k] || ""; inputs["url_" + k] = i; grid.appendChild(i);
  });
  grid.appendChild(el("label", null, "CivitAI API key"));
  const civ = el("input"); civ.type = "password"; civ.value = cfg.civitai_key || ""; grid.appendChild(civ);
  dlg.appendChild(grid);
  dlg.insertAdjacentHTML("beforeend", "<div class='vte-msg'>NVIDIA NIM lists only free chat models (embedding, rerank and safety models are hidden). The CivitAI key is optional and only helps with login-gated models.</div>");
  dlg.insertAdjacentHTML("beforeend", "<h4>Extra local model folders (one per line)</h4>");
  const dirs = el("textarea"); dirs.value = (cfg.local_dirs || []).join("\n"); dlg.appendChild(dirs);
  dlg.insertAdjacentHTML("beforeend", "<div class='vte-msg'>Any Hugging Face style model folder inside these (or inside ComfyUI's text_encoders folders) shows up in the Local model list. Vision-language and plain text models both work.</div>");

  dlg.insertAdjacentHTML("beforeend", "<h4>Prompt groups (up to 5)</h4><div class='vte-msg'>Each group is a named list of prompt pieces, one per line: five subjects, five locations, a sci-fi set, whatever you like. Pick a group on any preset line of the encoder and it will draw from it.</div>");
  const gbox = el("div");
  const groupEls = pre.groups.map((g) => {
    const w = el("div", "vte-grp");
    const top = el("div", "vte-row");
    const name = el("input"); name.type = "text"; name.value = g.name; name.style.width = "180px";
    const side = el("select", "vte-sel");
    ["positive", "negative"].forEach((v) => { const o = el("option", null, v); o.value = v; side.appendChild(o); });
    side.value = g.side;
    top.append(name, side);
    const ta = el("textarea"); ta.value = (g.items || []).join("\n"); ta.placeholder = "one prompt piece per line";
    w.append(top, ta); gbox.appendChild(w);
    return { name, side, ta };
  });
  dlg.appendChild(gbox);
  const msg = el("div", "vte-msg");
  const row = el("div", "vte-row");
  row.append(btn("Save", "", async () => {
    const keys = {}, urls = {};
    keyNames.forEach(([k]) => { keys[k] = inputs["key_" + k].value; });
    ["ollama", "lmstudio", "openrouter", "opencode", "nvidia_nim", "gemini"].forEach((k) => { urls[k] = inputs["url_" + k].value; });
    const a = await jpost("/violet/llm/settings", { keys, urls, civitai_key: civ.value, local_dirs: dirs.value.split("\n").map((x) => x.trim()).filter(Boolean) });
    const b = await jpost("/violet/presets", { groups: groupEls.map((g) => ({ name: g.name.value, side: g.side.value, items: g.ta.value.split("\n").map((x) => x.trim()).filter(Boolean) })) });
    msg.textContent = a && b ? "Saved." : "Save failed.";
    if (a && b) { if (onSaved) onSaved(b); setTimeout(() => back.remove(), 500); }
  }, "on"), btn("Close", "", () => back.remove()), msg);
  dlg.appendChild(row);
  document.body.appendChild(back);
}

// ---------------- node panel ----------------
function build(node) {
  const root = el("div", "vte");
  const wget = (k) => (node.widgets || []).find((w) => w.name === k);
  const sides = {};
  let groups = [];
  let instr = [];
  let activeInstr = 0;

  const groupNames = () => groups.map((g) => g.name);
  const commit = (kind) => { const w = wget(kind + "_presets_json"); if (w) w.value = JSON.stringify(sides[kind].slots); };
  const commitInstr = () => { const w = wget("instructions_json"); if (w) w.value = JSON.stringify(instr); };
  const resize = () => { setTimeout(() => { const h = root.scrollHeight + 8; if (widget && widget.__h !== h) { widget.__h = h; node.setSize([Math.max(node.size[0], 470), node.computeSize()[1]]); node.setDirtyCanvas(true, true); } }, 30); };
  let widget = null;
  root.__setWidget = (w) => { widget = w; };

  const render = (kind) => {
    const side = sides[kind];
    side.list.innerHTML = "";
    side.slots.forEach((s, i) => {
      const row = el("div", "vte-row" + (s.on ? "" : " off"));
      const cb = el("input"); cb.type = "checkbox"; cb.checked = s.on; cb.title = "Include this line";
      cb.onchange = () => { s.on = cb.checked; row.classList.toggle("off", !s.on); commit(kind); };
      const lab = el("input"); lab.type = "text"; lab.placeholder = `Line ${i + 1}`; lab.value = s.label;
      lab.oninput = () => { s.label = lab.value; commit(kind); };
      const gsel = el("select", "vte-sel"); gsel.title = "Draw extra pieces from a prompt group";
      const none = el("option", null, "no group"); none.value = ""; gsel.appendChild(none);
      groups.filter((g) => g.side === kind && g.items.length).forEach((g) => { const o = el("option", null, `${g.name} (${g.items.length})`); o.value = g.name; gsel.appendChild(o); });
      if (s.group && ![...gsel.options].some((o) => o.value === s.group)) { const o = el("option", null, s.group); o.value = s.group; gsel.appendChild(o); }
      gsel.value = s.group;
      const msel = el("select", "vte-sel"); msel.title = "How to pick from the group";
      MODES.forEach((m) => { const o = el("option", null, m); o.value = m; msel.appendChild(o); }); msel.value = s.mode;
      msel.style.display = s.group ? "" : "none";
      gsel.onchange = () => { s.group = gsel.value; msel.style.display = s.group ? "" : "none"; commit(kind); };
      msel.onchange = () => { s.mode = msel.value; commit(kind); };
      const ta = el("textarea");
      ta.placeholder = kind === "positive" ? "trigger words, subject, scene, location..." : "negative group...";
      ta.value = s.text;
      ta.oninput = () => { s.text = ta.value; commit(kind); };
      ["pointerdown", "wheel", "keydown"].forEach((ev) => ta.addEventListener(ev, stop));
      row.append(cb, lab, gsel, msel, ta);
      side.list.appendChild(row);
    });
    resize();
  };

  const mkSide = (kind, title) => {
    const box = el("div", "vte-side");
    const head = el("div", "vte-head " + (kind === "positive" ? "pos" : "neg"));
    const msg = el("div", "vte-msg");
    const say = (m) => { msg.textContent = m; setTimeout(() => { if (msg.textContent === m) msg.textContent = ""; }, 3000); };
    const list = el("div");
    sides[kind] = { slots: blank(), list, say };
    head.append(el("span", null, title),
      btn("Load saved", "Replace these four lines with the system-saved ones", async () => {
        const d = await jget("/violet/presets"); if (!d) return say("Could not reach server");
        sides[kind].slots = norm(d[kind]); render(kind); commit(kind); say("Loaded system presets");
      }),
      btn("Save to system", "Save these four lines so every new node starts with them", async () => {
        const r = await jpost("/violet/presets", { [kind]: sides[kind].slots }); say(r ? "Saved to system" : "Save failed");
      }));
    box.append(head, list, msg);
    return box;
  };

  // --- instruction presets ---
  const instBox = el("div", "vte-side");
  const instHead = el("div", "vte-head llm");
  const instTabs = el("span");
  const instMsg = el("div", "vte-msg");
  const instWidgetText = () => wget("enhance_instruction");
  const drawTabs = () => {
    instTabs.innerHTML = "";
    instr.forEach((s, i) => { const b = btn(`${i + 1}: ${(s.label || "").slice(0, 22) || "empty"}`, s.label, () => selectInstr(i), i === activeInstr ? "on" : ""); instTabs.appendChild(b); });
  };
  const selectInstr = (i) => {
    activeInstr = i; drawTabs();
    const w = instWidgetText(); if (w) { w.value = instr[i].text; if (w.inputEl) w.inputEl.value = instr[i].text; }
    instLabel.value = instr[i].label;
  };
  const instLabel = el("input"); instLabel.type = "text"; instLabel.style.width = "110px"; instLabel.placeholder = "preset name";
  instLabel.oninput = () => { instr[activeInstr].label = instLabel.value; commitInstr(); drawTabs(); };
  root.__syncInstr = () => { const w = instWidgetText(); if (w && instr[activeInstr]) { instr[activeInstr].text = w.value; commitInstr(); } };
  instHead.append(el("span", null, "Enhancer instruction presets"), instTabs, instLabel,
    btn("Keep edit", "Store what is in the Instruction box into this preset (session)", () => { root.__syncInstr(); instMsg.textContent = "Kept in this workflow."; }),
    btn("Save to system", "Save all four instruction presets", async () => { root.__syncInstr(); const r = await jpost("/violet/presets", { instructions: instr }); instMsg.textContent = r ? "Saved to system" : "Save failed"; }),
    btn("Reset defaults", "Restore the built-in four", async () => { const d = await jget("/violet/presets"); if (d) { instr = d.instructions; commitInstr(); selectInstr(0); } }));
  instBox.append(instHead, el("div", "vte-msg", "Pick a preset, then edit the Instruction box below. Trigger word handling is part of every default."), instMsg);

  // --- LLM picker ---
  const llmBox = el("div", "vte-side");
  const llmHead = el("div", "vte-head llm");
  // The model is always picked from a list the provider fills in; nobody types a model name.
  const modelSel = el("select", "vte-sel"); modelSel.style.cssText = "flex:1;min-width:180px;max-width:420px";
  const freeBox = el("label", "vte-msg"); freeBox.style.cssText = "display:none;align-items:center;gap:4px;cursor:pointer";
  const freeChk = document.createElement("input"); freeChk.type = "checkbox"; freeChk.checked = true;
  freeBox.append(freeChk, document.createTextNode("Free only"));
  const llmMsg = el("div", "vte-msg");
  const say = (m) => { llmMsg.textContent = m; };
  const setModel = (v) => { const w = wget("llm_model"); if (w && w.value !== v) { w.value = v; node.setDirtyCanvas(true, true); } };
  let loadSeq = 0;
  const loadModels = async () => {
    const seq = ++loadSeq;
    const p = (wget("provider") || {}).value || "local";
    say("Listing models...");
    const d = await jget("/violet/llm/models?provider=" + encodeURIComponent(p) + (freeChk.checked ? "&free=1" : ""));
    if (seq !== loadSeq) return; // a newer request (provider changed meanwhile) owns the list
    freeBox.style.display = d && d.free_filter ? "flex" : "none";
    const names = ((d && d.models) || []).slice();
    const cur = (wget("llm_model") || {}).value || "";
    modelSel.innerHTML = "";
    if (!names.length) {
      const o = el("option", null, cur ? cur + " (list unavailable)" : "(no models found)"); o.value = cur; modelSel.appendChild(o);
      say((d && d.error) || "No models found for this provider.");
      return;
    }
    // A model left over from another provider is not valid here: move to the first real one.
    const keep = names.includes(cur);
    const have = new Set((d && d.installed) || []);
    names.forEach((n) => { const o = el("option", null, d && d.installed ? n + (have.has(n) ? "  (installed)" : "  (downloads on first run)") : n); o.value = n; modelSel.appendChild(o); });
    modelSel.value = keep ? cur : names[0];
    setModel(modelSel.value);
    say(names.length + " model(s). " + ((d && d.note) || ""));
  };
  freeChk.onchange = () => loadModels();
  modelSel.onchange = () => setModel(modelSel.value);
  root.__loadModels = loadModels;
  const attach = async (quiet) => {
    if (!quiet) say("Looking for running LLM servers...");
    const d = await jpost("/violet/llm/detect", {});
    if (!d || !d.pick) { if (!quiet) say("No running LLM server found on the usual ports."); return false; }
    const p = d.pick;
    const pw = wget("provider"), mw = wget("llm_model");
    if (pw) pw.value = p.provider; if (mw) mw.value = p.model;
    if (p.base_url) { const cur = await jget("/violet/llm/settings"); const def = ((cur || {}).defaults || {})[p.provider]; if (def && def.replace(/\/$/, "") !== p.base_url.replace(/\/$/, "")) await jpost("/violet/llm/settings", { urls: { ...((cur || {}).urls || {}), [p.provider]: p.base_url } }); }
    await loadModels(); say(`Auto-attached to ${p.process} (${p.provider}) using ${p.model}. Found: ` + d.found.map((f) => `${f.process} ${f.models.length} models`).join(", "));
    node.setDirtyCanvas(true, true);
    return true;
  };
  root.__autoAttach = () => attach(true);
  llmHead.append(el("span", null, "LLM"), modelSel, freeBox,
    btn("Refresh", "Refresh the list for the chosen provider", loadModels),
    btn("Browse text encoders", "Open the Violet Model Browser on the text encoder folders", () => window.VioletModelBrowser && window.VioletModelBrowser.open("text_encoders", { mode: "models" })),
    btn("Attach to local process", "Find an LLM already running on this PC (Ollama, LM Studio, llama.cpp...) and use it", () => attach(false)),
    btn("Settings", "API keys, model folders, prompt groups", () => openSettings((b) => { if (b) { groups = b.groups; ["positive", "negative"].forEach(render); } loadModels(); })));
  llmBox.append(llmHead, llmMsg);

  // --- trigger panel ---
  const trgBox = el("div", "vte-side");
  const trgHead = el("div", "vte-head trg", "");
  trgHead.append(el("span", null, "Selected LoRA trigger words (sent first)"));
  const trgBody = el("div");
  trgBox.append(trgHead, trgBody);
  const upstreamWords = () => {
    const inp = (node.inputs || []).find((i) => i.name === "trigger_words");
    if (!inp || inp.link == null) return null;
    const link = app.graph.links[inp.link];
    const origin = link && app.graph.getNodeById(link.origin_id);
    if (!origin) return null;
    if (origin.type !== "SolarVioletLoraLoader") return { text: "Connected to " + (origin.title || origin.type) + "; words arrive when it runs.", tokens: [], nat: [] };
    let slots = []; try { slots = JSON.parse(((origin.widgets || []).find((w) => w.name === "lora_stack_json") || {}).value || "[]"); } catch {}
    const out = [], seen = new Set();
    slots.filter((s) => s.enabled !== false).forEach((s) => {
      const off = new Set((s.triggers_off || []).map((x) => x.toLowerCase()));
      (s.trigger_words || []).forEach((w) => { const k = w.toLowerCase(); if (!off.has(k) && !seen.has(k)) { seen.add(k); out.push(w); } });
    });
    return { words: out };
  };
  const isToken = (w) => !w.includes(" ") && (/[\d_-]/.test(w) || /[a-z][A-Z]/.test(w) || (w.replace(/[^A-Za-z]/g, "").length <= 5 && /[^aeiouyAEIOUY\W\d_]{3,}/.test(w)) || (w.length > 1 && w === w.toUpperCase() && /[A-Z]/.test(w)));
  const drawTrg = () => {
    const u = upstreamWords();
    let key = JSON.stringify(u);
    if (trgBody.__k === key) return; trgBody.__k = key;
    trgBody.innerHTML = "";
    if (!u) { trgBody.appendChild(el("div", "vte-msg", "Connect the LoRA loader's trigger_words output to see them here. Odd-spelling tokens go first as written; plain-language triggers are worked into the enhanced prompt.")); }
    else if (u.text) trgBody.appendChild(el("div", "vte-msg", u.text));
    else if (!u.words.length) trgBody.appendChild(el("div", "vte-msg", "No trigger words on the enabled LoRAs."));
    else u.words.forEach((w) => { const c = el("span", "vte-chip" + (isToken(w) ? " tok" : ""), w); c.title = isToken(w) ? "literal token: placed first as written" : "natural language: worked into the prompt"; trgBody.appendChild(c); });
    resize();
  };
  const timer = setInterval(() => { if (!root.isConnected) { if (root.__seen) clearInterval(timer); return; } root.__seen = true; drawTrg(); }, 1500);

  root.append(llmBox, trgBox, mkSide("positive", "Positive presets (4)"), mkSide("negative", "Negative presets (4)"), instBox);

  root.__reload = async (fresh) => {
    const sys = await jget("/violet/presets");
    groups = (sys && sys.groups) || [];
    for (const kind of ["positive", "negative"]) {
      const w = wget(kind + "_presets_json");
      let slots = parse(w && w.value);
      if (fresh && !hasContent(slots) && sys) slots = norm(sys[kind]);
      sides[kind].slots = slots; render(kind); commit(kind);
    }
    let cur = []; try { cur = JSON.parse((wget("instructions_json") || {}).value || "[]"); } catch {}
    instr = (Array.isArray(cur) && cur.length === SLOTS) ? cur : ((sys && sys.instructions) || []);
    if (!instr.length) instr = [{ label: "", text: "" }, { label: "", text: "" }, { label: "", text: "" }, { label: "", text: "" }];
    activeInstr = 0;
    const iw = instWidgetText();
    // keep whatever instruction text the workflow already holds; only seed a fresh node from preset 1
    if (fresh) selectInstr(0); else { drawTabs(); instLabel.value = instr[0].label; if (iw && iw.value) { const m = instr.findIndex((s) => s.text === iw.value); if (m >= 0) { activeInstr = m; drawTabs(); instLabel.value = instr[m].label; } } }
    commitInstr(); drawTrg(); loadModels();
  };
  return root;
}

app.registerExtension({
  name: "SolarViolet.TextEncoder",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "VioletTextEncoder") return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
      const root = build(this);
      const widget = this.addDOMWidget("violet_presets", "custom", root, { serialize: false });
      widget.__h = 520;
      widget.computeSize = (w) => [w, widget.__h];
      root.__setWidget(widget);
      const hide = () => {
        for (const n of ["positive_presets_json", "negative_presets_json", "instructions_json"]) {
          const w = (this.widgets || []).find((x) => x.name === n);
          if (!w) continue;
          if (w.element) w.element.style.display = "none";
          w.hidden = true; w.computeSize = () => [0, -4];
        }
        const iw = (this.widgets || []).find((x) => x.name === "enhance_instruction");
        if (iw && !iw.__hooked) {
          iw.__hooked = true;
          const attach = () => { const t = iw.inputEl || iw.element; if (t && t.addEventListener) t.addEventListener("input", () => root.__syncInstr()); };
          attach(); setTimeout(attach, 300);
        }
        // llm_model is filled from the provider's list (dropdown in the LLM row), never typed
        const mw = (this.widgets || []).find((x) => x.name === "llm_model");
        if (mw) { if (mw.element) mw.element.style.display = "none"; if (mw.inputEl) mw.inputEl.style.display = "none"; mw.hidden = true; mw.computeSize = () => [0, -4]; }
        const pw = (this.widgets || []).find((x) => x.name === "provider");
        if (pw && !pw.__hooked) { pw.__hooked = true; const cb = pw.callback; pw.callback = function () { const rr = cb ? cb.apply(this, arguments) : undefined; root.__loadModels(); return rr; }; }
      };
      hide();
      let configured = false;
      setTimeout(() => { hide(); if (!configured) root.__reload(true); }, 0);
      const prev = this.onConfigure;
      this.onConfigure = function () {
        configured = true;
        const rr = prev ? prev.apply(this, arguments) : undefined;
        hide(); root.__reload(false);
        return rr;
      };
      if (this.size[0] < 470) this.size[0] = 470;
      return r;
    };
  },
});
