"use strict";

const slug = location.pathname.split("/").filter(Boolean).pop();
let collection = null;

async function init() {
  const r = await fetch(`/api/collection/${slug}`).catch(() => null);
  document.getElementById("loading").style.display = "none";
  if (!r || !r.ok) {
    document.getElementById("not-found").style.display = "block";
    return;
  }
  collection = await r.json();
  render();
}

function render() {
  document.getElementById("content").style.display = "block";
  document.getElementById("col-title").textContent = collection.title || "Collection Bundle";
  document.getElementById("col-meta").innerHTML = [
    `<span class="col-chip"><b>${collection.files.length}</b> file${collection.files.length !== 1 ? 's' : ''}</span>`,
    `<span class="col-chip">expires <b>${fmtDate(collection.expires_at)}</b></span>`,
  ].join("");

  document.getElementById("file-list").innerHTML = collection.files.map(f => `
    <div class="file-card">
      <div class="file-icon">${getIcon(f.mime)}</div>
      <div class="file-info">
        <div class="file-name">${f.filename}</div>
        <div class="file-meta">
          <span>${fmtSize(f.size)}</span>
          <span>·</span>
          <span>${f.mime}</span>
        </div>
      </div>
      <a href="/api/download/${f.slug}" class="dl-btn" download="${f.filename}">↓ download</a>
    </div>
  `).join("");
}

function downloadAll() {
  toast('Downloading all files...');
  for (const f of collection.files) {
    const a = document.createElement("a");
    a.href     = `/api/download/${f.slug}`;
    a.download = f.filename;
    a.click();
  }
}

// Initialise
init();
