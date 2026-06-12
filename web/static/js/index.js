"use strict";

let selectedFile = null;
let uploadStart  = 0;

// Tab Switching
function switchTab(name, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
  document.getElementById('result').style.display = 'none';
}

// Drag & Drop Handlers
function onDragOver(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.add('dragover');
}

function onDragLeave(e) {
  document.getElementById('dropzone').classList.remove('dragover');
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
function doUpload() {
  if (!selectedFile) return;

  const btn = document.getElementById('upload-btn');
  btn.disabled  = true;
  btn.innerHTML = '<span class="spin"></span> Uploading...';
  uploadStart   = Date.now();

  document.getElementById('progress').style.display = 'block';
  document.getElementById('result').style.display   = 'none';

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('ttl', document.getElementById('f-ttl').value);
  const pw = document.getElementById('f-pw').value;
  const maxdl = document.getElementById('f-maxdl').value;
  if (pw) fd.append('password', pw);
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
    btn.innerHTML = 'Upload &amp; get link';

    if (xhr.status !== 200) {
      let msg = 'Upload failed';
      try { msg = JSON.parse(xhr.responseText).detail || msg; } catch {}
      toast(msg, false);
      return;
    }

    const r = JSON.parse(xhr.responseText);
    const tags = [
      ['size', fmtSize(r.size)],
      ['expires', fmtDate(r.expires_at)],
    ];
    if (r.protected) tags.push(['🔐', 'password protected']);
    if (r.max_downloads) tags.push(['max dl', r.max_downloads]);

    const downloadApiUrl = r.url.replace('/d/', '/api/download/');
    const note = `<code>curl -LO "${downloadApiUrl}"</code>` +
      (r.delete_token ? `  ·  delete token: <code>${r.delete_token.slice(0, 12)}…</code>` : '');

    showResult(r, tags, note);
    toast('File uploaded successfully!');
  };

  xhr.onerror = () => {
    document.getElementById('progress').style.display = 'none';
    btn.disabled  = false;
    btn.innerHTML = 'Upload &amp; get link';
    toast('Network error — is the server running?', false);
  };

  xhr.send(fd);
}

// Paste Execution
async function doPaste() {
  const content = document.getElementById('paste-text').value.trim();
  if (!content) return;

  const fd = new FormData();
  fd.append('content', content);
  fd.append('ttl', document.getElementById('p-ttl').value);
  fd.append('filename', document.getElementById('p-name').value || 'paste.txt');
  const pw = document.getElementById('p-pw').value;
  if (pw) fd.append('password', pw);

  try {
    const resp = await fetch('/api/paste', { method: 'POST', body: fd });
    if (!resp.ok) {
      const d = await resp.json().catch(() => ({}));
      toast(d.detail || 'paste failed', false);
      return;
    }
    const r = await resp.json();
    showResult(r,
      [['expires', fmtDate(r.expires_at)], ['size', fmtSize(r.size)]],
      null
    );
    toast('Paste shared successfully!');
  } catch(e) {
    toast('Network error', false);
  }
}
