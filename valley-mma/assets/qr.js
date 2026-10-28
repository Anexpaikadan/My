// Draws a QR code into every element with data-qr="text" (uses assets/vendor/qrcode.js).
window.drawQr = function (el, text) {
  var q = qrcode(0, 'M');
  q.addData(text);
  q.make();
  el.innerHTML = q.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
};
document.querySelectorAll('[data-qr]').forEach(function (el) {
  if (el.dataset.qr) window.drawQr(el, el.dataset.qr);
});
