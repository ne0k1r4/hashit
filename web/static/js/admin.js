"use strict";

const PAGE_SIZE = 50;
let token = localStorage.getItem("hashit_admin_token") || "";
let allFiles = [];
let page = 0;

// Auto-populate token on load if exists
window.addEventListener('DOMContentLoaded', () => {
  if (token) {
    const input = document.getElementById("token-input");
    if (input) input.value = token;
    load();
  }
});

async function load() {
  const inputEl = document.getElementById("token-input");
  if (!inputEl) return;
  token = inputEl.value.trim();
  localStorage.setItem("hashit_admin_token", token);

  try {
    const [statsRes, filesRes] = await Promise.all([
      fetch("/api/admin/stats", { headers: { "X-Admin-Token": token } }),
      fetch(`/api/admin/files?limit=500`, { headers: { "X-Admin-Token": token } }),
    ]);

    if (statsRes.status === 403) {
      toast("Wrong token supplied", false);
      document.getElementById("auth-screen").style.display = "flex";
      document.getElementById("dashboard").style.display   = "none";
      return;
    }

    if (!statsRes.ok || !filesRes.ok) {
      toast("Failed to connect", false);
      return;
    }

    const stats = await statsRes.json();
    const files = await filesRes.json();

    document.getElementById("auth-screen").style.display = "none";
    document.getElementById("dashboard").style.display   = "block";

    document.getElementById("s-files").textContent = stats.active_files;
    document.getElementById("s-size").textContent  = fmtSize(stats.total_size_bytes);
    document.getElementById("s-dls").textContent   = stats.total_downloads;
    document.getElementById("s-exp").textContent   = stats.expired_files;

    allFiles = files;
    page = 0;
    renderTable();
    toast(`Retrieved ${files.length} active files`);
  } catch(e) {
    toast("Connection error", false);
  }
}

function filterTable() {
  page = 0;
  renderTable();
}

// Convert dates to a human-friendly duration from now
function fmtAdminDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  const diff = d - now;
  if (diff < 0) return "expired";
  if (diff < 3600000) return Math.round(diff/60000)+"m";
  if (diff < 86400000) return Math.round(diff/3600000)+"h";
  return Math.round(diff/86400000)+"d";
}

function renderTable() {
  const q = document.getElementById("search").value.toLowerCase();
  const filtered = allFiles.filter(f =>
    !q || f.filename.toLowerCase().includes(q) || f.slug.includes(q)
  );
  const pageFiles = filtered.slice(page * PAGE_SIZE, (page+1) * PAGE_SIZE);

  const tbody = document.getElementById("files-tbody");
  if (!tbody) return;

  if (!filtered.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">No active files matching query</td></tr>`;
    return;
  }

  tbody.innerHTML = pageFiles.map(f => {
    const exp     = new Date(f.expires_at) < new Date();
    const typeTag = f.is_paste
      ? `<span class="badge badge-paste">paste</span>`
      : `<span class="badge badge-file">file</span>`;
    const expTag  = exp ? `<span class="badge badge-expired">expired</span>` : fmtAdminDate(f.expires_at);
    return `<tr>
      <td class="td-slug"><a href="/d/${f.slug}" target="_blank">${f.slug}</a></td>
      <td class="td-name" title="${f.filename}">${f.filename}</td>
      <td>${typeTag}</td>
      <td class="td-size">${fmtSize(f.size)}</td>
      <td class="td-dl">${f.downloads}</td>
      <td class="td-exp">${expTag}</td>
      <td class="td-ip">${f.ip || "—"}</td>
      <td><button class="del-btn" onclick="del('${f.slug}')" title="delete">✕</button></td>
    </tr>`;
  }).join("");

  document.getElementById("prev-btn").disabled = page === 0;
  document.getElementById("next-btn").disabled = (page+1)*PAGE_SIZE >= filtered.length;
  document.getElementById("page-label").textContent =
    `${page*PAGE_SIZE+1}–${Math.min((page+1)*PAGE_SIZE, filtered.length)} of ${filtered.length}`;
}

function prevPage() { if (page > 0) { page--; renderTable(); } }
function nextPage() { page++; renderTable(); }

async function del(slug) {
  if (!confirm(`Are you sure you want to delete ${slug}?`)) return;
  try {
    const r = await fetch(`/api/admin/files/${slug}`, {
      method: "DELETE",
      headers: { "X-Admin-Token": token },
    });
    if (r.ok) {
      allFiles = allFiles.filter(f => f.slug !== slug);
      renderTable();
      toast(`Successfully deleted ${slug}`);
    } else {
      toast("Delete operation failed", false);
    }
  } catch(e) {
    toast("Network error deleting file", false);
  }
}

async function purgeAll() {
  if (!confirm("Purge all expired files now?")) return;
  toast("Purging files...");
  await load();
  toast("Purge complete");
}
