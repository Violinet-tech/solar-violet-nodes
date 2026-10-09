// Violet node theme: header and body colors taken from the Violet Diffusion site palette
// (void #0A0710, ink #14101C, slate #1E1830, violet #A855F7, deep violet #6D28D9).

import { app } from "../../scripts/app.js";

// ComfyUI served over plain http from a LAN address (e.g. --listen 10.x.x.x) is not a secure
// context, so navigator.clipboard is undefined and every copy button silently did nothing.
// Provide a writeText that falls back to execCommand so the existing copy handlers work.
if (!(navigator.clipboard && window.isSecureContext)) {
  const writeText = (text) => new Promise((resolve, reject) => {
    const ta = document.createElement("textarea");
    ta.value = String(text);
    ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) {}
    ta.remove();
    ok ? resolve() : reject(new Error("copy failed"));
  });
  try { Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true }); } catch (e) {}
}

const isViolet =(name) => /^(Violet|SolarViolet|SolarLora|SolarModel|SolarPrompt|SolarImage)/.test(name || "");

app.registerExtension({
  name: "Violet.Theme",
  nodeCreated(node) {
    if (!isViolet(node.comfyClass || node.type)) return;
    if (!node.color) node.color = "#6D28D9";
    if (!node.bgcolor) node.bgcolor = "#1E1830";
  },
});
