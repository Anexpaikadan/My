// Valley MMA – page helpers: install as app, forms, exports, WhatsApp sharing, member QR scan.
(function () {
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };

  // ---- Install as phone app (PWA) ----
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
    navigator.serviceWorker.register('sw.js').catch(function () {});
  }
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferred = e;
    $$('[data-install]').forEach(function (b) { b.classList.remove('d-none'); });
  });
  $$('[data-install]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!deferred) return;
      deferred.prompt();
      deferred.userChoice.finally(function () { deferred = null; b.classList.add('d-none'); });
    });
  });

  // ---- Dates ----
  var addPlan = function (start, v, unit) {
    var p = start.split('-').map(Number);
    var d = new Date(Date.UTC(p[0], p[1] - 1, p[2]));
    if (unit === 'day') {
      d.setUTCDate(d.getUTCDate() + v);
    } else {
      var day = d.getUTCDate();
      d.setUTCDate(1);
      d.setUTCMonth(d.getUTCMonth() + v);
      var last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
      d.setUTCDate(Math.min(day, last));
    }
    d.setUTCDate(d.getUTCDate() - 1);
    return d.toISOString().slice(0, 10);
  };
  var money = function (n) { return '₹' + (Math.round(n * 100) / 100).toLocaleString('en-IN'); };

  // Plan + start date -> expiry date (member form and payment form)
  var planEnd = function () {
    var start = $('[data-plan-start]'), end = $('[data-plan-end]');
    if (!start || !end || !start.value) return;
    var opt = null;
    var sel = $('[data-plan-select]');
    if (sel) opt = sel.options[sel.selectedIndex];
    var radio = $('[data-plan-radio]:checked');
    if (radio) opt = radio;
    if (opt && opt.dataset && opt.dataset.v) end.value = addPlan(start.value, parseInt(opt.dataset.v, 10), opt.dataset.u);
  };
  $$('[data-plan-select], [data-plan-start]').forEach(function (el) { el.addEventListener('change', planEnd); });
  if ($('[data-plan-end]') && !$('[data-plan-end]').value) planEnd();

  // ---- Member form ----
  $$('[data-preview]').forEach(function (inp) {
    inp.addEventListener('change', function () {
      if (!inp.files[0]) return;
      var label = $('label[for="' + inp.id + '"]');
      label.innerHTML = '<img alt="">';
      label.querySelector('img').src = URL.createObjectURL(inp.files[0]);
    });
  });
  var bmi = function () {
    var h = parseFloat(($('#height_cm') || {}).value), w = parseFloat(($('#weight_kg') || {}).value);
    if ($('#bmi')) $('#bmi').value = h > 0 && w > 0 ? (w / Math.pow(h / 100, 2)).toFixed(1) : '';
  };
  $$('[data-bmi]').forEach(function (el) { el.addEventListener('input', bmi); });
  $$('[data-age-target]').forEach(function (el) {
    el.addEventListener('change', function () {
      if (!el.value) return;
      var b = new Date(el.value), n = new Date();
      var age = n.getFullYear() - b.getFullYear() - ((n.getMonth() < b.getMonth() || (n.getMonth() === b.getMonth() && n.getDate() < b.getDate())) ? 1 : 0);
      if (age > 0) document.getElementById(el.dataset.ageTarget).value = age;
    });
  });

  // ---- Payment form ----
  var pay = $('#payForm');
  if (pay) {
    var oldBal = parseFloat(pay.dataset.balance || '0');
    var paid = $('#paid'), touched = paid.value !== '';
    var total = function () {
      return $$('[data-sum]').reduce(function (s, el) {
        if (el.closest('.plan-fields') && el.closest('.plan-fields').classList.contains('d-none')) return s;
        return s + (parseFloat(el.value) || 0);
      }, 0);
    };
    var upiQr = $('#upiQr');
    var refresh = function () {
      var t = total();
      if (!touched) paid.value = t ? t.toFixed(2).replace(/\.00$/, '') : '';
      var p = parseFloat(paid.value) || 0;
      $('#sumTotal').textContent = money(t);
      var bal = oldBal + t - p;
      $('#sumBalance').textContent = money(bal);
      $('#sumBalance').className = bal > 0 ? 'text-danger' : 'text-success';
      var method = ($('[name=method]:checked') || {}).value;
      $('#upiBox').classList.toggle('d-none', method !== 'upi');
      if (upiQr && method === 'upi' && window.drawQr) window.drawQr(upiQr, upiQr.dataset.upi + (p > 0 ? '&am=' + p.toFixed(2) : ''));
    };
    var planChange = function () {
      var r = $('[data-plan-radio]:checked');
      var has = r && r.value !== '';
      $('.plan-fields').classList.toggle('d-none', !has);
      if (has) { $('#plan_fee').value = r.dataset.price; planEnd(); }
      refresh();
    };
    $$('[data-plan-radio]').forEach(function (r) { r.addEventListener('change', planChange); });
    $$('[data-sum]').forEach(function (el) { el.addEventListener('input', refresh); });
    $$('[name=method]').forEach(function (el) { el.addEventListener('change', refresh); });
    paid.addEventListener('input', function () { touched = true; refresh(); });
    $$('[data-fill]').forEach(function (b) {
      b.addEventListener('click', function () {
        var t = total() + (b.dataset.fill === 'all' ? oldBal : 0);
        paid.value = t.toFixed(2).replace(/\.00$/, ''); touched = true; refresh();
      });
    });
    var r0 = $('[data-plan-radio]:checked');
    $('.plan-fields').classList.toggle('d-none', !(r0 && r0.value !== ''));
    if (!$('[data-plan-end]').value) planEnd();
    refresh();
  }

  // ---- Accounts entry form: show the fields for income / expense / transfer ----
  var entry = $('#entryForm');
  if (entry) {
    var showType = function () {
      var type = ($('[data-entry-type]:checked') || {}).value || 'expense';
      $$('.when-cat', entry).forEach(function (el) { el.classList.toggle('d-none', type === 'transfer'); });
      $$('.when-transfer', entry).forEach(function (el) { el.classList.toggle('d-none', type !== 'transfer'); });
      $$('.when-income', entry).forEach(function (el) { el.classList.toggle('d-none', type !== 'income'); });
      $$('.when-expense', entry).forEach(function (el) { el.classList.toggle('d-none', type !== 'expense'); });
      $$('[data-cat-type]', entry).forEach(function (el) {
        var hide = el.dataset.catType !== type;
        el.classList.toggle('d-none', hide);
        if (hide) el.querySelector('input').checked = false;
      });
      var title = document.querySelector('.page-head h1');
      var radio = $('[data-entry-type]:checked');
      if (title && radio && !entry.querySelector('[name=id]').value) title.textContent = radio.dataset.title;
    };
    $$('[data-entry-type]').forEach(function (r) { r.addEventListener('change', showType); });
    showType();
  }

  // ---- Report export: print, PDF, Excel (CSV) ----
  var cellText = function (c) {
    var t = c.dataset.en !== undefined ? c.dataset.en : c.innerText;
    return t.replace(/\s+/g, ' ').trim();
  };
  var tableData = function (tbl) {
    var rows = function (sel) {
      return $$(sel, tbl).map(function (tr) {
        return $$('th, td', tr).filter(function (c) { return !c.classList.contains('no-export'); }).map(function (c) {
          return { content: cellText(c), colSpan: c.colSpan || 1 };
        });
      });
    };
    return { head: rows('thead tr'), body: rows('tbody tr').filter(function (r) { return r.length > 1 || (r[0] && r[0].colSpan > 1 && r[0].content !== ''); }), foot: rows('tfoot tr') };
  };
  $$('[data-export]').forEach(function (b) {
    b.addEventListener('click', function () {
      var tbl = $('#reportTable');
      if (!tbl) return;
      var kind = b.dataset.export;
      var title = tbl.dataset.title || document.title;
      var file = title.replace(/[^\w-]+/g, '_');
      if (kind === 'print') { window.print(); return; }
      var data = tableData(tbl);
      if (kind === 'csv') {
        var lines = [].concat(data.head, data.body, data.foot).map(function (r) {
          var out = [];
          r.forEach(function (c) {
            out.push('"' + c.content.replace(/₹/g, '').replace(/(\d),(?=\d{2})/g, '$1').replace(/"/g, '""') + '"');
            for (var i = 1; i < c.colSpan; i++) out.push('""');
          });
          return out.join(',');
        });
        var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob); a.download = file + '.csv';
        document.body.appendChild(a); a.click(); a.remove();
        return;
      }
      // PDF: the built-in PDF font has no ₹ or Malayalam letters, so English text and "Rs" are used.
      var fix = function (rows) {
        return rows.map(function (r) {
          return r.map(function (c) { return { content: c.content.replace(/₹/g, 'Rs ').replace(/✓/g, 'P').replace(/[^\x00-\x7F]/g, ''), colSpan: c.colSpan }; });
        });
      };
      var JsPDF = window.jspdf.jsPDF;
      var wide = tbl.dataset.landscape === '1' || data.head[0].length > 7;
      var doc = new JsPDF({ orientation: wide ? 'landscape' : 'portrait', unit: 'pt', format: 'a4' });
      doc.setFontSize(15); doc.setFont('helvetica', 'bold');
      doc.text((window.VM.gym || 'VALLEY MMA') + ' - ' + (window.VM.place || ''), 40, 36);
      doc.setFontSize(10); doc.setFont('helvetica', 'normal');
      doc.text(title.replace(/[^\x00-\x7F]/g, ''), 40, 52);
      doc.text((window.VM.phones || '').replace(/[^\x00-\x7F]/g, ''), doc.internal.pageSize.getWidth() - 40, 36, { align: 'right' });
      doc.autoTable({
        head: fix(data.head), body: fix(data.body), foot: fix(data.foot), startY: 64,
        theme: 'grid', styles: { fontSize: wide && data.head[0].length > 20 ? 6 : 9, cellPadding: wide && data.head[0].length > 20 ? 2 : 4 },
        headStyles: { fillColor: [54, 13, 217] }, footStyles: { fillColor: [26, 26, 26] },
        didDrawPage: function () {
          doc.setFontSize(8);
          doc.text('Printed ' + new Date().toLocaleString('en-IN'), 40, doc.internal.pageSize.getHeight() - 16);
        }
      });
      doc.save(file + '.pdf');
    });
  });

  // ---- Plans: edit modal and WhatsApp share ----
  var planModal = $('#planModal');
  if (planModal) {
    planModal.addEventListener('show.bs.modal', function (e) {
      var p = JSON.parse(e.relatedTarget.dataset.plan || '{}');
      var f = planModal.querySelector('form');
      f.id.value = p.id || '';
      f.name.value = p.name || '';
      f.duration_value.value = p.duration_value || 1;
      f.duration_unit.value = p.duration_unit || 'month';
      f.price.value = p.price !== undefined ? parseFloat(p.price) : '';
      f.sort_order.value = p.sort_order || 0;
      f.description.value = p.description || '';
      f.active.checked = p.active === undefined || String(p.active) === '1';
    });
  }
  var share = $('#shareModal');
  if (share) {
    var txt = $('#shareText');
    var open = function (phone) { window.open('https://wa.me/' + phone + '?text=' + encodeURIComponent(txt.value), '_blank', 'noopener'); };
    share.addEventListener('show.bs.modal', function (e) { txt.value = e.relatedTarget.dataset.text; });
    $$('#shareList a').forEach(function (a) { a.addEventListener('click', function (ev) { ev.preventDefault(); open(a.dataset.phone); }); });
    $('#shareGo').addEventListener('click', function () {
      var d = $('#sharePhone').value.replace(/\D/g, '');
      if (d.length === 10) d = (window.VM_CC || '91') + d;
      if (d.length >= 10) open(d);
    });
    $('#shareAny').addEventListener('click', function (ev) { ev.preventDefault(); open(''); });
    $('#shareSearch').addEventListener('input', function () {
      var q = this.value.toLowerCase();
      $$('#shareList a').forEach(function (a) { a.classList.toggle('d-none', a.dataset.name.indexOf(q) < 0); });
    });
  }

  // ---- Password check before money changes and deletes (forms with data-verify="message") ----
  var vModal = document.getElementById('verifyModal');
  if (vModal && window.bootstrap) {
    var modal = new bootstrap.Modal(vModal);
    var pending = null, pendingBtn = null;
    document.addEventListener('submit', function (e) {
      var f = e.target;
      if (!f.matches || !f.matches('form[data-verify]') || f.dataset.verified === '1' || e.defaultPrevented) return;
      e.preventDefault();
      pending = f; pendingBtn = e.submitter || null;
      document.getElementById('verifyMsg').textContent = f.dataset.verify || '';
      document.getElementById('verifyPass').value = '';
      modal.show();
    }, true);
    vModal.addEventListener('shown.bs.modal', function () { document.getElementById('verifyPass').focus(); });
    document.getElementById('verifyForm').addEventListener('submit', function (e) {
      e.preventDefault();
      if (!pending) return;
      var f = pending;
      var h = f.querySelector('input[name=verify_password]');
      if (!h) { h = document.createElement('input'); h.type = 'hidden'; h.name = 'verify_password'; f.appendChild(h); }
      h.value = document.getElementById('verifyPass').value;
      if (pendingBtn && pendingBtn.name) {
        var b = document.createElement('input'); b.type = 'hidden'; b.name = pendingBtn.name; b.value = pendingBtn.value; f.appendChild(b);
      }
      f.dataset.verified = '1';
      modal.hide();
      HTMLFormElement.prototype.submit.call(f);
      // Downloads keep the page open: ask again next time.
      setTimeout(function () { f.dataset.verified = ''; h.value = ''; }, 1500);
    });
  }

  // ---- Small helpers ----
  $$('[data-filter]').forEach(function (inp) {
    inp.addEventListener('input', function () {
      var q = inp.value.toLowerCase();
      $$(inp.dataset.filter).forEach(function (el) { el.classList.toggle('d-none', (el.dataset.text || '').indexOf(q) < 0); });
    });
  });
  $$('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var el = $(b.dataset.copy);
      el.select();
      if (navigator.clipboard) navigator.clipboard.writeText(el.value); else document.execCommand('copy');
      b.innerHTML = '<i class="bi bi-check2"></i>';
    });
  });
  $$('[data-random-pass]').forEach(function (b) {
    b.addEventListener('click', function () {
      $(b.dataset.randomPass).value = String(100000 + Math.floor(Math.random() * 900000));
    });
  });
  $$('a[data-sent]').forEach(function (a) {
    a.addEventListener('click', function () { a.classList.add('opacity-50'); });
  });
  $$('#attOrder [data-move]').forEach(function (b) {
    b.addEventListener('click', function () {
      var li = b.closest('li');
      if (b.dataset.move === 'up' && li.previousElementSibling) li.parentNode.insertBefore(li, li.previousElementSibling);
      if (b.dataset.move === 'down' && li.nextElementSibling) li.parentNode.insertBefore(li.nextElementSibling, li);
    });
  });

  // ---- QR scan from a photo (works without https, where the live camera is blocked) ----
  // input: <input type=file accept=image/* capture=environment>; onText gets the QR text.
  window.vmPhotoScan = function (input, readerId, onText, onError) {
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (!file) return;
      var sc = new Html5Qrcode(readerId);
      sc.scanFile(file, false).then(function (text) { onText(text); })
        .catch(function () { onError(); })
        .finally(function () { input.value = ''; try { sc.clear(); } catch (e) {} });
    });
  };
  window.vmLiveCameraOk = function () {
    return window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia;
  };

  // ---- Member app: scan the attendance QR inside the app ----
  var meScan = $('#meScan');
  if (meScan && window.Html5Qrcode) {
    var msg = $('#meScanMsg'), reader = $('#reader'), sc = null;
    // The gym QR opens checkin.php?d=…&k=… – go to it on this same address (the QR may show another one).
    var go = function (text) {
      var u = null;
      try { u = new URL(text, location.href); } catch (e) {}
      if (!u || !/checkin\.php$/.test(u.pathname) || !u.searchParams.get('d') || !u.searchParams.get('k')) {
        msg.textContent = window.VM_ME.wrong;
        return false;
      }
      location.href = 'checkin.php' + u.search;
      return true;
    };
    var photo = $('#mePhoto');
    var showPhoto = function (why) {
      reader.classList.add('d-none');
      $('#mePhotoWrap').classList.remove('d-none');
      msg.textContent = why || '';
    };
    if (photo) window.vmPhotoScan(photo, 'mePhotoReader', go, function () { msg.textContent = window.VM_ME.noQr; });
    if (!window.vmLiveCameraOk()) {
      meScan.classList.add('d-none');
      showPhoto('');
    }
    meScan.addEventListener('click', function () {
      reader.classList.remove('d-none');
      sc = sc || new Html5Qrcode('reader');
      sc.start({ facingMode: 'environment' }, { fps: 10, qrbox: 230 }, function (text) {
        sc.stop().finally(function () { if (!go(text)) meScan.click(); });
      }, function () {}).catch(function () {
        showPhoto(window.VM_ME.camErr);
      });
    });
  }
})();
