// Violet Image Compare: draws image A and image B inside the node, either with a draggable left/right slider
// (A on the left of the divider, B on the right) or side by side. Fresh Violet code.

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const st = document.createElement("style");
st.textContent = `
  .vic { width:100%; height:100%; display:flex; flex-direction:column; gap:4px; font-family:sans-serif; color:#F4F1FA; box-sizing:border-box; }
  .vic-bar { display:flex; gap:4px; align-items:center; font-size:10px; flex-wrap:wrap; }
  .vic-btn { font-size:10px; padding:2px 8px; border-radius:4px; border:1px solid #2A2140; background:#1E1830; color:#F4F1FA; cursor:pointer; }
  .vic-btn.on { background:#6D28D9; border-color:#A855F7; }
  .vic-stage { position:relative; flex:1; min-height:120px; background:#0A0710; border:1px solid #2A2140; border-radius:5px; overflow:hidden; user-select:none; }
  .vic-stage img { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; pointer-events:none; }
  .vic-clip { position:absolute; inset:0; overflow:hidden; }
  .vic-line { position:absolute; top:0; bottom:0; width:2px; background:#fff; box-shadow:0 0 4px #000; pointer-events:none; }
  .vic-knob { position:absolute; top:50%; width:22px; height:22px; margin:-11px 0 0 -10px; border-radius:50%; background:#fff; color:#1E1830; font-size:11px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 6px #000; pointer-events:none; }
  .vic-tag { position:absolute; top:4px; font-size:10px; padding:1px 6px; border-radius:8px; background:rgba(0,0,0,.6); color:#fff; pointer-events:none; }
  .vic-side { display:flex; width:100%; height:100%; gap:2px; }
  .vic-side > div { position:relative; flex:1; }
  .vic-empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:11px; color:#8F84A8; }
`;
document.head.appendChild(st);

const url = (f) => api.apiURL(`/view?filename=${encodeURIComponent(f.filename)}&type=${f.type}&subfolder=${encodeURIComponent(f.subfolder || "")}&rand=${Math.random()}`);

function build(node) {
  const root = document.createElement("div");
  root.className = "vic";
  const bar = document.createElement("div");
  bar.className = "vic-bar";
  const bSlide = Object.assign(document.createElement("button"), { className: "vic-btn on", textContent: "Slider" });
  const bSide = Object.assign(document.createElement("button"), { className: "vic-btn", textContent: "Side by side" });
  const idxLbl = document.createElement("span");
  const bPrev = Object.assign(document.createElement("button"), { className: "vic-btn", textContent: "<" });
  const bNext = Object.assign(document.createElement("button"), { className: "vic-btn", textContent: ">" });
  bar.append(bSlide, bSide, bPrev, idxLbl, bNext);
  const stage = document.createElement("div");
  stage.className = "vic-stage";
  root.append(bar, stage);

  const s = { mode: "slider", pos: 0.5, i: 0, a: [], b: [] };
  const paint = () => {
    stage.innerHTML = "";
    bSlide.classList.toggle("on", s.mode === "slider");
    bSide.classList.toggle("on", s.mode === "side");
    const n = Math.max(s.a.length, s.b.length);
    idxLbl.textContent = n > 1 ? `${s.i + 1}/${n}` : "";
    bPrev.style.display = bNext.style.display = n > 1 ? "" : "none";
    const A = s.a[s.i] || s.a[0], B = s.b[s.i] || s.b[0];
    if (!A && !B) {
      stage.innerHTML = '<div class="vic-empty">Run the graph to compare image A and image B</div>';
      return;
    }
    const mk = (f) => Object.assign(document.createElement("img"), { src: f ? url(f) : "", draggable: false });
    if (s.mode === "side") {
      const wrap = document.createElement("div");
      wrap.className = "vic-side";
      for (const [f, tag] of [[A, "A"], [B, "B"]]) {
        const cell = document.createElement("div");
        cell.append(mk(f), Object.assign(document.createElement("div"), { className: "vic-tag", textContent: tag, style: "left:4px" }));
        wrap.append(cell);
      }
      stage.append(wrap);
      return;
    }
    const imgB = mk(B), imgA = mk(A);
    const clip = document.createElement("div");
    clip.className = "vic-clip";
    clip.append(imgA);
    const line = Object.assign(document.createElement("div"), { className: "vic-line" });
    const knob = Object.assign(document.createElement("div"), { className: "vic-knob", textContent: "<>" });
    const tagA = Object.assign(document.createElement("div"), { className: "vic-tag", textContent: "A", style: "left:4px" });
    const tagB = Object.assign(document.createElement("div"), { className: "vic-tag", textContent: "B", style: "right:4px" });
    stage.append(imgB, clip, line, knob, tagA, tagB);
    const place = () => {
      const x = s.pos * 100;
      clip.style.clipPath = `inset(0 ${100 - x}% 0 0)`;
      line.style.left = `calc(${x}% - 1px)`;
      knob.style.left = `${x}%`;
    };
    place();
    const move = (e) => {
      const r = stage.getBoundingClientRect();
      s.pos = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      place();
    };
    stage.onpointerdown = (e) => {
      stage.setPointerCapture(e.pointerId);
      move(e);
      stage.onpointermove = move;
    };
    stage.onpointerup = () => (stage.onpointermove = null);
  };
  bSlide.onclick = () => { s.mode = "slider"; paint(); };
  bSide.onclick = () => { s.mode = "side"; paint(); };
  bPrev.onclick = () => { const n = Math.max(s.a.length, s.b.length); s.i = (s.i - 1 + n) % n; paint(); };
  bNext.onclick = () => { const n = Math.max(s.a.length, s.b.length); s.i = (s.i + 1) % n; paint(); };
  paint();
  return { root, s, paint };
}

app.registerExtension({
  name: "violet.imageCompare",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "VioletImageCompare") return;
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onCreated?.apply(this, arguments);
      const ui = build(this);
      this.__violetCmp = ui;
      const w = this.addDOMWidget("compare", "violet_compare", ui.root, { serialize: false, hideOnZoom: false });
      w.computeSize = (width) => [width, 340];
      this.setSize([Math.max(this.size[0], 420), Math.max(this.size[1], 420)]);
      return r;
    };
    const onExec = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (msg) {
      onExec?.apply(this, arguments);
      const ui = this.__violetCmp;
      if (!ui) return;
      ui.s.a = msg?.a_images || [];
      ui.s.b = msg?.b_images || [];
      ui.s.i = 0;
      ui.paint();
    };
  },
});
