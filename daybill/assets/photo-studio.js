// Photo studio (customer page): add one or more photos, give each photo its own size and number, place it in the
// frame (move / zoom / rotate / flip / brightness / contrast / colour). All photos are arranged on the photo paper
// automatically – new sheets are added when needed – with a live picture of the sheets. "Add to order" makes the
// print-ready PDF here in the browser (pdf-lib) and adds it to the order as one item.
// Needs assets/pdf-lib.min.js, assets/layout.js (paper sizes) and window.DaybillOrder (set by index.php).
(function () {
  var O = window.DaybillOrder;
  if (!O || !O.PHOTO || !window.DaybillLayout) return;
  var PHOTO = O.PHOTO, T = O.T, DL = window.DaybillLayout, $ = function (id) { return document.getElementById(id); };
  var MAX_PHOTOS = 12, MM = 72 / 25.4, GAP = DL.GAP;
  var tool = $('photoTool'), editor = $('stEdit'), bigSheet = $('ptPreview');
  var stage = $('stStage'), sctx = stage.getContext('2d'), canFilter = 'filter' in sctx;
  var paper = DL.papers[PHOTO.paper] || DL.papers.A4, margin = DL.margin(PHOTO.paper);
  var UW = paper[0] - 2 * margin, UH = paper[1] - 2 * margin; // printable area in mm
  var state = null;  // { photos: [...], item: order item being changed (or null), plan }
  var edit = null;   // photo open in the editor
  var frame = null;  // frame position on the editor stage (CSS px)
  var lastSize = null;

  function def(id) { return O.PDEFS[id]; }
  function fits(S) { return (S.w <= UW && S.h <= UH) || (S.h <= UW && S.w <= UH); }
  var SIZES = PHOTO.sizes.filter(fits);
  if (!SIZES.length) return;
  function isId(S) { return S.h > S.w && S.w <= 60; } // passport / visa photos get the face guide
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function fmt(s) { var a = arguments; return s.replace(/%(\d)\$[sd]/g, function (_, n) { return a[+n]; }).replace(/%[sd]/, a[1]); }

  // Upright or turned on the paper, whichever fits more photos of this size on one sheet.
  function orient(S) {
    function n(w, h) { return w <= UW && h <= UH ? Math.floor((UW + GAP) / (w + GAP)) * Math.floor((UH + GAP) / (h + GAP)) : 0; }
    var a = n(S.w, S.h), b = n(S.h, S.w);
    return { rot: S.w !== S.h && b > a, max: Math.max(a, b) };
  }

  // ---------- arranging: rows of photos (tallest first), a new sheet when the paper is full ----------
  function pack() {
    var pieces = [], sheets = [], sheet = null, row = null;
    state.photos.forEach(function (p, i) {
      var S = def(p.size), o = orient(S);
      for (var k = 0; k < p.copies; k++) pieces.push({ p: i, w: o.rot ? S.h : S.w, h: o.rot ? S.w : S.h, rot: o.rot });
    });
    pieces.sort(function (a, b) { return b.h - a.h || b.w - a.w || a.p - b.p; });
    pieces.forEach(function (c) {
      if (row && row.x + c.w > UW + 0.01) {
        var y = row.y + row.h + GAP;
        row = y + c.h <= UH + 0.01 ? { x: 0, y: y, h: c.h } : null;
      }
      if (!row) { sheet = []; sheets.push(sheet); row = { x: 0, y: 0, h: c.h }; }
      c.x = row.x; c.y = row.y; row.x += c.w + GAP; sheet.push(c);
    });
    sheets.forEach(function (s) { // centre the block left–right, start at the top
      var right = 0;
      s.forEach(function (c) { right = Math.max(right, c.x + c.w); });
      s.forEach(function (c) { c.x += margin + (UW - right) / 2; c.y += margin; });
    });
    return { pw: paper[0], ph: paper[1], sheets: sheets };
  }

  // ---------- drawing one photo ----------
  function filterOf(p) { return 'brightness(' + p.bright + '%) contrast(' + p.contrast + '%) saturate(' + p.sat + '%)'; }
  function adjusted(p) { return p.bright !== 100 || p.contrast !== 100 || p.sat !== 100; }
  function scaleOf(p, fw, fh) {
    var odd = p.rot % 2 === 1, bw = odd ? p.src.height : p.src.width, bh = odd ? p.src.width : p.src.height;
    return { s: (p.fit ? Math.min(fw / bw, fh / bh) : Math.max(fw / bw, fh / bh)) * p.zoom, bw: bw, bh: bh };
  }
  // The photo inside a fw×fh frame at fx,fy: "fill" covers the frame, "fit" shows the whole photo.
  function paint(x, fx, fy, fw, fh, p) {
    var src = p.src, k = scaleOf(p, fw, fh).s;
    x.save();
    x.beginPath(); x.rect(fx, fy, fw, fh); x.clip();
    x.translate(fx + fw / 2 + p.ox * fw, fy + fh / 2 + p.oy * fh);
    x.rotate(p.rot * Math.PI / 2);
    if (p.flip) x.scale(p.rot % 2 ? 1 : -1, p.rot % 2 ? -1 : 1); // always a left–right mirror on screen
    x.drawImage(src, -src.width * k / 2, -src.height * k / 2, src.width * k, src.height * k);
    x.restore();
  }
  // Keeps a filled frame free of white edges (and a fitted photo inside its frame).
  function clamp(p) {
    var S = def(p.size), fw = 1000, fh = 1000 * S.h / S.w, m = scaleOf(p, fw, fh);
    var mx = Math.abs(m.bw * m.s - fw) / 2 / fw, my = Math.abs(m.bh * m.s - fh) / 2 / fh;
    p.ox = Math.max(-mx, Math.min(mx, p.ox)); p.oy = Math.max(-my, Math.min(my, p.oy));
  }
  // Older Safari has no canvas filters: change the pixels by hand (same order as the CSS filters).
  function manual(c, p) {
    var x = c.getContext('2d'), d = x.getImageData(0, 0, c.width, c.height), a = d.data;
    var b = p.bright / 100, k = p.contrast / 100, s = p.sat / 100;
    for (var i = 0; i < a.length; i += 4) {
      var r = a[i] * b, g = a[i + 1] * b, bl = a[i + 2] * b;
      r = (r - 128) * k + 128; g = (g - 128) * k + 128; bl = (bl - 128) * k + 128;
      var L = 0.2126 * r + 0.7152 * g + 0.0722 * bl;
      a[i] = L + (r - L) * s; a[i + 1] = L + (g - L) * s; a[i + 2] = L + (bl - L) * s; // Uint8ClampedArray clamps
    }
    x.putImageData(d, 0, 0);
  }
  // The finished photo (its size at longPx on the long side); turn = 90° for photos placed sideways.
  function render(p, longPx, turn) {
    var S = def(p.size), k = longPx / Math.max(S.w, S.h), w = Math.round(S.w * k), h = Math.round(S.h * k);
    var c = el('canvas'), x = c.getContext('2d');
    c.width = turn ? h : w; c.height = turn ? w : h;
    x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height);
    if (turn) { x.translate(c.width, 0); x.rotate(Math.PI / 2); }
    if (canFilter) x.filter = filterOf(p);
    paint(x, 0, 0, w, h, p);
    if (!canFilter && adjusted(p)) manual(c, p);
    return c;
  }
  function printPx(p) { var S = def(p.size); return Math.min(2400, Math.round(Math.max(S.w, S.h) / 25.4 * 300)); } // 300 dpi
  function small(p) { return p.prev || (p.prev = render(p, 480, false)); }
  function toBlob(c, q) { return new Promise(function (r) { c.toBlob(r, 'image/jpeg', q || 0.92); }); }

  // ---------- sheets ----------
  function drawSheet(cv, plan, i, widthPx) {
    var s = widthPx / plan.pw, x = cv.getContext('2d');
    cv.width = Math.round(plan.pw * s); cv.height = Math.round(plan.ph * s);
    x.fillStyle = '#fff'; x.fillRect(0, 0, cv.width, cv.height);
    (plan.sheets[i] || []).forEach(function (c) {
      var img = small(state.photos[c.p]), dx = c.x * s, dy = c.y * s, dw = c.w * s, dh = c.h * s;
      if (!c.rot) x.drawImage(img, dx, dy, dw, dh);
      else { x.save(); x.translate(dx + dw, dy); x.rotate(Math.PI / 2); x.drawImage(img, 0, 0, dh, dw); x.restore(); }
      x.strokeStyle = 'rgba(0,0,0,.22)'; x.lineWidth = 1; x.strokeRect(dx + .5, dy + .5, dw - 1, dh - 1);
    });
  }
  function hit(plan, i, mmX, mmY) {
    var found = -1;
    (plan.sheets[i] || []).forEach(function (c) { if (mmX >= c.x && mmX <= c.x + c.w && mmY >= c.y && mmY <= c.y + c.h) found = c.p; });
    return found;
  }

  // ---------- main screen: sheets + list of photos ----------
  function totals() {
    var n = 0;
    state.photos.forEach(function (p) { n += p.copies; });
    return { pieces: n, sheets: state.plan.sheets.length };
  }
  function renderMain() {
    var has = state.photos.length > 0;
    $('stEmpty').classList.toggle('hidden', has);
    $('stMain').classList.toggle('hidden', !has);
    $('stFoot').classList.toggle('hidden', !has);
    if (!has) return;
    var plan = state.plan = pack(), t = totals();

    // Sheets (swipe sideways); tap a photo to change it, tap the paper for a big preview
    var box = $('stSheets'), w = Math.min(230, Math.max(150, box.clientWidth * 0.62 || 200)), dpr = window.devicePixelRatio || 1;
    box.innerHTML = '';
    plan.sheets.slice(0, 8).forEach(function (_, i) {
      var fig = el('figure', 'st-sheet'), cv = el('canvas');
      drawSheet(cv, plan, i, w * dpr);
      cv.style.width = w + 'px';
      cv.addEventListener('click', function (e) {
        var r = cv.getBoundingClientRect(), p = hit(plan, i, (e.clientX - r.left) / r.width * plan.pw, (e.clientY - r.top) / r.height * plan.ph);
        if (p >= 0) openEditor(p); else openPreview();
      });
      fig.appendChild(cv);
      fig.appendChild(el('figcaption', '', fmt(T.photo_sheet_of, i + 1, plan.sheets.length)));
      box.appendChild(fig);
    });
    if (plan.sheets.length > 8) box.appendChild(el('span', 'st-more', '+' + (plan.sheets.length - 8)));
    $('stInfo').textContent = fmt(T.st_summary, t.pieces, t.sheets, PHOTO.paper);

    // One row per photo
    var list = $('stList');
    list.innerHTML = '';
    state.photos.forEach(function (p, i) {
      var S = def(p.size), row = el('div', 'st-row'), th = el('button', 'st-thumb'), cv = el('canvas');
      var ph = 64, pw = Math.round(ph * S.w / S.h), dpr2 = window.devicePixelRatio || 1;
      cv.width = pw * dpr2; cv.height = ph * dpr2; cv.style.width = pw + 'px'; cv.style.height = ph + 'px';
      cv.getContext('2d').drawImage(small(p), 0, 0, cv.width, cv.height);
      th.type = 'button'; th.appendChild(cv); th.onclick = function () { openEditor(i); };
      var mid = el('div', 'st-row-main');
      mid.appendChild(el('b', '', S.name));
      mid.appendChild(el('small', '', S.w + ' × ' + S.h + ' mm' + (p.fit ? ' · ' + T.st_fit : '')));
      var ctl = el('div', 'st-row-ctl'), step = el('span', 'stepper sm'), minus = el('button', '', '−'), plus = el('button', '', '+'), num = el('input');
      minus.type = plus.type = 'button'; num.type = 'number'; num.min = 1; num.max = 500; num.value = p.copies; num.inputMode = 'numeric';
      minus.onclick = function () { setCopies(p, p.copies - 1); };
      plus.onclick = function () { setCopies(p, p.copies + 1); };
      num.onchange = function () { setCopies(p, parseInt(num.value, 10)); };
      step.appendChild(minus); step.appendChild(num); step.appendChild(plus);
      var ed = el('button', 'btn small', '✏️ ' + T.st_edit);
      ed.type = 'button'; ed.onclick = function () { openEditor(i); };
      ctl.appendChild(step); ctl.appendChild(ed); mid.appendChild(ctl);
      var x = el('button', 'x', '✕');
      x.type = 'button'; x.setAttribute('aria-label', T.st_remove);
      x.onclick = function () { state.photos.splice(i, 1); renderMain(); };
      row.appendChild(th); row.appendChild(mid); row.appendChild(x);
      list.appendChild(row);
    });
    $('stAddWrap').classList.toggle('hidden', state.photos.length >= MAX_PHOTOS);

    var pay = $('stPay');
    pay.innerHTML = '';
    pay.appendChild(el('small', '', T.estimate));
    pay.appendChild(el('b', '', O.money(O.photoPrice({ photo: t }))));
  }
  function setCopies(p, n) { p.copies = Math.max(1, Math.min(500, n || 1)); renderMain(); if (edit === p) syncControls(); }

  // ---------- big preview: only the sheets, with the photos at their size ----------
  function openPreview() {
    var box = $('ptBig'), plan = state.plan, w = Math.min(window.innerWidth - 32, 620), dpr = window.devicePixelRatio || 1, t = totals();
    box.innerHTML = '';
    box.appendChild(el('p', 'pt-cap', fmt(T.st_summary, t.pieces, t.sheets, PHOTO.paper)));
    plan.sheets.forEach(function (_, i) {
      var cv = el('canvas');
      drawSheet(cv, plan, i, w * Math.min(2, dpr));
      cv.style.width = w + 'px';
      box.appendChild(cv);
      box.appendChild(el('p', 'pt-cap', fmt(T.photo_sheet_of, i + 1, plan.sheets.length)));
    });
    DaybillSheet.open(bigSheet);
  }
  $('stPreviewBtn').addEventListener('click', openPreview);

  // ---------- editor ----------
  var sizeBox = $('stSizes');
  SIZES.forEach(function (S) {
    var b = el('button', 'st-size'), k = 26 / Math.max(S.w, S.h), i = el('i');
    b.type = 'button'; b.dataset.id = S.id;
    i.style.width = Math.round(S.w * k) + 'px'; i.style.height = Math.round(S.h * k) + 'px';
    b.appendChild(i); b.appendChild(el('span', '', S.name));
    b.onclick = function () {
      if (edit.size === S.id) return;
      edit.size = lastSize = S.id; edit.zoom = 1; edit.ox = edit.oy = 0; edit.guide = isId(S);
      var max = orient(S).max;
      if (edit.copies > max * 4) edit.copies = max;
      autoPlace(edit); changed(); syncControls();
    };
    sizeBox.appendChild(b);
  });

  function openEditor(i) {
    edit = state.photos[i];
    syncControls();
    DaybillSheet.open(editor);
    requestAnimationFrame(drawStage);
  }
  function syncControls() {
    if (!edit) return;
    var S = def(edit.size), max = orient(S).max;
    sizeBox.querySelectorAll('.st-size').forEach(function (b) {
      b.classList.toggle('on', b.dataset.id === edit.size);
      if (b.dataset.id === edit.size && b.scrollIntoView && editor.hasAttribute('open')) b.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    });
    $('stZoom').value = edit.zoom; $('stBright').value = edit.bright; $('stContrast').value = edit.contrast; $('stSat').value = edit.sat;
    editor.querySelector('[data-t=fit]').classList.toggle('on', edit.fit);
    editor.querySelector('[data-t=flip]').classList.toggle('on', edit.flip);
    editor.querySelector('[data-t=bw]').classList.toggle('on', edit.sat === 0);
    var g = editor.querySelector('[data-t=guide]');
    g.classList.toggle('hidden', !isId(S)); g.classList.toggle('on', edit.guide);
    var num = $('stCount');
    if (document.activeElement !== num) num.value = edit.copies;
    var quick = $('stQuick');
    quick.innerHTML = '';
    [1, 2, 4, 6, 8].filter(function (n) { return n < max; }).map(function (n) { return [n, String(n)]; })
      .concat([[max, T.full_sheet + ' (' + max + ')']]).forEach(function (q) {
        var c = el('button', 'chip' + (q[0] === edit.copies ? ' on' : ''), q[1]);
        c.type = 'button'; c.onclick = function () { setCopies(edit, q[0]); };
        quick.appendChild(c);
      });
    $('stFitInfo').textContent = fmt(T.st_fit_n, max, PHOTO.paper);
  }

  var queued = false, dragging = false;
  function changed() { if (edit) { clamp(edit); edit.prev = null; } schedule(); }
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(function () { queued = false; drawStage(); });
  }
  function drawStage() {
    if (!edit || !editor.hasAttribute('open')) return;
    var wrap = stage.parentNode, cssW = wrap.clientWidth || 320;
    var cssH = Math.round(Math.max(220, Math.min(window.innerHeight * 0.46, cssW * 1.1)));
    var dpr = window.devicePixelRatio || 1, S = def(edit.size), pad = 30, aspect = S.w / S.h;
    if (stage.width !== Math.round(cssW * dpr) || stage.height !== Math.round(cssH * dpr)) {
      stage.width = Math.round(cssW * dpr); stage.height = Math.round(cssH * dpr);
      stage.style.width = cssW + 'px'; stage.style.height = cssH + 'px';
    }
    var fw = cssW - 2 * pad, fh = fw / aspect;
    if (fh > cssH - 2 * pad - 12) { fh = cssH - 2 * pad - 12; fw = fh * aspect; }
    frame = { x: (cssW - fw) / 2, y: (cssH - fh) / 2 - 6, w: fw, h: fh };
    var x = sctx, f = frame;
    x.setTransform(dpr, 0, 0, dpr, 0, 0);
    x.fillStyle = '#171a21'; x.fillRect(0, 0, cssW, cssH);
    // The photo also shows dimmed outside the frame, so it is easy to see what is cut off
    x.save(); x.globalAlpha = 0.35;
    if (canFilter) x.filter = filterOf(edit);
    paintFree(x, f, edit);
    x.restore();
    x.fillStyle = '#fff'; x.fillRect(f.x, f.y, f.w, f.h);
    if (canFilter) x.filter = filterOf(edit);
    paint(x, f.x, f.y, f.w, f.h, edit);
    x.filter = 'none';
    stage.style.filter = canFilter || !adjusted(edit) ? '' : filterOf(edit);
    x.strokeStyle = '#fff'; x.lineWidth = 2; x.strokeRect(f.x - 1, f.y - 1, f.w + 2, f.h + 2);
    if (dragging) { // thirds while moving
      x.strokeStyle = 'rgba(255,255,255,.45)'; x.lineWidth = 1; x.beginPath();
      for (var k = 1; k < 3; k++) { x.moveTo(f.x + f.w * k / 3, f.y); x.lineTo(f.x + f.w * k / 3, f.y + f.h); x.moveTo(f.x, f.y + f.h * k / 3); x.lineTo(f.x + f.w, f.y + f.h * k / 3); }
      x.stroke();
    }
    if (edit.guide && isId(S)) { // face guide: head inside the oval, top of head and chin near the lines
      x.save(); x.setLineDash([6, 4]); x.strokeStyle = 'rgba(255,255,255,.9)'; x.lineWidth = 1.5;
      x.beginPath(); x.ellipse(f.x + f.w / 2, f.y + f.h * 0.46, f.w * 0.3, f.h * 0.35, 0, 0, Math.PI * 2); x.stroke();
      x.beginPath(); x.moveTo(f.x, f.y + f.h * 0.1); x.lineTo(f.x + f.w, f.y + f.h * 0.1);
      x.moveTo(f.x, f.y + f.h * 0.82); x.lineTo(f.x + f.w, f.y + f.h * 0.82); x.stroke();
      x.restore();
    }
    x.fillStyle = '#c9cfdb'; x.font = '600 12px system-ui, sans-serif'; x.textAlign = 'center';
    x.fillText(S.w + ' × ' + S.h + ' mm', cssW / 2, f.y + f.h + 18);
    $('stZoom').value = edit.zoom;
  }
  // Same as paint() but without cutting at the frame (for the dimmed surroundings).
  function paintFree(x, f, p) {
    var src = p.src, k = scaleOf(p, f.w, f.h).s;
    x.translate(f.x + f.w / 2 + p.ox * f.w, f.y + f.h / 2 + p.oy * f.h);
    x.rotate(p.rot * Math.PI / 2);
    if (p.flip) x.scale(p.rot % 2 ? 1 : -1, p.rot % 2 ? -1 : 1);
    x.drawImage(src, -src.width * k / 2, -src.height * k / 2, src.width * k, src.height * k);
  }

  // Drag to move, two fingers to zoom, mouse wheel to zoom, double tap to centre again
  var pointers = new Map(), pinch = null, lastTap = 0;
  stage.addEventListener('pointerdown', function (e) {
    if (!edit) return;
    stage.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    pinch = null; dragging = true;
    if (pointers.size === 1 && e.timeStamp - lastTap < 300) { edit.zoom = 1; edit.ox = edit.oy = 0; autoPlace(edit); changed(); }
    lastTap = e.timeStamp;
  });
  stage.addEventListener('pointermove', function (e) {
    if (!pointers.has(e.pointerId) || !frame) return;
    var prev = pointers.get(e.pointerId);
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    if (pointers.size === 1) {
      edit.ox += (e.clientX - prev[0]) / frame.w; edit.oy += (e.clientY - prev[1]) / frame.h;
    } else if (pointers.size === 2) {
      var pts = Array.from(pointers.values()), d = Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]);
      if (pinch) edit.zoom = Math.max(1, Math.min(6, edit.zoom * d / pinch));
      pinch = d;
      edit.ox += (e.clientX - prev[0]) / frame.w / 2; edit.oy += (e.clientY - prev[1]) / frame.h / 2;
    }
    changed();
  });
  ['pointerup', 'pointercancel'].forEach(function (t) {
    stage.addEventListener(t, function (e) { pointers.delete(e.pointerId); pinch = null; if (!pointers.size) { dragging = false; schedule(); } });
  });
  stage.addEventListener('wheel', function (e) {
    e.preventDefault();
    edit.zoom = Math.max(1, Math.min(6, edit.zoom * (e.deltaY < 0 ? 1.08 : 0.93)));
    changed();
  }, { passive: false });

  function slider(id, key) { $(id).addEventListener('input', function () { edit[key] = +this.value; changed(); syncButtons(); }); }
  function syncButtons() { editor.querySelector('[data-t=bw]').classList.toggle('on', edit.sat === 0); }
  slider('stZoom', 'zoom'); slider('stBright', 'bright'); slider('stContrast', 'contrast'); slider('stSat', 'sat');
  editor.querySelectorAll('[data-t]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = b.dataset.t;
      if (t === 'rotate') { edit.rot = (edit.rot + 1) % 4; edit.ox = edit.oy = 0; edit.zoom = 1; }
      else if (t === 'flip') edit.flip = !edit.flip;
      else if (t === 'fit') { edit.fit = !edit.fit; edit.zoom = 1; edit.ox = edit.oy = 0; }
      else if (t === 'guide') edit.guide = !edit.guide;
      else if (t === 'bw') edit.sat = edit.sat === 0 ? 100 : 0;
      else if (t === 'reset') { edit.rot = 0; edit.flip = edit.fit = false; edit.zoom = 1; edit.ox = edit.oy = 0; edit.bright = edit.contrast = edit.sat = 100; autoPlace(edit); }
      changed(); syncControls();
    });
  });
  $('stCount').addEventListener('input', function () { var n = parseInt(this.value, 10); if (n > 0) setCopies(edit, n); });
  editor.querySelectorAll('[data-st-step]').forEach(function (b) { b.onclick = function () { setCopies(edit, edit.copies + +b.dataset.stStep); }; });
  $('stDel').addEventListener('click', function () {
    var i = state.photos.indexOf(edit);
    if (i >= 0) state.photos.splice(i, 1);
    edit = null;
    DaybillSheet.close(editor);
  });
  editor.addEventListener('sheetclosed', function () { edit = null; renderMain(); });
  editor.addEventListener('transitionend', function () { if (edit) drawStage(); });
  window.addEventListener('resize', function () { if (edit) schedule(); });

  // ---------- photos in ----------
  // Any photo the phone can show (JPEG, PNG, WebP, iPhone HEIC in Safari …); kept at up to 2000 px.
  function loadImage(file) {
    return new Promise(function (resolve) {
      if (file.size > O.maxMb * 1048576 * 3) { alert(T.err_big.replace('%s', file.name)); return resolve(null); }
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        var k = Math.min(1, 2000 / Math.max(img.naturalWidth, img.naturalHeight)), c = el('canvas');
        c.width = Math.max(1, Math.round(img.naturalWidth * k)); c.height = Math.max(1, Math.round(img.naturalHeight * k));
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        resolve(c);
      };
      img.onerror = function () { URL.revokeObjectURL(url); alert(T.photo_bad + ' (' + file.name + ')'); resolve(null); };
      img.src = url;
    });
  }
  function newPhoto(src, name) {
    var id = lastSize && SIZES.some(function (S) { return S.id === lastSize; }) ? lastSize : SIZES[0].id, S = def(id);
    return { src: src, name: name, size: id, copies: S.w * S.h <= 3600 ? Math.min(orient(S).max, 4) : 1,
      rot: 0, flip: false, fit: false, zoom: 1, ox: 0, oy: 0, bright: 100, contrast: 100, sat: 100, guide: isId(S), face: null, prev: null };
  }
  // Chrome on some phones can find the face: then passport photos are placed for you.
  function findFace(p) {
    if (!('FaceDetector' in window)) return;
    try {
      new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 }).detect(p.src).then(function (faces) {
        if (!faces || !faces[0]) return;
        p.face = faces[0].boundingBox;
        if (autoPlace(p)) { p.prev = null; if (edit === p) schedule(); else if (state) renderMain(); }
      }).catch(function () {});
    } catch (e) {}
  }
  function autoPlace(p) {
    var S = def(p.size);
    if (!p.face || p.rot || p.flip || p.fit || !isId(S)) return false;
    var fw = 1000, fh = 1000 * S.h / S.w, f = p.face, base = Math.max(fw / p.src.width, fh / p.src.height);
    p.zoom = Math.max(1, Math.min(6, 0.5 * fh / (f.height * base)));
    var s = base * p.zoom;
    p.ox = -((f.x + f.width / 2) - p.src.width / 2) * s / fw;
    p.oy = (0.47 * fh - fh / 2 - ((f.y + f.height / 2) - p.src.height / 2) * s) / fh;
    clamp(p);
    return true;
  }
  async function addFiles(files, replace) {
    files = Array.prototype.slice.call(files || []);
    if (!files.length) return;
    if (replace) {
      var src = await loadImage(files[0]);
      if (src && edit) { edit.src = src; edit.face = null; edit.zoom = 1; edit.ox = edit.oy = 0; edit.rot = 0; changed(); findFace(edit); }
      return;
    }
    var added = [];
    for (var i = 0; i < files.length && state.photos.length < MAX_PHOTOS; i++) {
      var c = await loadImage(files[i]);
      if (c) { var p = newPhoto(c, files[i].name.replace(/\.[^.]+$/, '') || 'photo'); state.photos.push(p); added.push(p); findFace(p); }
    }
    if (files.length > added.length && state.photos.length >= MAX_PHOTOS) alert(fmt(T.st_max, MAX_PHOTOS));
    renderMain();
    if (added.length === 1) openEditor(state.photos.indexOf(added[0])); // one photo: straight to size & position
  }
  ['stFile', 'stFile2'].forEach(function (id) { $(id).addEventListener('change', function () { var f = this.files; addFiles(f).then(function () {}); this.value = ''; }); });
  $('stFile3').addEventListener('change', function () { addFiles(this.files, true); this.value = ''; });

  // Sizes on the start screen
  SIZES.forEach(function (S) { $('stSizeInfo').appendChild(el('span', 'chip', S.name)); });

  function openTool(item) {
    state = { item: item || null, photos: item ? item.studio.map(function (p) { return Object.assign({}, p); }) : [] };
    edit = null;
    DaybillSheet.open(tool);
    renderMain();
  }
  $('photoBtn').addEventListener('click', function () {
    if (O.items.length >= O.maxFiles) return O.showErr(T.err_max);
    openTool(null);
  });
  tool.addEventListener('transitionend', function () { if (state && state.photos.length) renderMain(); });

  // ---------- add to the order ----------
  async function buildPdf(plan) {
    var lib = window.PDFLib, doc = await lib.PDFDocument.create(), grey = lib.rgb(0.78, 0.78, 0.78), emb = {};
    for (var i = 0; i < plan.sheets.length; i++) {
      var page = doc.addPage([plan.pw * MM, plan.ph * MM]);
      for (var j = 0; j < plan.sheets[i].length; j++) {
        var c = plan.sheets[i][j], key = c.p + (c.rot ? 'r' : '');
        if (!emb[key]) {
          var p = state.photos[c.p], blob = await toBlob(render(p, printPx(p), c.rot));
          emb[key] = await doc.embedJpg(await blob.arrayBuffer());
        }
        var y = plan.ph - c.y - c.h; // PDF measures from the bottom
        page.drawImage(emb[key], { x: c.x * MM, y: y * MM, width: c.w * MM, height: c.h * MM });
        page.drawRectangle({ x: c.x * MM, y: y * MM, width: c.w * MM, height: c.h * MM, borderColor: grey, borderWidth: 0.3 });
      }
    }
    return new Blob([await doc.save()], { type: 'application/pdf' });
  }

  $('stAdd').addEventListener('click', async function () {
    if (!state || !state.photos.length) return;
    var btn = this, label = btn.innerHTML;
    btn.disabled = true; btn.textContent = T.preparing;
    try {
      var plan = state.plan = pack(), t = totals(), pdf = await buildPdf(plan), previews = [];
      for (var i = 0; i < Math.min(plan.sheets.length, 6); i++) { // pictures of the sheets for the shop staff
        var cv = el('canvas');
        drawSheet(cv, plan, i, 900);
        previews.push(await toBlob(cv, 0.85));
      }
      var first = await toBlob(render(state.photos[0], printPx(state.photos[0]), false));
      var it = state.item;
      if (!it) {
        var node = el('div', 'file photo-item');
        node.innerHTML = '<div class="file-head"><span class="fname"></span><button type="button" class="x" aria-label="✕">✕</button></div>' +
          '<div class="pi-row"><div class="pi-thumbs"></div><div class="pi-txt"><div class="chips"></div><div class="price muted"></div></div></div>' +
          '<button type="button" class="btn block pi-edit"></button>';
        node.querySelector('.fname').textContent = '📷 ' + T.photo_print;
        node.querySelector('.pi-edit').textContent = '✏️ ' + T.photo_edit;
        it = { node: node, pages: 1 };
        node.querySelector('.x').onclick = function () { O.items.splice(O.items.indexOf(it), 1); node.remove(); O.refresh(); };
        node.querySelector('.pi-edit').onclick = function () { openTool(it); };
        node.querySelector('.pi-thumbs').onclick = function () { openTool(it); };
        O.items.push(it); O.list.appendChild(node);
      }
      it.file = new File([first], 'photos.jpg', { type: 'image/jpeg' });
      it.printBlob = pdf;
      it.previews = previews;
      it.studio = state.photos.map(function (p) { return Object.assign({}, p); });
      it.photo = { code: state.photos.map(function (p) { return p.size + ':' + p.copies; }).join(','), pieces: t.pieces, sheets: t.sheets,
        labels: state.photos.map(function (p) { return def(p.size).name + ' × ' + p.copies; }) };
      var thumbs = it.node.querySelector('.pi-thumbs');
      thumbs.innerHTML = '';
      state.photos.slice(0, 4).forEach(function (p) {
        var S = def(p.size), c = el('canvas'), h = 56, w = Math.round(h * S.w / S.h);
        c.width = w * 2; c.height = h * 2; c.style.width = w + 'px'; c.style.height = h + 'px';
        c.getContext('2d').drawImage(small(p), 0, 0, c.width, c.height);
        thumbs.appendChild(c);
      });
      if (state.photos.length > 4) thumbs.appendChild(el('span', 'st-more', '+' + (state.photos.length - 4)));
      DaybillSheet.close(tool);
      O.showErr('');
      O.refresh();
    } catch (e) {
      alert(T.layout_fail.replace('%s', T.photo_print) + ' (' + e.message + ')');
    } finally {
      btn.disabled = false; btn.innerHTML = label;
    }
  });
})();
