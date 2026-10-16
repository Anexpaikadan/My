# ============================================================
# DayBill ERP - 📲 owner's evening report on WhatsApp  (v6.4, v6.5)
# ------------------------------------------------------------
# One short message the owner gets every evening — even when not in the
# shop (Settings ▸ WhatsApp ▸ Owner WhatsApp No. + "Send the owner's
# evening report automatically" at a time), or with Day Close ▸ 📲:
#   sales (bills, average, vs the same day last week), payments, returns,
#   expenses · cash short / over at shift close · best items · stock
#   alerts (AI inventory) · cashier warnings · cloud backup
# In English or Arabic (Settings ▸ WhatsApp ▸ Evening report language).
#
# How it is sent:
#   WhatsApp app mode   the chat opens with the text typed (press Send)
#   Cloud API + the evening-report TEMPLATE (approved in Meta: header =
#                       document, body {{1}} date, {{2}} sales, {{3}} summary)
#                       → the report as a PDF, delivered every day
#   Cloud API, no template → plain text: WhatsApp delivers it ONLY when the
#                       owner wrote to the shop number in the last 24 hours
#   From Day Close / Settings (someone at the PC) a failed Cloud API send
#   opens the WhatsApp app instead.
# ============================================================

import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _q(sql, params=()):
    try:
        return [dict(r) for r in (db.fetchall(sql, params) or [])]
    except Exception:
        return []


def _m(v):
    return "{:,.2f}".format(_f(v))


def _cfg(key, default=""):
    try:
        from config import settings as cfg
        v = cfg.get(key, default)
        return default if v is None else v
    except Exception:
        return default


def lang():
    v = str(_cfg("owner_report_lang", "en") or "en").lower()
    return "ar" if v.startswith("ar") or "عرب" in v else "en"


# ── words ─────────────────────────────────────────────────────
W = {
    "en": {"sales": "🧾 Sales *{t} SAR* · {n} bill(s)", "avg": " · avg {a}",
           "vs": "   {arrow} {pct:.0f}% vs last {wd} ({lw})", "returns": "↩ Returns {t} SAR ({n})",
           "expenses": "💸 Expenses {t} SAR", "short": "⚠ Cash SHORT {t} SAR ({u})",
           "over": "💰 Cash over {t} SAR ({u})", "cash_ok": "✔ Cash counted = expected ({n} shift(s))",
           "best": "⭐ Best items:", "stock": "📦 Stock (health {s}/100):", "watch": "👀 Cashier watch:",
           "backup_ok": "☁ Cloud backup ✔ {t}", "cashier": "cashier", "bills": "{n} bills",
           "short_s": "cash short {t}", "alerts": "{n} alert(s)", "all_ok": "all normal",
           "docs": "👔 Documents to renew ({n}):", "expired": "EXPIRED", "in_days": "in {n} day(s)",
           "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
           "wdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
           "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
           "pay": {}},
    "ar": {"sales": "🧾 المبيعات *{t} ريال* · {n} فاتورة", "avg": " · المتوسط {a}",
           "vs": "   {arrow} {pct:.0f}% مقارنة بيوم {wd} الماضي ({lw})", "returns": "↩ المرتجعات {t} ريال ({n})",
           "expenses": "💸 المصروفات {t} ريال", "short": "⚠ عجز في الصندوق {t} ريال ({u})",
           "over": "💰 زيادة في الصندوق {t} ريال ({u})",
           "cash_ok": "✔ النقد المعدود = المتوقع ({n} وردية)",
           "best": "⭐ الأكثر مبيعاً:", "stock": "📦 المخزون (الصحة {s}/100):", "watch": "👀 مراقبة الكاشير:",
           "backup_ok": "☁ النسخة السحابية ✔ {t}", "cashier": "كاشير", "bills": "{n} فاتورة",
           "short_s": "عجز {t}", "alerts": "{n} تنبيه", "all_ok": "كل شيء طبيعي",
           "docs": "👔 وثائق تحتاج تجديد ({n}):", "expired": "منتهية", "in_days": "بعد {n} يوم",
           "days": ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
           "wdays": ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
           "months": None,
           "pay": {"cash": "نقدي", "card": "شبكة", "mada": "مدى", "credit": "آجل", "credit card": "بطاقة",
                   "debit card": "بطاقة", "bank transfer": "تحويل بنكي", "bank": "بنك", "stc pay": "STC Pay",
                   "tabby": "تابي", "tamara": "تمارا", "split": "مختلط", "voucher": "قسيمة",
                   "apple pay": "Apple Pay", "cheque": "شيك"}},
}

# the stock and cashier lines come from other modules in English
_AR_STOCK = [
    (r"Order now: (\d+) item\(s\) out or running out within 3 days — (.*)",
     "اطلب الآن: {0} صنف نفد أو ينفد خلال 3 أيام — {1}"),
    (r"Best sellers \(A\) running low: (.*)", "الأصناف الأكثر مبيعاً (A) قاربت على النفاد: {0}"),
    (r"(\d+) expired batch\(es\), ([\d,.]+) SAR.*", "{0} دفعة منتهية الصلاحية بقيمة {1} ريال — أزلها من الرف"),
    (r"(\d+) item\(s\) priced BELOW cost — (.*)", "{0} صنف سعره أقل من التكلفة — {1}"),
    (r"(\d+) item\(s\) with minus stock.*", "{0} صنف رصيده بالسالب — سجّل المشتريات أو قم بالجرد"),
    (r"([\d,.]+) SAR of stock may expire before it sells — (.*)",
     "{0} ريال من المخزون قد تنتهي صلاحيته قبل بيعه — {1}"),
    (r"Move stock between branches instead of buying: (\d+) suggestion\(s\).*",
     "انقل المخزون بين الفروع بدل الشراء: {0} اقتراح"),
    (r"Money stuck: (\d+) item\(s\) not sold for 60 days \(([\d,.]+) SAR\).*",
     "أموال مجمدة: {0} صنف لم يُبع منذ 60 يوماً ({1} ريال) — اعمل عرضاً"),
]
_AR_FLAGS = [
    (r"High discounts ([\d.]+%)", "خصومات عالية {0}"),
    (r"Many returns ×(\d+) \(([\d.]+%)\)", "مرتجعات كثيرة ×{0} ({1})"),
    (r"Items removed ×(\d+)", "أصناف حُذفت قبل الدفع ×{0}"),
    (r"Bills cleared ×(\d+)", "فواتير أُلغيت قبل الدفع ×{0}"),
    (r"Deleted docs ×(\d+)", "مستندات محذوفة ×{0}"),
    (r"Cash short ([\d,.]+)", "عجز نقدي {0}"),
]


def _ar(text, table):
    for pat, tpl in table:
        m = re.fullmatch(pat, text.strip())
        if m:
            return tpl.format(*m.groups())
    return text


def _sales(day):
    r = _q("SELECT COUNT(*) AS n, ISNULL(SUM(total_amount),0) AS t FROM sales_invoices "
           "WHERE invoice_status='confirmed' AND ISNULL(invoice_type_code,'388')<>'381' "
           "AND invoice_date=?", (day,))
    r = r[0] if r else {}
    return int(_f(r.get("n"))), _f(r.get("t"))


def _date_text(dd, lg):
    w = W[lg]
    if lg == "ar":
        return "%s %s" % (w["days"][dd.weekday()], dd.strftime("%d/%m/%Y"))
    return "%s %02d %s %d" % (w["days"][dd.weekday()], dd.day, w["months"][dd.month - 1], dd.year)


def build(day=None, lg=None):
    """→ (text, data). day = 'YYYY-MM-DD' (today by default); lg 'en' / 'ar'
    (Settings ▸ WhatsApp ▸ Evening report language by default)."""
    lg = lg or lang()
    w = W[lg]
    d = day or date.today().isoformat()
    dd = datetime.strptime(d[:10], "%Y-%m-%d").date()
    c = _q("SELECT TOP 1 company_name_en, company_name_ar FROM company")
    c = c[0] if c else {}
    shop = ((c.get("company_name_ar") if lg == "ar" else None) or c.get("company_name_en")
            or c.get("company_name_ar") or "DayBill")
    n, total = _sales(d)
    n_lw, total_lw = _sales((dd - timedelta(days=7)).isoformat())
    ch = ((total - total_lw) / total_lw * 100.0) if total_lw else None
    pay = _q("SELECT ISNULL(payment_method,'cash') AS m, SUM(ISNULL(total_amount,0)) AS t FROM sales_invoices "
             "WHERE invoice_status='confirmed' AND ISNULL(invoice_type_code,'388')<>'381' AND invoice_date=? "
             "GROUP BY payment_method", (d,))
    ret = _q("SELECT COUNT(*) AS n, ISNULL(SUM(total_amount),0) AS t FROM sales_returns "
             "WHERE ISNULL(return_status,'confirmed')='confirmed' AND return_date=?", (d,))
    ret = ret[0] if ret else {}
    exp = _q("SELECT ISNULL(SUM(ISNULL(amount,0)+ISNULL(vat_amount,0)),0) AS t FROM expenses WHERE expense_date=?", (d,))
    exp_t = _f(exp[0].get("t")) if exp else 0.0
    name_col = "sil.product_name_ar" if lg == "ar" else "sil.product_name_en"
    top = _q("SELECT TOP 5 ISNULL(NULLIF(%s,''), sil.product_name_en) AS name, "
             "SUM(ISNULL(sil.line_amount,0)) AS a, SUM(ISNULL(sil.quantity,0)) AS q "
             "FROM sales_invoice_lines sil JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
             "WHERE si.invoice_status='confirmed' AND ISNULL(si.invoice_type_code,'388')<>'381' "
             "AND si.invoice_date=? GROUP BY ISNULL(NULLIF(%s,''), sil.product_name_en) "
             "ORDER BY SUM(ISNULL(sil.line_amount,0)) DESC" % (name_col, name_col), (d,))
    shifts = _q("SELECT ISNULL(u.full_name_en, ISNULL(s.username,'')) AS u, ISNULL(s.difference,0) AS diff "
                "FROM cashier_shifts s LEFT JOIN users u ON u.user_id=s.user_id "
                "WHERE s.status='closed' AND CONVERT(date, s.closed_at)=?", (d,))
    lines = ["*%s — %s*" % (shop, _date_text(dd, lg)), ""]
    s = w["sales"].format(t=_m(total), n=n)
    if n:
        s += w["avg"].format(a=_m(total / n))
    lines.append(s)
    if ch is not None:
        lines.append(w["vs"].format(arrow="▲" if ch >= 0 else "▼", pct=abs(ch), wd=w["wdays"][dd.weekday()],
                                    lw=_m(total_lw)))
    if pay:
        def pname(m):
            k = str(m or "cash").replace("_", " ").lower()
            return w["pay"].get(k) or k.title()
        lines.append("   " + " · ".join("%s %s" % (pname(p["m"]), _m(p["t"])) for p in pay))
    if _f(ret.get("n")):
        lines.append(w["returns"].format(t=_m(ret.get("t")), n=int(_f(ret.get("n")))))
    if exp_t:
        lines.append(w["expenses"].format(t=_m(exp_t)))
    short_total = 0.0
    if shifts:
        short = [x for x in shifts if _f(x["diff"]) < -0.005]
        over = [x for x in shifts if _f(x["diff"]) > 0.005]
        if short or over:
            for x in short:
                short_total += -_f(x["diff"])
                lines.append(w["short"].format(t=_m(-_f(x["diff"])), u=x["u"] or w["cashier"]))
            for x in over:
                lines.append(w["over"].format(t=_m(x["diff"]), u=x["u"] or w["cashier"]))
        else:
            lines.append(w["cash_ok"].format(n=len(shifts)))
    if top:
        lines.append("")
        lines.append(w["best"])
        for i, t in enumerate(top, 1):
            lines.append("   %d. %s — %s" % (i, t["name"] or "?", _m(t["a"])))
    alerts = []
    try:
        from modules import inventory_ai as IA
        h = IA.health(today=dd)
        alerts = [a["what"] for a in h["actions"] if a["priority"] in ("high", "medium")][:3]
        if alerts:
            lines.append("")
            lines.append(w["stock"].format(s=h["score"]))
            lines += ["   • " + (_ar(a, _AR_STOCK) if lg == "ar" else a) for a in alerts]
    except Exception:
        pass
    flags = []
    try:
        from modules import cashier_watch as CW
        flags = CW.flags_text(d)
        if flags:
            lines.append("")
            lines.append(w["watch"])
            for f in flags[:5]:
                who, _, what = f.partition(": ")
                lines.append("   • %s: %s" % (who, _ar(what, _AR_FLAGS) if lg == "ar" else what))
    except Exception:
        pass
    try:                                           # v6.6: employee documents expiring
        from modules import hr_time as HT
        docs = [x for x in HT.expiring() if x["days_left"] <= 7]
        if docs:
            lines.append("")
            lines.append(w["docs"].format(n=len(docs)))
            lines += ["   • %s — %s %s" % (x["name"], x["doc"], (w["expired"] if x["days_left"] < 0 else
                                                                 w["in_days"].format(n=x["days_left"])))
                      for x in docs[:5]]
    except Exception:
        pass
    try:
        from modules import cloud_backup as CB
        if CB.enabled():
            a = CB.alert_text()
            st = CB.status()
            lines.append("")
            lines.append(a if a else w["backup_ok"].format(t=st.get("last_ok") or ""))
    except Exception:
        pass
    lines.append("")
    lines.append("— DayBill ERP")
    bits = [w["bills"].format(n=n)]
    if short_total:
        bits.append(w["short_s"].format(t=_m(short_total)))
    if alerts or flags:
        bits.append(w["alerts"].format(n=len(alerts) + len(flags)))
    if len(bits) == 1:
        bits.append(w["all_ok"])
    data = {"date": d, "date_text": _date_text(dd, lg), "lang": lg, "shop": shop, "bills": n,
            "sales": round(total, 2), "last_week": round(total_lw, 2),
            "change_pct": None if ch is None else round(ch, 1), "returns": _f(ret.get("t")),
            "expenses": exp_t, "top": top, "stock_alerts": alerts, "cashier_flags": flags,
            "shifts": shifts, "cash_short": round(short_total, 2),
            "summary": " · ".join(bits)}                 # one line (WhatsApp template {{3}})
    return "\n".join(lines), data


def template_params(data):
    """{{1}} date, {{2}} sales, {{3}} one-line summary — WhatsApp does not
    allow new lines or tabs in template values."""
    cur = "ريال" if data.get("lang") == "ar" else "SAR"
    vals = [data["date_text"], "%s %s" % (_m(data["sales"]), cur), data["summary"]]
    return [re.sub(r"\s{2,}", " ", str(v).replace("\n", " ").replace("\t", " ")).strip() or "-" for v in vals]


# ── PDF (sent with the Cloud API template; also handy to print) ─────
def _plain(line):
    """No emoji / WhatsApp *bold* marks in the PDF."""
    s = line.replace("*", "").replace("▲", "+").replace("▼", "-")
    out = []
    for ch in s:
        if ord(ch) > 0xFFFF or unicodedata.category(ch) == "So" or ch in "️‍":
            continue
        out.append(ch)
    return "".join(out).strip()


def make_pdf(text, data, path=None):
    """The report as a one-page PDF → path."""
    from reportlab.lib.pagesizes import A5
    from reportlab.pdfgen import canvas
    from modules import pdf_invoice as PI
    PI._register_fonts()
    font = getattr(PI, "_AR_FONT", None) or "Helvetica"
    bold = getattr(PI, "_AR_FONT_BOLD", None) or "Helvetica-Bold"
    if not path:
        try:
            from modules import whatsapp as wa
            folder = wa.pdf_folder()
        except Exception:
            import tempfile
            folder = tempfile.gettempdir()
        path = os.path.join(folder, "Evening_Report_%s.pdf" % data["date"])
    rtl = data.get("lang") == "ar"
    W_, H_ = A5
    cv = canvas.Canvas(path, pagesize=A5)
    cv.setTitle("DayBill evening report %s" % data["date"])
    y = H_ - 40
    lines = [_plain(l) for l in text.split("\n")]
    for i, ln in enumerate(lines):
        if y < 40:
            cv.showPage()
            y = H_ - 40
        if not ln:
            y -= 7
            continue
        is_head = i == 0 or ln.endswith(":")
        cv.setFont(bold if is_head else font, 13 if i == 0 else (10.5 if is_head else 10))
        shown = PI._shape_arabic(ln) if (rtl or PI._has_arabic(ln)) else ln
        if rtl:
            cv.drawRightString(W_ - 32, y, shown)
        else:
            cv.drawString(32, y, shown)
        y -= 20 if i == 0 else 15
    cv.save()
    return path


def owner_phone():
    try:
        from modules import whatsapp as wa
        return wa.normalize_phone(_cfg("wa_owner_phone", "") or "")
    except Exception:
        return ""


def owner_template():
    return str(_cfg("wa_owner_template", "") or "").strip()


NO_TEMPLATE_NOTE = ("Sent as a text message ✔ — WhatsApp delivers it only if the owner wrote to the shop "
                    "number in the last 24 hours. To get it every day, approve a template in Meta and type its "
                    "name in Settings ▸ WhatsApp ▸ Evening report template.")


def send(day=None, interactive=False):
    """Build and send to the owner → (ok, message).
    interactive=True (Day Close / Settings button): if the Cloud API fails,
    the WhatsApp app opens with the report instead."""
    phone = owner_phone()
    if not phone:
        return False, "Set the owner's WhatsApp number: Settings ▸ WhatsApp ▸ Owner WhatsApp No."
    text, data = build(day)
    from modules import whatsapp as wa
    try:
        if wa.mode() == "api":
            tpl = owner_template()
            if tpl:
                try:
                    pdf = make_pdf(text, data)
                except Exception as e:
                    pdf = None
                    print("[DayBill] evening report PDF:", e)
                ok, res = wa.api_send(phone, text, pdf, template_params(data), template=tpl,
                                      kind="owner_report", lang="ar" if data["lang"] == "ar" else None)
                msg = "Evening report sent ✔ (PDF + template %s)" % tpl if ok else "WhatsApp Cloud API: %s" % res
            else:
                ok, res = wa.api_send(phone, text, template="", kind="owner_report")
                msg = NO_TEMPLATE_NOTE if ok else "WhatsApp Cloud API: %s" % res
            wa.log("owner_report", None, phone, ok, res)
            if not ok and interactive:
                how = wa.open_chat(phone, text)
                wa.log("owner_report", None, phone, True, "opened chat (%s) after the Cloud API failed" % how)
                return True, msg + "\n\nWhatsApp opened with the report instead — press Send."
            return ok, msg
        how = wa.open_chat(phone, text)
        wa.log("owner_report", None, phone, True, "opened chat (%s)" % how)
        return True, "WhatsApp opened with the evening report — press Send."
    except Exception as e:
        return False, "WhatsApp: %s" % str(e)[:200]
