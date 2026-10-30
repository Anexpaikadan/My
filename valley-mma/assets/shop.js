// Fight shop: category filter and the product pop-up (photo slideshow, price, WhatsApp enquiry).
(function () {
  var list = window.VM_SHOP || [], T = window.VM_SHOP_T || {};
  var modalEl = document.getElementById('productModal');
  if (!modalEl) return;
  var modal = new bootstrap.Modal(modalEl);
  var byId = {};
  list.forEach(function (p) { byId[p.id] = p; });
  var el = function (id) { return document.getElementById(id); };

  function open(id) {
    var p = byId[id];
    if (!p) return;
    el('pmName').textContent = p.name;
    el('pmPrice').innerHTML = p.price;
    el('pmCat').textContent = p.cat || '';
    el('pmDesc').textContent = p.desc || '';
    var st = el('pmStock');
    st.textContent = p.stock ? T.in : T.out;
    st.className = 'badge ms-auto ' + (p.stock ? 'bg-success' : 'bg-secondary');
    el('pmWa').href = p.wa;
    var slides = el('pmSlides'), dots = el('pmDots');
    slides.innerHTML = ''; dots.innerHTML = '';
    var imgs = p.imgs.length ? p.imgs : [null];
    imgs.forEach(function (src, i) {
      var item = document.createElement('div');
      item.className = 'carousel-item' + (i === 0 ? ' active' : '');
      item.innerHTML = src ? '<img class="d-block w-100 pm-img" alt="">' : '<div class="pm-img pm-noimg"><i class="bi bi-bag"></i></div>';
      if (src) item.querySelector('img').src = src;
      slides.appendChild(item);
      if (imgs.length > 1) {
        var b = document.createElement('button');
        b.type = 'button'; b.setAttribute('data-bs-target', '#pmCarousel'); b.setAttribute('data-bs-slide-to', i);
        b.setAttribute('aria-label', String(i + 1));
        if (i === 0) b.className = 'active';
        dots.appendChild(b);
      }
    });
    modalEl.querySelectorAll('.carousel-control-prev, .carousel-control-next').forEach(function (b) { b.classList.toggle('d-none', imgs.length < 2); });
    var c = bootstrap.Carousel.getInstance(el('pmCarousel'));
    if (c) c.to(0);
    if (history.replaceState) history.replaceState(null, '', '#p' + id);
    modal.show();
  }

  document.querySelectorAll('[data-product]').forEach(function (b) {
    b.addEventListener('click', function () { open(+b.dataset.product); });
  });
  modalEl.addEventListener('hidden.bs.modal', function () { if (history.replaceState) history.replaceState(null, '', location.pathname); });
  document.querySelectorAll('.shop-cats button').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.shop-cats button').forEach(function (x) { x.classList.toggle('on', x === b); });
      document.querySelectorAll('.shop-item').forEach(function (it) { it.classList.toggle('d-none', !!b.dataset.cat && it.dataset.cat !== b.dataset.cat); });
    });
  });
  var m = /^#p(\d+)$/.exec(location.hash);
  if (m) open(+m[1]);
})();
