// LoRA detail card for the Violet loader: info cache, CivitAI fetch, precision / sampler / cfg / steps line,
// and the pop-up card that appears when the mouse rests on a stack card's preview and stays until closed.

const css = document.createElement("style");
css.textContent = `
  .vd-meta { font-size:9px; color:#9db; display:flex; gap:5px; flex-wrap:wrap; margin-top:1px; }
  .vd-meta b { font-weight:600; color:#cfe; background:#10303A; padding:0 4px; border-radius:6px; }
  .vd-meta i { font-style:normal; color:#8F84A8; }
  .vd-pop { position:fixed; top:64px; right:18px; width:420px; max-width:92vw; max-height:calc(100vh - 90px); overflow-y:auto;
    background:#14101C; color:#F4F1FA; border:1px solid #6D28D9; border-radius:10px; z-index:100000;
    box-shadow:0 12px 40px rgba(0,0,0,.65); font-family:sans-serif; font-size:12px; }
  .vd-pop header { display:flex; align-items:center; gap:8px; padding:8px 10px; border-bottom:1px solid #2A2140; position:sticky; top:0; background:#14101C; }
  .vd-pop header h4 { margin:0; flex:1; font-size:13px; color:#C89BF5; word-break:break-word; }
  .vd-x { background:none; border:none; color:#B8ADCF; font-size:18px; cursor:pointer; }
  .vd-body { padding:10px; display:flex; flex-direction:column; gap:8px; }
  .vd-hero { width:100%; max-height:340px; object-fit:contain; background:#0A0710; border-radius:8px; }
  .vd-row { display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
  .vd-pill { font-size:10px; padding:1px 7px; border-radius:9px; background:#2a2140; color:#C89BF5; }
  .vd-pill.g { background:#10303A; color:#A5F0FB; }
  .vd-sec { font-size:10px; text-transform:uppercase; letter-spacing:.06em; color:#B8ADCF; margin-top:2px; }
  .vd-text { white-space:pre-wrap; background:#0A0710; border:1px solid #2A2140; border-radius:6px; padding:6px 8px; max-height:220px; overflow-y:auto; line-height:1.4; user-select:text; }
  .vd-gal { display:flex; gap:5px; overflow-x:auto; padding-bottom:3px; }
  .vd-gal img { height:74px; border-radius:5px; cursor:pointer; border:2px solid transparent; flex-shrink:0; }
  .vd-gal img.on { border-color:#A855F7; }
  .vd-btn { background:#2A2140; color:#F4F1FA; border:1px solid #3A2D5C; border-radius:5px; font-size:11px; padding:4px 9px; cursor:pointer; }
  .vd-btn:hover { border-color:#A855F7; } .vd-btn.pri { background:#A855F7; border-color:#A855F7; }
  .vd-btn:disabled { opacity:.5; cursor:default; }
  .vd-msg { font-size:10px; color:#B8ADCF; }
  .vd-chip { display:inline-block; font-size:10px; padding:2px 7px; margin:2px 3px 2px 0; border-radius:10px; background:#2A1A4A; color:#C89BF5; border:1px solid #6D28D9; cursor:pointer; }
`;
document.head.appendChild(css);

const cache = new Map();
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function getInfo(name, force) {
  if (!force && cache.has(name)) return cache.get(name);
  try {
    const r = await fetch("/violet/lora_info?name=" + encodeURIComponent(name));
    if (r.ok) { const d = await r.json(); cache.set(name, d); return d; }
  } catch (e) {}
  return null;
}

async function fetchCivitai(name, force) {
  const r = await fetch("/violet/lora_fetch", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, force: !!force }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || r.statusText);
  cache.set(name, d);
  return d;
}

async function downloadPreviews(name) {
  const r = await fetch("/violet/lora_previews", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}

// "BF16 · Euler · CFG 3.5 · 28 steps" pieces for the stack card
function metaHtml(info) {
  if (!info) return "";
  const g = (info.civitai && info.civitai.gen) || {};
  const parts = [];
  if (info.precision) parts.push("<b>" + esc(info.precision) + "</b>");
  if (g.sampler) parts.push("<i>sampler</i> " + esc(g.sampler) + (g.scheduler ? " / " + esc(g.scheduler) : ""));
  if (g.cfg != null) parts.push("<i>CFG</i> " + esc(g.cfg) + ((g.cfg_all || []).length > 1 ? " (" + esc(g.cfg_all.join(", ")) + ")" : ""));
  if (g.steps != null) parts.push("<i>steps</i> " + esc(g.steps) + ((g.steps_all || []).length > 1 ? " (" + esc(g.steps_all.join(", ")) + ")" : ""));
  if (!parts.length || (!g.sampler && g.cfg == null && g.steps == null)) parts.push("<i>no sampler data yet, use the cloud button</i>");
  return parts.join(" ");
}

let pop = null;
function closePop() { if (pop) { pop.remove(); pop = null; document.removeEventListener("keydown", onKey, true); document.removeEventListener("mousedown", onOutside, true); } }
const onKey = (e) => { if (e.key === "Escape") closePop(); };
const onOutside = (e) => { if (pop && !pop.contains(e.target) && !e.target.closest(".vd-hoverable")) closePop(); };

async function showDetail(name, slot) {
  closePop();
  pop = document.createElement("div");
  pop.className = "vd-pop";
  document.body.appendChild(pop);
  document.addEventListener("keydown", onKey, true);
  document.addEventListener("mousedown", onOutside, true);
  const draw = (info) => {
    if (!pop) return;
    const c = (info && info.civitai) || {};
    const g = c.gen || {};
    const imgs = (c.images || []).filter((i) => i.type !== "video");
    const words = (info && info.trigger_words) || (slot && slot.trigger_words) || [];
    pop.innerHTML =
      '<header><h4>' + esc((info && info.alias) || name) + '</h4><button class="vd-btn" data-a="ren" title="Rename">\u270E</button><button class="vd-x" title="Close (Esc)">✕</button></header><div class="vd-body">' +
      (info && info.preview ? '<img class="vd-hero" src="' + info.preview + '">' : "") +
      '<div class="vd-row">' +
      (info && info.base_model ? '<span class="vd-pill">' + esc(info.base_model) + "</span>" : "") +
      (info && info.precision ? '<span class="vd-pill g">' + esc(info.precision) + "</span>" : "") +
      (c.version_name ? '<span class="vd-pill">' + esc(c.version_name) + "</span>" : "") +
      (c.creator ? '<span class="vd-pill">by ' + esc(c.creator) + "</span>" : "") +
      (c.published_at ? '<span class="vd-pill">' + esc(String(c.published_at).slice(0, 10)) + "</span>" : "") +
      (info && info.size ? '<span class="vd-pill">' + (info.size / 1048576).toFixed(0) + " MB</span>" : "") +
      "</div>" +
      '<div class="vd-row">' +
      (g.sampler ? '<span class="vd-pill g">' + esc(g.sampler) + (g.scheduler ? " / " + esc(g.scheduler) : "") + "</span>" : "") +
      (g.cfg != null ? '<span class="vd-pill g">CFG ' + esc(g.cfg) + "</span>" : "") +
      (g.steps != null ? '<span class="vd-pill g">' + esc(g.steps) + " steps</span>" : "") +
      (!g.sampler && g.cfg == null && g.steps == null ? '<span class="vd-msg">No sampler / CFG / steps data yet. Fetch from CivitAI.</span>' : "") +
      "</div>" +
      (words.length ? '<div class="vd-sec">Trigger words (click to copy)</div><div class="tw">' + words.map((w) => '<span class="vd-chip">' + esc(w) + "</span>").join("") + "</div>" : "") +
      (c.version_description ? '<div class="vd-sec">Version notes</div><div class="vd-text">' + esc(c.version_description) + "</div>" : "") +
      (c.model_description ? '<div class="vd-sec">Model page description</div><div class="vd-text">' + esc(c.model_description) + "</div>" : "") +
      ((c.tags || []).length ? '<div class="vd-sec">Tags</div><div class="vd-row">' + c.tags.map((t) => '<span class="vd-pill">' + esc(t) + "</span>").join("") + "</div>" : "") +
      (imgs.length ? '<div class="vd-sec">Example images (' + imgs.length + ')</div><div class="vd-gal">' +
        imgs.slice(0, 40).map((im, i) => '<img data-i="' + i + '" loading="lazy" src="' + esc(im.url) + '">').join("") + '</div><div class="vd-text ex" style="display:none"></div>' : "") +
      '<div class="vd-row">' +
      '<button class="vd-btn pri" data-a="fetch">' + (info && info.has_fetch ? "Refresh from CivitAI" : "Fetch from CivitAI") + "</button>" +
      (info && info.has_fetch ? '<button class="vd-btn" data-a="dl" title="Save every example image and its prompt as .txt next to the LoRA">Download all preview images + captions</button>' : "") +
      (c.page_url ? '<a class="vd-btn" target="_blank" rel="noopener" href="' + esc(c.page_url) + '" style="text-decoration:none">Open page</a>' : "") +
      '</div><div class="vd-msg st"></div></div>';
    pop.querySelector(".vd-x").onclick = closePop;
    pop.querySelector("[data-a=ren]").onclick = () => rename(name, slot, (newName) => { if (newName && newName !== name) closePop(); else showDetail(name, slot); });
    pop.querySelectorAll(".vd-chip").forEach((el) => { el.onclick = () => { try { navigator.clipboard.writeText(el.textContent); } catch (e) {} }; });
    const st = pop.querySelector(".st");
    const ex = pop.querySelector(".ex");
    pop.querySelectorAll(".vd-gal img").forEach((el) => {
      el.onclick = () => {
        pop.querySelectorAll(".vd-gal img").forEach((x) => x.classList.remove("on"));
        el.classList.add("on");
        const im = imgs[+el.dataset.i];
        ex.style.display = "block";
        ex.textContent = (im.prompt ? "Prompt:\n" + im.prompt : "(no prompt published)") +
          (im.negative ? "\n\nNegative:\n" + im.negative : "") +
          "\n\n" + [im.sampler && "Sampler " + im.sampler, im.cfg != null && "CFG " + im.cfg, im.steps != null && "Steps " + im.steps, im.seed && "Seed " + im.seed].filter(Boolean).join(" | ");
      };
    });
    const f = pop.querySelector("[data-a=fetch]");
    f.onclick = async () => {
      f.disabled = true; st.textContent = "Contacting CivitAI (large files are hashed first, this can take a minute)...";
      try { const d = await fetchCivitai(name, true); if (slot) applyToSlot(slot, d); draw(d); notify(name, d);
        if (!d.has_fetch) pop.querySelector(".st").textContent = "Not found on CivitAI (file hash unknown there)."; }
      catch (e) { st.textContent = "Failed: " + e.message; f.disabled = false; }
    };
    const dl = pop.querySelector("[data-a=dl]");
    if (dl) dl.onclick = async () => {
      dl.disabled = true; st.textContent = "Downloading images and captions...";
      try { const r = await downloadPreviews(name); st.textContent = "Saved " + r.saved + " images + captions to " + r.folder + (r.failed ? " (" + r.failed + " failed)" : ""); }
      catch (e) { st.textContent = "Failed: " + e.message; }
      dl.disabled = false;
    };
  };
  draw(await getInfo(name, true));
}

const listeners = new Set();
function notify(name, info) { listeners.forEach((fn) => { try { fn(name, info); } catch (e) {} }); }

function applyToSlot(slot, info) {
  if (!info) return;
  if (info.preview) slot.preview = info.preview + (info.preview.includes("?") ? "&" : "?") + "t=" + Date.now();
  if (info.base_model) slot.base_model = info.base_model;
  const have = new Set((slot.trigger_words || []).map((w) => w.toLowerCase()));
  (info.trigger_words || []).forEach((w) => { if (!have.has(w.toLowerCase())) (slot.trigger_words = slot.trigger_words || []).push(w); });
}

// Attach hover-to-pop behaviour to an element; the card stays until closed.
function hoverPop(el, name, slot, delay = 450) {
  el.classList.add("vd-hoverable");
  let t = null;
  el.addEventListener("mouseenter", () => { t = setTimeout(() => showDetail(name, slot), delay); });
  el.addEventListener("mouseleave", () => clearTimeout(t));
  el.addEventListener("click", () => { clearTimeout(t); showDetail(name, slot); });
}

// Rename dialog: change only how the LoRA is shown in Violet UIs, or rename the file (and its previews/sidecars) on disk.
function rename(name, slot, done) {
  const back = document.createElement("div");
  back.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100002;display:flex;align-items:center;justify-content:center";
  const box = document.createElement("div");
  box.style.cssText = "width:min(460px,92vw);background:#14101C;color:#F4F1FA;border:1px solid #6D28D9;border-radius:10px;padding:14px;font:12px sans-serif";
  const stem = name.replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, "");
  box.innerHTML = '<div style="font-size:13px;color:#C89BF5;margin-bottom:6px">Rename LoRA</div><div class="vd-msg" style="margin-bottom:6px">' + esc(name) + '</div>' +
    '<input class="rn" style="width:100%;box-sizing:border-box;background:#0A0710;color:#F4F1FA;border:1px solid #2A2140;border-radius:4px;padding:6px;font-size:12px">' +
    '<div class="vd-msg" style="margin:8px 0">Display name changes only how it looks in Violet UIs; workflows keep working. Renaming the file also renames its preview and info files, and any saved workflow that names the old file will need re-pointing.</div>' +
    '<div class="vd-row"><button class="vd-btn pri" data-m="display">Change display name</button><button class="vd-btn" data-m="file">Rename file on disk</button><button class="vd-btn" data-m="x">Cancel</button></div><div class="vd-msg st" style="margin-top:6px"></div>';
  back.appendChild(box); document.body.appendChild(back);
  const inp = box.querySelector(".rn"); inp.value = (slot && slot.alias) || stem; inp.focus(); inp.select();
  const st = box.querySelector(".st");
  back.addEventListener("mousedown", (e) => { if (e.target === back) back.remove(); });
  box.querySelectorAll("[data-m]").forEach((b) => b.onclick = async () => {
    const mode = b.dataset.m; if (mode === "x") { back.remove(); return; }
    if (mode === "file" && !confirm("Rename the file on disk? Saved workflows that use the old file name will need to be re-pointed.")) return;
    st.textContent = "Working...";
    try {
      const r = await fetch("/violet/lora_rename", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, mode, value: inp.value }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.error || r.statusText);
      cache.delete(name); if (d.info) cache.set(d.name, d.info);
      if (slot) { if (mode === "file") { slot.name = d.name; if (d.info.preview) slot.preview = d.info.preview + "&t=" + Date.now(); } else slot.alias = d.info.alias || ""; }
      back.remove(); if (done) done(d.name, d.info);
    } catch (e) { st.textContent = "Failed: " + e.message; }
  });
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") box.querySelector("[data-m=display]").click(); if (e.key === "Escape") back.remove(); e.stopPropagation(); });
}

window.VioletLoraDetail = { rename, getInfo, fetchCivitai, downloadPreviews, metaHtml, showDetail, closePop, hoverPop, applyToSlot, listeners };
