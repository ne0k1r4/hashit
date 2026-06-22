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

// Sakura Blossom Falling Animation
window.addEventListener('DOMContentLoaded', () => {
  const canvas = document.createElement('canvas');
  canvas.id = 'sakura-canvas';
  canvas.style.position = 'fixed';
  canvas.style.top = '0';
  canvas.style.left = '0';
  canvas.style.width = '100vw';
  canvas.style.height = '100vh';
  canvas.style.pointerEvents = 'none';
  canvas.style.zIndex = '0';
  document.body.prepend(canvas);

  const ctx = canvas.getContext('2d');
  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const petals = [];
  const maxPetals = 45;

  class Petal {
    constructor() {
      this.reset();
      this.y = Math.random() * height; // initial distribution
    }

    reset() {
      this.x = Math.random() * width;
      this.y = -20;
      this.size = Math.random() * 8 + 6;
      this.speedY = Math.random() * 1.2 + 0.8;
      this.speedX = Math.random() * 1.0 - 0.3;
      this.angle = Math.random() * 360;
      this.spinSpeed = Math.random() * 1.5 - 0.75;
      this.opacity = Math.random() * 0.4 + 0.4;
    }

    update() {
      this.y += this.speedY;
      this.x += this.speedX + Math.sin(this.y / 30) * 0.4; // sway
      this.angle += this.spinSpeed;

      if (this.y > height || this.x < -20 || this.x > width + 20) {
        this.reset();
      }
    }

    draw() {
      ctx.save();
      ctx.translate(this.x, this.y);
      ctx.rotate(this.angle * Math.PI / 180);
      
      // Draw organic petal path
      ctx.beginPath();
      ctx.ellipse(0, 0, this.size, this.size / 2, 0, 0, 2 * Math.PI);
      
      // Gradient pink style
      const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, this.size);
      grad.addColorStop(0, `rgba(255, 182, 193, ${this.opacity})`);
      grad.addColorStop(1, `rgba(255, 105, 180, ${this.opacity * 0.5})`);
      
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.restore();
    }
  }

  for (let i = 0; i < maxPetals; i++) {
    petals.push(new Petal());
  }

  function loop() {
    ctx.clearRect(0, 0, width, height);
    for (let p of petals) {
      p.update();
      p.draw();
    }
    requestAnimationFrame(loop);
  }
  loop();
});
