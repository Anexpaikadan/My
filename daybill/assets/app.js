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


// ---- Sheets: pages and options that slide up from the bottom, like a phone app ----------
//   <button data-sheet="#id">       opens <dialog class="sheet" id="id"> on this page
//   <a data-sheet-url="page.php">  opens that page inside a sheet (the page shows without its own bars)
// The sheets are shown by this code (open attribute + own dark backdrop), not by the browser's
// dialog.showModal(): that works the same on iPhone/iPad Safari (all versions), Android and PC.
(function () {
  var inFrame = window.self !== window.top;
  // A page opened inside a sheet that is not a sheet page (e.g. after "Open shop" or a new login): show it full screen.
  if (inFrame && !document.documentElement.classList.contains('in-sheet')) {
    try { window.top.location.href = location.href; } catch (e) {}
    return;
  }

  var stack = [], skipPop = 0, shade = null, lockY = 0, root = document.documentElement;

  // Dark layer behind the top sheet; tapping it closes that sheet.
  function paintShade() {
    if (!shade) {
      shade = document.createElement('div');
      shade.className = 'sheet-shade';
      document.body.appendChild(shade);
      shade.addEventListener('click', function () { if (stack.length) close(stack[stack.length - 1]); });
    }
    var top = stack[stack.length - 1];
    if (top) shade.style.zIndex = parseInt(top.style.zIndex, 10) - 1;
    shade.classList.toggle('on', !!top);
  }

  // The page behind must not scroll (iPhone ignores overflow:hidden on the page).
  function lock(on) {
    var b = document.body;
    if (on && !root.classList.contains('sheet-open')) {
      lockY = window.scrollY || window.pageYOffset || 0;
      root.classList.add('sheet-open');
      b.style.top = -lockY + 'px';
    } else if (!on && root.classList.contains('sheet-open')) {
      root.classList.remove('sheet-open');
      b.style.top = '';
      window.scrollTo(0, lockY);
    }
  }

  function open(d) {
    if (d.hasAttribute('open') && !d.classList.contains('out')) return;
    wire(d);
    clearTimeout(d._closing);
    d.style.zIndex = 1001 + stack.length * 2;
    d.classList.remove('out', 'in');
    d.setAttribute('open', '');
    d.getBoundingClientRect(); // start below the screen, then slide up
    requestAnimationFrame(function () { requestAnimationFrame(function () { d.classList.add('in'); }); });
    stack.push(d);
    paintShade();
    lock(true);
    try { history.pushState({ sheet: stack.length }, ''); } catch (e) {}
  }

  function close(d, fromBack) {
    if (!d || !d.hasAttribute('open') || d.classList.contains('out')) return;
    d.classList.remove('in'); d.classList.add('out');
    var i = stack.indexOf(d); if (i >= 0) stack.splice(i, 1);
    paintShade();
    if (!fromBack) { skipPop++; history.back(); }
    d._closing = setTimeout(function () {
      d.removeAttribute('open'); d.classList.remove('out'); d.style.transform = '';
      if (!stack.length) lock(false);
      d.dispatchEvent(new Event('sheetclosed'));
    }, 260);
  }

  window.addEventListener('popstate', function () {
    if (skipPop) { skipPop--; return; }
    if (stack.length) close(stack[stack.length - 1], true);
  });
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'Escape' || e.key === 'Esc') && stack.length) { e.preventDefault(); close(stack[stack.length - 1]); }
  });

  function wire(d) {
    if (d._wired) return; d._wired = true;
    d.addEventListener('cancel', function (e) { e.preventDefault(); close(d); });
    d.querySelectorAll('.sheet-x, [data-sheet-close]').forEach(function (b) {
      b.addEventListener('click', function (e) { e.preventDefault(); close(d); });
    });
    // Swipe the handle/title down to close
    var head = d.querySelector('.sheet-head'), y0 = null, dy = 0;
    if (head) {
      head.addEventListener('touchstart', function (e) { y0 = e.touches[0].clientY; dy = 0; d.style.transition = 'none'; }, { passive: true });
      head.addEventListener('touchmove', function (e) {
        if (y0 === null) return; dy = Math.max(0, e.touches[0].clientY - y0); d.style.transform = 'translateY(' + dy + 'px)';
      }, { passive: true });
      head.addEventListener('touchend', function () {
        d.style.transition = ''; if (dy > 90) close(d); else d.style.transform = ''; y0 = null;
      });
    }
  }

  // Sheet with another page inside (Settings pages)
  var frameSheet = null;
  function openUrl(url, title) {
    if (!frameSheet) {
      frameSheet = document.createElement('dialog');
      frameSheet.className = 'sheet sheet-frame';
      frameSheet.innerHTML = '<div class="sheet-head"><span class="grip"></span><b class="sheet-title"></b>' +
        '<button type="button" class="sheet-x" aria-label="Close">✕</button></div><div class="sheet-load"></div>' +
        '<div class="sheet-frame-box"><iframe title=""></iframe></div>';
      document.body.appendChild(frameSheet);
      var fr = frameSheet.querySelector('iframe');
      fr.addEventListener('load', function () {
        frameSheet.classList.add('loaded');
        frameSheet._loads = (frameSheet._loads || 0) + 1;
      });
      // Something was saved inside: refresh this page (e.g. the subtitles of the Settings menu).
      frameSheet.addEventListener('sheetclosed', function () {
        if (frameSheet._loads > 1) location.reload();
        fr.src = 'about:blank';
      });
    }
    frameSheet._loads = 0;
    frameSheet.classList.remove('loaded');
    frameSheet.querySelector('.sheet-title').textContent = title || '';
    frameSheet.querySelector('iframe').src = url + (url.indexOf('?') < 0 ? '?' : '&') + 'sheet=1';
    open(frameSheet);
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-sheet], [data-sheet-url]');
    if (!t) return;
    e.preventDefault();
    if (t.dataset.sheetUrl) return openUrl(t.dataset.sheetUrl, t.dataset.sheetTitle || t.textContent.trim());
    var d = document.querySelector(t.dataset.sheet);
    if (d) open(d);
  });

  window.DaybillSheet = { open: open, close: close, openUrl: openUrl };
})();


// Page-change animation: skip it on reloads and when a sheet is open; never report a skipped animation as an error.
(function () {
  function quiet(vt) { if (vt) { vt.ready.catch(function () {}); vt.finished.catch(function () {}); vt.updateCallbackDone && vt.updateCallbackDone.catch(function () {}); } }
  window.addEventListener('pageswap', function (e) {
    quiet(e.viewTransition);
    var nav = e.activation && e.activation.navigationType;
    if (e.viewTransition && (nav === 'reload' || document.querySelector('dialog[open]'))) e.viewTransition.skipTransition();
  });
  window.addEventListener('pagereveal', function (e) { quiet(e.viewTransition); });
})();
