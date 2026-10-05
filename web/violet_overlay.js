// Violet custom nodes frontend extension
// - Solar Violet LoRA Loader: card stack UI (enable/reorder/strength), trigger-word panel,
//   multi-result search picker
// - Runtime-editable extra LoRA folders (ComfyUI settings + floating menu)
// - Sidebar panels: LoRA Manager + Violet Custom Nodes Manager

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const style = document.createElement("style");
style.textContent = `
  .sv-card-grid { display:flex; flex-direction:column; gap:8px; width:100%; height:100%; box-sizing:border-box; padding:4px 0; }
  .sv-fixed { flex:none; }
  .sv-list { flex:1 1 auto; min-height:0; overflow-y:auto; overscroll-behavior:contain; display:flex; flex-direction:column; gap:8px; padding-right:6px; scrollbar-width:auto; scrollbar-color:#6D28D9 #14101C; }
  .sv-list::-webkit-scrollbar { width:12px; }
  .sv-list::-webkit-scrollbar-track { background:#14101C; border-radius:6px; }
  .sv-list::-webkit-scrollbar-thumb { background:#6D28D9; border-radius:6px; border:2px solid #14101C; }
  .sv-list::-webkit-scrollbar-thumb:hover { background:#A855F7; }
  .sv-card .sv-btn { font-size:calc(var(--sv-font,13px) * .95); padding:4px 8px; }
  .sv-card { flex:none; display:flex; align-items:center; gap:10px; background:#1E1830; border:1px solid #2A2140; border-radius:6px; padding:var(--sv-pad,8px) 10px; }
  .sv-card.off { opacity:0.45; }
  .sv-card img { width:var(--sv-thumb,56px); height:var(--sv-thumb,56px); object-fit:cover; border-radius:4px; background:#0A0710; flex-shrink:0; }
  .sv-card-info { flex:1; min-width:0; }
  .sv-card-name { font-size:var(--sv-font,13px); font-weight:600; color:#F4F1FA; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .sv-base { font-size:8px; padding:0 4px; border-radius:6px; background:#2A2140; color:#C89BF5; margin-left:5px; font-weight:400; }
  .sv-card-tags { font-size:calc(var(--sv-font,13px) * .82); color:#B8ADCF; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .sv-card-strength { display:flex; align-items:center; gap:4px; margin-top:2px; }
  .sv-card-strength input[type=range] { flex:1; max-width:220px; min-width:90px; }
  .sv-card-strength span { font-size:calc(var(--sv-font,13px) * .9); color:#B8ADCF; width:38px; }
  .sv-card-actions { display:flex; gap:3px; flex-shrink:0; }
  .sv-btn { background:#333a; color:#F4F1FA; border:1px solid #3A2D5C; border-radius:4px; font-size:12px; padding:4px 8px; cursor:pointer; }
  .sv-btn:hover { border-color:#A855F7; }
  .sv-btn.primary { background:#A855F7; border-color:#A855F7; color:#fff; }
  .sv-btn.danger { color:#E879F9; }
  .sv-controls { display:flex; gap:10px; align-items:center; flex-wrap:wrap; padding:4px 0; }
  .sv-controls label { font-size:12px; color:#D9D0EC; display:flex; align-items:center; gap:4px; }
  .sv-search { flex:1; box-sizing:border-box; min-height:38px; padding:9px 12px; background:#0A0710; color:#F4F1FA; border:1px solid #3A2D5C; border-radius:6px; font-size:14px; }
  .sv-search:focus { outline:none; border-color:#A855F7; }
  .sv-add-row .sv-btn { font-size:15px; padding:7px 13px; }
  .sv-add-row { display:flex; gap:4px; margin-top:4px; align-items:center; }
  .sv-picker { position:relative; }
  .sv-drop { position:absolute; left:0; right:0; bottom:100%; max-height:340px; overflow-y:auto; overscroll-behavior:contain; background:#14101C; border:1px solid #3A2D5C; border-radius:6px; z-index:50; }
  .sv-drop-item { display:flex; align-items:center; gap:8px; padding:6px 8px; cursor:pointer; font-size:13px; color:#F4F1FA; }
  .sv-drop-item:hover, .sv-drop-item.hl { background:#2A2140; }
  .sv-drop-item img { width:36px; height:36px; object-fit:cover; border-radius:3px; }
  .sv-drop-item small { color:#B8ADCF; margin-left:auto; }
  .sv-trig { background:#0A0710; border:1px solid #2A2140; border-radius:6px; padding:8px 10px; max-height:220px; overflow-y:auto; overscroll-behavior:contain; }
  .sv-trig-title { font-size:12px; color:#B8ADCF; display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; gap:6px; }
  .sv-chip { display:inline-block; font-size:12px; padding:3px 10px; margin:3px 4px 3px 0; border-radius:12px; background:#2A1A4A; color:#C89BF5; border:1px solid #6D28D9; cursor:pointer; user-select:none; }
  .sv-chip.off { background:transparent; color:#8F84A8; border-color:#2A2140; text-decoration:line-through; }
  .sv-trig-box { width:100%; box-sizing:border-box; margin-top:4px; min-height:60px; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:4px; font-size:12px; padding:6px 8px; resize:vertical; }
  .sv-dirs textarea { width:100%; min-height:90px; box-sizing:border-box; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:4px; font-size:11px; padding:6px; }
  .sv-dirs .msg { font-size:10px; color:#B8ADCF; margin:4px 0; }
  .sv-panel { color:#F4F1FA; font-family:inherit; padding:8px; }
  .sv-panel h3 { margin:0 0 8px; font-size:13px; color:#A855F7; }
  .sv-panel-list { max-height:340px; overflow-y:auto; display:flex; flex-direction:column; gap:4px; }
  .sv-panel-item { display:flex; align-items:center; gap:6px; padding:4px 6px; background:#1E1830; border:1px solid #2A2140; border-radius:4px; }
  .sv-panel-item img { width:28px; height:28px; object-fit:cover; border-radius:3px; }
  .sv-panel-item .n { flex:1; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .sv-badge { font-size:9px; padding:1px 5px; border-radius:8px; }
  .sv-badge.ok { background:#22D3EE; color:#000; }
  .sv-badge.off { background:#E879F9; color:#fff; }
  .sv-fab { position:fixed; bottom:24px; right:24px; width:46px; height:46px; border-radius:50%; background:#A855F7; color:#fff; font-size:20px; display:flex; align-items:center; justify-content:center; cursor:pointer; z-index:9998; box-shadow:0 4px 16px rgba(0,0,0,0.5); }
  .sv-fab-menu { position:fixed; bottom:80px; right:24px; background:#1E1830; border:1px solid #2A2140; border-radius:8px; overflow:hidden; z-index:9999; display:flex; flex-direction:column; min-width:190px; }
  .sv-fab-menu button { background:none; border:none; color:#F4F1FA; padding:10px 14px; text-align:left; cursor:pointer; font-size:12px; }
  .sv-fab-menu button:hover { background:#2A2140; }
  .sv-manager-backdrop { position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:99999; display:flex; align-items:center; justify-content:center; }
  .sv-manager { width:80vw; max-width:760px; height:78vh; background:#14101C; border:1px solid #2A2140; border-radius:8px; color:#F4F1FA; display:flex; flex-direction:column; overflow:hidden; }
  .sv-manager-head { padding:12px 16px; border-bottom:1px solid #2A2140; display:flex; justify-content:space-between; align-items:center; }
  .sv-manager-head h3 { margin:0; font-size:14px; color:#A855F7; }
  .sv-manager-close { background:none; border:none; color:#B8ADCF; font-size:20px; cursor:pointer; }
  .sv-manager-body { flex:1; overflow-y:auto; padding:12px; }
`;
document.head.appendChild(style);

function placeholder() {
  return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Crect width='60' height='60' fill='%231a1a26'/%3E%3Ctext x='30' y='33' text-anchor='middle' fill='%23666' font-size='8'%3EN/A%3C/text%3E%3C/svg%3E";
}

const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function fetchManagerModels() {
  try {
    const res = await fetch("/violet/lora_catalog");
    if (res.ok) {
      const d = await res.json();
      if (Array.isArray(d)) return d;
    }
  } catch (e) {}
  return [];
}

async function getSettings() {
  try {
    return await (await fetch("/violet/settings")).json();
  } catch (e) {
    return { lora_dirs: [], missing: [], builtin: [] };
  }
}

// One path per line. Saved server-side; applied live to every LoRA loader in ComfyUI.
function buildDirsEditor(onSaved) {
  const wrap = document.createElement("div");
  wrap.className = "sv-dirs";
  wrap.innerHTML =
    '<div class="msg">Extra LoRA folders, one path per line. Applied immediately to every LoRA loader node (no restart). Subfolders are included.</div>' +
    '<textarea spellcheck="false" placeholder="D:/MoreLoras"></textarea>' +
    '<div class="sv-add-row"><button class="sv-btn primary">Save &amp; apply</button><span class="msg st"></span></div>' +
    '<div class="msg bi"></div>';
  const ta = wrap.querySelector("textarea");
  const st = wrap.querySelector(".st");
  const bi = wrap.querySelector(".bi");
  const show = (cfg) => {
    ta.value = (cfg.lora_dirs || []).join("\n");
    bi.textContent = "Built-in: " + (cfg.builtin || []).join("  |  ");
    st.textContent = cfg.missing && cfg.missing.length ? "Not found: " + cfg.missing.join(", ") : "";
  };
  getSettings().then(show);
  wrap.querySelector("button").addEventListener("click", async () => {
    st.textContent = "Saving...";
    try {
      const r = await fetch("/violet/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lora_dirs: ta.value.split("\n").map((x) => x.trim()).filter(Boolean) }),
      });
      const cfg = await r.json();
      show(cfg);
      if (!(cfg.missing && cfg.missing.length)) st.textContent = "Applied.";
      try { await app.refreshComboInNodes(); } catch (e) {}
      if (onSaved) onSaved(cfg);
    } catch (e) {
      st.textContent = "Failed: " + e;
    }
  });
  return wrap;
}

// ---------- Solar Violet LoRA Loader widget ----------
// ---------- strip appearance (applies to every loader node, saved server-side) ----------
const LOOK = { thumb: 56, font: 13, pad: 8, show_tags: true, show_meta: true };
function applyLook() {
  const r = document.documentElement.style;
  r.setProperty("--sv-thumb", LOOK.thumb + "px");
  r.setProperty("--sv-font", LOOK.font + "px");
  r.setProperty("--sv-pad", LOOK.pad + "px");
  let el = document.getElementById("sv-look-css");
  if (!el) { el = document.createElement("style"); el.id = "sv-look-css"; document.head.appendChild(el); }
  el.textContent = (LOOK.show_tags ? "" : ".sv-card-tags{display:none}") + (LOOK.show_meta ? "" : ".vd-meta{display:none}");
}
let lookSaveTimer = null;
function saveLook() {
  clearTimeout(lookSaveTimer);
  lookSaveTimer = setTimeout(() => fetch("/violet/ui", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(LOOK) }).catch(() => {}), 400);
}
fetch("/violet/ui").then((r) => r.json()).then((d) => {
  // the old default strip size (40 / 11 / 5) was never a choice, so it moves to the larger default
  if (d && d.thumb === 40 && d.font === 11 && d.pad === 5) { delete d.thumb; delete d.font; delete d.pad; }
  Object.assign(LOOK, d); applyLook();
}).catch(() => {});
function buildLookRow() {
  const row = document.createElement("div");
  row.className = "sv-controls";
  row.style.cssText += ";width:100%;background:#0A0710;border-radius:6px;padding:4px 6px";
  const sl = (label, key, min, max) => {
    const l = document.createElement("label");
    const i = document.createElement("input");
    i.type = "range"; i.min = min; i.max = max; i.value = LOOK[key];
    const v = document.createElement("span"); v.textContent = LOOK[key];
    i.addEventListener("input", () => { LOOK[key] = +i.value; v.textContent = i.value; applyLook(); saveLook(); });
    l.append(label + " ", i, v); row.appendChild(l);
  };
  sl("Photo", "thumb", 20, 220); sl("Text", "font", 8, 22); sl("Spacing", "pad", 1, 20);
  const cb = (label, key) => {
    const l = document.createElement("label"); const i = document.createElement("input"); i.type = "checkbox"; i.checked = LOOK[key];
    i.addEventListener("change", () => { LOOK[key] = i.checked; applyLook(); saveLook(); });
    l.append(i, " " + label); row.appendChild(l);
  };
  cb("Trigger line", "show_tags"); cb("Sampler line", "show_meta");
  const reset = document.createElement("button");
  reset.className = "sv-btn"; reset.textContent = "Reset";
  reset.addEventListener("click", () => {
    Object.assign(LOOK, { thumb: 56, font: 13, pad: 8, show_tags: true, show_meta: true }); applyLook(); saveLook();
    const fresh = buildLookRow(); fresh.style.display = "flex"; row.replaceWith(fresh);
  });
  row.appendChild(reset);
  return row;
}

// Scroll a list with the wheel instead of letting the canvas zoom: stop the wheel from reaching the canvas while the list can still move that way.
function trapWheel(el) {
  el.addEventListener("wheel", (e) => {
    if (el.scrollHeight <= el.clientHeight + 1) return;
    const top = el.scrollTop <= 0, bottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
    if ((e.deltaY < 0 && top) || (e.deltaY > 0 && bottom)) return;
    e.stopPropagation();
  }, { passive: true });
}

function createLoaderWidget(node) {
  const container = document.createElement("div");
  container.className = "sv-card-grid";
  container.__need = 160;
  container.__min = 160;
  let slots = [];
  let stepInc = 0.1;
  let catalog = null;
  const wv = (n) => (node.widgets || []).find((x) => x.name === n);
  const getCatalog = async (force) => {
    if (!catalog || force) catalog = await fetchManagerModels();
    return catalog;
  };

  function persist() {
    const w = wv("lora_stack_json");
    if (w) w.value = JSON.stringify(slots);
    const inc = wv("step_increment");
    if (inc) inc.value = stepInc;
    node.setDirtyCanvas(true, true);
  }

  function triggerText() {
    const seen = new Set();
    const out = [];
    slots.filter((s) => s.enabled !== false).forEach((s) => {
      const off = new Set((s.triggers_off || []).map((x) => x.toLowerCase()));
      (s.trigger_words || []).forEach((w) => {
        const k = w.toLowerCase();
        if (!off.has(k) && !seen.has(k)) { seen.add(k); out.push(w); }
      });
    });
    return out.join(", ");
  }

  function buildControls() {
    const c = document.createElement("div");
    c.className = "sv-controls sv-fixed";
    const all = document.createElement("button");
    all.className = "sv-btn";
    const allOn = slots.length > 0 && slots.every((s) => s.enabled !== false);
    all.textContent = allOn ? "Disable all" : "Enable all";
    all.addEventListener("click", () => { slots.forEach((s) => { s.enabled = !allOn; }); refresh(); persist(); });
    c.appendChild(all);
    const incLabel = document.createElement("label");
    incLabel.append("Step ");
    const stepSel = document.createElement("select");
    [0.05, 0.1, 0.2, 0.5].forEach((v) => {
      const o = document.createElement("option");
      o.value = v; o.textContent = v;
      stepSel.appendChild(o);
    });
    stepSel.value = stepInc;
    stepSel.addEventListener("change", () => { stepInc = parseFloat(stepSel.value); refresh(); persist(); });
    incLabel.appendChild(stepSel);
    c.appendChild(incLabel);
    const look = document.createElement("button");
    look.className = "sv-btn"; look.textContent = "Aa"; look.title = "Resize the strips: photo, text, spacing";
    const lookRow = buildLookRow();
    lookRow.style.display = "none";
    look.addEventListener("click", () => { lookRow.style.display = lookRow.style.display === "none" ? "flex" : "none"; });
    c.appendChild(look);
    c.appendChild(lookRow);
    return c;
  }

  function buildCard(slot) {
    const card = document.createElement("div");
    card.className = "sv-card" + (slot.enabled === false ? " off" : "");
    const tags = (slot.trigger_words || []).slice(0, 3).join(", ");
    const strength = slot.strength == null ? 1 : slot.strength;
    card.innerHTML =
      '<input type="checkbox" class="sv-en" title="Enable / disable"' + (slot.enabled === false ? "" : " checked") + ">" +
      '<img src="' + (slot.preview || placeholder()) + '" alt="" loading="lazy">' +
      '<div class="sv-card-info">' +
      '<div class="sv-card-name" title="' + esc(slot.name) + '">' + esc(slot.alias || slot.name || "unnamed") +
      (slot.base_model ? '<span class="sv-base">' + esc(slot.base_model) + "</span>" : "") + "</div>" +
      '<div class="sv-card-tags">' + esc(tags) + "</div>" +
      '<div class="vd-meta"></div>' +
      '<div class="sv-card-strength"><input type="range" min="0" max="2" step="' + stepInc + '" value="' + strength + '"><span>' + Number(strength).toFixed(2) + "</span></div>" +
      "</div>" +
      '<div class="sv-card-actions">' +
      '<button class="sv-btn" data-a="up" title="Move up">\u25B2</button>' +
      '<button class="sv-btn" data-a="dn" title="Move down">\u25BC</button>' +
      '<button class="sv-btn" data-a="copy" title="Copy trigger words">\u29C9</button>' +
      '<button class="sv-btn" data-a="info" title="Details, CivitAI page text, example images">ⓘ</button>' +
      '<button class="sv-btn" data-a="ren" title="Rename: display name or the file itself">\u270E</button>' +
      '<button class="sv-btn danger" data-a="rm" title="Remove">\u2715</button>' +
      "</div>";
    card.querySelector(".sv-en").addEventListener("change", (e) => { slot.enabled = e.target.checked; refresh(); persist(); });
    card.querySelector("input[type=range]").addEventListener("input", (e) => {
      slot.strength = parseFloat(e.target.value);
      card.querySelector(".sv-card-strength span").textContent = slot.strength.toFixed(2);
      persist();
    });
    const act = (a) => card.querySelector("[data-a=" + a + "]");
    const VD = window.VioletLoraDetail;
    if (VD) {
      const meta = card.querySelector(".vd-meta");
      VD.getInfo(slot.name).then((info) => { if (info) meta.innerHTML = VD.metaHtml(info); });
      VD.hoverPop(card.querySelector("img"), slot.name, slot);
      act("info").addEventListener("click", () => VD.showDetail(slot.name, slot));
      act("ren").addEventListener("click", () => VD.rename(slot.name, slot, () => { refresh(); persist(); }));
      VD.getInfo(slot.name).then((info) => { if (info && (info.alias || "") !== (slot.alias || "")) { slot.alias = info.alias || ""; refresh(); } });
    }
    // Per-card copy always copies this LoRA's full trigger list, independent of the trigger panel selection.
    act("copy").addEventListener("click", async () => {
      const words = (slot.trigger_words || []).join(", ");
      if (words) { try { await navigator.clipboard.writeText(words); } catch (e) {} }
    });
    act("rm").addEventListener("click", () => {
      const i = slots.indexOf(slot);
      if (i >= 0) { slots.splice(i, 1); refresh(); persist(); }
    });
    const move = (d) => {
      const i = slots.indexOf(slot);
      const j = i + d;
      if (j < 0 || j >= slots.length) return;
      const t = slots[i]; slots[i] = slots[j]; slots[j] = t;
      refresh(); persist();
    };
    act("up").addEventListener("click", () => move(-1));
    act("dn").addEventListener("click", () => move(1));
    return card;
  }

  function buildTriggerPanel() {
    const withWords = slots.filter((s) => s.enabled !== false && (s.trigger_words || []).length);
    if (!withWords.length) return null;
    const box = document.createElement("div");
    box.className = "sv-trig sv-fixed";
    trapWheel(box);
    const title = document.createElement("div");
    title.className = "sv-trig-title";
    title.innerHTML = "<span>Trigger words: click to include / exclude. Included words go to the prompt output.</span>";
    const copyAll = document.createElement("button");
    copyAll.className = "sv-btn";
    copyAll.textContent = "Copy";
    title.appendChild(copyAll);
    box.appendChild(title);
    const ta = document.createElement("textarea");
    ta.className = "sv-trig-box";
    ta.readOnly = true;
    const sync = () => { ta.value = triggerText(); };
    withWords.forEach((s) => {
      s.trigger_words.forEach((w) => {
        const chip = document.createElement("span");
        const isOff = () => (s.triggers_off || []).some((x) => x.toLowerCase() === w.toLowerCase());
        chip.className = "sv-chip" + (isOff() ? " off" : "");
        chip.textContent = w;
        chip.title = s.name;
        chip.addEventListener("click", () => {
          s.triggers_off = s.triggers_off || [];
          const i = s.triggers_off.findIndex((x) => x.toLowerCase() === w.toLowerCase());
          if (i >= 0) s.triggers_off.splice(i, 1); else s.triggers_off.push(w);
          chip.classList.toggle("off", isOff());
          sync();
          persist();
        });
        box.appendChild(chip);
      });
    });
    box.appendChild(ta);
    sync();
    copyAll.addEventListener("click", async () => { try { await navigator.clipboard.writeText(triggerText()); } catch (e) {} });
    return box;
  }

  function addFromCatalog(m) {
    if (slots.length >= 30) { alert("Max 30 LoRAs"); return; }
    const slot = {
      name: m.name, strength: 1, enabled: true, preview: m.preview,
      base_model: m.base_model || "", trigger_words: m.trigger_words || [], triggers_off: [],
    };
    slots.push(slot);
    refresh();
    persist();
    const VD = window.VioletLoraDetail;
    if (VD && !m.has_fetch) {
      VD.fetchCivitai(m.name).then((d) => {
        if (slots.includes(slot) && d) { VD.applyToSlot(slot, d); refresh(); persist(); }
      }).catch(() => {});
    }
  }

  node.__violetAddLora = addFromCatalog;

  function buildAddRow() {
    const wrap = document.createElement("div");
    wrap.className = "sv-picker sv-fixed";
    const drop = document.createElement("div");
    drop.className = "sv-drop";
    trapWheel(drop);
    drop.style.display = "none";
    const r = document.createElement("div");
    r.className = "sv-add-row";
    const s = document.createElement("input");
    s.className = "sv-search";
    s.placeholder = "Search LoRAs or trigger words...";
    s.title = "Type to find a LoRA by name or trigger word; Enter adds the highlighted one";
    const rf = document.createElement("button");
    rf.className = "sv-btn";
    rf.title = "Rescan LoRA folders";
    rf.textContent = "\u21BB";
    r.appendChild(s);
    r.appendChild(rf);
    wrap.appendChild(drop);
    wrap.appendChild(r);
    let hl = 0;
    let results = [];
    const render = async () => {
      const q = s.value.trim().toLowerCase();
      const cat = await getCatalog();
      const used = new Set(slots.map((x) => x.name));
      results = cat.filter((m) => !used.has(m.name) && (!q || m.name.toLowerCase().includes(q) ||
        (m.trigger_words || []).some((w) => w.toLowerCase().includes(q)))).slice(0, 40);
      hl = Math.min(hl, Math.max(0, results.length - 1));
      drop.innerHTML = "";
      if (!results.length) { drop.style.display = "none"; return; }
      results.forEach((m, i) => {
        const it = document.createElement("div");
        it.className = "sv-drop-item" + (i === hl ? " hl" : "");
        it.innerHTML = '<img src="' + (m.preview || placeholder()) + '" loading="lazy"><span>' + esc(m.name) + "</span><small>" + esc(m.base_model) + "</small>";
        it.addEventListener("mousedown", (e) => { e.preventDefault(); addFromCatalog(m); });
        drop.appendChild(it);
      });
      drop.style.display = "block";
    };
    s.addEventListener("input", () => { hl = 0; render(); });
    s.addEventListener("focus", render);
    s.addEventListener("blur", () => setTimeout(() => { drop.style.display = "none"; }, 120));
    s.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { hl = Math.min(hl + 1, results.length - 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { hl = Math.max(hl - 1, 0); render(); e.preventDefault(); }
      else if (e.key === "Enter" && results[hl]) { addFromCatalog(results[hl]); }
      else if (e.key === "Escape") { drop.style.display = "none"; }
    });
    rf.addEventListener("click", async () => { await getCatalog(true); render(); });
    return wrap;
  }

  // The node grows as LoRAs are loaded, one strip each up to ten, and never shrinks under a size the person chose.
  // The strip list scrolls on its own (scroll bar and wheel), so more than ten loaded, or a node dragged smaller, still works.
  function fit() {
    const list = container.querySelector(".sv-list");
    if (!list) return;
    // an estimate from the strip settings: measuring a strip before the node is laid out reads far too tall
    const cardH = Math.max(LOOK.thumb, LOOK.font * 7.4) + LOOK.pad * 2 + 6;
    const fixed = [...container.querySelectorAll(".sv-fixed")].reduce((a, el) => a + (el.offsetHeight || (el.classList.contains("sv-trig") ? 120 : 44)) + 8, 0);
    container.__min = Math.round(fixed + Math.min(slots.length, 2) * (cardH + 8) + 16);
    container.__need = Math.round(fixed + Math.min(slots.length, 10) * (cardH + 8) + 16);
    const base = node.computeSize ? node.computeSize() : null;
    const w = Math.max(node.size[0], 480);
    const h = base ? Math.max(node.size[1], base[1] - container.__min + container.__need) : node.size[1];
    if (w !== node.size[0] || h !== node.size[1]) node.setSize([w, h]);
    node.setDirtyCanvas(true, true);
  }

  function refresh() {
    const keep = (container.querySelector(".sv-list") || {}).scrollTop || 0;
    container.innerHTML = "";
    container.appendChild(buildControls());
    const list = document.createElement("div");
    list.className = "sv-list";
    trapWheel(list);
    slots.forEach((s) => list.appendChild(buildCard(s)));
    container.appendChild(list);
    const tp = buildTriggerPanel();
    if (tp) container.appendChild(tp);
    container.appendChild(buildAddRow());
    list.scrollTop = keep;
    requestAnimationFrame(fit);
    setTimeout(fit, 80);   // a hidden tab never fires animation frames
  }

  async function backfill() {
    const missing = slots.filter((s) => !(s.trigger_words && s.trigger_words.length) || !s.preview);
    if (!missing.length) return;
    const cat = await getCatalog();
    let changed = false;
    missing.forEach((s) => {
      const m = cat.find((x) => x.name === s.name);
      if (!m) return;
      if (!(s.trigger_words && s.trigger_words.length) && m.trigger_words && m.trigger_words.length) { s.trigger_words = m.trigger_words; changed = true; }
      if (!s.preview && m.preview) { s.preview = m.preview; changed = true; }
      if (!s.base_model && m.base_model) { s.base_model = m.base_model; changed = true; }
    });
    if (changed) { refresh(); persist(); }
  }

  container.__reload = () => {
    try {
      const p = JSON.parse((wv("lora_stack_json") || {}).value || "[]");
      slots = Array.isArray(p) ? p : [];
    } catch (e) { slots = []; }
    const inc = wv("step_increment");
    if (inc && Number(inc.value)) stepInc = Number(inc.value);
    refresh();
    backfill();
  };
  container.__reload();
  return container;
}

// ---------- Sidebar panels ----------
function buildLoraManagerPanel(body) {
  const VD = window.VioletLoraDetail;
  const bar = document.createElement("div");
  bar.className = "sv-add-row";
  const fetchAll = document.createElement("button");
  fetchAll.className = "sv-btn primary"; fetchAll.textContent = "Fetch CivitAI data for all";
  const dupBtn = document.createElement("button");
  dupBtn.className = "sv-btn"; dupBtn.textContent = "Find duplicates";
  const status = document.createElement("span");
  status.className = "msg"; status.style.cssText = "font-size:10px;color:#B8ADCF;margin-left:6px";
  bar.append(fetchAll, dupBtn, status);
  body.appendChild(bar);
  const dupBox = document.createElement("div");
  body.appendChild(dupBox);
  const list = document.createElement("div");
  list.className = "sv-panel-list";
  list.style.maxHeight = "50vh";
  body.appendChild(list);
  let models = [];

  const render = () => {
    list.innerHTML = "";
    if (!models.length) { list.innerHTML = "<div style='color:#5B4E7A;font-size:11px'>No LoRAs found.</div>"; return; }
    models.forEach((m) => {
      const it = document.createElement("div");
      it.className = "sv-panel-item";
      it.innerHTML = '<img src="' + (m.preview || placeholder()) + '"><span class="n">' + esc(m.name) + "</span>" +
        (m.precision ? '<span class="sv-badge ok">' + esc(m.precision) + "</span>" : "") +
        '<span class="sv-badge ' + (m.has_fetch ? "ok" : "off") + '">' + (m.has_fetch ? "CivitAI" : "no CivitAI") + "</span>";
      if (VD) VD.hoverPop(it.querySelector("img"), m.name, null);
      list.appendChild(it);
    });
  };
  list.innerHTML = "<div style='color:#5B4E7A;font-size:11px'>Scanning LoRAs...</div>";
  fetchManagerModels().then((m) => { models = m; render(); });

  fetchAll.addEventListener("click", async () => {
    fetchAll.disabled = true;
    const todo = models.filter((m) => !m.has_fetch);
    let done = 0, hit = 0;
    for (const m of todo) {
      status.textContent = "Fetching " + (++done) + "/" + todo.length + ": " + m.name;
      try { const d = await VD.fetchCivitai(m.name); if (d.has_fetch) hit++; Object.assign(m, d); } catch (e) {}
    }
    status.textContent = "Done. " + hit + " of " + todo.length + " found on CivitAI.";
    fetchAll.disabled = false; render();
  });

  const fmt = (b) => (b / 1048576 >= 1024 ? (b / 1073741824).toFixed(2) + " GB" : (b / 1048576).toFixed(0) + " MB");
  dupBtn.addEventListener("click", async () => {
    status.textContent = "Scanning library for duplicates...";
    dupBox.innerHTML = "";
    let res;
    try { res = await (await fetch("/violet/duplicates")).json(); } catch (e) { status.textContent = "Scan failed: " + e; return; }
    status.textContent = res.groups.length + " group(s) in " + res.scanned + " LoRAs. Reclaimable: " + fmt(res.reclaimable_bytes) +
      ". Nothing is deleted; removals move to a _violet_duplicates folder.";
    res.groups.forEach((g) => {
      const box = document.createElement("div");
      box.className = "sv-trig"; box.style.margin = "6px 0";
      box.innerHTML = '<div class="sv-trig-title"><span><b>' + esc(g.reason) + "</b> (" + esc(g.confidence) + " confidence)</span></div>";
      g.members.forEach((m) => {
        const row = document.createElement("label");
        row.style.cssText = "display:flex;gap:6px;align-items:center;font-size:11px;padding:2px 0";
        const cb = document.createElement("input");
        cb.type = "checkbox"; cb.checked = m.verdict === "remove"; cb.disabled = m.verdict === "keep"; cb.dataset.name = m.name;
        row.appendChild(cb);
        row.insertAdjacentHTML("beforeend",
          '<span class="sv-badge ' + (m.verdict === "keep" ? "ok" : "off") + '">' + esc(m.verdict) + "</span><span style='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='" + esc(m.name) + "'>" +
          esc(m.name) + "</span><small style='color:#B8ADCF'>" + esc([m.version, m.published, m.precision, fmt(m.size), m.note].filter(Boolean).join(" \u00B7 ")) + "</small>");
        const rb = document.createElement("button");
        rb.className = "sv-btn"; rb.textContent = "\u270E"; rb.title = "Rename display name or file";
        rb.addEventListener("click", (e) => { e.preventDefault(); VD.rename(m.name, null, () => dupBtn.click()); });
        row.appendChild(rb);
        box.appendChild(row);
      });
      dupBox.appendChild(box);
    });
    if (res.groups.length) {
      const go = document.createElement("button");
      go.className = "sv-btn danger"; go.textContent = "Move checked LoRAs to _violet_duplicates";
      go.addEventListener("click", async () => {
        const names = [...dupBox.querySelectorAll("input:checked")].map((x) => x.dataset.name);
        if (!names.length || !confirm("Move " + names.length + " LoRA(s) and their previews into a _violet_duplicates folder next to them? You can move them back any time.")) return;
        const r = await (await fetch("/violet/duplicates/quarantine", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ names }) })).json();
        status.textContent = "Moved " + r.moved.length + ".";
        try { await app.refreshComboInNodes(); } catch (e) {}
        models = await fetchManagerModels(); render(); dupBox.innerHTML = "";
      });
      dupBox.appendChild(go);
    }
  });
}

function buildNodesManagerPanel(body) {
  const list = document.createElement("div");
  list.className = "sv-panel-list";
  body.appendChild(list);
  list.innerHTML = "<div style='color:#5B4E7A;font-size:11px'>Loading...</div>";
  try {
    api.getObjectInfo().then((info) => {
      const violetNodes = Object.entries(info).filter(([name]) => name.startsWith("Solar") || name.includes("Violet"));
      list.innerHTML = "";
      if (!violetNodes.length) { list.innerHTML = "<div style='color:#5B4E7A;font-size:11px'>No Violet nodes registered.</div>"; return; }
      violetNodes.forEach(([name, def]) => {
        const it = document.createElement("div");
        it.className = "sv-panel-item";
        it.innerHTML = '<span class="n">' + esc(def.display_name || name) + '</span><span class="sv-badge ok">\u2713</span>';
        list.appendChild(it);
      });
    }).catch(() => { list.innerHTML = "<div style='color:#5B4E7A;font-size:11px'>Unavailable.</div>"; });
  } catch (e) {
    list.innerHTML = "<div style='color:#5B4E7A;font-size:11px'>Unavailable.</div>";
  }
}

// ---------- Manager overlays (floating button, works across frontend versions) ----------
function openManagerOverlay(title, buildContent) {
  const old = document.querySelector(".sv-manager-backdrop");
  if (old) old.remove();
  const backdrop = document.createElement("div");
  backdrop.className = "sv-manager-backdrop";
  const panel = document.createElement("div");
  panel.className = "sv-manager";
  panel.innerHTML = '<div class="sv-manager-head"><h3>' + esc(title) + '</h3><button class="sv-manager-close" title="Close">\u2715</button></div><div class="sv-manager-body"></div>';
  buildContent(panel.querySelector(".sv-manager-body"));
  panel.querySelector(".sv-manager-close").addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });
  backdrop.appendChild(panel);
  document.body.appendChild(backdrop);
}

function makeFloatingMenu() {
  const btn = document.createElement("div");
  btn.className = "sv-fab";
  btn.title = "ComfyViolet";
  btn.innerHTML = "\u2726";
  btn.addEventListener("click", () => {
    const menu = document.querySelector(".sv-fab-menu");
    if (menu) { menu.remove(); return; }
    const m = document.createElement("div");
    m.className = "sv-fab-menu";
    const items = [
      { label: "Violet LoRA Manager", fn: () => openManagerOverlay("Violet LoRA Manager", buildLoraManagerPanel) },
      { label: "Violet LoRA Browser", fn: () => window.VioletModelBrowser && window.VioletModelBrowser.openLoras() },
      { label: "Violet Model Browser", fn: () => window.VioletModelBrowser && window.VioletModelBrowser.openModels() },
      { label: "LoRA folders (settings)", fn: () => openManagerOverlay("LoRA folders", (b) => b.appendChild(buildDirsEditor())) },
      { label: "Violet Custom Nodes", fn: () => openManagerOverlay("Violet Custom Nodes", buildNodesManagerPanel) },
    ];
    items.forEach((it) => {
      const b = document.createElement("button");
      b.textContent = it.label;
      b.addEventListener("click", () => { it.fn(); m.remove(); });
      m.appendChild(b);
    });
    document.body.appendChild(m);
  });
  document.body.appendChild(btn);
}

app.registerExtension({
  name: "SolarViolet.Managers",
  async setup() {
    setTimeout(makeFloatingMenu, 1200);
    try {
      app.ui.settings.addSetting({
        id: "Violet.LoraFolders",
        name: "Violet: extra LoRA folders (all LoRA loaders)",
        type: () => {
          const tr = document.createElement("tr");
          const td = document.createElement("td");
          td.colSpan = 2;
          td.appendChild(buildDirsEditor());
          tr.appendChild(td);
          return tr;
        },
        defaultValue: "",
      });
    } catch (e) {
      console.warn("[ComfyViolet] settings entry unavailable", e);
    }
  },
});

// LoRA browser -> loader bridge: add to the selected LoRA loader, or place a new one in the workflow.
window.VioletLoraLoader = {
  add(m) {
    const g = app.graph, canvas = app.canvas;
    const sel = Object.values(canvas.selected_nodes || {})[0];
    // Add to the loader that is already in the workflow: the selected one, otherwise the first one found.
    // A new loader is only made when the workflow has none.
    const existing = (g._nodes || []).filter((n) => n.type === "SolarVioletLoraLoader" && n.__violetAddLora);
    let node = sel && sel.type === "SolarVioletLoraLoader" ? sel : (existing[0] || null);
    let created = false;
    if (!node) {
      node = LiteGraph.createNode("SolarVioletLoraLoader");
      if (!node) throw new Error("Solar Violet LoRA Loader node is not available");
      const ds = canvas.ds, cw = canvas.canvas.width, ch = canvas.canvas.height;
      node.pos = [(cw / 2 - ds.offset[0] * ds.scale) / ds.scale - 100, (ch / 2 - ds.offset[1] * ds.scale) / ds.scale - 60];
      g.add(node);
      created = true;
    }
    if (!node.__violetAddLora) throw new Error("LoRA loader is still starting, try again");
    node.__violetAddLora(m);
    canvas.selectNode(node);
    g.setDirtyCanvas(true, true);
    const count = (g._nodes || []).filter((n) => n.type === "SolarVioletLoraLoader").length;
    return (created ? "No LoRA loader in the workflow yet, so one was added with " : count > 1 ? "Added to the selected LoRA loader (select another node first to use a different one): " : "Added to the LoRA loader: ") + m.name;
  },
  folders() { openManagerOverlay("LoRA folders", (b) => b.appendChild(buildDirsEditor())); },
};

// ---------- Node extension (loader UI) ----------
app.registerExtension({
  name: "SolarViolet.LoraLoader",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "SolarVioletLoraLoader") return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
      const container = createLoaderWidget(this);
      // node.addDOMWidget is the call that attaches the element on frontend 1.53.x;
      // window.comfyAPI.domWidget.addWidget silently builds an element-less widget.
      this.addWidget("button", "Open LoRA Browser", null, () => {
        try { app.canvas.selectNode(this); } catch (e) { /* older frontend */ }   // the browser then adds to this loader
        if (window.VioletModelBrowser) window.VioletModelBrowser.openLoras();
      });
      this.addDOMWidget("violet_lora_stack", "custom", container, { serialize: false, getMinHeight: () => container.__min });
      if (this.size[0] < 480) this.setSize([480, this.size[1]]);
      const hideJson = () => {
        const w = (this.widgets || []).find((x) => x.name === "lora_stack_json");
        if (!w) return;
        if (w.element) w.element.style.display = "none";
        w.hidden = true;
        w.computeSize = () => [0, -4];
      };
      hideJson();
      setTimeout(() => { hideJson(); container.__reload(); }, 0);
      const prevConfigure = this.onConfigure;
      this.onConfigure = function () {
        const rr = prevConfigure ? prevConfigure.apply(this, arguments) : undefined;
        hideJson();
        container.__reload();
        return rr;
      };
      return r;
    };
  },
});

console.log("[ComfyViolet] custom nodes frontend loaded");
