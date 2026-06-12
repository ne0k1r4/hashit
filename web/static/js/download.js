"use strict";

const slug = location.pathname.split('/').filter(Boolean).pop();
let fileInfo = null;

function showError(msg) {
  const el = document.getElementById('error-box');
  el.textContent = msg;
  el.style.display = 'block';
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideError() {
  document.getElementById('error-box').style.display = 'none';
}

function showExpired(msg) {
  document.getElementById('card-loading').style.display = 'none';
  document.getElementById('card-main').style.display    = 'none';
  document.getElementById('card-expired').style.display = 'block';
  document.getElementById('expired-msg').textContent = msg || 'This link has expired or never existed.';
}

async function loadInfo(password) {
  let url = `/api/info/${slug}`;
  if (password) url += `?password=${encodeURIComponent(password)}`;
  try {
    const r = await fetch(url);
    if (r.status === 404 || r.status === 410) {
      const d = await r.json().catch(() => ({}));
      showExpired(d.detail);
      return null;
    }
    if (r.status === 401) return 'needs_password';
    if (r.status === 403) return 'wrong_password';
    if (!r.ok) { showExpired('Something went wrong.'); return null; }
    return r.json();
  } catch(e) {
    showExpired('Could not reach the server.');
    return null;
  }
}

async function init() {
  const info = await loadInfo(null);
  document.getElementById('card-loading').style.display = 'none';

  if (!info) return;

  if (info === 'needs_password') {
    renderCard(null, true);
    return;
  }

  fileInfo = info;
  renderCard(info, info.protected);
}

function renderCard(info, needsPw) {
  document.getElementById('card-main').style.display = 'block';

  if (info) {
    document.getElementById('file-icon').textContent = getIcon(info.mime);
    document.getElementById('file-name').textContent = info.filename;
    document.getElementById('file-size').textContent = fmtSize(info.size);

    // Meta chips representation
    const chips = [
      `<span class="meta-chip">expires <b>${fmtDate(info.expires_at)}</b></span>`,
      `<span class="meta-chip">downloads <b>${info.downloads}${info.max_downloads ? '/' + info.max_downloads : ''}</b></span>`,
    ];
    if (info.max_downloads && info.downloads >= info.max_downloads - 1) {
      const remaining = info.max_downloads - info.downloads;
      chips.push(`<span class="meta-chip warn">⚠ <b>${remaining} download${remaining !== 1 ? 's' : ''} left</b></span>`);
    }
    if (info.protected) {
      chips.push(`<span class="meta-chip">🔐 <b>password locked</b></span>`);
    }
    document.getElementById('meta-row').innerHTML = chips.join('');
  } else {
    // Unknown because of password protection
    document.getElementById('file-name').textContent = 'Password Protected';
    document.getElementById('file-size').textContent = 'Decrypt to reveal file properties';
    document.getElementById('file-icon').textContent = '🔐';
  }

  if (needsPw) {
    document.getElementById('pw-section').style.display = 'block';
    document.getElementById('dl-btn').textContent = 'Decrypt & Download';
  } else {
    document.getElementById('pw-section').style.display = 'none';
    document.getElementById('dl-btn').textContent = 'Download';
  }

  document.getElementById('dl-btn').disabled = false;
}

async function doDownload() {
  hideError();

  const btn = document.getElementById('dl-btn');
  const pw  = document.getElementById('pw-input').value;

  if (!fileInfo || fileInfo.protected) {
    if (!pw) { showError('Password required'); return; }

    const check = await loadInfo(pw);
    if (check === 'wrong_password') {
      showError('Incorrect password');
      return;
    }
    if (check === 'needs_password') {
      showError('Password required');
      return;
    }
    if (!check) return;
    fileInfo = check;
    renderCard(fileInfo, false);
  }

  btn.innerHTML = '<div class="spinner"></div>';
  btn.disabled  = true;

  let url = `/api/download/${slug}`;
  if (pw) url += `?password=${encodeURIComponent(pw)}`;

  try {
    const r = await fetch(url);
    if (r.status === 401 || r.status === 403) {
      showError('Incorrect password');
      btn.disabled  = false;
      btn.textContent = 'Decrypt & Download';
      return;
    }
    if (r.status === 410) {
      showExpired('Download limit reached. This file has self-destructed.');
      return;
    }
    if (!r.ok) {
      showError('Download failed. Please try again.');
      btn.disabled  = false;
      btn.textContent = 'Download';
      return;
    }

    const blob = await r.blob();
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = fileInfo?.filename || 'file';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);

    btn.disabled     = false;
    btn.textContent  = '✓ Downloaded';
    toast('File downloaded successfully!');
    setTimeout(() => { btn.textContent = 'Download again'; }, 2500);

  } catch(e) {
    showError('Network error. Check your connection.');
    btn.disabled  = false;
    btn.textContent = 'Download';
  }
}

function copyLink() {
  navigator.clipboard.writeText(location.href).then(() => {
    const btn = document.querySelector('.btn-secondary');
    btn.textContent = '✓ Copied link';
    toast('Link copied to clipboard!');
    setTimeout(() => btn.textContent = 'Copy link', 1500);
  });
}

// Initialise load
init();
