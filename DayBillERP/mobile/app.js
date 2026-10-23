/* ==========================================================
   DayBill Mobile — one app, the modules your user may use:
   Goods In · Goods Out · Stock Count · Stock Adjust ·
   Product Info · Price Check · Van Sales ·
   Purchase Order · Barcode Labels · Offer Poster (v7.2) · Price Change (v7.3)
   Shop Wi-Fi: talks to DayBill on the shop PC (/api).
   Van: talks to your Hostinger relay (van_api.php) and works with
   no signal — bills wait on the phone and go when online.
   ========================================================== */
(() => {
"use strict";
const CFG = window.DAYBILL || { mode: "wifi", api: "/api" };
const RELAY = CFG.mode === "relay";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n2 = v => (Math.round((+v || 0) * 100) / 100).toFixed(2);
const nq = v => { const x = Math.round((+v || 0) * 1000) / 1000; return String(x); };
const LS = {
  get(k, d = null) { try { const v = localStorage.getItem("db_" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("db_" + k, JSON.stringify(v)); } catch (e) { toast("Phone storage is full", true); } },
  del(k) { try { localStorage.removeItem("db_" + k); } catch (e) {} }
};

/* ---------- small IndexedDB store (van catalog + bills survive restarts) ---------- */
const KV = {
  _db: null,
  open() {
    if (this._db) return Promise.resolve(this._db);
    return new Promise(res => {
      try {
        const r = indexedDB.open("daybill", 1);
        r.onupgradeneeded = () => r.result.createObjectStore("kv");
        r.onsuccess = () => { this._db = r.result; res(this._db); };
        r.onerror = () => res(null);
      } catch (e) { res(null); }
    });
  },
  async get(k, d = null) {
    const db = await this.open();
    if (!db) return LS.get("kv_" + k, d);
    return new Promise(res => {
      const q = db.transaction("kv").objectStore("kv").get(k);
      q.onsuccess = () => res(q.result === undefined ? d : q.result);
      q.onerror = () => res(d);
    });
  },
  async set(k, v) {
    const db = await this.open();
    if (!db) return LS.set("kv_" + k, v);
    return new Promise(res => {
      const tx = db.transaction("kv", "readwrite");
      tx.objectStore("kv").put(v, k);
      tx.oncomplete = () => res(true); tx.onerror = () => res(false);
    });
  }
};

/* ---------- words ---------- */
const WORDS = {
  ar: {
    "Sign in": "دخول", "User name": "اسم المستخدم", "Password": "كلمة المرور", "Device name": "اسم الجهاز",
    "Van code": "رمز السيارة", "PIN": "الرقم السري", "Sign out": "خروج", "Save": "حفظ", "Send": "إرسال",
    "Scan or type barcode / name": "امسح الباركود أو اكتب الاسم", "Items": "الأصناف", "Qty": "الكمية",
    "Supplier": "المورد", "Supplier invoice no.": "رقم فاتورة المورد", "Reason": "السبب", "Note": "ملاحظة",
    "Add": "إضافة", "Remove": "خصم", "Stock": "المخزون", "Price": "السعر", "Customer": "العميل",
    "Cash": "نقداً", "Card": "شبكة", "Credit": "آجل", "Total": "الإجمالي", "VAT": "الضريبة",
    "Sync now": "مزامنة الآن", "Bills": "الفواتير", "New bill": "فاتورة جديدة", "History": "السجل",
    "Waiting to send": "بانتظار الإرسال", "Clear": "مسح", "Back": "رجوع", "Print": "طباعة",
    "Cash customer": "عميل نقدي", "Today": "اليوم", "Unit": "الوحدة", "Barcode": "الباركود",
    "Today's list": "قائمة جرد اليوم", "to count today": "صنف للجرد اليوم", "left": "متبقي",
    "last counted": "آخر جرد", "never counted": "لم يُجرد", "Nothing to count today": "لا يوجد جرد اليوم",
    "The owner approves the count in DayBill before stock changes.": "يعتمد المالك الجرد في DayBill قبل تغيير المخزون.",
    "Deliver in (days)": "التوريد خلال (أيام)", "Low stock": "مخزون منخفض", "Orders": "الطلبات",
    "Label design": "تصميم الملصق", "Print now on the shop label printer": "اطبع الآن على طابعة الملصقات",
    "Each scan adds one label. Tap the number to type how many.": "كل مسح يضيف ملصقاً. اضغط الرقم لكتابة العدد.",
    "Headline (empty = automatic)": "العنوان (فارغ = تلقائي)", "From": "من", "To": "إلى", "Size": "المقاس",
    "Design": "التصميم", "Start this offer in POS and sales too": "فعّل العرض في نقطة البيع والمبيعات أيضاً",
    "Print now on the shop printer": "اطبع الآن على طابعة المحل", "Save purchase order": "حفظ أمر الشراء",
    "Print labels": "طباعة الملصقات", "Make poster": "إنشاء الملصق", "Open PDF": "فتح PDF",
    "Send to supplier on WhatsApp": "إرسال للمورد عبر واتساب", "Choose the supplier first": "اختر المورد أولاً",
    "Scan the first item": "امسح أول صنف", "labels": "ملصق", "cost": "التكلفة", "reorder at": "حد الطلب",
    "Add all": "إضافة الكل", "Save new prices": "حفظ الأسعار الجديدة", "Print new shelf labels": "طباعة ملصقات الرف الجديدة",
    "Allow below cost": "السماح بأقل من التكلفة", "tap to type": "اضغط للكتابة", "margin": "الهامش", "new prices": "أسعار جديدة",
    "New shelf price (with VAT) for": "سعر الرف الجديد (شامل الضريبة) لـ",
    "Type the new price of every item (tap the price)": "اكتب السعر الجديد لكل صنف (اضغط على السعر)",
    "Scan an item, then tap its price to type the new shelf price (with VAT). The number is how many labels.": "امسح الصنف ثم اضغط السعر لكتابة سعر الرف الجديد (شامل الضريبة). الرقم = عدد الملصقات.", "order": "اطلب", "Copy AI poster prompt (ChatGPT / Gemini)": "نسخ وصف الملصق للذكاء الاصطناعي"
  }
};
const L = () => LS.get("lang", "en");
const t = s => (WORDS[L()] && WORDS[L()][s]) || s;

/* ---------- state ---------- */
let S = LS.get("session", null);          // {token, user, modules, module_list, company, settings, van_code}
let current = { screen: null, onScan: null };
const ANDROID = () => window.DayBillAndroid || null;          // the DayBill Android app (APK)
const device = () => {
  let d = LS.get("device", "");
  if (!d) {
    try { d = ANDROID() ? ANDROID().deviceName() : ""; } catch (e) { d = ""; }
    d = d || ("Device-" + Math.random().toString(36).slice(2, 6).toUpperCase());
    LS.set("device", d);
  }
  return d;
};

function toast(msg, err = false, ms = 2600) {
  const el = $("#toast"); el.textContent = msg; el.className = "show" + (err ? " err" : "");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.className = "", ms);
  if (err) beep(220, 0.25);
}
let audio;
function beep(f = 1200, d = 0.07) {
  try {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    const o = audio.createOscillator(), g = audio.createGain();
    o.frequency.value = f; o.connect(g); g.connect(audio.destination); g.gain.value = 0.15;
    o.start(); o.stop(audio.currentTime + d);
  } catch (e) {}
  try { if (navigator.vibrate) navigator.vibrate(f < 500 ? [80, 60, 80] : 30); } catch (e) {}
}

/* ---------- API ---------- */
async function api(name, { params = null, body = null, timeout = 20000 } = {}) {
  let url = RELAY ? `${CFG.api}?a=${encodeURIComponent(name)}` : `${CFG.api}/${name}`;
  if (params) {
    const q = new URLSearchParams(params).toString();
    if (q) url += (url.includes("?") ? "&" : "?") + q;
  }
  // van relay: a fresh address every time, so no saved (cached) answer of the site can get in the way
  if (RELAY) url += (url.includes("?") ? "&" : "?") + "_=" + Date.now();
  const ctl = new AbortController(); const tm = setTimeout(() => ctl.abort(), timeout);
  const opt = { method: body ? "POST" : "GET", headers: {}, signal: ctl.signal, cache: "no-store" };
  if (S && S.token) opt.headers.Authorization = "Bearer " + S.token;
  if (body) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(url, opt); }
  catch (e) { const err = new Error(navigator.onLine === false ? "No signal / network" : "Can't reach DayBill — check Wi-Fi / server"); err.offline = true; throw err; }
  finally { clearTimeout(tm); }
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (r.status === 401 && name !== "login") { logout(true); throw new Error(j.error || "Please sign in again"); }
  if (!r.ok) throw new Error(j.error || ("Error " + r.status));
  return j;
}

/* ---------- send queue: nothing is lost when the network drops ---------- */
function queue() { return LS.get("queue", []); }
function sent() { return LS.get("sent", []); }
function addSent(rec) { const s = sent(); s.unshift(rec); LS.set("sent", s.slice(0, 80)); }
async function enqueue(doc) {
  const q = queue(); q.push({ doc, at: Date.now() }); LS.set("queue", q);
  return flush();
}
let flushing = false;
async function flush() {
  if (flushing || !S) return null;
  flushing = true; let last = null;
  try {
    let q = queue();
    while (q.length) {
      const it = q[0];
      try {
        const res = await api("submit", { body: { doc: it.doc, device: device() } });
        last = res;
        addSent({ uid: it.doc.uid, type: it.doc.type, title: it.doc.title || it.doc.type, status: res.status, result: res.result, at: Date.now() });
        await markVanBill(it.doc.uid, res);
      } catch (e) {
        if (e.offline) break;                    // try again later
        addSent({ uid: it.doc.uid, type: it.doc.type, title: it.doc.title || it.doc.type, status: "error", result: e.message, at: Date.now() });
        await markVanBill(it.doc.uid, { status: "error", result: e.message });
        last = { status: "error", result: e.message };
      }
      q = queue(); q.shift(); LS.set("queue", q);
    }
  } finally { flushing = false; paintQueue(); }
  return last;
}
function paintQueue() {
  const el = $("#qcount"); if (!el) return;
  const n = queue().length; el.textContent = n ? `⏳ ${n}` : "✓"; el.title = n ? t("Waiting to send") : "";
}
setInterval(() => { if (queue().length) flush(); }, 20000);
window.addEventListener("online", () => flush());

/* ---------- scanning: PDT keyboard wedge, Android app, camera ---------- */
// A PDT scanner "types" the code + Enter. When no box has the cursor (after a
// tap somewhere), the keys go into the scan box so no character is lost.
document.addEventListener("keydown", e => {
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return;   // the field handles it
  const box = $("#scan");
  if (!current.onScan || !box) return;
  if (e.key === "Enter") { e.preventDefault(); const v = box.value.trim(); box.value = ""; if (v) current.onScan(v); return; }
  if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) { e.preventDefault(); box.value += e.key; box.focus(); }
});
window.daybillScan = code => { if (current.onScan && code) current.onScan(String(code).trim()); };   // Android app / DataWedge
const canCamera = () => !!(window.DayBillAndroid && window.DayBillAndroid.scanCamera) ||
  (("BarcodeDetector" in window) && window.isSecureContext && navigator.mediaDevices);
async function camera() {
  if (window.DayBillAndroid && window.DayBillAndroid.scanCamera) { window.DayBillAndroid.scanCamera(); return; }
  if (!canCamera()) { toast("Camera scan: use the DayBill Android app or the PDT scan button", true); return; }
  const box = document.createElement("div"); box.className = "camera";
  box.innerHTML = `<video playsinline muted></video><button class="danger">✕ ${t("Back")}</button>`;
  document.body.appendChild(box);
  let stream, stop = false;
  const close = () => { stop = true; try { stream.getTracks().forEach(x => x.stop()); } catch (e) {} box.remove(); };
  box.querySelector("button").onclick = close;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    const v = box.querySelector("video"); v.srcObject = stream; await v.play();
    const det = new BarcodeDetector({ formats: ["ean_13", "ean_8", "code_128", "code_39", "upc_a", "upc_e", "qr_code", "itf"] });
    const loop = async () => {
      if (stop) return;
      try { const r = await det.detect(v); if (r.length) { close(); window.daybillScan(r[0].rawValue); return; } } catch (e) {}
      requestAnimationFrame(loop);
    };
    loop();
  } catch (e) { close(); toast("Camera: " + e.message, true); }
}

/* ---------- screens ---------- */
function shell(title, body, { back = true, sub = "" } = {}) {
  current.onScan = null; current.billUid = null;
  document.documentElement.dir = L() === "ar" ? "rtl" : "ltr";
  $("#app").innerHTML = `<div class="top">${back ? `<button id="back">‹</button>` : ""}
    <h1>${esc(title)}${sub ? `<span class="sub">${esc(sub)}</span>` : ""}</h1>
    <button id="qcount" title="">✓</button></div>${body}`;
  if (back) $("#back").onclick = () => home();
  $("#qcount").onclick = () => history();
  paintQueue();
}

/* login */
async function login() {
  current.onScan = null;
  document.documentElement.dir = L() === "ar" ? "rtl" : "ltr";
  let shop = "";
  try {
    const p = await api("ping"); shop = (p.shop || "") + (p.shop_ar ? " · " + p.shop_ar : "");
    if (p.problem) shop = "⚠ " + p.problem;
  }
  catch (e) { shop = RELAY && e.offline ? "" : "⚠ " + e.message; }
  $("#app").innerHTML = `<div class="login">
    <div class="logo"><b>DayBill</b><span class="muted">${RELAY ? "Van Sales" : "Mobile · PDT"}</span></div>
    <div class="shop">${esc(shop)}</div>
    <div class="card">
      ${RELAY ? `<label>${t("Van code")}</label><input id="u" autocapitalize="characters" value="${esc(LS.get("last_user", ""))}">
               <label>${t("PIN")}</label><input id="p" type="password" inputmode="numeric">`
              : `<label>${t("User name")}</label><input id="u" autocapitalize="off" value="${esc(LS.get("last_user", ""))}">
               <label>${t("Password")}</label><input id="p" type="password">`}
      <label>${t("Device name")}</label><input id="d" value="${esc(device())}">
      <div class="spacer"></div>
      <button class="primary" id="go" style="width:100%">${t("Sign in")}</button>
      <div class="spacer"></div>
      <div class="row"><button class="ghost" id="lang">${L() === "ar" ? "English" : "العربية"}</button></div>
    </div></div>`;
  $("#lang").onclick = () => { LS.set("lang", L() === "ar" ? "en" : "ar"); login(); };
  const go = async () => {
    const u = $("#u").value.trim(), p = $("#p").value;
    LS.set("device", $("#d").value.trim() || device()); LS.set("last_user", u);
    $("#go").disabled = true;
    try {
      const r = await api("login", { body: RELAY ? { van_code: u, pin: p, device: device() } : { username: u, password: p, device: device() } });
      S = r; LS.set("session", S);
      if (S.modules.length === 1) openModule(S.modules[0]); else home();
      flush();
    } catch (e) { toast(e.message, true); $("#go").disabled = false; }
  };
  $("#go").onclick = go; $("#p").onkeydown = e => { if (e.key === "Enter") go(); };
}
function logout(silent) {
  if (!silent && queue().length && !confirm("Documents are still waiting to send. Sign out anyway? (they stay on this phone)")) return;
  if (!silent) api("logout").catch(() => {});
  S = null; LS.del("session"); login();
}

/* home */
function home() {
  if (!S) return login();
  shell(S.company?.company_name_en || "DayBill", `<div class="wrap">
    <div class="muted" style="margin-bottom:10px">👤 ${esc(S.user)} · 📱 ${esc(device())}</div>
    <div class="tiles">${S.module_list.map(m => `<div class="tile" data-k="${m.key}"><span class="ic">${m.icon}</span>
      ${esc(L() === "ar" ? m.ar : m.en)}<small>${esc(L() === "ar" ? m.en : m.ar)}</small></div>`).join("")}
      <div class="tile" data-k="history"><span class="ic">🕘</span>${t("History")}<small>${queue().length ? queue().length + " ⏳" : ""}</small></div>
    </div>
    <div class="spacer"></div>
    <div class="row"><button id="lang">${L() === "ar" ? "English" : "العربية"}</button><button class="danger" id="out">${t("Sign out")}</button></div>
    ${ANDROID() ? `<div class="row" style="margin-top:8px"><button id="aset">⚙ Server</button><button id="aprn">🖨 Printer</button></div>` : ""}
  </div>`, { back: false, sub: S.user });
  if ($("#aset")) { $("#aset").onclick = () => ANDROID().openSettings(); $("#aprn").onclick = () => ANDROID().choosePrinter(); }
  $$(".tile").forEach(el => el.onclick = () => el.dataset.k === "history" ? history() : openModule(el.dataset.k));
  $("#out").onclick = () => logout();
  $("#lang").onclick = () => { LS.set("lang", L() === "ar" ? "en" : "ar"); home(); };
}
function openModule(k) {
  if (k === "info") return infoScreen(false);
  if (k === "price") return infoScreen(true);
  if (k === "van") return vanHome();
  if (JOBS[k]) return jobScreen(k);
  return scanList(k);
}

/* ---------- product lookup (Wi-Fi server, or the van's own catalog) ---------- */
async function lookup(code) {
  if (RELAY) return localLookup(code);
  return api("resolve", { params: { code } });       // always the live stock
}

/* ---------- Goods In / Goods Out / Stock Count / Stock Adjust ---------- */
const LISTS = {
  goods_in: { title: "Goods In", ar: "استلام بضاعة", btn: "Send to DayBill (draft purchase)" },
  goods_out: { title: "Goods Out", ar: "إخراج بضاعة", btn: "Take out of stock" },
  count: { title: "Stock Count", ar: "جرد", btn: "Save count" },
  adjust: { title: "Stock Adjust", ar: "تسوية", btn: "Save adjustment" }
};
function scanList(k) {
  const cfg = LISTS[k];
  let D = LS.get("draft_" + k, null) || { lines: [], header: {}, mode: "+", askQty: false };
  const save = () => LS.set("draft_" + k, D);
  const hdr = {
    goods_in: `<div class="card"><label>${t("Supplier")}</label>
      <button id="sup" style="width:100%;text-align:start">${esc(D.header.supplier_name || "Choose supplier…")}</button>
      <label>${t("Supplier invoice no.")}</label><input id="supinv" value="${esc(D.header.supplier_invoice || "")}"></div>`,
    goods_out: `<div class="card"><label>${t("Reason")}</label><select id="reason">${(S.settings.out_reasons || ["Damaged"]).map(r =>
      `<option ${D.header.reason === r ? "selected" : ""}>${esc(r)}</option>`).join("")}</select></div>`,
    count: `<div class="card"><div class="seg"><button data-a="0" class="${D.askQty ? "" : "on"}">Each scan +1</button>
      <button data-a="1" class="${D.askQty ? "on" : ""}">Scan + type qty</button></div>
      <div class="muted" style="margin-top:6px">The counted quantity REPLACES the stock of each product counted.</div>
      <button id="plan" style="width:100%;margin-top:8px">📋 ${t("Today's list")}</button></div>`,
    adjust: `<div class="card"><div class="seg"><button data-m="+" class="green ${D.mode === "+" ? "on" : ""}">➕ ${t("Add")}</button>
      <button data-m="-" class="red ${D.mode === "-" ? "on" : ""}">➖ ${t("Remove")}</button></div>
      <label>${t("Note")}</label><input id="note" value="${esc(D.header.note || "")}"></div>`
  }[k];
  shell(L() === "ar" ? cfg.ar : t(cfg.title), `<div class="wrap">
    <div class="scan"><input id="scan" placeholder="${t("Scan or type barcode / name")}" autocomplete="off" enterkeyhint="go">
      ${canCamera() ? `<button id="cam">📷</button>` : ""}</div>
    <div id="hit"></div>${hdr}<ul class="lines" id="lines"></ul><div class="spacer"></div></div>
    <div class="bottom"><div class="tot" id="tot"></div><button class="danger" id="clr">${t("Clear")}</button>
      <button class="primary" id="send">${t("Send")}</button></div>`);
  const scanEl = $("#scan");
  const focus = () => setTimeout(() => { if (document.activeElement?.tagName !== "INPUT" || document.activeElement === scanEl) scanEl.focus(); }, 30);
  if ($("#cam")) $("#cam").onclick = camera;
  if ($("#sup")) $("#sup").onclick = () => pickSupplier(s => { D.header.supplier_id = s.supplier_id; D.header.supplier_name = s.supplier_name_en; save(); $("#sup").textContent = s.supplier_name_en; });
  if ($("#supinv")) $("#supinv").oninput = e => { D.header.supplier_invoice = e.target.value; save(); };
  if ($("#reason")) { D.header.reason = $("#reason").value; $("#reason").onchange = e => { D.header.reason = e.target.value; save(); }; }
  if ($("#note")) $("#note").oninput = e => { D.header.note = e.target.value; save(); };
  $$(".seg button[data-m]").forEach(b => b.onclick = () => { D.mode = b.dataset.m; save(); scanList(k); });
  $$(".seg button[data-a]").forEach(b => b.onclick = () => { D.askQty = b.dataset.a === "1"; save(); scanList(k); });
  if ($("#plan")) $("#plan").onclick = () => countPlan(D);

  const paint = flashKey => {
    const ul = $("#lines");
    if (!D.lines.length) { ul.innerHTML = `<div class="empty">📦 Scan the first item</div>`; }
    else ul.innerHTML = D.lines.map((l, i) => `<li class="ln ${l.key === flashKey ? "flash" : ""}" data-i="${i}">
      ${k === "adjust" ? `<span class="sign ${l.sign < 0 ? "minus" : "plus"}">${l.sign < 0 ? "−" : "+"}</span>` : ""}
      <div class="info"><div class="nm">${esc(l.name)}</div>
        <span class="unit" data-u="${i}">${esc(l.unit)}${l.factor !== 1 ? " ×" + nq(l.factor) : ""} ▾</span>
        ${k === "goods_in" ? ` <span class="muted" data-c="${i}">cost ${n2(l.cost)} ✎</span>` : ""}</div>
      <div class="qty"><button data-d="-1" data-i="${i}">−</button><input data-q="${i}" inputmode="decimal" value="${nq(l.qty)}">
        <button data-d="1" data-i="${i}">+</button></div></li>`).join("");
    const pieces = D.lines.reduce((a, l) => a + l.qty * l.factor * (l.sign || 1), 0);
    $("#tot").innerHTML = `${D.lines.length} ${t("Items")}<small>${nq(pieces)} pcs</small>`;
    $$("button[data-d]", ul).forEach(b => b.onclick = () => { const l = D.lines[+b.dataset.i]; l.qty = Math.max(0, l.qty + (+b.dataset.d)); if (!l.qty) D.lines.splice(+b.dataset.i, 1); save(); paint(); focus(); });
    $$("input[data-q]", ul).forEach(inp => { inp.onchange = () => { const l = D.lines[+inp.dataset.q]; l.qty = Math.max(0, parseFloat(inp.value) || 0); if (!l.qty) D.lines.splice(+inp.dataset.q, 1); save(); paint(); focus(); };
      inp.onkeydown = e => { if (e.key === "Enter") { inp.blur(); } }; });
    $$("[data-u]", ul).forEach(s => s.onclick = () => { const l = D.lines[+s.dataset.u]; if (!l.units || l.units.length < 2) return;
      const j = (l.units.findIndex(u => u.unit_id === l.unit_id) + 1) % l.units.length; const u = l.units[j];
      l.unit_id = u.unit_id; l.unit = u.unit; l.factor = u.factor; if (u.cost != null) l.cost = u.cost; l.key = l.product_id + "-" + u.unit_id + (l.sign < 0 ? "m" : ""); save(); paint(); });
    $$("[data-c]", ul).forEach(s => s.onclick = () => { const l = D.lines[+s.dataset.c]; const v = prompt("Cost per " + l.unit, n2(l.cost)); if (v != null) { l.cost = parseFloat(v) || 0; save(); paint(); } });
  };
  current.onScan = async code => {
    scanEl.value = "";
    let c;
    try { c = await lookup(code); }
    catch (e) {
      if (!e.offline) {          // maybe a name: show matches
        try { const r = await api("search", { params: { q: code } }); if (r.items.length) return pickProduct(r.items, it => current.onScan(it.code)); } catch (x) {}
      }
      $("#hit").innerHTML = `<div class="card miss">✖ ${esc(e.message)}</div>`; beep(220, .3); return;
    }
    const u = c.units.find(x => x.unit_id === c.scanned_unit_id) || c.units[0] || { unit: "PCs", factor: 1 };
    const sign = k === "adjust" && D.mode === "-" ? -1 : 1;
    const key = c.product_id + "-" + u.unit_id + (sign < 0 ? "m" : "");
    let l = D.lines.find(x => x.key === key);
    const add = c.via === "scale" ? (c.scan_qty || 1) : 1;
    if (l) l.qty += add;
    else { l = { key, product_id: c.product_id, name: c.name, unit_id: u.unit_id, unit: u.unit, factor: u.factor, qty: add, sign,
      cost: u.cost != null ? u.cost : null, units: c.units.map(x => ({ unit_id: x.unit_id, unit: x.unit, factor: x.factor, cost: x.cost })) };
      D.lines.unshift(l); }
    save();
    $("#hit").innerHTML = `<div class="card hit"><div class="nm">${esc(c.name)}</div><div class="muted">${esc(u.unit)} · ${t("Stock")} ${esc(c.stock_text)}</div></div>`;
    beep(); paint(key);
    if (D.askQty) { const inp = $(`input[data-q="${D.lines.indexOf(l)}"]`); if (inp) { inp.focus(); inp.select(); } }
  };
  scanEl.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); const v = scanEl.value.trim(); if (v) current.onScan(v); } };
  $("#clr").onclick = () => { if (D.lines.length && !confirm("Clear the whole list?")) return; D = { lines: [], header: D.header, mode: D.mode, askQty: D.askQty }; save(); paint(); focus(); };
  $("#send").onclick = async () => {
    if (!D.lines.length) return toast("The list is empty", true);
    if (k === "goods_in" && !D.header.supplier_id && !confirm("No supplier chosen — send for the cash supplier?")) return;
    $("#send").disabled = true;
    const doc = { uid: device() + "-" + k + "-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6), type: k,
      title: cfg.title, header: D.header,
      lines: D.lines.map(l => ({ product_id: l.product_id, unit_id: l.unit_id, unit: l.unit, factor: l.factor, qty: l.qty, cost: l.cost, sign: l.sign })) };
    const res = await enqueue(doc);
    $("#send").disabled = false;
    if (res && res.status !== "error") {
      toast("✔ " + (res.result || "Sent"), false, 4000);
      D = { lines: [], header: k === "goods_out" ? { reason: D.header.reason } : {}, mode: D.mode, askQty: D.askQty }; save(); scanList(k);
    } else if (res && res.status === "error") toast(res.result, true, 5000);
    else { toast("No connection — saved on this device, it will send by itself", false, 4000);
      D = { lines: [], header: {}, mode: D.mode, askQty: D.askQty }; save(); scanList(k); }
  };
  paint(); focus();
}

/* v6.4: today's cycle-count list (A weekly, B monthly, C quarterly) */
async function countPlan(D) {
  let r;
  try { r = await api("count_plan"); } catch (e) { return toast(e.message, true); }
  const done = new Set((D.lines || []).map(l => l.product_id));
  const left = r.items.filter(it => !done.has(it.product_id)).length;
  sheet(`<div class="muted" style="margin-bottom:6px">${r.items.length} ${t("to count today")} · ${left} ${t("left")}
    ${r.approval ? "<br>" + t("The owner approves the count in DayBill before stock changes.") : ""}</div>` +
    (r.items.map(it => `<div class="item"><div class="grow"><b>${done.has(it.product_id) ? "✓ " : ""}${esc(it.name)}</b>
      <div class="muted">${esc(it.code || "")} · ${it.last_counted ? t("last counted") + " " + esc(it.last_counted) : t("never counted")}</div></div>
      <span class="badge ${it.class === "A" ? "red" : it.class === "B" ? "amber" : ""}">${esc(it.class)}</span></div>`).join("")
     || `<div class="empty">✔ ${t("Nothing to count today")}</div>`));
}

function sheet(html) {
  const p = document.createElement("div"); p.className = "pick";
  p.innerHTML = `<div class="sheet">${html}<button style="width:100%" class="danger" data-x>✕ ${t("Back")}</button></div>`;
  p.onclick = e => { if (e.target === p || e.target.hasAttribute("data-x")) p.remove(); };
  document.body.appendChild(p); return p;
}
function pickSupplier(cb) {
  const p = sheet(`<input id="sq" placeholder="Search supplier"><div id="sl" style="margin-top:8px"></div>`);
  const load = async () => {
    try { const r = await api("suppliers", { params: { q: $("#sq", p).value } });
      $("#sl", p).innerHTML = r.items.map((s, i) => `<div class="item" data-i="${i}"><div class="grow"><b>${esc(s.supplier_name_en)}</b><div class="muted">${esc(s.supplier_code)}</div></div></div>`).join("") || `<div class="empty">—</div>`;
      $$(".item", p).forEach(el => el.onclick = () => { cb(r.items[+el.dataset.i]); p.remove(); });
    } catch (e) { toast(e.message, true); }
  };
  $("#sq", p).oninput = () => { clearTimeout(load.t); load.t = setTimeout(load, 250); };
  load(); $("#sq", p).focus();
}
function pickProduct(items, cb) {
  const p = sheet(items.map((it, i) => `<div class="item" data-i="${i}"><div class="grow"><b>${esc(it.name)}</b>
    <div class="muted">${esc(it.code || "")} ${it.name_ar ? "· " + esc(it.name_ar) : ""}</div></div><span class="badge">${nq(it.stock ?? "")}</span></div>`).join(""));
  $$(".item", p).forEach(el => el.onclick = () => { p.remove(); cb(items[+el.dataset.i]); });
}

/* ---------- Product Info / Price Check ---------- */
function infoScreen(priceOnly) {
  shell(priceOnly ? t("Price") + " ✓" : "Product Info", `<div class="wrap">
    <div class="scan"><input id="scan" placeholder="${t("Scan or type barcode / name")}" autocomplete="off">
    ${canCamera() ? `<button id="cam">📷</button>` : ""}</div><div id="out"><div class="empty">🔎 Scan any barcode</div></div></div>`);
  if ($("#cam")) $("#cam").onclick = camera;
  const scanEl = $("#scan");
  current.onScan = async code => {
    scanEl.value = "";
    try {
      const c = await lookup(code);
      const u = c.units.find(x => x.unit_id === c.scanned_unit_id) || c.units[0] || {};
      beep();
      $("#out").innerHTML = `<div class="card hit"><div class="nm">${esc(c.name)}</div><div class="muted">${esc(c.name_ar)}</div>
        <div class="big">${esc(S.settings?.currency || "SAR")} ${n2(u.price_vat)}</div>
        <div>per <b>${esc(u.unit)}</b>${u.factor !== 1 ? ` (${nq(u.factor)} pcs)` : ""} · incl. VAT ${nq(c.vat_rate)}%</div>
        ${u.offer ? `<div style="margin-top:6px"><span class="badge red">🏷 ${esc(u.offer)}</span> <s class="muted">${n2(u.normal_price_vat)}</s></div>` : ""}</div>
        ${priceOnly ? "" : `<div class="card"><div class="kv"><b>Code</b><span>${esc(c.code)}</span><b>${t("Stock")}</b><span><b>${nq(c.stock)}</b> = ${esc(c.stock_text)}</span>
          <b>Category</b><span>${esc(c.category)}</span>${c.location ? `<b>Location</b><span>${esc(c.location)}</span>` : ""}
          ${c.last_purchase ? `<b>Last buy</b><span>${esc((c.last_purchase.invoice_date || "").slice(0, 10))} · ${esc(c.last_purchase.supplier_name_en)} · ${n2(c.last_purchase.unit_price)}/${esc(c.last_purchase.unit_of_measure_en)}</span>` : ""}
          ${c.reorder_level ? `<b>Reorder at</b><span>${nq(c.reorder_level)} ${c.stock <= c.reorder_level ? '<span class="badge red">LOW</span>' : ""}</span>` : ""}</div></div>`}
        <div class="card"><table class="units"><tr><th>${t("Unit")}</th><th>${t("Price")}</th>${priceOnly ? "" : `<th>${t("Stock")}</th>`}<th>${t("Barcode")}</th></tr>
          ${c.units.map(x => `<tr class="${x.unit_id === u.unit_id ? "sel" : ""}"><td>${esc(x.unit)}${x.factor !== 1 ? " ×" + nq(x.factor) : ""}</td>
            <td>${n2(x.price_vat)}</td>${priceOnly ? "" : `<td>${nq(x.stock_in_unit)}</td>`}<td>${esc(x.barcode)}${x.extra_barcodes?.length ? `<div class="muted">${x.extra_barcodes.map(esc).join("<br>")}</div>` : ""}</td></tr>`).join("")}</table></div>`;
    } catch (e) {
      $("#out").innerHTML = `<div class="card miss">✖ ${esc(e.message)}</div>`; beep(220, .3);
    }
  };
  scanEl.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); const v = scanEl.value.trim(); if (v) current.onScan(v); } };
  setTimeout(() => scanEl.focus(), 50);
}

/* ==========================================================
   v7.2 — Purchase Order · Barcode Labels · Offer Poster
   Scan items on the PDT; DayBill on the PC saves the order,
   prints the labels on the label printer or draws the poster.
   ========================================================== */
const JOBS = {
  po: { title: "Purchase Order", ar: "أمر شراء", btn: "Save purchase order" },
  labels: { title: "Barcode Labels", ar: "طباعة الباركود", btn: "Print labels" },
  poster: { title: "Offer Poster", ar: "ملصق العروض", btn: "Make poster" },
  price_change: { title: "Price Change", ar: "تغيير السعر", btn: "Save new prices" }
};
const pdfUrl = docId => `${CFG.api}/file?doc=${encodeURIComponent(docId)}&t=${encodeURIComponent(S.token)}`;
const today = (d = 0) => { const x = new Date(Date.now() + d * 864e5); return x.toISOString().slice(0, 10); };
function jobScreen(k) {
  if (RELAY) return toast("This works on the shop Wi-Fi only", true);
  const cfg = JOBS[k];
  const fresh = () => ({ lines: [], header: k === "po" ? { expected_days: 7 } : k === "labels" ? { print: true } :
    k === "price_change" ? { reason: (S.settings?.price_reasons || ["Other"])[0], print_labels: true, print: true, allow_below_cost: false } :
    { offer_type: "percent", value: 10, start: today(), end: today(7), size: "a4", theme: "sale", create_offer: true, print: false } });
  let D = LS.get("draft_" + k, null) || fresh();
  const save = () => LS.set("draft_" + k, D);
  const H = D.header;
  const hdr = {
    po: `<div class="card"><label>${t("Supplier")}</label>
      <button id="sup" style="width:100%;text-align:start">${esc(H.supplier_name || "Choose supplier…")}</button>
      <div class="row"><div><label>${t("Deliver in (days)")}</label><input id="days" inputmode="numeric" value="${esc(H.expected_days ?? 7)}"></div>
        <div><label>${t("Note")}</label><input id="note" value="${esc(H.note || "")}"></div></div>
      <div class="row" style="margin-top:8px"><button id="low">⚠ ${t("Low stock")}</button><button id="mine">📋 ${t("Orders")}</button></div></div>`,
    labels: `<div class="card"><label>${t("Label design")}</label><select id="tpl"><option value="">…</option></select>
      <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="prn" style="width:auto;min-height:0" ${H.print ? "checked" : ""}>
        ${t("Print now on the shop label printer")}</label>
      <div class="muted">${t("Each scan adds one label. Tap the number to type how many.")}</div></div>`,
    poster: `<div class="card"><div class="seg" id="otype">${[["percent", "% off"], ["price", "New price"], ["amount", "− Amount"], ["buy_get", "Buy X get Y"], ["none", "Price only"]]
        .map(([v, n]) => `<button data-o="${v}" class="${H.offer_type === v ? "on" : ""}">${t(n)}</button>`).join("")}</div>
      <div class="row" id="vals"></div>
      <label>${t("Headline (empty = automatic)")}</label><input id="head" value="${esc(H.headline || "")}" placeholder="e.g. WEEKEND SALE">
      <input id="head_ar" dir="rtl" style="margin-top:6px" value="${esc(H.headline_ar || "")}" placeholder="العنوان بالعربي (اختياري)">
      <div class="row"><div><label>${t("From")}</label><input type="date" id="st" value="${esc(H.start)}"></div>
        <div><label>${t("To")}</label><input type="date" id="en" value="${esc(H.end)}"></div></div>
      <div class="row"><div><label>${t("Size")}</label><select id="size"></select></div><div><label>${t("Design")}</label><select id="theme"></select></div></div>
      <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="mko" style="width:auto;min-height:0" ${H.create_offer ? "checked" : ""}>
        ${t("Start this offer in POS and sales too")}</label>
      <label style="display:flex;gap:8px;align-items:center;margin-top:4px"><input type="checkbox" id="prn" style="width:auto;min-height:0" ${H.print ? "checked" : ""}>
        ${t("Print now on the shop printer")}</label></div>`,
    price_change: `<div class="card"><label>${t("Reason")}</label><select id="why">${(S.settings?.price_reasons || ["Other"]).map(r =>
        `<option ${H.reason === r ? "selected" : ""}>${esc(r)}</option>`).join("")}</select>
      <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="pl" style="width:auto;min-height:0" ${H.print_labels ? "checked" : ""}>
        ${t("Print new shelf labels")}</label>
      <select id="tpl" style="margin-top:4px"><option value="">…</option></select>
      <label style="display:flex;gap:8px;align-items:center;margin-top:4px"><input type="checkbox" id="low" style="width:auto;min-height:0" ${H.allow_below_cost ? "checked" : ""}>
        ${t("Allow below cost")}</label>
      <div class="muted">${t("Scan an item, then tap its price to type the new shelf price (with VAT). The number is how many labels.")}</div></div>`
  }[k];
  shell(L() === "ar" ? cfg.ar : t(cfg.title), `<div class="wrap">
    <div class="scan"><input id="scan" placeholder="${t("Scan or type barcode / name")}" autocomplete="off" enterkeyhint="go">
      ${canCamera() ? `<button id="cam">📷</button>` : ""}</div>
    <div id="hit"></div>${hdr}<ul class="lines" id="lines"></ul><div class="spacer"></div></div>
    <div class="bottom"><div class="tot" id="tot"></div><button class="danger" id="clr">${t("Clear")}</button>
      <button class="primary" id="send">${t(cfg.btn)}</button></div>`);
  const scanEl = $("#scan");
  const focus = () => setTimeout(() => { if (document.activeElement?.tagName !== "INPUT" || document.activeElement === scanEl) scanEl.focus(); }, 30);
  if ($("#cam")) $("#cam").onclick = camera;
  const bind = (id, key, num) => { const el = $("#" + id); if (el) el.oninput = el.onchange = () => { H[key] = el.type === "checkbox" ? el.checked : (num ? parseFloat(el.value) || 0 : el.value); save(); if (k === "poster") paint(); }; };
  if (k === "po") {
    $("#sup").onclick = () => pickSupplier(s => { H.supplier_id = s.supplier_id; H.supplier_name = s.supplier_name_en; save(); $("#sup").textContent = s.supplier_name_en; });
    bind("days", "expected_days", true); bind("note", "note");
    $("#low").onclick = async () => {
      let r; try { r = await api("po_suggest", { params: H.supplier_id ? { supplier_id: H.supplier_id } : {} }); } catch (e) { return toast(e.message, true); }
      if (!r.items.length) return toast(t("Nothing is below its reorder level"));
      const p = sheet(`<div class="muted" style="margin-bottom:6px">${t("Low stock")} — ${t("tap to add, or add all")}</div>
        <button class="primary" id="all" style="width:100%;margin-bottom:8px">＋ ${t("Add all")} (${r.items.length})</button>` +
        r.items.map((it, i) => `<div class="item" data-i="${i}"><div class="grow"><b>${it.from_supplier ? "★ " : ""}${esc(it.name)}</b>
          <div class="muted">${t("Stock")} ${nq(it.stock)} / ${t("reorder at")} ${nq(it.reorder_level)} · ${t("order")} ${nq(it.qty)}</div></div></div>`).join(""));
      const add = it => { if (!D.lines.find(l => l.product_id === it.product_id))
        D.lines.push({ key: it.product_id + "-0", product_id: it.product_id, name: it.name, unit_id: null, unit: "", factor: 1, qty: it.qty, cost: it.cost, units: [] }); };
      $("#all", p).onclick = () => { r.items.forEach(add); save(); p.remove(); paint(); };
      $$(".item", p).forEach(el => el.onclick = () => { add(r.items[+el.dataset.i]); save(); el.style.opacity = .4; paint(); });
    };
    $("#mine").onclick = async () => {
      let r; try { r = await api("po_list"); } catch (e) { return toast(e.message, true); }
      sheet(r.items.map(o => `<div class="item"><div class="grow"><b>${esc(o.po_number)}</b><div class="muted">${esc(String(o.po_date || "").slice(0, 10))} · ${esc(o.supplier_name_en)}</div></div>
        <div class="right"><b>${n2(o.total_amount)}</b><br><span class="badge ${o.status === "open" ? "amber" : "green"}">${esc(o.status)}</span></div></div>`).join("") || `<div class="empty">—</div>`);
    };
  }
  if (k === "price_change") {
    $("#why").onchange = () => { H.reason = $("#why").value; save(); };
    bind("pl", "print_labels"); bind("low", "allow_below_cost");
  }
  if (k === "labels" || k === "price_change") {
    api("label_designs").then(r => {
      const sel = $("#tpl"); if (!sel) return;
      sel.innerHTML = r.items.map(x => `<option value="${x.id}">${esc(x.name)} · ${esc(x.size)}${x.default ? " ★" : ""}</option>`).join("") || `<option value="">(no design — make one in DayBill)</option>`;
      if (!H.template_id || !r.items.find(x => String(x.id) === String(H.template_id))) H.template_id = (r.items.find(x => x.default) || r.items[0] || {}).id || "";
      sel.value = H.template_id; save();
      sel.onchange = () => { H.template_id = sel.value; save(); };
    }).catch(e => toast(e.message, true));
    if (k === "labels") bind("prn", "print");
  }
  if (k === "poster") {
    const vals = () => {
      const o = H.offer_type;
      $("#vals").innerHTML = o === "percent" || o === "amount" ? `<div><label>${o === "percent" ? "% " + t("off") : t("Amount off")}</label><input id="val" inputmode="decimal" value="${esc(H.value ?? "")}"></div>`
        : o === "buy_get" ? `<div><label>${t("Buy")}</label><input id="buy" inputmode="numeric" value="${esc(H.buy_qty ?? 2)}"></div><div><label>${t("Get free")}</label><input id="get" inputmode="numeric" value="${esc(H.get_qty ?? 1)}"></div>`
        : o === "price" ? `<div class="muted" style="margin-top:8px">${t("Tap a product's price to type its offer price.")}</div>` : "";
      bind("val", "value", true); bind("buy", "buy_qty", true); bind("get", "get_qty", true);
    };
    $$("#otype button").forEach(b => b.onclick = () => { H.offer_type = b.dataset.o; if (H.offer_type === "buy_get") { H.buy_qty = H.buy_qty || 2; H.get_qty = H.get_qty || 1; }
      save(); $$("#otype button").forEach(x => x.classList.toggle("on", x === b)); vals(); paint(); });
    vals();
    ["head:headline", "head_ar:headline_ar", "st:start", "en:end", "mko:create_offer", "prn:print"].forEach(p => { const [id, key] = p.split(":"); bind(id, key); });
    api("poster_options").then(r => {
      $("#size").innerHTML = r.sizes.map(x => `<option value="${x.key}">${esc(x.name)}</option>`).join("");
      $("#theme").innerHTML = r.themes.map(x => `<option value="${x.key}">${esc(x.name)}</option>`).join("");
      $("#size").value = H.size || "a4"; $("#theme").value = H.theme || "sale";
      bind("size", "size"); bind("theme", "theme");
    }).catch(e => toast(e.message, true));
  }
  const newPrice = l => {
    const o = H.offer_type, p = +l.price || 0;
    if (o === "percent") return Math.max(0, p * (1 - (+H.value || 0) / 100));
    if (o === "amount") return Math.max(0, p - (+H.value || 0));
    if (o === "price") return l.new_price != null ? +l.new_price : null;
    return null;
  };
  const paint = flashKey => {
    const ul = $("#lines");
    if (!D.lines.length) ul.innerHTML = `<div class="empty">📦 ${t("Scan the first item")}</div>`;
    else ul.innerHTML = D.lines.map((l, i) => {
      const np = k === "poster" ? newPrice(l) : null;
      return `<li class="ln ${l.key === flashKey ? "flash" : ""}">
      <div class="info"><div class="nm">${esc(l.name)}</div>
        ${l.unit ? `<span class="unit" data-u="${i}">${esc(l.unit)}${l.factor !== 1 ? " ×" + nq(l.factor) : ""}${(l.units || []).length > 1 ? " ▾" : ""}</span>` : ""}
        ${k === "po" ? ` <span class="muted" data-c="${i}">${t("cost")} ${n2(l.cost)} ✎ = <b>${n2(l.qty * (l.cost || 0))}</b></span>` : ""}
        ${k === "poster" ? ` <span class="muted" data-p="${i}">${np != null && np < l.price ? `<s>${n2(l.price)}</s> → <b style="color:var(--red)">${n2(np)}</b>` : n2(l.price)}${H.offer_type === "price" ? " ✎" : ""}</span>` : ""}
        ${k === "labels" ? ` <span class="muted">${esc(l.barcode || t("no barcode yet — made on print"))}</span>` : ""}
        ${k === "price_change" ? ` <span class="muted" data-np="${i}">${n2(l.price)} → <b style="color:${l.new_price != null ? (l.cost && l.new_price / (1 + (l.vat || 0) / 100) < l.cost ? "var(--red)" : "var(--green)") : "var(--muted)"}">${l.new_price != null ? n2(l.new_price) : t("tap to type")}</b> ✎${l.cost ? ` · ${t("cost")} ${n2(l.cost)}${l.new_price != null ? ` · ${t("margin")} ${Math.round((1 - l.cost / (l.new_price / (1 + (l.vat || 0) / 100))) * 100)}%` : ""}` : ""}</span>` : ""}</div>
      ${k === "poster" ? `<button class="danger" data-x="${i}" style="min-height:42px;width:42px;padding:0">✕</button>` :
        `<div class="qty"><button data-d="-1" data-i="${i}">−</button><input data-q="${i}" inputmode="decimal" value="${nq(l.qty)}">
        <button data-d="1" data-i="${i}">+</button></div>`}</li>`; }).join("");
    if (k === "po") $("#tot").innerHTML = `${D.lines.length} ${t("Items")}<small>${esc(S.settings?.currency || "")} ${n2(D.lines.reduce((a, l) => a + l.qty * (l.cost || 0), 0))} + ${t("VAT")}</small>`;
    else if (k === "labels") $("#tot").innerHTML = `${D.lines.reduce((a, l) => a + (+l.qty || 0), 0)} ${t("labels")}<small>${D.lines.length} ${t("Items")}</small>`;
    else if (k === "price_change") $("#tot").innerHTML = `${D.lines.filter(l => l.new_price != null).length} / ${D.lines.length} ${t("new prices")}<small>${D.lines.reduce((a, l) => a + (+l.qty || 0), 0)} ${t("labels")}</small>`;
    else $("#tot").innerHTML = `${D.lines.length} ${t("Items")}<small>${D.lines.length > 12 ? t("12 show on the poster") : ""}</small>`;
    $$("button[data-d]", ul).forEach(b => b.onclick = () => { const l = D.lines[+b.dataset.i]; l.qty = Math.max(0, l.qty + (+b.dataset.d)); if (!l.qty) D.lines.splice(+b.dataset.i, 1); save(); paint(); focus(); });
    $$("button[data-x]", ul).forEach(b => b.onclick = () => { D.lines.splice(+b.dataset.x, 1); save(); paint(); focus(); });
    $$("input[data-q]", ul).forEach(inp => { inp.onchange = () => { const l = D.lines[+inp.dataset.q]; l.qty = Math.max(0, parseFloat(inp.value) || 0); if (!l.qty) D.lines.splice(+inp.dataset.q, 1); save(); paint(); focus(); };
      inp.onkeydown = e => { if (e.key === "Enter") inp.blur(); }; });
    $$("[data-u]", ul).forEach(s => s.onclick = () => { const l = D.lines[+s.dataset.u]; if (!l.units || l.units.length < 2) return;
      const j = (l.units.findIndex(u => u.unit_id === l.unit_id) + 1) % l.units.length; const u = l.units[j];
      Object.assign(l, { unit_id: u.unit_id, unit: u.unit, factor: u.factor, key: l.product_id + "-" + u.unit_id, price: u.price_vat, barcode: u.barcode });
      if (u.cost != null) l.cost = u.cost; save(); paint(); });
    $$("[data-c]", ul).forEach(s => s.onclick = () => { const l = D.lines[+s.dataset.c]; const v = prompt(t("Cost per") + " " + (l.unit || "unit"), n2(l.cost)); if (v != null) { l.cost = parseFloat(v) || 0; save(); paint(); } });
    $$("[data-np]", ul).forEach(s => s.onclick = () => { const l = D.lines[+s.dataset.np];
      const v = prompt(t("New shelf price (with VAT) for") + " " + l.name + " · " + (l.unit || ""), l.new_price != null ? n2(l.new_price) : n2(l.price));
      if (v != null && v !== "") { l.new_price = Math.round((parseFloat(v) || 0) * 100) / 100; save(); paint(); } });
    $$("[data-p]", ul).forEach(s => s.onclick = () => { if (H.offer_type !== "price") return; const l = D.lines[+s.dataset.p];
      const v = prompt(t("Offer price for") + " " + l.name, l.new_price != null ? n2(l.new_price) : n2(l.price)); if (v != null) { l.new_price = parseFloat(v) || 0; save(); paint(); } });
  };
  current.onScan = async code => {
    scanEl.value = "";
    let c;
    try { c = await lookup(code); }
    catch (e) {
      try { const r = await api("search", { params: { q: code } }); if (r.items.length) return pickProduct(r.items, it => current.onScan(it.code)); } catch (x) {}
      $("#hit").innerHTML = `<div class="card miss">✖ ${esc(e.message)}</div>`; beep(220, .3); return;
    }
    const u = c.units.find(x => x.unit_id === c.scanned_unit_id) || c.units[0] || { unit: "PCs", factor: 1 };
    const key = c.product_id + "-" + u.unit_id;
    let l = D.lines.find(x => x.key === key);
    if (l && k === "price_change") { /* already in the list: just show it */ }
    else if (l && k !== "poster") l.qty += 1;
    else if (!l) { l = { key, product_id: c.product_id, name: c.name, unit_id: u.unit_id, unit: u.unit, factor: u.factor, qty: 1,
      cost: u.cost != null ? u.cost : null, price: u.normal_price_vat || u.price_vat, barcode: u.barcode, vat: c.vat_rate,
      units: c.units.map(x => ({ unit_id: x.unit_id, unit: x.unit, factor: x.factor, cost: x.cost, price_vat: x.normal_price_vat || x.price_vat, barcode: x.barcode })) };
      D.lines.unshift(l); }
    save();
    $("#hit").innerHTML = `<div class="card hit"><div class="nm">${esc(c.name)}</div><div class="muted">${esc(u.unit)} · ${t("Stock")} ${esc(c.stock_text)}${k === "po" && c.reorder_level ? " · " + t("reorder at") + " " + nq(c.reorder_level) : ""}</div></div>`;
    beep(); paint(key);
    if (k === "price_change" && l.new_price == null) setTimeout(() => { const el = $(`[data-np="${D.lines.indexOf(l)}"]`); if (el) el.click(); }, 80);
  };
  scanEl.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); const v = scanEl.value.trim(); if (v) current.onScan(v); } };
  $("#clr").onclick = () => { if (D.lines.length && !confirm("Clear the whole list?")) return; D.lines = []; save(); paint(); focus(); };
  $("#send").onclick = async () => {
    if (!D.lines.length) return toast("The list is empty", true);
    if (k === "po" && !H.supplier_id) return toast(t("Choose the supplier first"), true);
    if (k === "poster" && H.offer_type === "price" && D.lines.some(l => l.new_price == null)) return toast(t("Type the offer price of every product (tap the price)"), true);
    if (k === "price_change" && D.lines.some(l => l.new_price == null)) return toast(t("Type the new price of every item (tap the price)"), true);
    $("#send").disabled = true;
    const doc = { uid: device() + "-" + k + "-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6), type: k, title: cfg.title,
      header: H, lines: D.lines.map(l => ({ product_id: l.product_id, unit_id: l.unit_id, unit: l.unit, factor: l.factor, qty: l.qty,
        copies: l.qty, cost: l.cost, new_price: l.new_price, old_price: l.price })) };
    let res;
    try { res = await api("submit", { body: { doc, device: device() }, timeout: 60000 }); }
    catch (e) { $("#send").disabled = false; return toast(e.message, true, 5000); }
    $("#send").disabled = false;
    addSent({ uid: doc.uid, type: k, title: cfg.title, status: res.status, result: res.result, at: Date.now() });
    if (res.status === "error") return toast(res.result, true, 5000);
    beep(1500, .12);
    const keepHead = k === "po" ? { expected_days: H.expected_days } : k === "labels" ? { print: H.print, template_id: H.template_id } :
      k === "price_change" ? { reason: H.reason, print_labels: H.print_labels, print: true, template_id: H.template_id, allow_below_cost: false } :
      { offer_type: H.offer_type, value: H.value, start: H.start, end: H.end, size: H.size, theme: H.theme, create_offer: H.create_offer, print: H.print };
    D = { lines: [], header: keepHead }; save();
    const p = sheet(`<div class="card hit"><div class="nm">✔ ${esc(res.result || "Done")}</div></div>
      ${res.file ? `<a href="${pdfUrl(res.doc_id)}" target="_blank" rel="noopener"><button class="primary" style="width:100%;margin-bottom:8px">📄 ${t("Open PDF")}</button></a>` : ""}
      ${res.whatsapp_text ? `<button class="green" id="wa" style="width:100%;margin-bottom:8px">💬 ${t("Send to supplier on WhatsApp")}</button>` : ""}
      ${res.prompt ? `<button id="cp" style="width:100%;margin-bottom:8px">🎨 ${t("Copy AI poster prompt (ChatGPT / Gemini)")}</button>` : ""}`);
    if ($("#wa", p)) $("#wa", p).onclick = () => { const ph = String(res.supplier_phone || "").replace(/\D/g, "").replace(/^0/, "966");
      window.open(`https://wa.me/${ph}?text=${encodeURIComponent(res.whatsapp_text)}`, "_blank"); };
    if ($("#cp", p)) $("#cp", p).onclick = async () => { try { await navigator.clipboard.writeText(res.prompt); toast(t("Copied — paste it in ChatGPT or Gemini")); }
      catch (e) { prompt("Copy:", res.prompt); } };
    const obs = new MutationObserver(() => { if (!document.body.contains(p)) { obs.disconnect(); jobScreen(k); } });
    obs.observe(document.body, { childList: true });
  };
  paint(); focus();
}

/* ---------- history ---------- */
async function history() {
  shell(t("History"), `<div class="wrap"><div id="h"><div class="empty">…</div></div></div>`);
  const q = queue();
  let rows = q.map(x => ({ title: x.doc.title || x.doc.type, status: "waiting", result: t("Waiting to send"), at: x.at }));
  let server = [];
  if (!RELAY) { try { server = (await api("docs")).items.map(d => ({ title: d.title, status: d.status, result: d.result, at: d.created_at })); } catch (e) {} }
  rows = rows.concat(server.length ? server : sent());
  $("#h").innerHTML = (q.length ? `<button class="primary" id="fl" style="width:100%;margin-bottom:10px">⟳ ${t("Sync now")} (${q.length})</button>` : "") +
    (rows.map(r => `<div class="card"><div class="row"><b>${esc(r.title)}</b><span class="right"><span class="badge ${r.status === "applied" ? "green" : r.status === "error" || r.status === "rejected" ? "red" : "amber"}">${esc(r.status)}</span></span></div>
      <div class="muted">${esc(typeof r.at === "number" ? new Date(r.at).toLocaleString() : String(r.at || "").replace("T", " ").slice(0, 16))}</div><div>${esc(r.result || "")}</div></div>`).join("") || `<div class="empty">—</div>`);
  if ($("#fl")) $("#fl").onclick = async () => { await flush(); history(); };
}

/* ==========================================================
   VAN SALES — works with no signal
   ========================================================== */
let CAT = null, IDX = null;
async function loadCatalog() {
  if (!CAT) CAT = await KV.get("catalog", null);
  if (CAT && !IDX) buildIndex();
  return CAT;
}
function buildIndex() {
  IDX = { bc: new Map(), code: new Map(), id: new Map(), cust: new Map() };
  for (const p of CAT.products) {
    IDX.id.set(p.id, p);
    if (p.code) IDX.code.set(String(p.code).toUpperCase(), p);
    for (const u of p.units) for (const b of u.barcodes || []) IDX.bc.set(String(b), { p, u });
  }
  for (const c of CAT.customers) IDX.cust.set(c.customer_id, c);
}
function localLookup(code) {
  code = String(code).trim().replace(/\s+/g, "");
  if (!IDX) throw new Error("Sync the van first (no product list yet)");
  let hit = IDX.bc.get(code);
  if (!hit) { const p = IDX.code.get(code.toUpperCase()); if (p) hit = { p, u: p.units.find(u => u.default) || p.units[0] }; }
  if (!hit) throw new Error(`No product for “${code}”`);
  const { p, u } = hit;
  return { product_id: p.id, name: p.name, name_ar: p.name_ar, code: p.code, vat_rate: p.vat, stock: p.stock,
    stock_text: nq(p.stock), units: p.units.map(x => ({ ...x, price_vat: x.price_vat, stock_in_unit: p.stock / (x.factor || 1), barcode: (x.barcodes || [])[0] || "" })),
    scanned_unit_id: u.unit_id, category: "", via: "unit" };
}
async function syncVan(quiet) {
  try {
    await flush();
    try {                         // which van bills are already in DayBill
      const d = await api("docs");
      const st = new Map((d.items || []).map(x => [x.doc_uid, x]));
      const b = await vanBills(); let ch = false;
      for (const x of b) { const y = st.get(x.uid); if (y && y.status !== x.status) { x.status = y.status; x.result = y.result; ch = true; } }
      if (ch) await saveVanBills(b);
    } catch (e) {}
    const c = await api("catalog", { timeout: 60000 });
    await KV.set("catalog", c); CAT = c; IDX = null; buildIndex();
    LS.set("cat_at", Date.now());
    if (!quiet) toast(`✔ ${c.products.length} products · ${c.customers.length} customers`);
    return true;
  } catch (e) { if (!quiet) toast(e.message, true); return false; }
}
async function vanBills() { return (await KV.get("van_bills", [])) || []; }
async function saveVanBills(b) { return KV.set("van_bills", b); }
async function markVanBill(uid, res) {
  const b = await vanBills(); const x = b.find(z => z.uid === uid);
  if (x) { x.status = res.status; x.result = res.result; await saveVanBills(b); }
}
function vanPrefix() { return (S.van_code || device()).toUpperCase().replace(/[^A-Z0-9]/g, "") || "VAN"; }

async function vanHome() {
  await loadCatalog();
  const bills = await vanBills();
  const today = localTime(new Date().toISOString()).slice(0, 10);
  const td = bills.filter(b => b.date === today);
  const sum = p => n2(td.filter(b => b.payment === p).reduce((a, b) => a + b.total, 0));
  const age = LS.get("cat_at", 0);
  shell(t("Van Sales") , `<div class="wrap">
    <div class="card"><div class="row"><div><b>${t("Today")}</b> · ${td.length} ${t("Bills")}</div>
      <div class="right"><b>${n2(td.reduce((a, b) => a + b.total, 0))}</b></div></div>
      <div class="muted">${t("Cash")} ${sum("cash")} · ${t("Card")} ${sum("card")} · ${t("Credit")} ${sum("credit")}</div>
      <div class="muted">${CAT ? `${CAT.products.length} products · updated ${new Date(age).toLocaleString()}` : "⚠ No product list yet — press Sync"}</div></div>
    <button class="primary" id="nb" style="width:100%;font-size:20px;min-height:64px">＋ ${t("New bill")}</button>
    <div class="spacer"></div>
    <div class="row"><button id="sy">⟳ ${t("Sync now")}</button>${S.module_list.length > 1 ? `<button id="hm">⌂ Home</button>` : `<button class="danger" id="lo">${t("Sign out")}</button>`}</div>
    <div class="spacer"></div>
    ${bills.slice(0, 30).map((b, i) => `<div class="card" data-b="${i}"><div class="row"><b>${esc(b.number)}</b><span class="right"><b>${n2(b.total)}</b></span></div>
      <div class="row"><span class="muted">${esc(b.customer_name)} · ${esc(b.payment)} · ${esc(localTime(b.time).slice(11))}</span>
      <span class="right"><span class="badge ${b.status === "applied" ? "green" : b.status === "error" ? "red" : "amber"}">${b.status === "applied" ? "✓ in DayBill" : b.status === "sent" ? "↑ sent" : esc(b.status || "waiting")}</span></span></div></div>`).join("")}
  </div>`, { back: S.module_list.length > 1 });
  $("#nb").onclick = () => CAT ? vanBill() : toast("Press Sync first to load products", true);
  $("#sy").onclick = async () => { $("#sy").disabled = true; await syncVan(); vanHome(); };
  if ($("#hm")) $("#hm").onclick = home;
  if ($("#lo")) $("#lo").onclick = () => logout();
  $$("[data-b]").forEach(el => el.onclick = () => showBill(bills[+el.dataset.b]));
  if (!CAT && navigator.onLine !== false) syncVan(true).then(ok => ok && vanHome());
}

function calcLine(l, incl, rate) {
  const gross = l.qty * l.price - (l.discount || 0);
  if (incl && rate) { const tax = gross / (1 + rate / 100); return { taxable: tax, vat: gross - tax, total: gross }; }
  return { taxable: gross, vat: gross * rate / 100, total: gross + gross * rate / 100 };
}
// halalas, half up (10.005 → 10.01) — the same rounding as DayBill
const r2 = v => { const x = Math.abs(+v || 0); const r = Math.round(x * 100 + 1e-7) / 100; return v < 0 ? -r : r; };
// v6.9.2: the ZATCA way, exactly as DayBill books it — each line's taxable in
// halalas, the VAT worked out once per rate on the bill total
function billTotals(B) {
  const incl = !!CAT.settings.price_incl_vat, vatOn = CAT.settings.vat_enabled !== false;
  const byRate = {}; let tot = 0;
  for (const l of B.lines) {
    const rate = vatOn ? (+l.vat_rate || 0) : 0, r = calcLine(l, incl, rate);
    l.total = r2(r.total); tot += l.total;
    byRate[rate] = (byRate[rate] || 0) + r2(r.taxable);
  }
  let vat = 0, tx = 0;
  for (const k in byRate) { vat += r2(byRate[k] * (+k) / 100); tx += byRate[k]; }
  B.vat = r2(vat);
  if (incl) { B.total = r2(tot); B.taxable = r2(B.total - B.vat); }
  else { B.taxable = r2(tx); B.total = r2(B.taxable + B.vat); }
  return B;
}
function vanBill() {
  let B = LS.get("van_draft", null) || { lines: [], customer_id: null, customer_name: t("Cash customer"), payment: "cash" };
  const save = () => LS.set("van_draft", B);
  shell(t("New bill"), `<div class="wrap">
    <div class="scan"><input id="scan" placeholder="${t("Scan or type barcode / name")}" autocomplete="off">
    ${canCamera() ? `<button id="cam">📷</button>` : ""}</div>
    <div class="card"><button id="cu" style="width:100%;text-align:start">👤 ${esc(B.customer_name)}</button>
      <div class="seg" style="margin-top:8px">${["cash", "card", "credit"].map(p => `<button data-p="${p}" class="${B.payment === p ? "on" : ""}">${t(p[0].toUpperCase() + p.slice(1))}</button>`).join("")}</div></div>
    <ul class="lines" id="lines"></ul><div class="spacer"></div></div>
    <div class="bottom"><div class="tot" id="tot"></div><button class="danger" id="clr">✕</button><button class="green" id="ok">✔ ${t("Save")}</button></div>`);
  const scanEl = $("#scan");
  if ($("#cam")) $("#cam").onclick = camera;
  $("#cu").onclick = () => pickCustomer(c => { B.customer_id = c ? c.customer_id : null; B.customer_name = c ? c.customer_name_en : t("Cash customer"); B.customer_vat = c ? c.vat_registration_no : ""; save(); vanBill(); });
  $$("[data-p]").forEach(b => b.onclick = () => { if (b.dataset.p === "credit" && !B.customer_id) return toast("Choose the customer for a credit bill", true); B.payment = b.dataset.p; save(); vanBill(); });
  const paint = fk => {
    billTotals(B);
    $("#lines").innerHTML = B.lines.length ? B.lines.map((l, i) => `<li class="ln ${l.key === fk ? "flash" : ""}"><div class="info"><div class="nm">${esc(l.name)}</div>
      <span class="unit" data-u="${i}">${esc(l.unit)} ▾</span> <span class="muted">${n2(l.price)} → <b>${n2(l.total)}</b></span></div>
      <div class="qty"><button data-d="-1" data-i="${i}">−</button><input data-q="${i}" inputmode="decimal" value="${nq(l.qty)}"><button data-d="1" data-i="${i}">+</button></div></li>`).join("")
      : `<div class="empty">🛒 Scan or search items</div>`;
    $("#tot").innerHTML = `${n2(B.total)}<small>${t("VAT")} ${n2(B.vat)} · ${B.lines.length} ${t("Items")}</small>`;
    $$("button[data-d]").forEach(b => b.onclick = () => { const l = B.lines[+b.dataset.i]; l.qty = Math.max(0, l.qty + (+b.dataset.d)); if (!l.qty) B.lines.splice(+b.dataset.i, 1); save(); paint(); });
    $$("input[data-q]").forEach(inp => inp.onchange = () => { const l = B.lines[+inp.dataset.q]; l.qty = Math.max(0, parseFloat(inp.value) || 0); if (!l.qty) B.lines.splice(+inp.dataset.q, 1); save(); paint(); });
    $$("[data-u]").forEach(s => s.onclick = () => { const l = B.lines[+s.dataset.u]; const p = IDX.id.get(l.product_id); if (!p || p.units.length < 2) return;
      const j = (p.units.findIndex(u => u.unit_id === l.unit_id) + 1) % p.units.length; const u = p.units[j];
      Object.assign(l, { unit_id: u.unit_id, unit: u.unit, factor: u.factor, price: u.price, key: p.id + "-" + u.unit_id }); save(); paint(); });
  };
  const addProduct = (p, u, qty = 1) => {
    const key = p.id + "-" + u.unit_id;
    let l = B.lines.find(x => x.key === key);
    if (l) l.qty += qty;
    else { l = { key, product_id: p.id, name: p.name, name_ar: p.name_ar, unit_id: u.unit_id, unit: u.unit, factor: u.factor, price: u.price, vat_rate: p.vat, qty }; B.lines.unshift(l); }
    if (p.stock < l.qty * l.factor) toast(`⚠ ${p.name}: only ${nq(p.stock)} pcs in stock`, true, 2000); else beep();
    save(); paint(key);
  };
  current.onScan = code => {
    scanEl.value = "";
    try { const c = localLookup(code); const p = IDX.id.get(c.product_id); addProduct(p, p.units.find(u => u.unit_id === c.scanned_unit_id) || p.units[0]); }
    catch (e) {
      const qy = code.toLowerCase();
      const m = CAT.products.filter(p => (p.name + " " + p.name_ar + " " + p.code).toLowerCase().includes(qy)).slice(0, 20);
      if (m.length) pickProduct(m.map(p => ({ ...p, stock: p.stock })), it => { const p = IDX.id.get(it.id); addProduct(p, p.units.find(u => u.default) || p.units[0]); });
      else { toast(e.message, true); }
    }
  };
  scanEl.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); const v = scanEl.value.trim(); if (v) current.onScan(v); } };
  $("#clr").onclick = () => { if (B.lines.length && !confirm("Cancel this bill?")) return; LS.del("van_draft"); vanHome(); };
  $("#ok").onclick = async () => {
    if (!B.lines.length) return toast("The bill is empty", true);
    if (B.payment === "credit" && !B.customer_id) return toast("Choose the customer for a credit bill", true);
    billTotals(B);
    const seq = LS.get("van_seq", 0) + 1; LS.set("van_seq", seq);
    const now = new Date();
    const bill = { ...B, number: vanPrefix() + (S.device_no ? "-" + S.device_no : "") + "-" + String(seq).padStart(5, "0"), uid: "van-" + vanPrefix() + "-" + device() + "-" + seq + "-" + now.getTime(),
      date: localTime(now.toISOString()).slice(0, 10), time: now.toISOString().replace(/\.\d+Z$/, "Z"), status: "waiting" };
    const bills = await vanBills(); bills.unshift(bill); await saveVanBills(bills.slice(0, 400));
    LS.del("van_draft");
    current.billUid = bill.uid;
    enqueue({ uid: bill.uid, type: "van_sale", title: "Van " + bill.number,
      header: { number: bill.number, customer_id: bill.customer_id, customer_name: bill.customer_name, payment: bill.payment, total: bill.total, date: bill.date, time: bill.time },
      lines: bill.lines.map(l => ({ product_id: l.product_id, unit_id: l.unit_id, unit: l.unit, factor: l.factor, qty: l.qty, price: l.price, discount: l.discount || 0 })) })
      .then(async () => {                      // still on this bill? show where it went
        if (current.billUid !== bill.uid) return;
        const b2 = (await vanBills()).find(x => x.uid === bill.uid);
        const badge = $("#bstat"); if (b2 && badge) { badge.className = "badge " + statusClass(b2.status); badge.textContent = statusText(b2.status); }
      });
    showBill(bill, true);
  };
  paint(); setTimeout(() => scanEl.focus(), 50);
}
function pickCustomer(cb) {
  const p = sheet(`<input id="cq" placeholder="Search customer (name / phone / code)"><div class="item" data-cash><div class="grow"><b>${t("Cash customer")}</b></div></div><div id="cl"></div>`);
  const draw = () => {
    const q = $("#cq", p).value.toLowerCase();
    const m = CAT.customers.filter(c => (c.customer_name_en + " " + (c.customer_name_ar || "") + " " + (c.phone || "") + " " + c.customer_code).toLowerCase().includes(q)).slice(0, 40);
    $("#cl", p).innerHTML = m.map((c, i) => `<div class="item" data-i="${i}"><div class="grow"><b>${esc(c.customer_name_en)}</b><div class="muted">${esc(c.customer_code)} ${esc(c.phone || "")}</div></div>
      <span class="badge ${c.balance > 0 ? "amber" : ""}">${n2(c.balance)}</span></div>`).join("");
    $$("[data-i]", p).forEach(el => el.onclick = () => { cb(m[+el.dataset.i]); p.remove(); });
  };
  $("[data-cash]", p).onclick = () => { cb(null); p.remove(); };
  $("#cq", p).oninput = draw; draw();
}

/* ---------- receipt: ZATCA QR, print (Android app / RawBT / browser), WhatsApp ---------- */
function tlv(tag, val) { const b = new TextEncoder().encode(String(val)); return [tag, b.length, ...b]; }
function zatcaQR(b) {
  const c = CAT.company || {};
  const bytes = [...tlv(1, c.company_name_en || c.company_name_ar || "Shop"), ...tlv(2, String(c.vat_registration_no || "").replace(/\D/g, "")),
    ...tlv(3, b.time), ...tlv(4, n2(b.total)), ...tlv(5, n2(b.vat))];
  let s = ""; bytes.forEach(x => s += String.fromCharCode(x)); return btoa(s);
}
function localTime(iso) {
  const d = new Date(iso); if (isNaN(d)) return String(iso || "").replace("T", " ").slice(0, 16);
  const z = x => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}`;
}
function receiptText(b) {
  const c = CAT.company || {}, W = 32, line = "-".repeat(W);
  const pad = (a, z) => { a = String(a); z = String(z); return a.slice(0, W - z.length - 1).padEnd(W - z.length) + z; };
  let s = `${c.company_name_en || ""}\n${c.company_name_ar || ""}\nVAT ${c.vat_registration_no || ""}\nSIMPLIFIED TAX INVOICE\n${line}\n`;
  s += `No: ${b.number}\nDate: ${localTime(b.time)}\nCustomer: ${b.customer_name}\n${line}\n`;
  for (const l of b.lines) s += `${l.name.slice(0, W)}\n` + pad(`  ${nq(l.qty)} ${l.unit} x ${n2(l.price)}`, n2(l.total)) + "\n";
  s += `${line}\n` + pad("Total excl. VAT", n2(b.taxable)) + "\n" + pad("VAT", n2(b.vat)) + "\n" + pad("TOTAL SAR", n2(b.total)) + "\n" + pad("Paid by", b.payment.toUpperCase()) + "\n";
  return s + `${line}\n${(CAT.settings && CAT.settings.receipt_footer) || "Thank you!"}\n`;
}
function escpos(b) {
  const enc = s => [...new TextEncoder().encode(s.replace(/[^\x0A\x20-\x7E]/g, ""))];   // printers: plain English text
  const qr = zatcaQR(b), qb = [...new TextEncoder().encode(qr)], len = qb.length + 3;
  const out = [0x1B, 0x40, 0x1B, 0x61, 1, ...enc(receiptText(b)),
    0x1D, 0x28, 0x6B, 4, 0, 0x31, 0x41, 0x32, 0x00,      // QR model 2
    0x1D, 0x28, 0x6B, 3, 0, 0x31, 0x43, 0x05,            // size 5
    0x1D, 0x28, 0x6B, 3, 0, 0x31, 0x45, 0x31,            // error level M
    0x1D, 0x28, 0x6B, len & 255, len >> 8, 0x31, 0x50, 0x30, ...qb,
    0x1D, 0x28, 0x6B, 3, 0, 0x31, 0x51, 0x30, 0x0A, 0x0A, 0x0A, 0x1D, 0x56, 0x42, 0x00];
  let s = ""; out.forEach(x => s += String.fromCharCode(x)); return btoa(s);
}
function qrImg(data) {
  try { const q = qrcode(0, "M"); q.addData(data); q.make(); return q.createImgTag(4, 8); } catch (e) { return ""; }
}
const statusClass = s => s === "applied" ? "green" : s === "error" ? "red" : "amber";
const statusText = s => s === "applied" ? "✓ in DayBill" : s === "sent" ? "↑ sent to the shop" : s === "error" ? "⚠ problem — see History" : "waiting — sends when online";
function showBill(b, fresh) {
  shell(b.number, `<div class="wrap">
    <div class="card"><div class="row"><b>${esc(b.customer_name)}</b><span class="right big" style="font-size:30px">${n2(b.total)}</span></div>
      <div class="muted">${t("VAT")} ${n2(b.vat)} · ${esc(b.payment)} · ${esc(localTime(b.time))}</div>
      <div><span id="bstat" class="badge ${statusClass(b.status)}">${esc(statusText(b.status))}</span></div></div>
    <div id="printarea"><div class="receipt">${esc(receiptText(b))}</div><div class="qrbox">${qrImg(zatcaQR(b))}</div></div>
    <div class="row" style="margin-top:10px"><button class="primary" id="pr">🖨 ${t("Print")}</button><button id="wa">💬 WhatsApp</button></div>
    <div class="row" style="margin-top:8px"><button id="pdf">📄 PDF / browser print</button><button class="green" id="nx">＋ ${t("New bill")}</button></div>
  </div>`);
  current.billUid = b.uid;
  $("#back").onclick = vanHome;
  $("#nx").onclick = vanBill;
  $("#pdf").onclick = () => window.print();
  $("#wa").onclick = () => {
    const c = (CAT.customers || []).find(x => x.customer_id === b.customer_id);
    const ph = String((c && c.phone) || "").replace(/\D/g, "").replace(/^0/, "966");
    window.open(`https://wa.me/${ph}?text=${encodeURIComponent(receiptText(b))}`, "_blank");
  };
  $("#pr").onclick = () => {
    const data = escpos(b);
    if (window.DayBillAndroid && window.DayBillAndroid.printEscPos) {          // DayBill Android app → paired Bluetooth printer
      const r = window.DayBillAndroid.printEscPos(data);
      toast(r === "ok" || r === true ? "🖨 Printed" : String(r || "Printing…"), !(r === "ok" || r === true));
    } else {                                                                   // Chrome on Android → RawBT app → Bluetooth printer
      location.href = "intent:base64," + data + "#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;";
    }
  };
  if (fresh) { beep(1500, .12); toast("✔ " + b.number + " saved"); }
}

/* ---------- start ---------- */
window.addEventListener("load", () => {
  if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("sw.js").catch(() => {});
});
window.DayBillApp = { home, login, flush, syncVan, state: () => S };
if (S && S.token) { if (S.modules.length === 1) openModule(S.modules[0]); else home(); flush(); }
else login();
})();
