# ============================================================
# DayBill ERP - Invoice Designer options (v7.9)
# ------------------------------------------------------------
# Everything the Invoice Designer adds on top of "place fields on a
# page", kept in one place so the designer, the PDF renderer and the
# print engine read it the same way.
#
#   Document codes      SI · Sales Invoice, PI · Purchase Invoice …
#                       (the same short codes as the journals)
#   Design slots        ★ Default, Design 2, Design 3 per document —
#                       the Print menu offers "Print design 2 / 3"
#   Page settings       lines per page, minimum lines (blank rows keep
#                       the table a fixed height), row gap, custom paper
#                       size, pre-printed paper, ask the printer each
#                       time, graphics or text (dot-matrix) printing
#   Sections            Invoice header (page 1 only) · Page header
#                       (every page) · Details (the items) · Page footer
#                       (every page) · Invoice footer (last page only)
#   Field settings      format (amount, qty, date, UPPER, in words),
#                       hide when empty / zero, italic, underline,
#                       colour, box, max length, lock position
# ============================================================
import json
import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── document codes ────────────────────────────────────────────
CODES = {
    "sales_invoice": "SI", "pos_invoice": "POS", "sales_return": "SR",
    "purchase_invoice": "PI", "purchase_return": "PR", "quotation": "SQ",
    "purchase_order": "PO", "receipt_voucher": "RV", "payment_voucher": "PV",
}


def code_of(doc_type):
    return CODES.get(doc_type, "")


def doc_label(doc_type, label):
    """'SI · Sales Invoice'."""
    c = code_of(doc_type)
    return f"{c} · {label}" if c else label


# ── design slots ──────────────────────────────────────────────
SLOTS = (1, 2, 3)
SLOT_NAMES = {1: "★ Default", 2: "Design 2", 3: "Design 3"}
SLOT_OPTIONS = {"design2": 2, "design3": 3}      # print option → slot


def slots_of(template):
    """The slots this template holds: [1] for the ★ default, plus 2/3."""
    t = template or {}
    out = []
    if t.get("is_default"):
        out.append(1)
    try:
        s = int(t.get("design_slot") or 0)
    except (TypeError, ValueError):
        s = 0
    if s in (2, 3):
        out.append(s)
    return out


def slot_badge(template):
    return "  ".join(SLOT_NAMES[s] if s != 1 else "★ prints" for s in slots_of(template))


def set_slot(template_id, report_type, slot):
    """Make this template the ★ default (1), Design 2 or Design 3 of its
    document. One template per slot; it keeps its other slots."""
    from config.database import db
    from modules import report_designer as rd
    slot = int(slot)
    if slot == 1:
        rd.set_default(template_id, report_type)
        return True
    if slot not in (2, 3):
        return False
    db.execute("UPDATE report_templates SET design_slot=NULL WHERE report_type=? AND design_slot=?",
               (report_type, slot))
    db.execute("UPDATE report_templates SET design_slot=? WHERE template_id=?", (slot, template_id))
    return True


def clear_slot(template_id, slot):
    from config.database import db
    if int(slot) in (2, 3):
        db.execute("UPDATE report_templates SET design_slot=NULL WHERE template_id=? AND design_slot=?",
                   (template_id, int(slot)))


def template_for(report_type, slot=1):
    """The template printed for this slot (None when the slot is empty)."""
    from config.database import db
    from modules import report_designer as rd
    if int(slot or 1) == 1:
        return rd.get_default_template(report_type)
    try:
        return rd._norm(db.fetchone(
            "SELECT TOP 1 * FROM report_templates WHERE is_active=1 AND report_type=? "
            "AND design_slot=? ORDER BY template_id", (report_type, int(slot))))
    except Exception:
        return None


def free_slots(report_type):
    """Slots 2 / 3 that hold a design for this document → [2, 3]."""
    return [s for s in (2, 3) if template_for(report_type, s)]


# ── page settings ─────────────────────────────────────────────
PAGE_DEFAULTS = {
    "lines_per_page": 0,      # 0 = as many rows as fit
    "min_lines": 0,           # pad with blank rows up to this many
    "row_gap": 0.0,           # extra mm under every item row
    "custom_w": 0.0,          # paper "Custom": width / height in mm
    "custom_h": 0.0,
    "preprinted": False,      # paper already has the letterhead: no colour bands
    "ask_printer": False,     # always show the printer box
    "print_mode": "graphics", # graphics (laser / inkjet / thermal) or text (dot-matrix)
}
PRINT_MODES = {"graphics": "Graphics (laser · inkjet · thermal)",
               "text": "Text (dot-matrix)"}


def page_settings(template):
    """The template's page settings with every key present."""
    raw = (template or {}).get("page_json")
    try:
        d = json.loads(raw) if isinstance(raw, str) and raw.strip() else dict(raw or {})
    except (ValueError, TypeError):
        d = {}
    out = dict(PAGE_DEFAULTS)
    for k, dv in PAGE_DEFAULTS.items():
        v = d.get(k, dv)
        try:
            if isinstance(dv, bool):
                v = bool(v) if not isinstance(v, str) else v.strip().lower() in ("1", "true", "yes")
            elif isinstance(dv, int):
                v = max(0, int(float(v or 0)))
            elif isinstance(dv, float):
                v = max(0.0, float(v or 0))
            else:
                v = str(v or dv)
        except (TypeError, ValueError):
            v = dv
        out[k] = v
    if out["print_mode"] not in PRINT_MODES:
        out["print_mode"] = "graphics"
    return out


def page_json(settings):
    s = dict(PAGE_DEFAULTS)
    s.update({k: v for k, v in (settings or {}).items() if k in PAGE_DEFAULTS})
    return json.dumps(page_settings({"page_json": s}))


def paper_mm(template, table=None):
    """(width, height) in mm; height None = a roll that grows."""
    table = table or {"A4": (210, 297), "A5": (148, 210), "Letter": (216, 279),
                      "80mm": (80, None), "58mm": (58, None)}
    paper = str((template or {}).get("paper_size") or "A4")
    if paper == "Custom":
        s = page_settings(template)
        w = s["custom_w"] if s["custom_w"] >= 30 else 210
        h = s["custom_h"] if s["custom_h"] >= 30 else 297
        return w, h
    return table.get(paper, (210, 297))


# ── sections (bands) ──────────────────────────────────────────
BANDS = [
    ("invoice_header", "Invoice header", "page 1 only"),
    ("page_header", "Page header", "every page"),
    ("detail", "Details", "the items"),
    ("page_footer", "Page footer", "every page"),
    ("invoice_footer", "Invoice footer", "last page only"),
]
BAND_NAMES = {k: n for k, n, _w in BANDS}
REPEAT_BANDS = ("page_header", "page_footer")
BAND_COLORS = {"invoice_header": "#E0E7FF", "page_header": "#DCFCE7", "detail": "#FEF9C3",
               "page_footer": "#DCFCE7", "invoice_footer": "#FCE7F3"}


def table_rect(elements):
    """(top, bottom) of the items table in designer px, or None."""
    tops = [e for e in elements or [] if e.get("type") in ("table", "item_col")]
    if not tops:
        return None
    return (min(float(e.get("y", 0)) for e in tops),
            max(float(e.get("y", 0)) + float(e.get("h", 0)) for e in tops))


def band_of(el, elements=None, rect=None):
    """Which section a field is in: its own choice, else where it sits
    (above the items → invoice header, below → invoice footer)."""
    b = el.get("band") or "auto"
    if el.get("type") in ("table", "item_col"):
        return "detail"
    if b in BAND_NAMES:
        return b
    rect = rect if rect is not None else table_rect(elements)
    if rect is None:
        return "invoice_header"
    y = float(el.get("y", 0))
    return "invoice_header" if y + float(el.get("h", 0)) <= rect[0] + 1 else (
        "detail" if y < rect[1] and _beside(el, elements) else "invoice_footer")


def _beside(el, elements):
    cols = [e for e in elements or [] if e.get("type") in ("table", "item_col")]
    if not cols:
        return False
    x0 = min(float(e.get("x", 0)) for e in cols)
    x1 = max(float(e.get("x", 0)) + float(e.get("w", 0)) for e in cols)
    x, w = float(el.get("x", 0)), float(el.get("w", 0))
    return x >= x1 - 1 or x + w <= x0 + 1


def band_counts(elements):
    rect = table_rect(elements)
    out = {k: 0 for k, _n, _w in BANDS}
    for e in elements or []:
        out[band_of(e, elements, rect)] += 1
    return out


# ── field formats ─────────────────────────────────────────────
FORMATS = [
    ("", "As it is"),
    ("amount", "Amount  1,234.50"),
    ("amount0", "Amount, no decimals  1,235"),
    ("qty", "Quantity  12.5"),
    ("date", "Date  31-12-2026"),
    ("date_long", "Date  31 Dec 2026"),
    ("upper", "UPPER CASE"),
    ("lower", "lower case"),
    ("title", "Title Case"),
    ("words", "Amount in words"),
]
FORMAT_NAMES = dict(FORMATS)


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _date(v):
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) else v.date()
    s = str(v or "").strip()[:10]
    for f in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def is_zero(value):
    n = _num(value)
    return n is not None and abs(n) < 0.005


def format_value(value, fmt="", max_len=0):
    """The value as the field's format wants it (unknown → unchanged)."""
    s = "" if value is None else str(value)
    fmt = fmt or ""
    if fmt in ("amount", "amount0", "qty", "words"):
        n = _num(s)
        if n is not None:
            if fmt == "amount":
                s = f"{n:,.2f}"
            elif fmt == "amount0":
                s = f"{n:,.0f}"
            elif fmt == "qty":
                s = (f"{n:,.3f}".rstrip("0").rstrip(".")) or "0"
            else:
                try:
                    from modules.template_renderer import amount_in_words
                    s = amount_in_words(n) or s
                except Exception:
                    pass
    elif fmt in ("date", "date_long"):
        d = _date(s)
        if d:
            s = d.strftime("%d-%m-%Y") if fmt == "date" else d.strftime("%d %b %Y")
    elif fmt == "upper":
        s = s.upper()
    elif fmt == "lower":
        s = s.lower()
    elif fmt == "title":
        s = s.title()
    try:
        max_len = int(max_len or 0)
    except (TypeError, ValueError):
        max_len = 0
    if max_len > 0 and len(s) > max_len:
        s = s[:max(1, max_len - 1)] + "…"
    return s
