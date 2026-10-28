// Attendance page: live QR code, ID card scanner (front/back camera) and member search.
(function () {
  var cfg = window.VM_ATT || {};

  // ---- Today's QR: redraw when it changes and keep the present count up to date ----
  var qr = document.getElementById('attQr');
  if (qr) {
    var lastUrl = qr.dataset.qr;
    var refresh = parseInt(qr.dataset.refresh || '0', 10);
    setInterval(function () {
      fetch('attendance.php?action=token', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.url !== lastUrl) { lastUrl = d.url; window.drawQr(qr, d.url); }
          document.getElementById('qrCount').textContent = d.count;
          var badge = document.getElementById('todayCount');
          if (badge) badge.textContent = d.count;
        }).catch(function () {});
      fetch('attendance.php?action=list', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (list) {
          var el = document.getElementById('qrLast');
          if (el && list.length) el.textContent = list[0].name + ' · ' + list[0].time;
        }).catch(function () {});
    }, refresh > 0 ? 10000 : 15000);

    document.getElementById('qrFull').addEventListener('click', function () {
      var p = document.getElementById('qrPanel');
      if (document.fullscreenElement) document.exitFullscreen();
      else if (p.requestFullscreen) p.requestFullscreen();
    });
  }

  // ---- Scan member ID cards ----
  var startBtn = document.getElementById('scanStart');
  if (startBtn && window.VMScan) {
    var flipBtn = document.getElementById('scanFlip');
    var stopBtn = document.getElementById('scanStop');
    var out = document.getElementById('scanResult');
    var scanner = null;
    var facing = cfg.facing || 'environment';
    var last = '', lastAt = 0, busy = false;

    var beep = function (ok) {
      try {
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        var o = ctx.createOscillator(); var g = ctx.createGain();
        o.frequency.value = ok ? 880 : 220; o.connect(g); g.connect(ctx.destination);
        g.gain.value = 0.15; o.start(); o.stop(ctx.currentTime + (ok ? 0.15 : 0.4));
      } catch (e) {}
      if (navigator.vibrate) navigator.vibrate(ok ? 80 : [80, 60, 80]);
    };
    var esc = function (s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; };

    var onScan = function (text) {
      var now = Date.now();
      if (busy || (text === last && now - lastAt < 4000)) return;
      last = text; lastAt = now; busy = true;
      var fd = new FormData();
      fd.append('action', 'card'); fd.append('code', text); fd.append('csrf', cfg.csrf);
      fetch('attendance.php', { method: 'POST', body: fd, credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          beep(d.ok && d.status !== 'expired');
          if (!d.ok) { out.innerHTML = '<div class="alert alert-danger">' + esc(d.msg) + '</div>'; return; }
          var cls = d.status === 'expired' ? 'danger' : (d.new ? 'success' : 'info');
          out.innerHTML = '<div class="alert alert-' + cls + ' d-flex align-items-center gap-3 text-start">' +
            '<img src="' + esc(d.photo) + '" class="avatar" style="width:64px;height:64px" alt="">' +
            '<div><div class="fw-bold fs-5">' + esc(d.name) + ' <small>' + esc(d.adm_no) + '</small></div>' +
            '<div>' + esc(d.msg) + '</div><div class="small">' + esc(d.status_text) + '</div></div></div>';
        })
        .catch(function () { out.innerHTML = '<div class="alert alert-danger">Network error</div>'; })
        .finally(function () { setTimeout(function () { busy = false; }, 1200); });
    };

    var start = function () {
      scanner = scanner || window.vmNewScanner('reader');
      return window.vmStartCamera(scanner, facing, window.vmScanConfig, onScan)
        .then(function () {
          startBtn.classList.add('d-none'); flipBtn.classList.remove('d-none'); stopBtn.classList.remove('d-none');
        })
        .catch(function (err) {
          out.innerHTML = '<div class="alert alert-warning">' + esc(cfg.camErr) + '<br><small>' + esc(String(err)) + '</small></div>';
        });
    };
    var stop = function () {
      if (!scanner) return Promise.resolve();
      return scanner.stop().catch(function () {}).then(function () {
        startBtn.classList.remove('d-none'); flipBtn.classList.add('d-none'); stopBtn.classList.add('d-none');
      });
    };
    startBtn.addEventListener('click', start);
    stopBtn.addEventListener('click', stop);
    flipBtn.addEventListener('click', function () {
      facing = facing === 'environment' ? 'user' : 'environment';
      stop().then(start);
    });
    // No https: the live camera is blocked, so read the card from a photo instead.
    window.addEventListener('load', function () {
      var photo = document.getElementById('cardPhoto');
      if (photo && window.vmPhotoScan) {
        window.vmPhotoScan(photo, 'cardPhotoReader', onScan, function () {
          out.innerHTML = '<div class="alert alert-warning">' + esc(cfg.noQr) + '</div>';
        });
      }
      if (window.vmLiveCameraOk && !window.vmLiveCameraOk()) {
        startBtn.classList.add('d-none');
        out.innerHTML = '<div class="alert alert-info small">' + esc(cfg.httpsCam) + '</div>';
      }
    });
    // Stop the camera when leaving the tab.
    document.querySelectorAll('[data-tab]').forEach(function (b) {
      b.addEventListener('shown.bs.tab', function () { if (b.dataset.tab !== 'card') stop(); });
    });
  }
})();
