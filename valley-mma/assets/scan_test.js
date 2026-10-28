// Scanner test page (scan_test.php): runs after app.js so the shared camera helpers exist.
window.addEventListener('load', function () {
  var T = window.VM_TEST, $ = function (s) { return document.querySelector(s); };
  var set = function (name, ok, text) {
    var li = document.querySelector('[data-check="' + name + '"]');
    li.querySelector('.ic').innerHTML = ok === null ? '…' : (ok ? '<i class="bi bi-check-circle-fill text-success"></i>' : '<i class="bi bi-x-circle-fill text-danger"></i>');
    li.querySelector('.res').textContent = text || (ok ? T.ok : T.bad);
    li.classList.toggle('list-group-item-danger', ok === false);
  };
  var esc = function (s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; };
  var out = function (cls, html) { $('#tOut').innerHTML = '<div class="alert alert-' + cls + '">' + html + '</div>'; };
  $('#tHere').textContent = location.href;

  set('version', window.VM_JS === T.server, window.VM_JS === T.server ? T.ok : T.oldFiles + ' (' + (window.VM_JS || '?') + ')');
  set('https', window.isSecureContext, window.isSecureContext ? location.protocol : T.noHttps);
  var api = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  set('api', api, api ? T.ok : T.noApi);
  var pol = document.permissionsPolicy || document.featurePolicy;
  var allowed = pol && pol.allowsFeature ? pol.allowsFeature('camera') : true;
  set('policy', allowed, allowed ? T.ok : T.blocked);
  set('lib', !!(window.VMScan && window.jsQR), window.jsQR ? T.ok : T.noLib);
  set('camera', null, T.press);

  var show = function (text) {
    var u = null;
    try { u = new URL(text, location.href); } catch (e) {}
    var att = u && /checkin\.php$/.test(u.pathname) && u.searchParams.get('k');
    var html = '<b>' + esc(T.read) + '</b><br><span class="text-break">' + esc(text) + '</span>';
    if (att) html += '<br>' + (u.host === location.host ? '✓ ' + esc(T.attOk) : '⚠ ' + esc(T.otherSite) + ' ' + esc(u.host));
    out(att && u.host === location.host ? 'success' : 'info', html);
  };
  var sc = null;
  $('#tStart').addEventListener('click', function () {
    if (!window.VMScan) return;
    sc = sc || window.vmNewScanner('reader');
    window.vmStartCamera(sc, 'environment', window.vmScanConfig, function (text) { show(text); })
      .then(function () { set('camera', true, T.camOk); })
      .catch(function (err) {
        var n = (err && err.name) || String(err);
        var msg = /NotAllowed|Permission/i.test(n + err) ? T.denied : /NotFound|Overconstrained/i.test(n + err) ? T.notFound
          : /NotReadable|TrackStart|Could not start/i.test(n + err) ? T.busy : T.other;
        set('camera', false, n);
        out('danger', esc(msg) + '<br><small class="text-break">' + esc(String(err)) + '</small>');
      });
  });
  if (window.vmPhotoScan && window.VMScan) {
    window.vmPhotoScan($('#tPhoto'), 'tPhotoReader', show, function () { out('warning', esc(T.noQr)); });
  }
});
