"use strict";

const slug = location.pathname.split('/').filter(Boolean).pop();
let fileInfo = null;

const MASCOTS = {
  happy: '/static/img/waifu_mascot.png',
  worried: '/static/img/waifu_mascot_worried.png',
  pout: '/static/img/waifu_mascot_pout.png'
};

function setMascot(emotion, text) {
  const img = document.getElementById('mascot-img');
  const bubble = document.getElementById('mascot-bubble');
  if (img && MASCOTS[emotion]) {
    img.src = MASCOTS[emotion];
  }
  if (bubble && text) {
    bubble.textContent = text;
  }
}

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
  setMascot('pout', "Baka! The link is expired or doesn't exist! (>_<)");
}

// Crypto & Decryption Helpers
async function sha256(str) {
  const buf = new TextEncoder().encode(str);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function getAuthHash(password) {
  return sha256(password + "hashit_auth");
}

async function decryptFile(encryptedBlob, password) {
  const fileBytes = new Uint8Array(await encryptedBlob.arrayBuffer());
  const salt = fileBytes.slice(0, 16);
  const iv = fileBytes.slice(16, 28);
  const ciphertext = fileBytes.slice(28);

  const passwordKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );

  const aesKey = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: salt,
      iterations: 100000,
      hash: "SHA-256"
    },
    passwordKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );

  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: iv },
    aesKey,
    ciphertext
  );

  return new Blob([decrypted]);
}

async function loadInfo(passwordHash) {
  let url = `/api/info/${slug}`;
  if (passwordHash) url += `?password=${encodeURIComponent(passwordHash)}`;
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
  const hashPw = location.hash ? decodeURIComponent(location.hash.substring(1)) : null;
  if (hashPw) {
    document.getElementById('pw-input').value = hashPw;
  }

  const authHash = hashPw ? await getAuthHash(hashPw) : null;
  const info = await loadInfo(authHash);
  document.getElementById('card-loading').style.display = 'none';

  if (!info) return;

  if (info === 'needs_password' || info === 'wrong_password') {
    setMascot('worried', "P-password protect? (⁄ ⁄•⁄-⁄•⁄ ⁄) Enter the password to decrypt, Senpai...");
    renderCard(null, true);
    return;
  }

  fileInfo = info;
  renderCard(info, info.protected);

  if (info.protected) {
    setMascot('worried', "Password verified! File is ready to decrypt and download, Senpai! ♡");
  } else {
    setMascot('happy', "Your file is ready to download, Senpai! ♡");
  }
}

function renderCard(info, needsPw) {
  document.getElementById('card-main').style.display = 'block';

  if (info) {
    document.getElementById('file-icon').textContent = getIcon(info.mime);
    document.getElementById('file-name').textContent = info.filename;
    document.getElementById('file-size').textContent = fmtSize(info.size);

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
    document.getElementById('file-name').textContent = 'Password Protected';
    document.getElementById('file-size').textContent = 'Decrypt to reveal file properties';
    document.getElementById('file-icon').textContent = '🔐';
  }

  if (needsPw) {
    document.getElementById('pw-section').style.display = 'block';
    document.getElementById('dl-btn').textContent = 'Decrypt & Download, Senpai! ♡';
  } else {
    document.getElementById('pw-section').style.display = 'none';
    document.getElementById('dl-btn').textContent = 'Download, Senpai! ♡';
  }

  document.getElementById('dl-btn').disabled = false;
}

async function doDownload() {
  hideError();

  const btn = document.getElementById('dl-btn');
  const pw  = document.getElementById('pw-input').value;

  let authHash = null;
  if (!fileInfo || fileInfo.protected) {
    if (!pw) {
      showError('Password required');
      setMascot('pout', "Password required, baka! (>_<)");
      return;
    }

    setMascot('worried', "Verifying password and decrypting file, Senpai... ♡");
    authHash = await getAuthHash(pw);
    const check = await loadInfo(authHash);
    if (check === 'wrong_password') {
      showError('Incorrect password');
      setMascot('pout', "Incorrect password, baka! (>_<)");
      return;
    }
    if (check === 'needs_password') {
      showError('Password required');
      setMascot('pout', "Password required, baka! (>_<)");
      return;
    }
    if (!check) return;
    fileInfo = check;
    renderCard(fileInfo, false);
  } else if (pw) {
    authHash = await getAuthHash(pw);
  }

  btn.innerHTML = '<div class="spinner"></div> Decrypting...';
  btn.disabled  = true;

  let url = `/api/download/${slug}`;
  if (authHash) url += `?password=${encodeURIComponent(authHash)}`;

  try {
    const r = await fetch(url);
    if (r.status === 401 || r.status === 403) {
      showError('Incorrect password');
      setMascot('pout', "Incorrect password, baka! (>_<)");
      btn.disabled  = false;
      btn.textContent = 'Decrypt & Download, Senpai! ♡';
      return;
    }
    if (r.status === 410) {
      showExpired('Download limit reached. This file has self-destructed.');
      return;
    }
    if (!r.ok) {
      showError('Download failed. Please try again.');
      setMascot('pout', "Download failed! Please try again, Senpai... (>_<)");
      btn.disabled  = false;
      btn.textContent = 'Download, Senpai! ♡';
      return;
    }

    const blob = await r.blob();
    
    let decryptedBlob;
    if (fileInfo.protected && pw) {
      try {
        const text = await blob.text();
        if (text.startsWith("enc:")) {
          const base64 = text.substring(4);
          const binaryStr = atob(base64);
          const len = binaryStr.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
          }
          const encBlob = new Blob([bytes]);
          decryptedBlob = await decryptFile(encBlob, pw);
        } else {
          decryptedBlob = await decryptFile(blob, pw);
        }
      } catch(e) {
        showError('Decryption failed. Check your password.');
        setMascot('pout', "Baka! Decryption failed... check your password! (>_<)");
        btn.disabled  = false;
        btn.textContent = 'Decrypt & Download, Senpai! ♡';
        return;
      }
    } else {
      decryptedBlob = blob;
    }

    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(decryptedBlob);
    a.download = fileInfo?.filename || 'file';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);

    btn.disabled     = false;
    btn.textContent  = '✓ Downloaded';
    toast('File downloaded successfully!');
    setMascot('happy', "Yay! File successfully downloaded, Senpai! ( >ᴗ<) ♡");
    setTimeout(() => { btn.textContent = 'Download again, Senpai! ♡'; }, 2500);

  } catch(e) {
    showError('Network error. Check your connection.');
    setMascot('pout', "Network error! Check your connection, Senpai... (>_<)");
    btn.disabled  = false;
    btn.textContent = 'Download, Senpai! ♡';
  }
}

function copyLink() {
  navigator.clipboard.writeText(location.href).then(() => {
    const btn = document.querySelector('.btn-secondary');
    btn.textContent = '✓ Copied link';
    toast('Link copied to clipboard!');
    setTimeout(() => btn.textContent = 'Copy link ( >ᴗ<)', 1500);
  });
}

// Initialise load
init();
