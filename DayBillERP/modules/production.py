# ============================================================
# DayBill ERP - Production entry (v7.0)
# ------------------------------------------------------------
# Making a product from its bill of materials (modules/bom.py):
#   the materials leave stock at their average cost, and the finished
#   product comes into stock at
#       (materials + labour + overhead) ÷ quantity made
#   Its average cost is worked out again the weighted-average way (its
#   purchase price is never touched).
#
# Status   draft      nothing moves (a plan — can be deleted)
#          confirmed  stock moves + the journal posts
#          cancelled  everything reversed (kept for the record)
# Changing a confirmed entry reverses it first and posts it again, so
# nothing is ever doubled — like every other DayBill document.
#
# Journal (voucher type PRD, source_type "production"):
#   Dr Inventory   finished goods (total cost)
#   Cr Inventory   materials used (at average cost)
#   Cr 5250 Production Labour & Overheads Applied   labour + overhead
#                  (+ the cost of service lines, e.g. outside work)
# so the Inventory account keeps matching stock × average cost.
#
# Stock card: inventory_transactions reference_type 'production',
#   txn_type 'production_out' (materials) / 'production_in' (made).
# Not enough stock of a material: refused, unless the setting
#   production_allow_negative is on (Settings key / company option).
#
# Tables: production_entries / production_lines
#         (database/patches/zzz_v700_production_patch.sql)
#
#   plan(product_id, qty, unit)          materials from the recipe × qty
#   get(entry_id)                        (header, lines)
#   save(header, lines, entry_id, user_id) → (entry_id, number, warning)
#   cancel(entry_id) / delete(entry_id)
#   stock_on_hand(ids, entry_id, branch) stock a run can use
#   shortfalls(lines, entry_id, branch)  materials short in stock
#   entries(date_from, date_to, status, text)
#   block_reason(entry_id, action)       why it can't be changed ('' = ok)
#   print_pdf(entry_id, path)            A4 production sheet
# ============================================================

import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db

try:
    from config import settings as cfg
except Exception:            # pragma: no cover
    cfg = None

REF = "production"                       # inventory_transactions.reference_type
SOURCE = "production"                    # journal_entries.source_type (voucher PRD)
TXN_OUT, TXN_IN = "production_out", "production_in"
APPLIED_CODE = "5250"
STATUSES = ("draft", "confirmed", "cancelled")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso(v):
    if v in (None, ""):
        return date.today().isoformat()
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("The date '%s' is not a date. Type it like %s."
                     % (s, date.today().isoformat()))


def ready():
    try:
        return db.execute_scalar("SELECT OBJECT_ID('production_entries','U')") is not None
    except Exception:
        return False


def _dp():
    from modules import doc_posting as dp
    return dp


# ── settings / accounts ───────────────────────────────────────
def _option(key):
    try:
        from modules import country
        return country.option(key)
    except Exception:
        return None


def allow_negative():
    """May a production run use more of a material than is in stock?"""
    v = _option("production_allow_negative")
    if v not in (None, ""):
        return str(v).strip().lower() in ("1", "true", "yes", "on")
    return bool(cfg.flag("production_allow_negative", False)) if cfg else False


def posts_journal():
    return bool(cfg.flag("production_post_journal", True)) if cfg else True


def prefix():
    p = str((cfg.get("production_prefix") if cfg else "") or "").strip()
    return p or "PRD"


def applied_account():
    """account_id of 'Production Labour & Overheads Applied' (5250) — made
    once when the chart of accounts does not have it yet."""
    from modules import account_defaults as ad
    for v in (ad._setting_value("default_production_applied"),
              _option("production_applied_account"),
              cfg.get("acc_production_applied") if cfg else None):
        try:
            a = ad._to_id(v) if v not in (None, "") else None
        except Exception:
            a = None
        if a:
            return a
    a = ad._id_from_code(APPLIED_CODE)
    if a:
        return a
    try:
        parent = ad._id_from_code("5000")
        db.execute("INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
                   "account_type, parent_account_id) VALUES (?,?,?,?,?)",
                   (APPLIED_CODE, "Production Labour & Overheads Applied",
                    "تكاليف العمالة والمصاريف المحملة على الإنتاج", "expense", parent))
        ad.invalidate()
        return ad._id_from_code(APPLIED_CODE)
    except Exception:
        return None


def next_number():
    from modules.doc_numbering import next_number as _nn
    try:
        return _nn("production_entries", "entry_number", prefix())
    except Exception:
        n = int(db.execute_scalar("SELECT COUNT(*) FROM production_entries") or 0) + 1
        return "%s-%06d" % (prefix(), n)


# ── the plan: materials from the recipe ───────────────────────
def _product(pid):
    return db.fetchone("SELECT product_id, product_code, product_name_en, unit_of_measure_en, "
                       "ISNULL(product_type,'product') AS product_type, "
                       "ISNULL(stock_quantity,0) AS stock_quantity, ISNULL(unit_price,0) AS unit_price "
                       "FROM products WHERE product_id=?", (int(pid),))


def plan(product_id, qty, unit_name=""):
    """What making `qty` (in `unit_name`) of the product needs, from its
    bill of materials. None when the product has no recipe.
    → {bom_id, qty_base, batches, labour_cost, overhead_cost, lines: [
         {component_id, product_code, product_name_en, qty_planned,
          qty_used, unit_name, unit_factor, is_stock, cost_each}]}
    A component made fresh (its own recipe marked "use up on sale") is
    opened up into its own materials, the same way a sale does."""
    from modules import bom
    dp = _dp()
    h = bom.header(product_id)
    if not h:
        return None
    qty_base = _f(qty) * dp.unit_factor(product_id, unit_name or "")
    out_q = _f(h.get("output_qty")) or 1.0
    out_f = dp.unit_factor(product_id, h.get("output_unit")) if h.get("output_unit") else 1.0
    batches = qty_base / (out_q * (out_f or 1.0))
    rows = {}
    order = []

    def add(cid, q, unit):
        p = _product(cid)
        if not p or q <= 0:
            return
        unit = unit or p.get("unit_of_measure_en") or "Unit"
        key = (int(cid), unit)
        if key not in rows:
            f = dp.unit_factor(cid, unit)
            rows[key] = {"component_id": int(cid), "product_code": p.get("product_code") or "",
                         "product_name_en": p.get("product_name_en") or "",
                         "qty_planned": 0.0, "unit_name": unit, "unit_factor": f,
                         "is_stock": str(p.get("product_type") or "").lower() != "service",
                         "cost_each": round(dp.unit_cost(cid) * f, 6)}
            order.append(key)
        rows[key]["qty_planned"] += q

    for ln in bom.lines(h["bom_id"]):
        cid = ln.get("component_id")
        if not cid:
            continue
        q = _f(ln.get("quantity")) * batches * (1 + _f(ln.get("waste_pct")) / 100.0)
        sub = bom.header(cid)
        if sub and (str(ln.get("product_type") or "").lower() == "service"
                    or sub.get("deduct_on_sale")):
            qb = q * dp.unit_factor(cid, ln.get("unit_name") or "")
            for c2, q2, _k in bom.explode(cid, qb, 1, stock_only=False):
                add(c2, q2, None)            # base units
            continue
        add(cid, q, ln.get("unit_name"))
    lines = []
    for key in order:
        r = rows[key]
        r["qty_planned"] = round(r["qty_planned"], 4)
        r["qty_used"] = r["qty_planned"]
        lines.append(r)
    return {"bom_id": int(h["bom_id"]), "qty_base": round(qty_base, 4), "batches": batches,
            "output_qty": out_q, "output_unit": h.get("output_unit") or "",
            "labour_cost": round(_f(h.get("labour_cost")) * batches, 2),
            "overhead_cost": round(_f(h.get("overhead_cost")) * batches, 2),
            "lines": lines}


# ── reading ───────────────────────────────────────────────────
def get(entry_id):
    h = db.fetchone("SELECT * FROM production_entries WHERE entry_id=?", (int(entry_id),))
    if not h:
        return None, []
    lines = db.fetchall("SELECT * FROM production_lines WHERE entry_id=? ORDER BY line_number",
                        (int(entry_id),)) or []
    return dict(h), [dict(l) for l in lines]


def entries(date_from=None, date_to=None, status=None, text="", limit=500):
    if not ready():
        return []
    sql = "SELECT TOP %d e.* FROM production_entries e WHERE 1=1" % int(limit)
    params = []
    if date_from:
        sql += " AND e.entry_date >= ?"
        params.append(str(date_from)[:10])
    if date_to:
        sql += " AND e.entry_date <= ?"
        params.append(str(date_to)[:10])
    if status and status in STATUSES:
        sql += " AND e.entry_status=?"
        params.append(status)
    t = str(text or "").strip()
    if t:
        sql += (" AND (e.entry_number LIKE ? OR e.product_code LIKE ? OR e.product_name_en LIKE ? "
                "OR e.notes LIKE ?)")
        params += ["%" + t + "%"] * 4
    sql += " ORDER BY e.entry_date DESC, e.entry_id DESC"
    try:
        return db.fetchall(sql, tuple(params)) or []
    except Exception:
        return []


def info(entry_id):
    """(number, status, date) of an entry."""
    try:
        r = db.fetchone("SELECT entry_number, entry_status, entry_date FROM production_entries "
                        "WHERE entry_id=?", (int(entry_id),)) or {}
    except Exception:
        r = {}
    return (str(r.get("entry_number") or entry_id), str(r.get("entry_status") or "").lower(),
            r.get("entry_date"))


def block_reason(entry_id, action="edit"):
    """'' when the entry may be changed (edit / cancel / delete), else why
    not — the same rules as the other documents (doc_edit)."""
    if not entry_id:
        return ""
    number, status, d = info(entry_id)
    if not status:
        return ""
    if status == "confirmed" and action in ("edit", "cancel"):
        try:
            from modules import doc_edit
            ok = doc_edit.allowed_posted()
        except Exception:
            ok = True
        if not ok:
            return ("%s is confirmed. Changing confirmed documents is switched off (Settings ▸ "
                    "Sales ▸ Allow edit / delete of confirmed documents)." % number)
    if status == "cancelled" and action in ("edit", "cancel"):
        return "%s is cancelled — it can't be changed." % number
    if status == "confirmed" and action == "delete":
        return ("%s is confirmed. Cancel it first (its stock and journal are reversed), "
                "then you can delete it." % number)
    try:
        from modules import financial_year as fy
        msg = fy.guard_active(str(d)[:10]) if d else ""
        if msg:
            return msg
    except Exception:
        pass
    return ""


# ── stock on hand / shortfall ─────────────────────────────────
def _branch_of(entry_id=None):
    if entry_id:
        try:
            b = db.execute_scalar("SELECT branch_id FROM production_entries WHERE entry_id=?",
                                  (int(entry_id),))
            if b:
                return int(b)
        except Exception:
            pass
    try:
        from modules import stock_branch
        return stock_branch.here()
    except Exception:
        return None


def stock_on_hand(component_ids, entry_id=None, branch_id=None):
    """{component_id: base qty a run can use} — this branch's stock when
    the shop has several branches, plus what this (confirmed) entry
    already took (it is given back before the entry is posted again)."""
    ids = sorted({int(c) for c in component_ids or [] if c})
    if not ids:
        return {}
    out = {}
    multi = False
    try:
        from modules import stock_branch as SB
        multi = SB.ready() and SB.multi()
    except Exception:
        SB = None
    if multi:
        b = branch_id or _branch_of(entry_id)
        by = SB.qty_by_branch(ids)
        for c in ids:
            out[c] = _f(by.get(c, {}).get(b))
    else:
        ph = ",".join("?" * len(ids))
        for r in db.fetchall("SELECT product_id, ISNULL(stock_quantity,0) AS q FROM products "
                             "WHERE product_id IN (%s)" % ph, tuple(ids)) or []:
            out[int(r["product_id"])] = _f(r["q"])
    if entry_id:
        try:
            for r in db.fetchall("SELECT product_id, SUM(ISNULL(qty_out_base,0)) AS q FROM "
                                 "inventory_transactions WHERE reference_type=? AND reference_id=? "
                                 "AND txn_type=? GROUP BY product_id",
                                 (REF, int(entry_id), TXN_OUT)) or []:
                if int(r["product_id"]) in out:
                    out[int(r["product_id"])] += _f(r["q"])
        except Exception:
            pass
    return {c: round(out.get(c, 0.0), 4) for c in ids}


def _need(lines):
    """{component_id: base qty used} of the stock lines."""
    dp = _dp()
    need = {}
    for ln in lines or []:
        cid = ln.get("component_id")
        if not cid:
            continue
        if not ln.get("is_stock", True) or not dp._is_stock_item(cid):
            continue
        f = _f(ln.get("unit_factor")) or dp.unit_factor(cid, ln.get("unit_name") or "")
        q = _f(ln.get("qty_used")) * f
        if q > 0:
            need[int(cid)] = need.get(int(cid), 0.0) + q
    return need


def shortfalls(lines, entry_id=None, branch_id=None, _have=None):
    """[(component_id, name, have, need)] in base units — the materials
    there is not enough of."""
    need = _need(lines)
    if not need:
        return []
    have = _have if _have is not None else stock_on_hand(list(need), entry_id, branch_id)
    out = []
    for cid, q in need.items():
        h = _f(have.get(cid))
        if h + 1e-6 < q:
            nm = next((str(l.get("product_name_en") or "") for l in lines
                       if l.get("component_id") == cid and l.get("product_name_en")), "")
            if not nm:
                try:
                    nm = db.execute_scalar("SELECT product_name_en FROM products WHERE product_id=?",
                                           (cid,)) or str(cid)
                except Exception:
                    nm = str(cid)
            out.append((cid, nm, round(h, 4), round(q, 4)))
    return out


def short_text(short):
    return "; ".join("%s (in stock %g, needs %g)" % (n, h, q) for _c, n, h, q in short)


# ── save / post ───────────────────────────────────────────────
def save(header, lines, entry_id=None, user_id=None):
    """Save (new or change) and post. header: entry_date, product_id,
    quantity, unit_name, labour_cost, overhead_cost, notes, entry_status
    ('draft' | 'confirmed'). lines: [{component_id, qty_planned, qty_used,
    unit_name, notes}]. → (entry_id, number, warning)"""
    from modules import financial_year as fy
    dp = _dp()
    if not ready():
        raise ValueError("Production needs the v7.0 database update (Updates ▸ Apply All Updates).")
    when = _iso(header.get("entry_date"))
    msg = fy.guard_active(when)
    old = None
    if entry_id:
        old, _ol = get(entry_id)
        if not old:
            raise ValueError("This production entry no longer exists.")
        if not msg:
            msg = block_reason(entry_id, "edit")
    if msg:
        raise ValueError(msg)
    pid = header.get("product_id")
    p = _product(pid) if pid else None
    if not p:
        raise ValueError("Choose the product you made.")
    if str(p.get("product_type") or "").lower() == "service":
        raise ValueError("%s is a service — only stock products can be made." % p["product_name_en"])
    from modules import bom
    bh = bom.header(pid)
    if not bh and not (old and int(old["product_id"]) == int(pid)):
        raise ValueError("%s has no Bill of Materials yet. Make one first (Production ▸ "
                         "Bill of Materials)." % p["product_name_en"])
    qty = _f(header.get("quantity"))
    if not (0 < qty < 1e9):
        raise ValueError("Type how many you made (more than 0).")
    unit = str(header.get("unit_name") or p.get("unit_of_measure_en") or "Unit")[:50]
    factor = dp.unit_factor(pid, unit)
    labour, overhead = _f(header.get("labour_cost")), _f(header.get("overhead_cost"))
    if labour < 0 or overhead < 0:
        raise ValueError("Labour and overhead can't be below 0.")
    status = "confirmed" if str(header.get("entry_status") or "").lower() == "confirmed" else "draft"
    if old and str(old.get("entry_status") or "").lower() == "confirmed":
        status = "confirmed"                 # a confirmed entry stays confirmed (Cancel undoes it)
    rows = []
    for ln in lines or []:
        cid = ln.get("component_id")
        if not cid:
            continue
        planned, used = _f(ln.get("qty_planned")), _f(ln.get("qty_used"))
        if planned < 0 or used < 0 or used >= 1e9 or planned >= 1e9:
            raise ValueError("Material quantities must be 0 or more (line %d)." % (len(rows) + 1))
        if not planned and not used:
            continue
        if int(cid) == int(pid):
            raise ValueError("The product made can't be one of its own materials.")
        c = _product(cid)
        if not c:
            raise ValueError("Material %s not found." % cid)
        u = str(ln.get("unit_name") or c.get("unit_of_measure_en") or "Unit")[:50]
        rows.append(dict(component_id=int(cid), product_code=c.get("product_code") or "",
                         product_name_en=c.get("product_name_en") or "",
                         qty_planned=round(planned, 4), qty_used=round(used, 4), unit_name=u,
                         unit_factor=dp.unit_factor(cid, u),
                         is_stock=str(c.get("product_type") or "").lower() != "service",
                         notes=str(ln.get("notes") or "")[:200] or None))
    if not any(r["qty_used"] > 0 for r in rows):
        raise ValueError("Add the materials used (at least one with a quantity).")
    try:
        from modules import branches as _br
        b_id, c_id = _br.current()
    except Exception:
        b_id = c_id = None
    from modules import posting
    warn = ""
    with db.transaction():                   # all of it, or nothing
        if entry_id:
            posting.remember_numbers((SOURCE,), entry_id)   # the journal keeps its number
        try:
            if entry_id:
                _unpost(int(entry_id))
                number = old["entry_number"]
                db.execute("UPDATE production_entries SET entry_date=?, product_id=?, product_code=?, "
                           "product_name_en=?, bom_id=?, quantity=?, unit_name=?, unit_factor=?, "
                           "qty_base=?, entry_status=?, labour_cost=?, overhead_cost=?, notes=?, "
                           "updated_at=GETDATE() WHERE entry_id=?",
                           (when, int(pid), p.get("product_code"), p.get("product_name_en"),
                            (bh or {}).get("bom_id") or old.get("bom_id"), qty, unit, factor,
                            round(qty * factor, 4), status, round(labour, 2), round(overhead, 2),
                            (header.get("notes") or "")[:500] or None, int(entry_id)))
                db.execute("DELETE FROM production_lines WHERE entry_id=?", (int(entry_id),))
            else:
                number = next_number()
                db.execute("INSERT INTO production_entries (entry_number, entry_date, product_id, "
                           "product_code, product_name_en, bom_id, quantity, unit_name, unit_factor, "
                           "qty_base, entry_status, labour_cost, overhead_cost, notes, branch_id, "
                           "counter_id, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (number, when, int(pid), p.get("product_code"), p.get("product_name_en"),
                            (bh or {}).get("bom_id"), qty, unit, factor, round(qty * factor, 4),
                            status, round(labour, 2), round(overhead, 2),
                            (header.get("notes") or "")[:500] or None, b_id, c_id, user_id))
                entry_id = db.last_identity("production_entries", "entry_id")
            for i, r in enumerate(rows, 1):
                each = round(dp.unit_cost(r["component_id"]) * r["unit_factor"], 6)
                db.execute("INSERT INTO production_lines (entry_id, line_number, component_id, "
                           "product_code, product_name_en, qty_planned, qty_used, unit_name, "
                           "unit_factor, is_stock, cost_each, line_cost, notes) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (int(entry_id), i, r["component_id"], r["product_code"],
                            r["product_name_en"], r["qty_planned"], r["qty_used"], r["unit_name"],
                            r["unit_factor"], 1 if r["is_stock"] else 0, each,
                            round(each * r["qty_used"], 2), r["notes"]))
            _totals(int(entry_id))
            if status == "confirmed":
                warn = _post(int(entry_id))
        finally:
            posting.forget_numbers((SOURCE,), entry_id)
    try:
        from modules.doc_actions import audit
        audit("edit" if old else "add", "production", int(entry_id),
              "%s · %s × %g %s (%s)" % (number, p.get("product_name_en"), qty, unit, status))
    except Exception:
        pass
    return int(entry_id), number, warn


def _totals(entry_id):
    """Header costs from the lines (a draft shows today's costs)."""
    h = db.fetchone("SELECT qty_base, unit_factor, labour_cost, overhead_cost FROM "
                    "production_entries WHERE entry_id=?", (entry_id,)) or {}
    mat = _f(db.execute_scalar("SELECT ISNULL(SUM(line_cost),0) FROM production_lines "
                               "WHERE entry_id=?", (entry_id,)))
    total = round(mat + _f(h.get("labour_cost")) + _f(h.get("overhead_cost")), 2)
    qb = _f(h.get("qty_base"))
    each = (total / qb * (_f(h.get("unit_factor")) or 1.0)) if qb else 0.0
    db.execute("UPDATE production_entries SET material_cost=?, total_cost=?, unit_cost=? "
               "WHERE entry_id=?", (round(mat, 2), total, round(each, 6), entry_id))
    return total


def _stock_row(pid):
    r = db.fetchone("SELECT ISNULL(stock_quantity,0) AS q, ISNULL(average_cost,0) AS a "
                    "FROM products WHERE product_id=?", (pid,)) or {}
    return _f(r.get("q")), _f(r.get("a"))


def _post(entry_id):
    """Move the stock and post the journal of a CONFIRMED entry (call
    after _unpost). Raises ValueError when it can't (stock short, journal
    refused) — the caller's transaction then keeps nothing."""
    dp = _dp()
    h, lines = get(entry_id)
    if not h or str(h.get("entry_status") or "").lower() != "confirmed":
        return ""
    tdate = _iso(h.get("entry_date"))
    num = str(h.get("entry_number") or "")
    pid = int(h["product_id"])
    branch = h.get("branch_id") or _branch_of(None)
    warn = []
    short = shortfalls(lines, None, branch)
    if short:
        if not allow_negative():
            raise ValueError("Not enough stock to make this: %s.\n\nBuy or move the stock in first, "
                             "or change the quantity used." % short_text(short))
        warn.append("stock went below 0: " + short_text(short))
    try:
        from modules import batches as _bt
    except Exception:
        _bt = None
    what = str(h.get("product_name_en") or h.get("product_code") or pid)
    mat_stock = mat_other = 0.0
    for ln in lines:
        cid = int(ln["component_id"])
        used = _f(ln.get("qty_used"))
        f = _f(ln.get("unit_factor")) or dp.unit_factor(cid, ln.get("unit_name") or "")
        base_cost = dp.unit_cost(cid)
        each = round(base_cost * f, 6)
        lc = round(each * used, 2)
        stock_item = dp._is_stock_item(cid)
        db.execute("UPDATE production_lines SET cost_each=?, line_cost=?, unit_factor=?, is_stock=? "
                   "WHERE line_id=?", (each, lc, f, 1 if stock_item else 0, ln["line_id"]))
        qb = used * f
        if not stock_item:                   # a service: its cost only, no stock
            mat_other += lc
            continue
        if qb <= 0:
            continue
        db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) - ? "
                   "WHERE product_id=?", (qb, cid))
        bal = _stock_row(cid)[0]
        db.execute(
            "INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type, "
            "reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base, "
            "balance_base, unit_cost, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, tdate, TXN_OUT, REF, entry_id, ln.get("unit_name") or "Unit", 0, 0, used,
             round(qb, 4), bal, round(base_cost, 4), ("%s · used for %s" % (num, what))[:300]))
        mat_stock += lc
        if _bt is not None:
            try:
                _bt.consume(cid, qb, REF, entry_id, branch)
            except Exception:
                pass
    mat_stock, mat_other = round(mat_stock, 2), round(mat_other, 2)
    labour, overhead = round(_f(h.get("labour_cost")), 2), round(_f(h.get("overhead_cost")), 2)
    total = round(mat_stock + mat_other + labour + overhead, 2)
    qty_base = _f(h.get("qty_base"))
    cost_base = total / qty_base if qty_base else 0.0
    # ── the finished product comes in ──
    old_q, old_a = _stock_row(pid)
    new_q = old_q + qty_base
    if cost_base > 0:
        if old_a <= 0 or old_q <= 0 or new_q <= 0:
            new_a = cost_base
        else:
            new_a = (old_q * old_a + qty_base * cost_base) / new_q
        db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) + ?, "
                   "average_cost=? WHERE product_id=?", (qty_base, round(new_a, 4), pid))
    else:
        db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) + ? "
                   "WHERE product_id=?", (qty_base, pid))
    q2, a2 = _stock_row(pid)
    db.execute(
        "INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type, "
        "reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base, "
        "balance_base, unit_cost, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, tdate, TXN_IN, REF, entry_id, h.get("unit_name") or "Unit", _f(h.get("quantity")),
         round(qty_base, 4), 0, 0, q2, round(cost_base, 4), ("%s · made" % num)[:300]))
    if _bt is not None:
        try:
            if _bt.tracked(pid):
                _bt.receive(pid, qty_base, REF, entry_id, num, None, branch, cost_base, tdate)
        except Exception:
            pass
    try:
        from modules import stock_branch as _sb
        _sb.stamp_doc(REF, entry_id, branch)
    except Exception:
        pass
    db.execute("UPDATE production_entries SET material_cost=?, total_cost=?, unit_cost=?, "
               "fg_avg_before=?, fg_avg_after=?, fg_stock_after=?, confirmed_at=GETDATE() "
               "WHERE entry_id=?",
               (round(mat_stock + mat_other, 2), total,
                round(cost_base * (_f(h.get("unit_factor")) or 1.0), 6),
                round(old_a, 4), round(a2, 4), round(q2, 4), entry_id))
    # ── the journal ──
    from modules import posting
    if posts_journal() and posting.enabled() and total > 0:
        from modules import account_defaults as ad
        inv = ad.inventory()
        app = applied_account() if (mat_other + labour + overhead) > 0 else None
        made = "%s × %g %s" % (what, _f(h.get("quantity")), h.get("unit_name") or "")
        jl = [(inv, total, 0, ("Made: " + made)[:200]),
              (inv, 0, mat_stock, "Materials used"),
              (app, 0, round(mat_other + labour + overhead, 2), "Labour & overheads applied")]
        jid = posting.post_journal(tdate, ("Production %s · %s" % (num, made))[:250], jl,
                                   SOURCE, entry_id, reference=num)
        if not jid:
            raise ValueError("Not saved — the journal was not posted: %s"
                             % (posting.last_error or "unknown reason"))
    return "; ".join(warn)


def _unpost(entry_id):
    """Undo everything the entry did: stock (and average costs) back,
    batches, its journal. Exact: the finished product's average cost goes
    back to what it was when nothing moved since."""
    h, lines = get(entry_id)
    if not h:
        return
    try:
        rows = db.fetchall("SELECT txn_id, product_id, txn_type, ISNULL(qty_in_base,0) AS qin, "
                           "ISNULL(qty_out_base,0) AS qout, ISNULL(unit_cost,0) AS cost FROM "
                           "inventory_transactions WHERE reference_type=? AND reference_id=?",
                           (REF, int(entry_id))) or []
    except Exception:
        rows = []
    each = {}
    for ln in lines:                         # the exact cost each material left with
        f = _f(ln.get("unit_factor")) or 1.0
        each[int(ln["component_id"])] = _f(ln.get("cost_each")) / f
    qb_h = _f(h.get("qty_base"))
    fg_cost = (_f(h.get("total_cost")) / qb_h) if qb_h else 0.0
    for r in rows:
        pid = r.get("product_id")
        qin, qout = _f(r["qin"]), _f(r["qout"])
        if not pid:
            continue
        q, a = _stock_row(pid)
        if qin > 0:                          # the finished product goes back out
            new_a = a
            if (h.get("fg_avg_before") is not None and h.get("fg_stock_after") is not None
                    and abs(q - _f(h.get("fg_stock_after"))) < 1e-6
                    and abs(a - _f(h.get("fg_avg_after"))) < 1e-6):
                new_a = _f(h.get("fg_avg_before"))          # nothing moved since: exact
            else:
                c = fg_cost or _f(r["cost"])
                rest = q - qin
                if c > 0 and rest > 0 and a > 0:
                    x = (q * a - qin * c) / rest
                    if x > 0:
                        new_a = x
            db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) - ?, "
                       "average_cost=? WHERE product_id=?", (qin, round(new_a, 4), pid))
        if qout > 0:                         # the materials come back in
            c = each.get(int(pid)) or _f(r["cost"])
            new_q = q + qout
            if c > 0 and a > 0 and abs(c - a) > 1e-6 and new_q > 0:
                new_a = c if q <= 0 else (q * a + qout * c) / new_q
                db.execute("UPDATE products SET average_cost=? WHERE product_id=?",
                           (round(new_a, 4), pid))
            db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) + ? "
                       "WHERE product_id=?", (qout, pid))
    if rows:
        db.execute("DELETE FROM inventory_transactions WHERE reference_type=? AND reference_id=?",
                   (REF, int(entry_id)))
    try:
        from modules import batches as _bt
        _bt.reverse(REF, int(entry_id))
    except Exception:
        pass
    db.execute("DELETE FROM journal_lines WHERE journal_id IN (SELECT journal_id FROM "
               "journal_entries WHERE source_type=? AND source_id=?)", (SOURCE, int(entry_id)))
    db.execute("DELETE FROM journal_entries WHERE source_type=? AND source_id=?",
               (SOURCE, int(entry_id)))
    db.execute("UPDATE production_entries SET fg_avg_before=NULL, fg_avg_after=NULL, "
               "fg_stock_after=NULL WHERE entry_id=?", (int(entry_id),))


def cancel(entry_id):
    """Cancel a production entry: stock and journal reversed, the entry
    kept as 'cancelled'. → number"""
    number, status, _d = info(entry_id)
    if not status:
        raise ValueError("This production entry no longer exists.")
    why = block_reason(entry_id, "cancel")
    if why:
        raise ValueError(why)
    with db.transaction():
        _unpost(int(entry_id))
        db.execute("UPDATE production_entries SET entry_status='cancelled', cancelled_at=GETDATE(), "
                   "updated_at=GETDATE() WHERE entry_id=?", (int(entry_id),))
    try:
        from modules.doc_actions import audit
        audit("cancel", "production", int(entry_id), "%s (was %s)" % (number, status))
    except Exception:
        pass
    return number


def delete(entry_id):
    """Delete a draft (or cancelled) entry. → number"""
    number, status, _d = info(entry_id)
    if not status:
        raise ValueError("This production entry no longer exists.")
    why = block_reason(entry_id, "delete")
    if why:
        raise ValueError(why)
    with db.transaction():
        _unpost(int(entry_id))               # nothing to undo for a draft — safe anyway
        db.execute("DELETE FROM production_lines WHERE entry_id=?", (int(entry_id),))
        db.execute("DELETE FROM production_entries WHERE entry_id=?", (int(entry_id),))
    try:
        from modules.doc_actions import audit
        audit("delete", "production", int(entry_id), "%s (%s)" % (number, status))
    except Exception:
        pass
    return number


# ── print: A4 production sheet ────────────────────────────────
def print_pdf(entry_id, path):
    """The production entry on A4: product made, materials planned /
    used, costs. → path"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    h, lines = get(entry_id)
    if not h:
        raise ValueError("This production entry no longer exists.")
    font, bold = "Helvetica", "Helvetica-Bold"
    shape = None
    try:
        from modules import pdf_invoice as _pi
        _pi._register_fonts()
        font = getattr(_pi, "_AR_FONT", None) or font
        bold = getattr(_pi, "_AR_FONT_BOLD", None) or font
        shape = getattr(_pi, "_shape_arabic", None)
    except Exception:
        pass

    def t(s):
        s = "" if s is None else str(s)
        if shape and any("؀" <= ch <= "ۿ" for ch in s):
            try:
                return shape(s)
            except Exception:
                return s
        return s
    try:
        from modules import country
        money = lambda x: country.money(x, sym=True)          # noqa: E731
    except Exception:
        money = lambda x: "{:,.2f}".format(_f(x))              # noqa: E731

    def num(x, dec=3):
        s_ = ("{:,.%df}" % dec).format(_f(x))
        return s_.rstrip("0").rstrip(".") if "." in s_ else s_

    def each(x):
        s_ = "{:,.4f}".format(_f(x))
        return s_[:-2] if s_.endswith("00") else s_.rstrip("0")
    try:
        company = dict(db.fetchone("SELECT TOP 1 * FROM company ORDER BY company_id") or {})
    except Exception:
        company = {}
    accent = colors.HexColor("#0F766E")
    W, H = A4
    m = 16 * mm
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle("Production %s" % h.get("entry_number"))

    def band():
        c.setFillColor(accent)
        c.rect(0, H - 30 * mm, W, 30 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(bold, 15)
        c.drawString(m, H - 13 * mm, t(company.get("company_name_en") or "DayBill ERP"))
        c.setFont(bold, 13)
        c.drawRightString(W - m, H - 13 * mm, "PRODUCTION ENTRY")
        c.setFont(font, 9)
        c.drawRightString(W - m, H - 19 * mm, "No: %s" % h.get("entry_number"))
        try:
            d = cfg.fmt_date(h.get("entry_date")) if cfg else str(h.get("entry_date"))[:10]
        except Exception:
            d = str(h.get("entry_date"))[:10]
        c.drawRightString(W - m, H - 24 * mm, "Date: %s   ·   %s" % (d, str(h.get("entry_status") or "").title()))

    band()
    y = H - 40 * mm
    c.setFillColor(colors.HexColor("#888"))
    c.setFont(bold, 8)
    c.drawString(m, y, "PRODUCT MADE")
    y -= 6 * mm
    c.setFillColor(colors.HexColor("#222"))
    c.setFont(bold, 12)
    c.drawString(m, y, t("%s  %s" % (h.get("product_code") or "", h.get("product_name_en") or "")))
    c.drawRightString(W - m, y, "%s %s" % (num(h.get("quantity")), t(h.get("unit_name") or "")))
    y -= 9 * mm
    cols = [("#", m, "l"), ("Material", m + 9 * mm, "l"), ("Planned", W - 104 * mm, "r"),
            ("Used", W - 84 * mm, "r"), ("Unit", W - 80 * mm, "l"),
            ("Cost each", W - 40 * mm, "r"), ("Line cost", W - m, "r")]

    def head(yy):
        c.setFillColor(accent)
        c.rect(m, yy - 7 * mm, W - 2 * m, 7 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(bold, 8)
        for name, x, al in cols:
            (c.drawRightString if al == "r" else c.drawString)(x, yy - 5 * mm, name)
        return yy - 7 * mm

    y = head(y)
    for i, ln in enumerate(lines, 1):
        if y < 75 * mm:
            c.showPage()
            band()
            y = head(H - 38 * mm)
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#F3F7F6"))
            c.rect(m, y - 7 * mm, W - 2 * m, 7 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#222"))
        c.setFont(font, 9)
        c.drawString(cols[0][1], y - 5 * mm, str(i))
        c.drawString(cols[1][1], y - 5 * mm, t(str(ln.get("product_name_en") or ""))[:44])
        c.drawRightString(cols[2][1], y - 5 * mm, num(ln.get("qty_planned")))
        c.drawRightString(cols[3][1], y - 5 * mm, num(ln.get("qty_used")))
        c.drawString(cols[4][1], y - 5 * mm, t(str(ln.get("unit_name") or ""))[:12])
        c.drawRightString(cols[5][1], y - 5 * mm, each(ln.get("cost_each")))
        c.drawRightString(cols[6][1], y - 5 * mm, "{:,.2f}".format(_f(ln.get("line_cost"))))
        y -= 7 * mm
    if y - 52 * mm < 46 * mm:                # the cost box needs room above the signatures
        c.showPage()
        band()
        y = H - 38 * mm
    y -= 6 * mm
    bx = W - m - 80 * mm
    for label, val, big in (("Materials", h.get("material_cost"), False),
                            ("Labour", h.get("labour_cost"), False),
                            ("Overhead", h.get("overhead_cost"), False),
                            ("TOTAL COST", h.get("total_cost"), True),
                            ("Cost of 1 %s" % (h.get("unit_name") or "unit"), h.get("unit_cost"), False)):
        if big:
            c.setFillColor(accent)
            c.rect(bx, y - 8 * mm, 80 * mm, 8 * mm, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont(bold, 11)
            c.drawString(bx + 3 * mm, y - 6 * mm, label)
            c.drawRightString(W - m - 3 * mm, y - 6 * mm, money(val))
            y -= 9 * mm
        else:
            c.setFillColor(colors.HexColor("#444"))
            c.setFont(font, 10)
            c.drawString(bx + 3 * mm, y - 5 * mm, t(label))
            c.drawRightString(W - m - 3 * mm, y - 5 * mm, money(val))
            y -= 6 * mm
    if h.get("notes"):
        c.setFillColor(colors.HexColor("#444"))
        c.setFont(bold, 8)
        c.drawString(m, y - 2 * mm, "Notes")
        c.setFont(font, 9)
        c.drawString(m, y - 7 * mm, t(str(h["notes"]))[:110])
    sig = 40 * mm
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.6)
    c.line(m, sig, m + 55 * mm, sig)
    c.line(W - m - 55 * mm, sig, W - m, sig)
    c.setFont(font, 8)
    c.setFillColor(colors.HexColor("#888"))
    c.drawString(m, sig - 4 * mm, "Made by")
    c.drawString(W - m - 55 * mm, sig - 4 * mm, "Checked by")
    c.setFont(font, 7)
    c.setFillColor(colors.HexColor("#999"))
    c.drawCentredString(W / 2, 12 * mm, "Generated by DayBill ERP")
    c.showPage()
    c.save()
    return path
