// QR scanner: phone camera → canvas → the phone's own QR reader (BarcodeDetector, e.g. Android Chrome)
// or jsQR (assets/vendor/jsQR.js). jsQR is used because it reads every code the app makes; the decoder
// of the html5-qrcode library missed about 1 in 12 of them.
(function () {
  var MAX = 960; // frames are scaled down to this width before reading (fast on phones, sharp enough)

  var native = null;
  if ('BarcodeDetector' in window) {
    try {
      BarcodeDetector.getSupportedFormats().then(function (f) {
        if (f.indexOf('qr_code') >= 0) native = new BarcodeDetector({ formats: ['qr_code'] });
      }).catch(function () {});
    } catch (e) {}
  }

  // Reads a QR from an image, video or canvas. Resolves with the text, or null.
  function readFrom(source, w, h, canvas) {
    if (native) {
      return native.detect(source).then(function (codes) {
        return codes.length ? codes[0].rawValue : readJs(source, w, h, canvas);
      }).catch(function () { return readJs(source, w, h, canvas); });
    }
    return Promise.resolve(readJs(source, w, h, canvas));
  }

  function readJs(source, w, h, canvas, size) {
    if (!window.jsQR || !w || !h) return null;
    var scale = Math.min(1, (size || MAX) / Math.max(w, h));
    var cw = Math.round(w * scale), ch = Math.round(h * scale);
    canvas.width = cw; canvas.height = ch;
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(source, 0, 0, cw, ch);
    var r = jsQR(ctx.getImageData(0, 0, cw, ch).data, cw, ch, { inversionAttempts: 'attemptBoth' });
    return r && r.data ? r.data : null;
  }

  // Live camera scanner in the element with id `id`.
  function Scanner(id) {
    this.box = document.getElementById(id);
    this.stream = null;
    this.timer = null;
    this.canvas = document.createElement('canvas');
  }

  Scanner.prototype.start = function (facing, onText) {
    var self = this;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return Promise.reject(new Error('NotSupportedError: camera needs https'));
    }
    var open = function (video) {
      return navigator.mediaDevices.getUserMedia({ audio: false, video: video });
    };
    return open({ facingMode: { ideal: facing || 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } })
      .catch(function () { return open(true); }) // any camera
      .then(function (stream) {
        self.stream = stream;
        self.box.innerHTML = '<div class="scan-view"><video playsinline muted autoplay></video><div class="scan-frame"></div></div>';
        var v = self.box.querySelector('video');
        v.setAttribute('playsinline', ''); // iPhone: play inside the page
        v.srcObject = stream;
        return v.play().catch(function () {}).then(function () {
          var busy = false;
          self.timer = setInterval(function () {
            if (busy || !v.videoWidth) return;
            busy = true;
            readFrom(v, v.videoWidth, v.videoHeight, self.canvas).then(function (text) {
              busy = false;
              if (text && self.stream) onText(text);
            }, function () { busy = false; });
          }, 150);
        });
      });
  };

  Scanner.prototype.stop = function () {
    clearInterval(this.timer);
    this.timer = null;
    if (this.stream) {
      this.stream.getTracks().forEach(function (t) { t.stop(); });
    }
    this.stream = null;
    if (this.box) this.box.innerHTML = '';
    return Promise.resolve();
  };

  // QR from a photo file. Resolves with the text or rejects when there is no QR.
  function readFile(file) {
    var canvas = document.createElement('canvas');
    return new Promise(function (resolve, reject) {
      var img = new Image();
      var url = URL.createObjectURL(file);
      img.onload = function () {
        URL.revokeObjectURL(url);
        var w = img.naturalWidth, h = img.naturalHeight;
        readFrom(img, w, h, canvas).then(function (t) {
          // Photos from phones are large: also try smaller and bigger working sizes.
          t = t || readJs(img, w, h, canvas, 1600) || readJs(img, w, h, canvas, 600) || readJs(img, w, h, canvas, 2400);
          if (t) resolve(t); else reject(new Error('no QR'));
        });
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('not an image')); };
      img.src = url;
    });
  }

  window.VMScan = { Scanner: Scanner, readFile: readFile, ready: function () { return !!window.jsQR; } };
})();
