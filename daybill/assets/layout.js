// Print layouts, built in the browser with pdf-lib (assets/pdf-lib.min.js):
//   nup  – 2 / 4 / 8 document pages on one sheet
//   grid – the same photo 2 / 4 / 6 / 8 times on one sheet
//   size – photos of an exact size (e.g. passport 35×45 mm), a chosen number of pieces
// A layout code is "id" or "id:pieces" (size layouts), e.g. "nup4", "passport:8".
(function () {
  var MM = 72 / 25.4; // PDF points per millimetre
  var PAPER = { A2: [420, 594], A3: [297, 420], A4: [210, 297], A5: [148, 210], A6: [105, 148],
    Letter: [216, 279], Legal: [216, 356], Tabloid: [279, 432], Statement: [140, 216],
    '10x15 cm': [102, 152], '13x18 cm': [127, 178] };
  var MARGIN = 6, GAP = 3; // mm; most printers cannot print the outer ~4 mm
  function margin(paper) { return /cm$/.test(paper) ? 3 : MARGIN; } // photo paper: photo printers print closer to the edge

  function parse(code, defs) {
    var parts = String(code || '').split(':'), d = defs[parts[0]];
    return d ? { id: parts[0], type: d.type, n: d.n || 0, w: d.w || 0, h: d.h || 0, pieces: +parts[1] || 0 } : null;
  }

  function paperMm(paper, landscape) {
    var p = PAPER[paper] || PAPER.A4;
    return landscape ? [p[1], p[0]] : [p[0], p[1]];
  }

  // Columns/rows for N pages or photos on a sheet.
  function grid(n, landscape) {
    var g = { 2: [1, 2], 4: [2, 2], 6: [2, 3], 8: [2, 4], 9: [3, 3], 12: [3, 4], 16: [4, 4] }[n] || [1, n];
    return landscape ? [g[1], g[0]] : g; // [cols, rows]
  }

  // How many photos of w×h mm fit on the sheet – upright or turned 90° (whichever fits more).
  function sizeFit(w, h, paper) {
    var p = paperMm(paper, false), m = margin(paper);
    function fit(cw, ch) {
      var cols = Math.max(1, Math.floor((p[0] - 2 * m + GAP) / (cw + GAP)));
      var rows = Math.max(1, Math.floor((p[1] - 2 * m + GAP) / (ch + GAP)));
      return { cols: cols, rows: rows, max: cols * rows, cw: cw, ch: ch, rot: false };
    }
    var a = fit(w, h), b = fit(h, w);
    if (w !== h && b.max > a.max) { b.rot = true; return b; }
    return a;
  }

  // Where every photo goes: {pw, ph, cw, ch, rot, perSheet, sheets: [[[x, y], …], …]} in mm, y from the bottom.
  function sizePlan(w, h, paper, pieces) {
    var p = paperMm(paper, false), f = sizeFit(w, h, paper), m = margin(paper);
    var total = pieces > 0 ? pieces : f.max, sheets = [];
    var blockW = f.cols * f.cw + (f.cols - 1) * GAP, left = (p[0] - blockW) / 2;
    for (var j = 0; j < total; j++) {
      var k = j % f.max, c = k % f.cols, r = Math.floor(k / f.cols);
      if (k === 0) sheets.push([]);
      sheets[sheets.length - 1].push([left + c * (f.cw + GAP), p[1] - m - (r + 1) * f.ch - r * GAP]);
    }
    return { pw: p[0], ph: p[1], cw: f.cw, ch: f.ch, rot: f.rot, perSheet: f.max, sheets: sheets };
  }

  // Draws a sheet preview on a canvas from a loaded <img> (same geometry as the PDF).
  function drawPreview(canvas, img, plan, index, widthPx) {
    var s = widthPx / plan.pw, cv = canvas, x = cv.getContext('2d');
    cv.width = Math.round(plan.pw * s); cv.height = Math.round(plan.ph * s);
    x.fillStyle = '#fff'; x.fillRect(0, 0, cv.width, cv.height);
    (plan.sheets[index] || []).forEach(function (pos) {
      var dx = pos[0] * s, dy = (plan.ph - pos[1] - plan.ch) * s, dw = plan.cw * s, dh = plan.ch * s;
      x.save(); x.beginPath(); x.rect(dx, dy, dw, dh); x.clip();
      x.translate(dx + dw / 2, dy + dh / 2);
      if (plan.rot) x.rotate(Math.PI / 2);
      var bw = plan.rot ? dh : dw, bh = plan.rot ? dw : dh;           // box in the photo's own (upright) direction
      var k = Math.max(bw / img.naturalWidth, bh / img.naturalHeight); // cover
      x.drawImage(img, -img.naturalWidth * k / 2, -img.naturalHeight * k / 2, img.naturalWidth * k, img.naturalHeight * k);
      x.restore();
      x.strokeStyle = '#c8c8c8'; x.lineWidth = 1; x.strokeRect(dx + .5, dy + .5, dw - 1, dh - 1);
    });
    x.strokeStyle = '#aab2c0'; x.strokeRect(.5, .5, cv.width - 1, cv.height - 1);
  }

  // Page numbers (1-based) chosen with a range like "1-3,5"; all pages when empty.
  function pageList(total, range) {
    range = String(range || '').replace(/\s+/g, '');
    var out = [];
    if (!/^(\d+(-\d+)?)(,\d+(-\d+)?)*$/.test(range)) {
      for (var i = 1; i <= total; i++) out.push(i);
      return out;
    }
    range.split(',').forEach(function (part) {
      var ab = part.split('-'), a = +ab[0], b = ab.length > 1 ? +ab[1] : a;
      if (b < a) { var t = a; a = b; b = t; }
      for (var i = a; i <= Math.min(b, total || b); i++) if (out.indexOf(i) < 0 && out.length < 5000) out.push(i);
    });
    return out.length ? out : [1];
  }

  // Number of sheets a layout produces (for the price shown before upload).
  function sheets(code, defs, pages, range, paper) {
    var L = parse(code, defs);
    if (!L) return null;
    if (L.type === 'nup') return Math.max(1, Math.ceil(pageList(pages, range).length / L.n));
    if (L.type === 'size' && L.pieces) return Math.ceil(L.pieces / sizeFit(L.w, L.h, paper || 'A4').max);
    return 1;
  }

  function pieces(code, defs, paper) {
    var L = parse(code, defs);
    if (!L) return 0;
    if (L.type === 'grid') return L.n;
    if (L.type === 'size') return L.pieces || sizeFit(L.w, L.h, paper).max;
    return 0;
  }

  // Photo → JPEG cropped to fill a w:h box ("cover"); rotated when that fills the box better.
  function photoJpeg(file, wMm, hMm, mayRotate, force) {
    return new Promise(function (resolve, reject) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () {
        URL.revokeObjectURL(url);
        var iw = img.naturalWidth, ih = img.naturalHeight;
        var rotate = force || (mayRotate && (iw > ih) !== (wMm > hMm) && Math.abs(iw - ih) > 2);
        var srcW = rotate ? ih : iw, srcH = rotate ? iw : ih; // size after rotation
        var target = wMm / hMm, sw = srcW, sh = srcH;
        if (srcW / srcH > target) sw = srcH * target; else sh = srcW / target;
        var px = Math.min(2400, Math.round(Math.max(wMm, hMm) / 25.4 * 300)); // ~300 dpi
        var cw = wMm >= hMm ? px : Math.round(px * wMm / hMm), ch = wMm >= hMm ? Math.round(px * hMm / wMm) : px;
        var c = document.createElement('canvas'), x = c.getContext('2d');
        c.width = cw; c.height = ch;
        x.fillStyle = '#fff'; x.fillRect(0, 0, cw, ch);
        x.save();
        if (rotate) { x.translate(cw, 0); x.rotate(Math.PI / 2); }
        var dw = rotate ? ch : cw, dh = rotate ? cw : ch;           // drawing box in rotated space
        var cropW = rotate ? sh : sw, cropH = rotate ? sw : sh;     // crop box in original image space
        x.drawImage(img, (iw - cropW) / 2, (ih - cropH) / 2, cropW, cropH, 0, 0, dw, dh);
        x.restore();
        c.toBlob(function (b) { b ? b.arrayBuffer().then(resolve, reject) : reject(new Error('image')); }, 'image/jpeg', 0.92);
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('Cannot read this image')); };
      img.src = url;
    });
  }

  function fitInto(w, h, boxW, boxH) { // keep aspect ratio inside a box
    var s = Math.min(boxW / w, boxH / h);
    return [w * s, h * s];
  }

  // Builds the print-ready PDF. Returns {blob, sheets, landscape}.
  async function build(file, code, defs, paper, range) {
    var L = parse(code, defs);
    if (!L || !window.PDFLib) throw new Error('Layout not available');
    var lib = window.PDFLib, out = await lib.PDFDocument.create();
    var isPdf = /\.pdf$/i.test(file.name) || file.type === 'application/pdf';
    var src = isPdf ? await lib.PDFDocument.load(await file.arrayBuffer(), { ignoreEncryption: true }) : null;
    var grey = lib.rgb(0.78, 0.78, 0.78), landscape = false;

    if (L.type === 'nup') {
      if (!src) throw new Error('Pages per sheet works with PDF files');
      landscape = L.n === 2 || L.n === 8;
      var p = paperMm(paper, landscape), g = grid(L.n, landscape);
      var cw = (p[0] - 2 * MARGIN - (g[0] - 1) * GAP) / g[0], ch = (p[1] - 2 * MARGIN - (g[1] - 1) * GAP) / g[1];
      var list = pageList(src.getPageCount(), range).filter(function (n) { return n <= src.getPageCount(); });
      var emb = await out.embedPdf(src, list.map(function (n) { return n - 1; }));
      for (var i = 0; i < emb.length; i += L.n) {
        var page = out.addPage([p[0] * MM, p[1] * MM]);
        for (var k = 0; k < L.n && i + k < emb.length; k++) {
          var e = emb[i + k], col = k % g[0], row = Math.floor(k / g[0]);
          var sz = fitInto(e.width, e.height, cw * MM, ch * MM);
          var x = (MARGIN + col * (cw + GAP)) * MM + (cw * MM - sz[0]) / 2;
          var y = (p[1] - MARGIN - (row + 1) * ch - row * GAP) * MM + (ch * MM - sz[1]) / 2;
          page.drawPage(e, { x: x, y: y, width: sz[0], height: sz[1] });
        }
      }
      return { blob: new Blob([await out.save()], { type: 'application/pdf' }), sheets: out.getPageCount(), landscape: landscape };
    }

    if (L.type === 'size') { // exact-size photos: as many sheets as needed
      var plan = sizePlan(L.w, L.h, paper, L.pieces), drawOne;
      if (src) {
        var ep1 = (await out.embedPdf(src, [0]))[0];
        drawOne = function (pg, x, y) {
          var s1 = fitInto(ep1.width, ep1.height, plan.cw * MM, plan.ch * MM);
          pg.drawPage(ep1, { x: x * MM + (plan.cw * MM - s1[0]) / 2, y: y * MM + (plan.ch * MM - s1[1]) / 2, width: s1[0], height: s1[1] });
        };
      } else {
        var jp = await out.embedJpg(await photoJpeg(file, plan.cw, plan.ch, false, plan.rot));
        drawOne = function (pg, x, y) { pg.drawImage(jp, { x: x * MM, y: y * MM, width: plan.cw * MM, height: plan.ch * MM }); };
      }
      plan.sheets.forEach(function (cellsOnSheet) {
        var pg = out.addPage([plan.pw * MM, plan.ph * MM]);
        cellsOnSheet.forEach(function (c) {
          drawOne(pg, c[0], c[1]);
          pg.drawRectangle({ x: c[0] * MM, y: c[1] * MM, width: plan.cw * MM, height: plan.ch * MM, borderColor: grey, borderWidth: 0.3 });
        });
      });
      return { blob: new Blob([await out.save()], { type: 'application/pdf' }), sheets: plan.sheets.length, landscape: false };
    }

    // Photo sheets: the same photo N times, filling the sheet
    var P = paperMm(paper, false), page2 = out.addPage([P[0] * MM, P[1] * MM]), cells = [];
    var cellW, cellH, cols, rows, count;
    var gg = grid(L.n, false), mg = margin(paper); cols = gg[0]; rows = gg[1]; count = L.n;
    cellW = (P[0] - 2 * mg - (cols - 1) * GAP) / cols; cellH = (P[1] - 2 * mg - (rows - 1) * GAP) / rows;
    var blockW = cols * cellW + (cols - 1) * GAP, left = (P[0] - blockW) / 2;
    for (var j = 0; j < count; j++) {
      var c2 = j % cols, r2 = Math.floor(j / cols);
      cells.push([left + c2 * (cellW + GAP), P[1] - mg - (r2 + 1) * cellH - r2 * GAP]);
    }
    var draw;
    if (src) { // PDF: its first page, kept whole
      var ep = (await out.embedPdf(src, [0]))[0];
      draw = function (x, y) {
        var s = fitInto(ep.width, ep.height, cellW * MM, cellH * MM);
        page2.drawPage(ep, { x: x * MM + (cellW * MM - s[0]) / 2, y: y * MM + (cellH * MM - s[1]) / 2, width: s[0], height: s[1] });
      };
    } else {
      var jpg = await out.embedJpg(await photoJpeg(file, cellW, cellH, L.type === 'grid'));
      draw = function (x, y) { page2.drawImage(jpg, { x: x * MM, y: y * MM, width: cellW * MM, height: cellH * MM }); };
    }
    cells.forEach(function (c) {
      draw(c[0], c[1]);
      page2.drawRectangle({ x: c[0] * MM, y: c[1] * MM, width: cellW * MM, height: cellH * MM, borderColor: grey, borderWidth: 0.3 });
    });
    return { blob: new Blob([await out.save()], { type: 'application/pdf' }), sheets: 1, landscape: false };
  }

  window.DaybillLayout = { parse: parse, sheets: sheets, pieces: pieces, build: build, sizeFit: sizeFit,
    sizePlan: sizePlan, drawPreview: drawPreview, papers: PAPER };
})();
