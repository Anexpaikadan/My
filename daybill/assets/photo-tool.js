// Photo print tool (customer page): choose a photo → size → place it in the frame (move / zoom / rotate /
// brightness / contrast) → how many → the photos are arranged on the paper automatically → preview → add to order.
// Needs assets/layout.js (geometry + PDF) and window.DaybillOrder (set by index.php).
(function () {
  var O = window.DaybillOrder;
  if (!O || !O.PHOTO) return;
  var PHOTO = O.PHOTO, PDEFS = O.PDEFS, T = O.T, $ = function (id) { return document.getElementById(id); };
  var tool = $('photoTool'), prevSheet = $('ptPreview'), stage = $('ptStage'), guide = $('ptGuide');
  var ctx = stage.getContext('2d'), canFilter = 'filter' in ctx;
  var cur = null, pointers = new Map(), pinch = null;

  // ---------- editor state ----------
  function fresh(img, name) {
    return { img: img, name: name, id: cur && cur.id || PHOTO.sizes[0].id, pieces: cur && cur.pieces || 0,
      rot: 0, zoom: 1, ox: 0, oy: 0, bright: 100, contrast: 100, item: null };
  }
  function L() { return PDEFS[cur.id]; }
  function fitMax() { return window.DaybillLayout.sizeFit(L().w, L().h, PHOTO.paper).max; }

  // Draws the photo into a w×h box the way the editor shows it (cover, then zoom / move / rotate).
  function paint(c, x, w, h, withFilter) {
    var im = cur.img, odd = cur.rot % 2 === 1;
    var iw = im.naturalWidth || im.width, ih = im.naturalHeight || im.height;
    var s = Math.max(w / (odd ? ih : iw), h / (odd ? iw : ih)) * cur.zoom;
    x.save();
    x.fillStyle = '#fff'; x.fillRect(0, 0, w, h);
    if (withFilter && canFilter) x.filter = 'brightness(' + cur.bright + '%) contrast(' + cur.contrast + '%)';
    x.translate(w / 2 + cur.ox * w, h / 2 + cur.oy * h);
    x.rotate(cur.rot * Math.PI / 2);
    x.drawImage(im, -iw * s / 2, -ih * s / 2, iw * s, ih * s);
    x.restore();
    if (withFilter && !canFilter && (cur.bright !== 100 || cur.contrast !== 100)) { // older Safari: adjust pixels by hand
      var d = x.getImageData(0, 0, w, h), p = d.data, b = cur.bright / 100, k = cur.contrast / 100;
      for (var i = 0; i < p.length; i += 4) for (var j = 0; j < 3; j++) p[i + j] = Math.max(0, Math.min(255, ((p[i + j] * b) - 128) * k + 128));
      x.putImageData(d, 0, 0);
    }
  }

  // Keeps the photo covering the whole frame (no white edges).
  function clamp() {
    var im = cur.img, odd = cur.rot % 2 === 1, W = 1000, H = 1000 * L().h / L().w;
    var iw = im.naturalWidth || im.width, ih = im.naturalHeight || im.height;
    var s = Math.max(W / (odd ? ih : iw), H / (odd ? iw : ih)) * cur.zoom;
    var mx = Math.max(0, ((odd ? ih : iw) * s - W) / 2 / W), my = Math.max(0, ((odd ? iw : ih) * s - H) / 2 / H);
    cur.ox = Math.max(-mx, Math.min(mx, cur.ox)); cur.oy = Math.max(-my, Math.min(my, cur.oy));
  }

  function drawStage() {
    var box = stage.parentNode.clientWidth || 300, aspect = L().w / L().h;
    var cssW = Math.min(box, aspect >= 1 ? 320 : 260), cssH = cssW / aspect, dpr = window.devicePixelRatio || 1;
    stage.style.width = cssW + 'px'; stage.style.height = cssH + 'px';
    stage.width = Math.round(cssW * dpr); stage.height = Math.round(cssH * dpr);
    stage.style.filter = canFilter ? '' : 'brightness(' + cur.bright + '%) contrast(' + cur.contrast + '%)';
    paint(stage, ctx, stage.width, stage.height, canFilter);
    // Face guide for ID / passport photos (small portrait sizes)
    guide.style.width = cssW + 'px'; guide.style.height = cssH + 'px';
    guide.classList.toggle('hidden', !(L().h > L().w && L().w <= 60));
  }

  // The finished photo at print quality (300 dpi) as a canvas.
  function finalCanvas(maxSide) {
    var w = L().w / 25.4 * 300, h = L().h / 25.4 * 300, k = Math.min(1, (maxSide || 2400) / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.round(w * k); c.height = Math.round(h * k);
    paint(c, c.getContext('2d'), c.width, c.height, true);
    return c;
  }
  function toBlob(c, q) { return new Promise(function (r) { c.toBlob(r, 'image/jpeg', q || 0.92); }); }
  function plan() { return window.DaybillLayout.sizePlan(L().w, L().h, PHOTO.paper, cur.pieces); }

  // ---------- render the whole tool ----------
  function render() {
    if (!cur) return;
    clamp();
    drawStage();
    document.querySelectorAll('#ptSizes .pt-size').forEach(function (b) { b.classList.toggle('on', b.dataset.id === cur.id); });
    $('ptZoom').value = cur.zoom; $('ptBright').value = cur.bright; $('ptContrast').value = cur.contrast;
    var max = fitMax(), p = plan(), count = $('ptCount');
    if (document.activeElement !== count) count.value = cur.pieces;
    var quick = $('ptQuick'); quick.innerHTML = '';
    [1, 2, 4, 6, 8].filter(function (n) { return n < max; }).map(function (n) { return [n, String(n)]; })
      .concat([[max, T.full_sheet + ' (' + max + ')']]).forEach(function (q) {
        var c = document.createElement('button'); c.type = 'button'; c.className = 'chip' + (q[0] === cur.pieces ? ' on' : '');
        c.textContent = q[1]; c.onclick = function () { setPieces(q[0]); }; quick.appendChild(c);
      });
    $('ptInfo').textContent = T.photo_info.replace('%1$d', max).replace('%2$s', PHOTO.paper).replace('%3$d', p.sheets.length);
    var pr = O.photoPrice({ photo: { id: cur.id, pieces: cur.pieces } }), pay = $('ptPay');
    pay.innerHTML = ''; pay.appendChild(document.createTextNode(T.estimate));
    var b = document.createElement('b'); b.textContent = O.money(pr); pay.appendChild(b);
    clearTimeout(render.t); render.t = setTimeout(thumbs, 120); // small sheet pictures (a little later while dragging)
  }
  function thumbs() {
    var box = $('ptSheets'), src = finalCanvas(600), p = plan();
    box.innerHTML = '';
    p.sheets.slice(0, 4).forEach(function (_, i) {
      var cv = document.createElement('canvas'); window.DaybillLayout.drawPreview(cv, src, p, i, 200); box.appendChild(cv);
    });
    if (p.sheets.length > 4) { var m = document.createElement('span'); m.className = 'pt-more'; m.textContent = '+' + (p.sheets.length - 4); box.appendChild(m); }
  }
  function setPieces(n) { cur.pieces = Math.max(1, Math.min(500, n || 1)); render(); }

  // ---------- preview: only the sheet(s) with the photos, size and number ----------
  function openPreview() {
    var big = $('ptBig'), src = finalCanvas(1200), p = plan(), w = Math.min(window.innerWidth - 32, 620);
    big.innerHTML = '';
    var head = document.createElement('p'); head.className = 'pt-cap';
    head.textContent = L().name + ' × ' + cur.pieces + ' · ' + PHOTO.paper;
    big.appendChild(head);
    p.sheets.forEach(function (_, i) {
      var cv = document.createElement('canvas'), cap = document.createElement('p');
      window.DaybillLayout.drawPreview(cv, src, p, i, w * 2); cv.style.width = w + 'px';
      cap.className = 'pt-cap'; cap.textContent = T.photo_sheet_of.replace('%1$d', i + 1).replace('%2$d', p.sheets.length);
      big.appendChild(cv); big.appendChild(cap);
    });
    DaybillSheet.open(prevSheet);
  }
  $('ptPreviewBtn').addEventListener('click', openPreview);
  $('ptSheets').addEventListener('click', openPreview);

  // ---------- inputs ----------
  PHOTO.sizes.forEach(function (S) {
    var b = document.createElement('button'), k = 30 / Math.max(S.w, S.h);
    b.type = 'button'; b.className = 'pt-size'; b.dataset.id = S.id;
    b.innerHTML = '<i style="width:' + Math.round(S.w * k) + 'px;height:' + Math.round(S.h * k) + 'px"></i><span></span>';
    b.querySelector('span').textContent = S.name;
    b.onclick = function () {
      if (cur.id === S.id) return;
      cur.id = S.id; cur.zoom = 1; cur.ox = cur.oy = 0;                 // new frame: start centred again
      if (cur.pieces > fitMax() * 4) cur.pieces = fitMax();
      render();
    };
    $('ptSizes').appendChild(b);
  });
  $('ptCount').addEventListener('input', function () { setPieces(parseInt(this.value, 10)); });
  tool.querySelectorAll('[data-pt-step]').forEach(function (b) { b.onclick = function () { setPieces(cur.pieces + +b.dataset.ptStep); }; });
  $('ptZoom').addEventListener('input', function () { cur.zoom = +this.value; render(); });
  $('ptBright').addEventListener('input', function () { cur.bright = +this.value; render(); });
  $('ptContrast').addEventListener('input', function () { cur.contrast = +this.value; render(); });
  $('ptRotate').onclick = function () { cur.rot = (cur.rot + 1) % 4; cur.ox = cur.oy = 0; render(); };
  $('ptReset').onclick = function () { cur.rot = 0; cur.zoom = 1; cur.ox = cur.oy = 0; cur.bright = cur.contrast = 100; render(); };

  // Drag to move, pinch / mouse wheel to zoom
  stage.addEventListener('pointerdown', function (e) { stage.setPointerCapture(e.pointerId); pointers.set(e.pointerId, [e.clientX, e.clientY]); pinch = null; });
  stage.addEventListener('pointermove', function (e) {
    if (!pointers.has(e.pointerId)) return;
    var prev = pointers.get(e.pointerId), r = stage.getBoundingClientRect();
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    if (pointers.size === 1) {
      cur.ox += (e.clientX - prev[0]) / r.width; cur.oy += (e.clientY - prev[1]) / r.height;
    } else if (pointers.size === 2) {
      var pts = Array.from(pointers.values()), d = Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]);
      if (pinch) cur.zoom = Math.max(1, Math.min(5, cur.zoom * d / pinch));
      pinch = d;
    }
    render();
  });
  ['pointerup', 'pointercancel'].forEach(function (t) { stage.addEventListener(t, function (e) { pointers.delete(e.pointerId); pinch = null; }); });
  stage.addEventListener('wheel', function (e) { e.preventDefault(); cur.zoom = Math.max(1, Math.min(5, cur.zoom * (e.deltaY < 0 ? 1.08 : 0.93))); render(); }, { passive: false });

  // Any photo the phone can show (JPEG, PNG, iPhone HEIC in Safari …) – it is re-saved as JPEG.
  function load(file) {
    if (!file) return;
    if (file.size > O.maxMb * 1048576 * 2) return alert(T.err_big.replace('%s', file.name));
    var url = URL.createObjectURL(file), img = new Image();
    img.onload = function () {
      var keep = cur;
      cur = fresh(img, file.name.replace(/\.[^.]+$/, '') || 'photo');
      if (keep && keep.item) cur.item = keep.item;
      if (keep && keep.id) cur.id = keep.id;
      if (!cur.pieces) cur.pieces = Math.min(fitMax(), 4);
      if (keep && keep.pieces) cur.pieces = keep.pieces;
      $('ptPick').classList.add('hidden'); $('ptMain').classList.remove('hidden');
      render();
    };
    img.onerror = function () { URL.revokeObjectURL(url); alert(T.photo_bad); };
    img.src = url;
  }
  $('ptFile').addEventListener('change', function () { load(this.files[0]); this.value = ''; });
  $('ptFile2').addEventListener('change', function () { load(this.files[0]); this.value = ''; });

  function openTool(item) {
    if (item) { cur = Object.assign({}, item.edit, { item: item }); }
    else cur = null;
    $('ptPick').classList.toggle('hidden', !!item); $('ptMain').classList.toggle('hidden', !item);
    DaybillSheet.open(tool);
    if (item) requestAnimationFrame(render);
  }
  $('photoBtn').addEventListener('click', function () {
    if (O.items.length >= O.maxFiles) return O.showErr(T.err_max);
    openTool(null);
  });
  // Re-draw when the sheet has its final width
  tool.addEventListener('transitionend', function () { if (cur) drawStage(); });

  // ---------- add to the order ----------
  $('ptAdd').addEventListener('click', async function () {
    if (!cur) return;
    var btn = this; btn.disabled = true;
    try {
      var photo = finalCanvas(2400), blob = await toBlob(photo), p = plan(), previews = [];
      var small = finalCanvas(900);
      for (var i = 0; i < Math.min(p.sheets.length, 6); i++) { // pictures of the sheets for the shop staff
        var cv = document.createElement('canvas'); window.DaybillLayout.drawPreview(cv, small, p, i, 900);
        previews.push(await toBlob(cv, 0.85));
      }
      var it = cur.item;
      if (!it) {
        var node = document.createElement('div');
        node.className = 'file photo-item';
        node.innerHTML = '<div class="file-head"><span class="fname"></span><button type="button" class="x" aria-label="✕">✕</button></div>' +
          '<div class="pi-row"><img class="pi-thumb" alt=""><div class="pi-txt"><div class="chips"></div><div class="price muted"></div></div></div>' +
          '<button type="button" class="btn block pi-edit"></button>';
        node.querySelector('.pi-edit').textContent = '✏️ ' + T.photo_edit;
        it = { node: node, pages: 1 };
        node.querySelector('.x').onclick = function () { O.items.splice(O.items.indexOf(it), 1); node.remove(); O.refresh(); };
        node.querySelector('.pi-edit').onclick = function () { openTool(it); };
        node.querySelector('.pi-thumb').onclick = function () { openTool(it); };
        O.items.push(it); O.list.appendChild(node);
      }
      if (it.url) URL.revokeObjectURL(it.url);
      it.file = new File([blob], cur.name + '.jpg', { type: 'image/jpeg' });
      it.url = URL.createObjectURL(blob);
      it.previews = previews;
      it.photo = { id: cur.id, pieces: cur.pieces };
      it.edit = Object.assign({}, cur, { item: null });
      it.node.querySelector('.fname').textContent = '📷 ' + cur.name;
      it.node.querySelector('.pi-thumb').src = it.url;
      DaybillSheet.close(tool);
      O.showErr('');
      O.refresh();
    } finally { btn.disabled = false; }
  });
})();
