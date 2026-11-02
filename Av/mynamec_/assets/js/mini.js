/* mini.js — tiny plain-JavaScript helper used by the public pages (replaces jQuery).
   Supports only what the login / register code needs:
   $(selector|element|array|fn), .val .hide .show .toggle .prop .attr .removeAttr .on .trigger
   .addClass .removeClass .toggleClass .hasClass .is(':visible'|':checked') .text .html .css .data
   .focus .each .offset .scrollTop .animate({scrollTop}) .toArray .length [i], $.ajax, $.map */
(function (w, d) {
  function W(list) { this.length = list.length; for (var i = 0; i < list.length; i++) this[i] = list[i]; }
  function $(sel) {
    if (typeof sel === 'function') { if (d.readyState !== 'loading') sel(); else d.addEventListener('DOMContentLoaded', sel); return; }
    if (sel instanceof W) return sel;
    if (!sel) return new W([]);
    if (typeof sel === 'string') { try { return new W(Array.prototype.slice.call(d.querySelectorAll(sel))); } catch (e) { return new W([]); } }
    if (sel === w || sel.nodeType) return new W([sel]);
    if (sel.length !== undefined) return new W(Array.prototype.slice.call(sel));
    return new W([sel]);
  }
  var P = W.prototype;
  P.each = function (fn) { for (var i = 0; i < this.length; i++) fn.call(this[i], i, this[i]); return this; };
  P.toArray = function () { return Array.prototype.slice.call(this); };
  P.val = function (v) { if (v === undefined) return this[0] ? this[0].value : undefined; return this.each(function () { this.value = v; }); };
  P.text = function (v) { if (v === undefined) return this[0] ? this[0].textContent : ''; return this.each(function () { this.textContent = v; }); };
  P.html = function (v) { if (v === undefined) return this[0] ? this[0].innerHTML : ''; return this.each(function () { this.innerHTML = v; }); };
  P.hide = function () { return this.each(function () { if (this.style.display !== 'none') this._d = this.style.display; this.style.display = 'none'; }); };
  P.show = function () { return this.each(function () { this.style.display = (this._d && this._d !== 'none') ? this._d : ''; if (getComputedStyle(this).display === 'none') this.style.display = 'block'; }); };
  P.toggle = function (on) { return this.each(function () { var vis = getComputedStyle(this).display !== 'none'; if (on === undefined ? vis : !on) $(this).hide(); else $(this).show(); }); };
  P.is = function (q) { var e = this[0]; if (!e) return false; if (q === ':visible') return !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length); if (q === ':checked') return !!e.checked; return e.matches ? e.matches(q) : false; };
  P.prop = function (k, v) { if (v === undefined) return this[0] ? this[0][k] : undefined; return this.each(function () { this[k] = v; }); };
  P.attr = function (k, v) {
    if (typeof k === 'object') { var o = k; return this.each(function () { for (var n in o) this.setAttribute(n, o[n]); }); }
    if (v === undefined) return this[0] ? this[0].getAttribute(k) : undefined; return this.each(function () { this.setAttribute(k, v); });
  };
  P.removeAttr = function (k) { return this.each(function () { this.removeAttribute(k); }); };
  P.data = function (k) { return this[0] ? this[0].getAttribute('data-' + k) : undefined; };
  P.css = function (k, v) { if (typeof k === 'object') { var o = k; return this.each(function () { for (var n in o) this.style[n] = o[n]; }); } return this.each(function () { this.style[k] = v; }); };
  function cls(m) { return function (c, on) { var list = String(c).split(/\s+/).filter(Boolean); return this.each(function () { var el = this; list.forEach(function (x) { if (m === 'toggle' && on !== undefined) el.classList.toggle(x, !!on); else el.classList[m](x); }); }); }; }
  P.addClass = cls('add'); P.removeClass = cls('remove'); P.toggleClass = cls('toggle');
  P.hasClass = function (c) { return !!(this[0] && this[0].classList.contains(c)); };
  P.on = function (ev, fn) { return this.each(function () { var el = this; ev.split(' ').forEach(function (e) { el.addEventListener(e, fn); }); }); };
  P.trigger = function (ev) { return this.each(function () { if (ev === 'focus' && this.focus) this.focus(); else this.dispatchEvent(new Event(ev, { bubbles: true })); }); };
  P.focus = function () { if (this[0] && this[0].focus) this[0].focus(); return this; };
  P.offset = function () { var e = this[0]; if (!e || e === w) return { top: 0, left: 0 }; var r = e.getBoundingClientRect(); return { top: r.top + w.pageYOffset, left: r.left + w.pageXOffset }; };
  P.scrollTop = function () { return w.pageYOffset || d.documentElement.scrollTop || 0; };
  P.animate = function (o) { if (o && o.scrollTop !== undefined) w.scrollTo({ top: o.scrollTop, behavior: 'smooth' }); return this; };
  $.map = function (arr, fn) { return Array.prototype.map.call(arr, fn); };
  $.ajax = function (o) {
    var body = new FormData(); var data = o.data || {};
    Object.keys(data).forEach(function (k) { body.append(k, data[k]); });
    fetch(o.url || location.pathname, { method: (o.method || o.type || 'POST').toUpperCase(), body: body, credentials: 'same-origin' })
      .then(function (r) { return o.dataType === 'json' ? r.json() : r.text(); })
      .then(function (res) { if (o.success) o.success(res); })
      .catch(function (e) { if (o.error) o.error(e); });
  };
  w.$ = w.jQuery = $;
})(window, document);
