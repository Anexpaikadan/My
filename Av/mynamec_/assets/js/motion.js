/* Motion helpers for the club site (plain JS, no library).
   1. Scroll reveal: cards and headings that start below the screen fade and rise in,
      in a short cascade (60ms apart, max 6 steps) when they scroll into view.
   2. Dashboard numbers count up once.
   Does nothing when the phone asks for reduced motion. */
(function () {
  if (!('IntersectionObserver' in window)) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var SEL = '.h-sec,.pt-box,.pcard,.sl-card,.fee,.tm-row,.rule-box,.prod,.ct-box,.person,.nt,' +
            '.dtile,.tile-l,.eq-card,.ws-card,.stat,.card,.mk-card,.ev-card,.ach-card';
  var vh = window.innerHeight || 800;
  var els = [].slice.call(document.querySelectorAll(SEL)).filter(function (el) {
    if (el.closest('.modal,.overlay,.popup-ov,.rv')) return false;          // not inside pop-ups or already-animated parents
    var r = el.getBoundingClientRect();
    return r.top > vh * 0.92 && r.width > 0;                                   // only things not yet on screen
  });
  // cascade index per parent, so siblings arrive one after another
  var count = new Map();
  els.forEach(function (el) {
    var p = el.parentNode, i = count.get(p) || 0;
    el.style.setProperty('--i', Math.min(i, 5));
    count.set(p, i + 1);
    el.classList.add('rv');
  });
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add('in');
      io.unobserve(e.target);
      var t = e.target;
      setTimeout(function () { t.classList.remove('rv', 'in'); t.style.removeProperty('--i'); }, 1100); // hand back to normal hover/press styles
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  els.forEach(function (el) { io.observe(el); });

  // count up plain whole numbers on dashboard tiles (keeps ₹ and commas)
  [].forEach.call(document.querySelectorAll('.dtile .n'), function (n) {
    var txt = n.textContent.trim(), m = txt.match(/^([^\d]*)([\d,]+)([^\d]*)$/);
    if (!m) return;
    var end = parseInt(m[2].replace(/,/g, ''), 10);
    if (!end || end > 1000000) return;
    var start = null, dur = 700, fmt = function (v) { return m[1] + (m[2].indexOf(',') > -1 ? v.toLocaleString('en-IN') : v) + m[3]; };
    n.setAttribute('aria-label', txt);
    function step(ts) {
      if (start === null) start = ts;
      var k = Math.min(1, (ts - start) / dur), e = 1 - Math.pow(1 - k, 3);   // ease-out
      n.textContent = fmt(Math.round(end * e));
      if (k < 1) requestAnimationFrame(step); else n.textContent = txt;
    }
    n.textContent = fmt(0);
    requestAnimationFrame(step);
  });
})();
