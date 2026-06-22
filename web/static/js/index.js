"use strict";

let selectedFile = null;
let uploadStart  = 0;

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

// Key Derivation and Encryption Helpers
async function sha256(str) {
  const buf = new TextEncoder().encode(str);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function getAuthHash(password) {
  return sha256(password + "hashit_auth");
}

async function encryptFile(file, password) {
  const fileBytes = new Uint8Array(await file.arrayBuffer());
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  
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
    ["encrypt"]
  );
  
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: iv },
    aesKey,
    fileBytes
  );
  
  const encryptedBytes = new Uint8Array(salt.byteLength + iv.byteLength + ciphertext.byteLength);
  encryptedBytes.set(salt, 0);
  encryptedBytes.set(iv, salt.byteLength);
  encryptedBytes.set(new Uint8Array(ciphertext), salt.byteLength + iv.byteLength);
  
  return new Blob([encryptedBytes], { type: "application/octet-stream" });
}

async function blobToBase64(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result.split(',')[1];
      resolve(base64);
    };
    reader.readAsDataURL(blob);
  });
}

// Tab Switching
function switchTab(name, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
  document.getElementById('result').style.display = 'none';

  if (name === 'paste') {
    setMascot('happy', "Pasting some code or secret texts, Senpai? I will keep them safe! ♡");
  } else {
    setMascot('happy', "Drop your files here, Senpai! I'll guard them! ♡");
  }
}

// Drag & Drop Handlers
function onDragOver(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.add('dragover');
  setMascot('happy', "Ooh! Dragging a file over for me, Senpai? Drop it! ♡");
}

function onDragLeave(e) {
  document.getElementById('dropzone').classList.remove('dragover');
  setMascot('happy', "Drop your files here, Senpai! I'll guard them! ♡");
}

function onDrop(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.remove('dragover');
  onFileSelect(e.dataTransfer.files);
}

function onFileSelect(files) {
  if (!files || !files.length) return;
  selectedFile = files[0];
  document.getElementById('dz-default').style.display = 'none';
  const sel = document.getElementById('dz-selected');
  sel.classList.add('show');
  document.getElementById('dz-name').textContent = selectedFile.name;
  document.getElementById('dz-size').textContent = fmtSize(selectedFile.size);
  document.getElementById('upload-btn').disabled = false;
  setMascot('happy', "Ooh, nice file, Senpai! Ready when you are! ( >ᴗ<) ♡");
}

// UI Result Visualizer
function showResult(r, tags, note) {
  const box = document.getElementById('result');
  document.getElementById('result-url').value = r.url;
  box.style.display = 'block';

  const meta = document.getElementById('result-meta');
  meta.innerHTML = tags.map(([k, v]) =>
    `<span class="meta-tag">${k} <b>${v}</b></span>`
  ).join('');

  document.getElementById('result-note').innerHTML = note || '';
  document.getElementById('copy-btn').textContent = 'Copy';
  document.getElementById('copy-btn').classList.remove('copied');

  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function copyUrl() {
  const url = document.getElementById('result-url').value;
  navigator.clipboard.writeText(url).then(() => {
    const btn = document.getElementById('copy-btn');
    btn.textContent = 'Copied ✓';
    btn.classList.add('copied');
    toast('URL copied to clipboard!');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
}

// Upload Execution (XHR)
async function doUpload() {
  if (!selectedFile) return;

  const btn = document.getElementById('upload-btn');
  btn.disabled  = true;
  btn.innerHTML = '<span class="spin"></span> Uploading...';
  uploadStart   = Date.now();

  document.getElementById('progress').style.display = 'block';
  document.getElementById('result').style.display   = 'none';

  setMascot('worried', "I'm uploading it right now! Don't look away, okay? (⁄ ⁄>⁄ ⁄<⁄ ⁄) ♡");

  const fd = new FormData();
  const pw = document.getElementById('f-pw').value;
  const maxdl = document.getElementById('f-maxdl').value;
  
  let filePayload = selectedFile;
  if (pw) {
    try {
      filePayload = await encryptFile(selectedFile, pw);
      const authHash = await getAuthHash(pw);
      fd.append('password', authHash);
    } catch(e) {
      toast('Encryption failed: ' + e.message, false);
      setMascot('pout', "Baka! Encryption failed... (>_<)");
      btn.disabled = false;
      btn.innerHTML = 'Upload for me, Senpai! ♡';
      document.getElementById('progress').style.display = 'none';
      return;
    }
  }

  fd.append('file', filePayload, selectedFile.name);
  fd.append('ttl', document.getElementById('f-ttl').value);
  if (maxdl) fd.append('max_downloads', maxdl);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/upload');

  xhr.upload.onprogress = e => {
    if (!e.lengthComputable) return;
    const pct   = Math.round(e.loaded / e.total * 100);
    const secs  = (Date.now() - uploadStart) / 1000;
    const speed = secs > 0 ? fmtSize(e.loaded / secs) + '/s' : '';
    document.getElementById('progress-fill').style.width = pct + '%';
    document.getElementById('progress-pct').textContent  = pct + '%';
    document.getElementById('progress-speed').textContent = speed;
  };

  xhr.onload = () => {
    document.getElementById('progress').style.display = 'none';
    btn.disabled  = false;
    btn.innerHTML = 'Upload for me, Senpai! ♡';

    if (xhr.status !== 200) {
      let msg = 'Upload failed';
      try { msg = JSON.parse(xhr.responseText).detail || msg; } catch {}
      toast(msg, false);
      setMascot('pout', "Oh no, baka! Upload failed: " + msg + " (>_<)");
      return;
    }

    const r = JSON.parse(xhr.responseText);
    const tags = [
      ['size', fmtSize(selectedFile.size)],
      ['expires', fmtDate(r.expires_at)],
    ];
    if (r.protected) tags.push(['🔐', 'password protected']);
    if (r.max_downloads) tags.push(['max dl', r.max_downloads]);

    const downloadApiUrl = r.url.replace('/d/', '/api/download/');
    const note = `<code>curl -LO "${downloadApiUrl}"</code>` +
      (r.delete_token ? `  ·  delete token: <code>${r.delete_token.slice(0, 12)}…</code>` : '');

    if (pw) {
      r.url += '#' + encodeURIComponent(pw);
    }

    showResult(r, tags, note);
    toast('File uploaded successfully!');
    setMascot('happy', "Yay! Your file was successfully guarded, Senpai! ( >ᴗ<) ♡");
  };

  xhr.onerror = () => {
    document.getElementById('progress').style.display = 'none';
    btn.disabled  = false;
    btn.innerHTML = 'Upload for me, Senpai! ♡';
    toast('Network error — is the server running?', false);
    setMascot('pout', "Baka! Network error... is the server running? (>_<)");
  };

  xhr.send(fd);
}

// Paste Execution
async function doPaste() {
  const content = document.getElementById('paste-text').value.trim();
  if (!content) return;

  setMascot('worried', "Pasting it onto the server... wait a second, Senpai! ♡");

  const fd = new FormData();
  const pw = document.getElementById('p-pw').value;
  
  let pasteContent = content;
  if (pw) {
    try {
      const authHash = await getAuthHash(pw);
      fd.append('password', authHash);
      const textBlob = new Blob([new TextEncoder().encode(content)], { type: "text/plain" });
      const encBlob = await encryptFile(textBlob, pw);
      const base64 = await blobToBase64(encBlob);
      pasteContent = "enc:" + base64;
    } catch(e) {
      toast('Paste encryption failed: ' + e.message, false);
      setMascot('pout', "Baka! Encryption failed... (>_<)");
      return;
    }
  }

  fd.append('content', pasteContent);
  fd.append('ttl', document.getElementById('p-ttl').value);
  fd.append('filename', document.getElementById('p-name').value || 'paste.txt');

  try {
    const resp = await fetch('/api/paste', { method: 'POST', body: fd });
    if (!resp.ok) {
      const d = await resp.json().catch(() => ({}));
      toast(d.detail || 'paste failed', false);
      setMascot('pout', "Baka! Paste failed: " + (d.detail || 'unknown error') + " (>_<)");
      return;
    }
    const r = await resp.json();
    
    if (pw) {
      r.url += '#' + encodeURIComponent(pw);
    }

    showResult(r,
      [['expires', fmtDate(r.expires_at)], ['size', fmtSize(r.size)]],
      null
    );
    toast('Paste shared successfully!');
    setMascot('happy', "Yay! Paste successfully shared, Senpai! ( >ᴗ<) ♡");
  } catch(e) {
    toast('Network error', false);
    setMascot('pout', "Network error... paste failed, baka! (>_<)");
  }
}
