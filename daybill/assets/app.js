// App behaviour shared by all pages: service worker, "Install app" buttons.
(function () {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(function () {});
  }

  var standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var deferred = null;

  function all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  function show(sel, on) { all(sel).forEach(function (el) { el.classList.toggle('hidden', !on); }); }

  function update() {
    show('[data-install]', !standalone && !!deferred);
    show('[data-install-ios]', !standalone && ios && !deferred);
    show('[data-installed]', standalone);
    show('[data-install-other]', !standalone && !ios && !deferred);
    // Cards that only hold an install box are shown when there is something to offer.
    all('.install-card').forEach(function (card) {
      card.classList.toggle('hidden', !card.querySelector('.install-box > :not(.hidden):not([data-installed])'));
    });
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault(); // show our own button instead of the mini-infobar
    deferred = e;
    update();
  });
  window.addEventListener('appinstalled', function () { deferred = null; standalone = true; update(); });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-install]');
    if (!btn || !deferred) return;
    deferred.prompt();
    deferred.userChoice.finally(function () { deferred = null; update(); });
  });

  document.addEventListener('DOMContentLoaded', update);
  if (document.readyState !== 'loading') update();
})();
