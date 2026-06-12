"use strict";

// MIME-type mappings to user-friendly emojis
const ICONS = {
  'image/':          '🖼️',
  'video/':          '🎬',
  'audio/':          '🎵',
  'text/':           '📄',
  'application/pdf': '📕',
  'application/zip': '📦',
  'application/gzip':'📦',
  'application/x-tar':'📦',
};

/**
 * Get emoji icon based on file mime type
 * @param {string} mime 
 * @returns {string} icon emoji
 */
function getIcon(mime) {
  if (!mime) return '📦';
  for (const [k, v] of Object.entries(ICONS)) {
    if (mime.startsWith(k)) return v;
  }
  return '📦';
}

/**
 * Format file size in bytes to human readable form
 * @param {number} n size in bytes
 * @returns {string} formatted string (e.g. "12.4 MB")
 */
function fmtSize(n) {
  const u = ['B','KB','MB','GB'];
  for (const x of u) {
    if (n < 1024) return n.toFixed(1) + ' ' + x;
    n /= 1024;
  }
  return n.toFixed(1) + ' GB';
}

/**
 * Format ISO string to a clean UTC representation
 * @param {string} iso ISO date string
 * @returns {string} formatted date string
 */
function fmtDate(iso) {
  return iso.slice(0, 16).replace('T', ' ') + ' UTC';
}

/**
 * Toggle password field visibility between password and text
 * @param {string} id input element ID
 * @param {HTMLButtonElement} btn button triggering toggle
 */
function togglePw(id, btn) {
  const input = document.getElementById(id);
  if (!input) return;
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.textContent = show ? '🙈' : '👁';
}

/**
 * Display a custom notification toast on the screen
 * @param {string} msg message content
 * @param {boolean} ok success status
 */
function toast(msg, ok = true) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = "toast " + (ok ? "ok" : "err");
  el.style.display = "block";
  
  // Clear any existing timeout on the element if we track it
  if (window._toastTimeout) {
    clearTimeout(window._toastTimeout);
  }
  window._toastTimeout = setTimeout(() => {
    el.style.display = "none";
  }, 2800);
}
