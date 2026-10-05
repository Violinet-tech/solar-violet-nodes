// Violet node theme: header and body colors taken from the Violet Diffusion site palette
// (void #0A0710, ink #14101C, slate #1E1830, violet #A855F7, deep violet #6D28D9).

import { app } from "../../scripts/app.js";

const isViolet = (name) => /^(Violet|SolarViolet|SolarLora|SolarModel|SolarPrompt|SolarImage)/.test(name || "");

app.registerExtension({
  name: "Violet.Theme",
  nodeCreated(node) {
    if (!isViolet(node.comfyClass || node.type)) return;
    if (!node.color) node.color = "#6D28D9";
    if (!node.bgcolor) node.bgcolor = "#1E1830";
  },
});
