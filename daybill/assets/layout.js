// Print layouts, built in the browser with pdf-lib (assets/pdf-lib.min.js):
//   nup  – 2 / 4 / 8 document pages on one sheet
//   grid – the same photo 2 / 4 / 6 / 8 times on one sheet
//   size – photos of an exact size (e.g. passport 35×45 mm), a chosen number of pieces
// A layout code is "id" or "id:pieces" (size layouts), e.g. "nup4", "passport:8".
(function () {
  var MM = 72 / 25.4; // PDF points per millimetre
  var PAPER = { A2: [420, 594], A3: [297, 420], A4: [210, 297], A5: [148, 210], A6: [105, 148],
    Letter: [216, 279], Legal: [216, 356], Tabloid: [279, 432], Statement: [140, 216] };
  var MARGIN = 6, GAP = 3; // mm; most printers cannot print the outer ~4 mm

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

  // How many photos of w×h mm fit on the sheet.
  function sizeFit(w, h, paper) {
    var p = paperMm(paper, false);
    var cols = Math.max(1, Math.floor((p[0] - 2 * MARGIN + GAP) / (w + GAP)));
    var rows = Math.max(1, Math.floor((p[1] - 2 * MARGIN + GAP) / (h + GAP)));
    return { cols: cols, rows: rows, max: cols * rows };
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
  function sheets(code, defs, pages, range) {
    var L = parse(code, defs);
    if (!L) return null;
    if (L.type === 'nup') return Math.max(1, Math.ceil(pageList(pages, range).length / L.n));
    return 1;
  }

  function pieces(code, defs, paper) {
    var L = parse(code, defs);
    if (!L) return 0;
    if (L.type === 'grid') return L.n;
    if (L.type === 'size') { var m = sizeFit(L.w, L.h, paper).max; return L.pieces ? Math.min(L.pieces, m) : m; }
    return 0;
  }

  // Photo → JPEG cropped to fill a w:h box ("cover"); rotated when that fills the box better.
  function photoJpeg(file, wMm, hMm, mayRotate) {
    return new Promise(function (resolve, reject) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () {
        URL.revokeObjectURL(url);
        var iw = img.naturalWidth, ih = img.naturalHeight;
        var rotate = mayRotate && (iw > ih) !== (wMm > hMm) && Math.abs(iw - ih) > 2;
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

    // Photo sheets (grid or exact size)
    var P = paperMm(paper, false), page2 = out.addPage([P[0] * MM, P[1] * MM]), cells = [];
    var cellW, cellH, cols, rows, count;
    if (L.type === 'grid') {
      var gg = grid(L.n, false); cols = gg[0]; rows = gg[1]; count = L.n;
      cellW = (P[0] - 2 * MARGIN - (cols - 1) * GAP) / cols; cellH = (P[1] - 2 * MARGIN - (rows - 1) * GAP) / rows;
    } else {
      var f = sizeFit(L.w, L.h, paper); cols = f.cols; rows = f.rows; cellW = L.w; cellH = L.h;
      count = L.pieces ? Math.min(L.pieces, f.max) : f.max;
    }
    var blockW = cols * cellW + (cols - 1) * GAP, left = (P[0] - blockW) / 2;
    for (var j = 0; j < count; j++) {
      var c2 = j % cols, r2 = Math.floor(j / cols);
      cells.push([left + c2 * (cellW + GAP), P[1] - MARGIN - (r2 + 1) * cellH - r2 * GAP]);
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

  window.DaybillLayout = { parse: parse, sheets: sheets, pieces: pieces, build: build, sizeFit: sizeFit };
})();
