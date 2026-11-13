// Valley MMA – motion: scroll reveal, numbers that count up, loading bar, success vibration,
// confetti, progress rings and the dark mode switch. Everything is optional: pages work without it.
(function () {
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- Dark mode switch (admin and member app) ----
  function setTheme(dark) {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.documentElement.dataset.bsTheme = dark ? 'dark' : 'light';
    try { localStorage.setItem('vm_theme', dark ? 'dark' : 'light'); } catch (e) {}
    $$('[data-theme-toggle]').forEach(function (b) { if (b.type === 'checkbox') b.checked = dark; });
  }
  $$('[data-theme-toggle]').forEach(function (b) {
    if (b.type === 'checkbox') b.checked = document.documentElement.dataset.theme === 'dark';
    b.addEventListener(b.type === 'checkbox' ? 'change' : 'click', function () {
      setTheme(b.type === 'checkbox' ? b.checked : document.documentElement.dataset.theme !== 'dark');
    });
  });

  // ---- Loading bar while the next page opens ----
  var bar = document.createElement('div');
  bar.id = 'vmBar';
  document.body.appendChild(bar);
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || a.target === '_blank' || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#' || /^(tel:|mailto:|upi:|intent:|whatsapp:|javascript:)/i.test(href) || a.hasAttribute('download')) return;
    if (a.origin !== location.origin || (a.pathname === location.pathname && a.search === location.search && a.hash)) return;
    bar.classList.add('on');
  });
  document.addEventListener('submit', function (e) { if (!e.defaultPrevented && e.target.target !== '_blank') setTimeout(function () { if (!e.defaultPrevented) bar.classList.add('on'); }, 0); });
  window.addEventListener('pageshow', function () { bar.classList.remove('on'); });

  // ---- Progress rings (data-ring="0-100") ----
  $$('.ring[data-ring]').forEach(function (r) {
    var fg = r.querySelector('.ring-fg');
    var pct = Math.max(0, Math.min(100, parseFloat(r.dataset.ring) || 0));
    if (fg) setTimeout(function () { fg.style.strokeDashoffset = String(264 - 264 * pct / 100); }, calm ? 0 : 80);
  });

  if (calm) return;

  // ---- Reveal on scroll ----
  if ('IntersectionObserver' in window) {
    var vh = window.innerHeight;
    var items = $$('.main > .card, .main > .row > [class*="col"] > .card, .main-bare > .card, .tile, .quick, .stat, .pub-sec > .pub-h, .pub-ticks li, .prog-card, .pub-card, .pub-batch, .rule-sec, .shop-item, .ach-card, .ev-card, .pub-times, .batch-card')
      .filter(function (el) { return el.getBoundingClientRect().top > vh * 0.92 && el.tagName !== 'FORM' && !el.closest('.modal') && !el.closest('.collapse:not(.show)'); });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('rv-in'); io.unobserve(en.target); }
      });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.05 });
    items.forEach(function (el) {
      var sibs = el.parentNode ? Array.prototype.indexOf.call(el.parentNode.children, el) : 0;
      el.style.setProperty('--i', String(Math.min(sibs, 5)));
      el.classList.add('rv');
      if (el.classList.contains('pub-h')) el.classList.add('rv-left');
      io.observe(el);
    });
    // Never leave anything hidden (e.g. when printing or if the observer does not fire).
    setTimeout(function () { $$('.rv:not(.rv-in)').forEach(function (el) { if (el.getBoundingClientRect().top < window.innerHeight) el.classList.add('rv-in'); }); }, 1200);
    window.addEventListener('beforeprint', function () { $$('.rv').forEach(function (el) { el.classList.add('rv-in'); }); });
  }

  // ---- Numbers count up (dashboard tiles) ----
  $$('.stat .num, [data-count]').forEach(function (el) {
    if (el.children.length) return;
    var text = el.textContent.trim();
    var m = /^([^\d-]*)(-?[\d,]+(?:\.\d+)?)(.*)$/.exec(text);
    if (!m) return;
    var target = parseFloat(m[2].replace(/,/g, ''));
    if (!isFinite(target) || target === 0 || Math.abs(target) > 1e9) return;
    var dec = (m[2].split('.')[1] || '').length, start = null, dur = 700;
    var fmt = function (n) { return m[1] + n.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + m[3]; };
    el.textContent = fmt(0);
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / dur), eased = 1 - Math.pow(1 - p, 3);
      el.textContent = p >= 1 ? text : fmt(dec ? target * eased : Math.round(target * eased));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });

  // ---- Success: vibration and confetti ----
  if (document.querySelector('.checkin-big.text-success, .pop-in') && navigator.vibrate) {
    try { navigator.vibrate([60, 40, 90]); } catch (e) {}
  }
  if (document.querySelector('[data-confetti]')) {
    var colors = ['#C8160E', '#FFC107', '#198754', '#ffffff', '#0d6efd', '#E8261C'];
    for (var i = 0; i < 70; i++) {
      var c = document.createElement('span');
      c.className = 'vm-confetti';
      c.style.left = (Math.random() * 100) + 'vw';
      c.style.background = colors[i % colors.length];
      c.style.setProperty('--dx', (Math.random() * 160 - 80) + 'px');
      c.style.setProperty('--rot', (Math.random() * 900 - 450) + 'deg');
      c.style.setProperty('--t', (1.8 + Math.random() * 1.8) + 's');
      c.style.animationDelay = (Math.random() * 0.5) + 's';
      document.body.appendChild(c);
      (function (n) { setTimeout(function () { n.remove(); }, 4500); })(c);
    }
  }
})();
