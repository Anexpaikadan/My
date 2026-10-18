# ============================================================
# DayBill ERP — Dot-Matrix (impact printer) invoice
# ------------------------------------------------------------
# Dot-matrix / impact printers (Epson LX/FX, TVS MSP, OKI ML,
# etc.) print fastest and cleanest from PLAIN TEXT, not from a
# rendered PDF. This module builds a monospaced, fixed-width
# text invoice and can:
#   • save it as a .txt file, and
#   • send it straight to the printer as raw text (Windows RAW
#     spooler, or lp/cat on Linux/Mac), optionally wrapped in a
#     few ESC/P control codes (condensed mode, cut, form-feed).
#
# Continuous-form widths supported: 80 columns (typical narrow
# carriage) and 132 columns (wide carriage). The layout adapts.
# ============================================================

from datetime import datetime


# ── ESC/P control codes (safe on most impact printers) ──────
ESC = b"\x1b"
INIT        = ESC + b"@"            # reset printer
CONDENSED   = ESC + b"\x0f"         # 17 cpi (fits 132 cols on narrow)
CONDENSED_OFF = b"\x12"
DRAFT       = ESC + b"x" + b"\x00"  # draft (fast) quality
EMPH_ON     = ESC + b"E"
EMPH_OFF    = ESC + b"F"
FORM_FEED   = b"\x0c"


def _money(x):
    try:
        from modules import country as _K
        return _K.num(x)
    except Exception:
        pass
    try:
        return f"{float(x or 0):,.2f}"
    except Exception:
        return "0.00"


def _k():
    """v7.0: (currency for a plain-text printer, tax word, tax-number label,
    country code) of the company's country."""
    try:
        from modules import country as _K
        sym = _K.symbol()
        if not sym.isascii():
            sym = "Rs." if _K.is_in() else _K.currency_code()
        return sym, _K.tax_name(), _K.tax_no_label(), _K.code()
    except Exception:
        return "SAR", "VAT", "VAT No", "SA"


def _line(char="-", width=80):
    return char * width


def _row(cols, widths, aligns):
    """Format one fixed-width row. cols/widths/aligns are parallel
    lists; text is clipped/padded to each width."""
    out = []
    for text, w, a in zip(cols, widths, aligns):
        s = str(text)[:w]
        if a == "r":
            out.append(s.rjust(w))
        elif a == "c":
            out.append(s.center(w))
        else:
            out.append(s.ljust(w))
    return " ".join(out)


# ── Template system ──────────────────────────────────────────
# A dot-matrix template = named dict stored in app settings:
#   { "id","name","width":80|132, "items_per_page":0(=no limit),
#     "sections":[ordered enabled section keys], "terms_text":str }
# Section order in the list == print order on paper.

ALL_SECTIONS = [
    ("header",    "Company header"),
    ("title",     "TAX INVOICE title bar"),
    ("meta",      "Invoice no / date / customer"),
    ("items",     "Products table"),
    ("totals",    "Totals block"),
    ("words",     "Amount in words"),
    ("balance",   "Party ledger balance"),
    ("payinfo",   "Paid / balance of this invoice"),
    ("terms",     "Payment terms"),
    ("summary",   "Item count summary"),
    ("signature", "Signature lines"),
    ("footer",    "ZATCA note + print time"),
]

DEFAULT_TEMPLATE = {
    "id": "dm_default", "name": "Default", "width": 80, "items_per_page": 0,
    "sections": ["header", "title", "meta", "items", "totals",
                 "summary", "footer"],
    "terms_text": "",
}


def get_templates():
    """All saved dot-matrix templates (always includes the default)."""
    try:
        import json
        from config import settings as cfg
        saved = json.loads(cfg.get("dotmatrix_templates", "[]") or "[]")
        saved = [t for t in saved if t.get("id") and t.get("name")]
    except Exception:
        saved = []
    return [dict(DEFAULT_TEMPLATE)] + saved


def get_active_template():
    try:
        from config import settings as cfg
        tid = str(cfg.get("dotmatrix_template_active", "dm_default"))
    except Exception:
        tid = "dm_default"
    for t in get_templates():
        if t["id"] == tid:
            tt = dict(DEFAULT_TEMPLATE); tt.update(t)
            return tt
    return dict(DEFAULT_TEMPLATE)


def _printable(text):
    """Dot-matrix printers use code page 437 — Arabic would print as ???."""
    if not text:
        return False
    try:
        str(text).encode("cp437")
        return True
    except UnicodeEncodeError:
        return False


def build_voucher_text(company, title, number, date_text, party_label, party_name,
                       amount, method="", narration="", width=80, extra=None):
    """Receipt / payment voucher as fixed-width text for dot-matrix."""
    W = 132 if int(width or 80) >= 132 else 80
    out = []

    def center(s):
        out.append(str(s).center(W))

    def left(s):
        out.append(str(s)[:W])
    center(company.get("company_name_en", ""))
    if company.get("vat_registration_no"):
        center(_k()[2] + ": " + str(company["vat_registration_no"]))
    out.append(_line("=", W)); center(title); out.append(_line("=", W))
    left(f"{'Number':<14}: {number}")
    left(f"{'Date':<14}: {date_text}")
    left(f"{party_label[:14]:<14}: {party_name}")
    if method:
        left(f"{'Method':<14}: {method}")
    for k_, v_ in extra or []:
        if v_:
            left(f"{str(k_)[:14]:<14}: {v_}")
    out.append(_line("-", W))
    left(f"{'AMOUNT (%s):' % _k()[0]:>{W-20}} {_money(amount):>18}")
    try:
        from modules.print_prefs import amount_in_words
        words = amount_in_words(amount)
    except Exception:
        words = ""
    if words:
        import textwrap
        for seg in textwrap.wrap("In words: " + words, W):
            left(seg)
    if narration:
        import textwrap
        for seg in textwrap.wrap("Narration: " + str(narration), W):
            left(seg)
    out.append(_line("-", W))
    out.append(""); out.append("")
    half = W // 2
    out.append(("_" * 24).ljust(half) + ("_" * 24).rjust(W - half))
    out.append("Received / Paid by".ljust(half) + "Authorized Signature".rjust(W - half))
    out.append("")
    return "\n".join(out) + "\n"


def _party_balance(invoice):
    """(previous_balance, net_balance) for the invoice's customer from
    vw_customer_balance; falls back to document sums. None if unknown."""
    cid = invoice.get("customer_id")
    if not cid:
        return None
    try:
        from config.database import db
        bal = db.execute_scalar(
            "SELECT ISNULL(balance_due,0) FROM vw_customer_balance "
            "WHERE customer_id=?", (cid,))
        if bal is None:
            bal = db.execute_scalar(
                "SELECT ISNULL(SUM(total_amount - ISNULL(paid_amount,0)),0) "
                "FROM sales_invoices WHERE customer_id=? "
                "AND invoice_status <> 'cancelled'", (cid,))
        net = float(bal or 0)
        this_due = float(invoice.get("total_amount", 0) or 0) - \
            float(invoice.get("paid_amount", 0) or 0)
        return net - this_due, net
    except Exception:
        return None


def build_invoice_text(invoice, company, lines, width=80, template=None, labels=None):
    """Return the invoice as plain fixed-width text, laid out by the
    active dot-matrix template (section order, items-per-page, extras).
    Pages are separated by form-feed (\\f) when items_per_page is set.
    labels: for other documents (purchase, returns, quotation, PO) —
    {"title", "number", "party", "zatca": False}."""
    lab = {"title": "TAX INVOICE", "number": "Invoice #", "party": "Customer",
           "zatca": True}
    lab.update(labels or {})
    tpl = dict(template) if template else get_active_template()
    W = 132 if int(tpl.get("width", width) or width) >= 132 else 80
    ipp = int(tpl.get("items_per_page", 0) or 0)
    sections = [s for s in tpl.get("sections", DEFAULT_TEMPLATE["sections"])
                if s in dict(ALL_SECTIONS)]
    if "items" not in sections:                    # items are mandatory
        sections.insert(0, "items")
    out = []

    def center(s):
        out.append(str(s).center(W))

    def left(s):
        out.append(str(s)[:W])

    # ── section renderers ──
    def sec_header():
        center(company.get("company_name_en", lab["title"]))
        if _printable(company.get("company_name_ar")):
            center(company.get("company_name_ar"))
        addr = " ".join(str(company.get(k, "")) for k in
                        ("building_number", "street_name_en", "district_en",
                         "city_en") if company.get(k))
        if addr:
            center(addr)
        if company.get("vat_registration_no"):
            center(_k()[2] + ": " + str(company["vat_registration_no"]))
        if company.get("cr_number"):
            center({"AE": "Trade Licence", "IN": "PAN"}.get(_k()[3], "CR No") + ": " + str(company["cr_number"]))

    def sec_title():
        out.append(_line("=", W))
        center(lab["title"])
        out.append(_line("=", W))

    def sec_meta():
        num = invoice.get("invoice_number", "")
        d = invoice.get("invoice_date", "")
        try:
            from config import settings as _cf
            d = _cf.fmt_date(d)
        except Exception:
            d = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        left(f"{lab['number'][:9]:<9}: {num}")
        left(f"{'Date':<9}: {d}")
        left(f"{lab['party'][:9]:<9}: {invoice.get('customer_name_en') or 'Cash Customer'}")
        for k_, v_ in lab.get("extra") or []:
            if v_:
                left(f"{str(k_)[:9]:<9}: {v_}")
        if invoice.get("payment_method"):
            left(f"Payment  : {invoice['payment_method']}")
        out.append(_line("-", W))

    if W >= 132:
        widths = [4, 58, 8, 14, 8, 16, 18]
    else:
        widths = [3, 28, 5, 9, 5, 10, 11]
    _tw = _k()[1]
    heads = ["#", "Description", "Qty", "Price", _tw + "%", _tw, "Total"]
    aligns = ["r", "l", "r", "r", "r", "r", "r"]

    def items_header():
        out.append(_row(heads, widths, aligns))
        out.append(_line("-", W))

    def item_row(i, ln):
        out.append(_row([
            i, ln.get("product_name_en", ""),
            f"{float(ln.get('quantity', 0)):g}",
            _money(ln.get("unit_price", 0)),
            f"{float(ln.get('vat_rate', 15)):g}",
            _money(ln.get("vat_amount", 0)),
            _money(ln.get("line_total", 0)),
        ], widths, aligns))

    def sec_items():
        items_header()
        page_head = [s for s in ("header", "title", "meta")
                     if s in sections]   # repeated on every page
        for i, ln in enumerate(lines, 1):
            if ipp > 0 and i > 1 and (i - 1) % ipp == 0:
                out.append(_line("-", W))
                left(f"Continued on next page …  ({i - 1}/{len(lines)} items)")
                out.append("\f")                    # form feed = new page
                for s in page_head:
                    RENDER[s]()
                items_header()
            item_row(i, ln)
        out.append(_line("-", W))

    def total_line(label, value):
        left(f"{label:>{W-20}} {_money(value):>18}")

    def sec_totals():
        total_line("Subtotal:", invoice.get("subtotal_amount",
                                            invoice.get("taxable_amount", 0)))
        if float(invoice.get("discount_amount", 0) or 0):
            total_line("Discount:", invoice.get("discount_amount", 0))
        _sym, _tw, _tl, _cc = _k()
        if _cc == "IN":                     # India: CGST + SGST, or IGST
            from modules import country as _K
            _pos = _K.place_of_supply("sales", invoice)
            _sp = _K.gst_split(invoice.get("vat_amount", 0), _pos)
            if _sp["igst"]:
                total_line("IGST:", _sp["igst"])
            else:
                total_line("CGST:", _sp["cgst"])
                total_line(_K.tax_head_label("sgst") + ":", _sp["sgst"])
        else:
            total_line(_tw + ":", invoice.get("vat_amount", 0))
        out.append(_line("=", W))
        total_line("GRAND TOTAL (%s):" % _k()[0], invoice.get("total_amount", 0))
        out.append(_line("=", W))

    def sec_words():
        try:
            from modules.print_prefs import amount_in_words
            words = amount_in_words(invoice.get("total_amount", 0))
        except Exception:
            words = ""
        if words:
            left("Amount in words:")
            import textwrap
            for seg in textwrap.wrap(words, W - 2):
                left("  " + seg)

    def sec_balance():
        pb = _party_balance(invoice) if lab.get("zatca") else None
        if pb is None:
            return
        prev, net = pb
        left(f"{'Previous Balance:':>{W-20}} {_money(prev):>18}")
        left(f"{'This Invoice Due:':>{W-20}} "
             f"{_money(float(invoice.get('total_amount', 0) or 0) - float(invoice.get('paid_amount', 0) or 0)):>18}")
        left(f"{'NET BALANCE (%s):' % _k()[0]:>{W-20}} {_money(net):>18}")
        out.append(_line("-", W))

    def sec_payinfo():
        paid = float(invoice.get("paid_amount", 0) or 0)
        bal = float(invoice.get("total_amount", 0) or 0) - paid
        left(f"{'Paid:':>{W-20}} {_money(paid):>18}")
        left(f"{'Balance:':>{W-20}} {_money(bal):>18}")

    def sec_terms():
        txt = str(tpl.get("terms_text", "") or "").strip()
        if not txt:
            return
        left("Payment Terms:")
        import textwrap
        for para in txt.splitlines():
            for seg in textwrap.wrap(para, W - 2):
                left("  " + seg)

    def sec_summary():
        total_qty = sum(float(l.get("quantity", 0) or 0) for l in lines)
        names = {}
        for l in lines:
            n = l.get("product_name_en", "")
            names[n] = names.get(n, 0) + 1
        reps = [f"{n} x{c}" for n, c in names.items() if c > 1]
        left(f"Items: {len(lines)} lines · {len(names)} products · qty {total_qty:g}")
        if reps:
            left("Repeated: " + ", ".join(reps[:5]))

    def sec_signature():
        out.append("")
        out.append("")
        half = W // 2
        out.append(("_" * 24).ljust(half) + ("_" * 24).rjust(W - half))
        out.append("Receiver's Signature".ljust(half) +
                   "Authorized Signature".rjust(W - half))

    def sec_footer():
        out.append("")
        if lab.get("zatca"):
            center("This is a ZATCA-compliant electronic tax invoice")
        try:
            from config import settings as _cf
            center(f"Printed {_cf.fmt_datetime(datetime.now())}")
        except Exception:
            center(f"Printed {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        out.append("")

    RENDER = {"header": sec_header, "title": sec_title, "meta": sec_meta,
              "items": sec_items, "totals": sec_totals, "words": sec_words,
              "balance": sec_balance, "payinfo": sec_payinfo,
              "terms": sec_terms, "summary": sec_summary,
              "signature": sec_signature, "footer": sec_footer}

    for s in sections:
        RENDER[s]()
    return "\n".join(out) + "\n"
