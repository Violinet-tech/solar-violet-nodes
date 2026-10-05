// Solar custom nodes frontend extension
// Provides a fully custom card-grid overlay for the Solar Model Selector node.

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Inject overlay CSS
const style = document.createElement("style");
style.textContent = `
  .solar-overlay-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 9999; display:flex; align-items:center; justify-content:center; }
  .solar-overlay { width: 80vw; max-width: 900px; height: 80vh; background: #14101C; border: 1px solid #2A2140; border-radius: 8px; color:#F4F1FA; display:flex; flex-direction:column; overflow:hidden; }
  .solar-overlay-head { padding: 12px 16px; border-bottom: 1px solid #2A2140; display:flex; justify-content:space-between; align-items:center; }
  .solar-overlay-head h3 { margin:0; font-size:14px; }
  .solar-overlay-search { padding: 10px 16px; border-bottom: 1px solid #1E1830; }
  .solar-overlay-search input { width:100%; padding:8px; background:#0A0710; color:#F4F1FA; border:1px solid #2A2140; border-radius:4px; }
  .solar-overlay-grid { flex:1; overflow:auto; padding:12px; display:grid; grid-template-columns: repeat(auto-fill, minmax(120px,1fr)); gap:10px; }
  .solar-card { background:#1E1830; border:1px solid #2A2140; border-radius:6px; cursor:pointer; overflow:hidden; display:flex; flex-direction:column; }
  .solar-card:hover { border-color:#A855F7; }
  .solar-card img { width:100%; height:100px; object-fit:cover; background:#0A0710; }
  .solar-card .c-name { font-size:11px; padding:6px; line-height:1.2; }
  .solar-card .c-meta { font-size:9px; padding:0 6px 6px; color:#B8ADCF; }
  .solar-overlay-empty { padding:24px; text-align:center; color:#5B4E7A; }
  .solar-overlay-close { background:none; border:none; color:#B8ADCF; font-size:20px; cursor:pointer; }
`;

document.head.appendChild(style);

function promptImage(p) {
  // If no preview, return placeholder
  return p || "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect width='120' height='120' fill='%231a1a26'/%3E%3Ctext x='60' y='60' text-anchor='middle' fill='%23666' font-size='10'%3ENo%20Preview%3C/text%3E%3C/svg%3E";
}

function openOverlay(node, title) {
  const backdrop = document.createElement("div");
  backdrop.className = "solar-overlay-backdrop";
  const overlay = document.createElement("div");
  overlay.className = "solar-overlay";
  overlay.innerHTML = `
    <div class="solar-overlay-head"><h3>${title}</h3><button class="solar-overlay-close">✕</button></div>
    <div class="solar-overlay-search"><input type="text" placeholder="Search models..."></div>
    <div class="solar-overlay-grid"></div>
  `;
  const close = overlay.querySelector(".solar-overlay-close");
  close.addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });

  const grid = overlay.querySelector(".solar-overlay-grid");
  const search = overlay.querySelector(".solar-overlay-search input");
  let models = [];

  function render() {
    grid.innerHTML = "";
    const q = search.value.toLowerCase();
    const filtered = models.filter(m => (m.name || "").toLowerCase().includes(q));
    if (!filtered.length) {
      grid.innerHTML = `<div class="solar-overlay-empty">No models. Scan folders in Solar Manager first.</div>`;
      return;
    }
    filtered.forEach(m => {
      const card = document.createElement("div");
      card.className = "solar-card";
      card.innerHTML = `
        <img src="${promptImage(m.preview)}" alt="" loading="lazy">
        <div class="c-name">${m.name || "unnamed"}</div>
        <div class="c-meta">${m.sizeMB || ""} MB</div>`;
      card.addEventListener("click", () => {
        node.widgets_values[0] = JSON.stringify(m);
        backdrop.remove();
        node.setDirtyCanvas(true);
      });
      grid.appendChild(card);
    });
  }

  search.addEventListener("input", render);

  try {
    // Try to fetch models from the Solar manager receiver server (best-effort)
    fetch("http://127.0.0.1:47291/models").then(r => r.json()).then(data => {
      models = Array.isArray(data) ? data : [];
      render();
    }).catch(() => {
      models = [];
      render();
    });
  } catch (e) {
    render();
  }

  document.body.appendChild(backdrop);
}

app.registerExtension({
  name: "Solar.CustomNodes",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name === "SolarModelSelector") {
      const onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const r = onNodeCreated?.apply(this, arguments);
        const widget = this.widgets?.find(w => w.name === "model_json");
        const btn = this.addWidget("button", "Browse Models", null, () => {
          openOverlay(this, "Select Model");
        });
        if (widget) widget.hidden = true;
        return r;
      };
    }
  },
});

console.log("[Solar] custom node overlay loaded");