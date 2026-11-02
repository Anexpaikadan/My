// Public home page: program and achievement pop-ups, achievements slider (swipe, arrows, dots, auto play).
(function () {
  var D = window.VM_HOME || { programs: [], ach: [], t: {} };
  var el = function (id) { return document.getElementById(id); };
  var modalEl = el('infoModal');
  if (!modalEl) return;
  var modal = new bootstrap.Modal(modalEl);
  var current = null;

  function row(icon, label, value) {
    if (!value) return '';
    var d = document.createElement('div');
    d.className = 'info-row';
    d.innerHTML = '<i class="bi ' + icon + '"></i><span><small></small><b></b></span>';
    d.querySelector('small').textContent = label;
    d.querySelector('b').textContent = value;
    return d.outerHTML;
  }
  function show(o) {
    var img = el('infoImg');
    img.style.backgroundImage = o.img ? 'url("' + o.img + '")' : '';
    img.classList.toggle('noimg', !o.img);
    el('infoKicker').textContent = o.kicker;
    el('infoName').textContent = o.name;
    el('infoShort').textContent = o.short || '';
    el('infoShort').classList.toggle('d-none', !o.short);
    el('infoRows').innerHTML = o.rows;
    el('infoDetails').textContent = o.details || '';
    el('infoTrial').classList.toggle('d-none', !o.program);
    current = o.program || null;
    modal.show();
  }
  var progs = {}, achs = {};
  D.programs.forEach(function (p) { progs[p.id] = p; });
  D.ach.forEach(function (a) { achs[a.id] = a; });

  document.querySelectorAll('[data-program]').forEach(function (b) {
    b.addEventListener('click', function () {
      var p = progs[b.dataset.program];
      if (!p) return;
      show({ img: p.img, kicker: D.t.program, name: p.name, short: p.short, details: p.details, program: p.name,
        rows: row('bi-people-fill', D.t.for, p.for) + row('bi-clock-fill', D.t.when, p.schedule)
          + row('bi-person-badge-fill', D.t.trainer, p.trainer + (p.trainerAbout ? ' – ' + p.trainerAbout : '')) });
    });
  });
  document.querySelectorAll('[data-ach]').forEach(function (b) {
    b.addEventListener('click', function () {
      var a = achs[b.dataset.ach];
      if (!a) return;
      show({ img: a.img, kicker: D.t.ach, name: a.title, short: a.name, details: a.details,
        rows: row('bi-trophy-fill', a.event ? '' : '', a.event) + row('bi-calendar-event', '', a.date) });
    });
  });
  // "Book your free trial" from a program: open the trial form with that program ticked.
  el('infoTrial').addEventListener('click', function () {
    var name = current;
    modalEl.addEventListener('hidden.bs.modal', function once() {
      modalEl.removeEventListener('hidden.bs.modal', once);
      document.querySelectorAll('#trial input[name=program]').forEach(function (r) { r.checked = r.value === name; });
      bootstrap.Modal.getOrCreateInstance(el('trialModal')).show();
    });
    modal.hide();
  });

  // Achievements slider
  var track = el('achTrack');
  if (!track) return;
  var cards = track.querySelectorAll('.ach-card'), dots = el('achDots'), timer = null;
  var step = function () { return cards.length ? cards[0].getBoundingClientRect().width + 12 : 0; };
  var index = function () { return Math.round(track.scrollLeft / (step() || 1)); };
  function go(i) {
    var max = cards.length - 1;
    if (i > max) i = 0;
    if (i < 0) i = max;
    track.scrollTo({ left: i * step(), behavior: 'smooth' });
  }
  if (cards.length > 1) {
    cards.forEach(function (_, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', String(i + 1));
      b.addEventListener('click', function () { go(i); restart(); });
      dots.appendChild(b);
    });
  } else {
    document.querySelectorAll('.ach-arrows').forEach(function (a) { a.classList.add('d-none'); });
  }
  function mark() {
    var i = index();
    dots.querySelectorAll('button').forEach(function (b, k) { b.classList.toggle('on', k === i); });
  }
  track.addEventListener('scroll', function () { window.requestAnimationFrame(mark); });
  mark();
  document.querySelectorAll('[data-ach-go]').forEach(function (b) {
    b.addEventListener('click', function () { go(index() + (+b.dataset.achGo)); restart(); });
  });
  function restart() {
    clearInterval(timer);
    if (cards.length > 1 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      timer = setInterval(function () { if (!document.hidden && !modalEl.classList.contains('show')) go(index() + 1); }, 4000);
    }
  }
  ['touchstart', 'mouseenter'].forEach(function (ev) { track.addEventListener(ev, function () { clearInterval(timer); }, { passive: true }); });
  ['touchend', 'mouseleave'].forEach(function (ev) { track.addEventListener(ev, restart, { passive: true }); });
  restart();
})();
