"use strict";

const THEMES = {
  dark:    { bg:"#0a0a0a", fg:"#e8e8e8", accent:"#00d46a" },
  neon:    { bg:"#080808", fg:"#00ff88", accent:"#ff00cc" },
  fire:    { bg:"#0a0000", fg:"#ff6600", accent:"#ff0000" },
  ocean:   { bg:"#040810", fg:"#4d9eff", accent:"#00d4ff" },
  purple:  { bg:"#080010", fg:"#cc88ff", accent:"#ff44cc" },
  gold:    { bg:"#0a0800", fg:"#ffd700", accent:"#ff8c00" },
  minimal: { bg:"#f8f8f8", fg:"#222222", accent:"#000000" },
  matrix:  { bg:"#000000", fg:"#00ff41", accent:"#00aa22" },
};

let state = {
  slug:   getSlugFromPath(),
  style:  "dots",
  theme:  "dark",
  size:   512,
  fg:     null,
  bg:     null,
  accent: null,
};

let debounceTimer = null;

function getSlugFromPath() {
  const m = location.pathname.match(/\/qr\/([a-z2-9]{8})/);
  return m ? m[1] : "x7k2m9ab";
}

// Populate Theme presets list on window load
window.addEventListener('DOMContentLoaded', () => {
  const tg = document.getElementById("theme-grid");
  if (!tg) return;
  
  for (const [name, colors] of Object.entries(THEMES)) {
    const div = document.createElement("div");
    div.className  = "theme-dot" + (name === "dark" ? " active" : "");
    div.title      = name;
    div.dataset.theme = name;
    div.style.background = `linear-gradient(135deg, ${colors.bg} 50%, ${colors.accent} 50%)`;
    div.style.border     = "2px solid " + (name === "dark" ? "var(--primary)" : "transparent");
    div.onclick = () => setTheme(name, div);
    tg.appendChild(div);
  }

  // Initialize Slug value display
  const disp = document.getElementById("url-display");
  if (disp) disp.textContent = state.slug;

  // Initialize theme options
  const t = THEMES["dark"];
  syncColorInputs(t.fg, t.bg, t.accent);

  // Trigger initial design rendering
  refresh();
});

function setStyle(s, btn) {
  state.style = s;
  document.querySelectorAll(".style-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  debounceRefresh();
}

function setTheme(name, dot) {
  state.theme  = name;
  state.fg = state.bg = state.accent = null;
  const t = THEMES[name];
  syncColorInputs(t.fg, t.bg, t.accent);
  document.querySelectorAll(".theme-dot").forEach(d => {
    d.classList.remove("active");
    d.style.border = "2px solid transparent";
  });
  dot.classList.add("active");
  dot.style.border = "2px solid var(--primary)";
  debounceRefresh();
}

function onColor(which, val) {
  if (which === "fg")  { state.fg = val; document.getElementById("fg-hex").textContent  = val; document.getElementById("fg-swatch").style.background  = val; }
  if (which === "bg")  { state.bg = val; document.getElementById("bg-hex").textContent  = val; document.getElementById("bg-swatch").style.background  = val; }
  if (which === "acc") { state.accent = val; document.getElementById("acc-hex").textContent = val; document.getElementById("acc-swatch").style.background = val; }
  debounceRefresh();
}

function syncColorInputs(fg, bg, accent) {
  const fgColor = document.getElementById("fg-color");
  if (!fgColor) return;
  fgColor.value = fg;
  document.getElementById("bg-color").value  = bg;
  document.getElementById("acc-color").value = accent;
  document.getElementById("fg-hex").textContent  = fg;
  document.getElementById("bg-hex").textContent  = bg;
  document.getElementById("acc-hex").textContent = accent;
  document.getElementById("fg-swatch").style.background  = fg;
  document.getElementById("bg-swatch").style.background  = bg;
  document.getElementById("acc-swatch").style.background = accent;
}

function onSize(val) {
  state.size = parseInt(val);
  document.getElementById("size-val").textContent = `${val} × ${val}`;
  debounceRefresh();
}

function onUrlChange() {
  const val = document.getElementById("url-display").textContent.trim();
  state.slug = val.replace(/.*\/d\//, "").replace(/.*\/qr\//, "").trim() || val;
  debounceRefresh();
}

function buildUrl() {
  const p = new URLSearchParams({ style: state.style, theme: state.theme, size: state.size });
  if (state.fg)     p.set("fg",     state.fg);
  if (state.bg)     p.set("bg",     state.bg);
  if (state.accent) p.set("accent", state.accent);
  return `/api/qr/${state.slug}?${p}`;
}

function debounceRefresh(ms=300) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(refresh, ms);
}

function refresh() {
  const img     = document.getElementById("qr-img");
  const spinner = document.getElementById("spinner");
  const badge   = document.getElementById("preview-badge");
  if (!img) return;

  img.style.display     = "none";
  spinner.style.display = "block";
  badge.textContent     = `${state.style} · ${state.theme}`;

  const url = buildUrl();
  const newImg = new window.Image();
  newImg.onload = () => {
    img.src           = url;
    img.style.display = "block";
    spinner.style.display = "none";
    img.classList.remove("loading");
    document.getElementById("preview-meta").innerHTML = `
      <span class="pmeta">style <b>${state.style}</b></span>
      <span class="pmeta">theme <b>${state.theme}</b></span>
      <span class="pmeta">size <b>${state.size}px</b></span>
    `;
  };
  newImg.onerror = () => {
    spinner.style.display = "none";
    img.style.display = "block";
    img.alt = "Failed to render. Is the server running?";
  };
  newImg.src = url;
}

function download() {
  const a  = document.createElement("a");
  a.href   = buildUrl();
  a.download = `hashit-qr-${state.slug}-${state.style}.png`;
  a.click();
}

function copyLink() {
  const url = location.origin + buildUrl();
  navigator.clipboard.writeText(url).then(() => {
    const btn = document.querySelector(".share-btn");
    btn.textContent = "✓ Copied!";
    toast('API endpoint copied to clipboard!');
    setTimeout(() => btn.innerHTML = "⧉ Copy API endpoint URL", 1800);
  });
}
