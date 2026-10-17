# ============================================================
# DayBill ERP - Document posting engine (stock + accounts)
# ------------------------------------------------------------
# ONE place that decides what a sales invoice / POS bill, purchase,
# sales return or purchase return does to STOCK and to the BOOKS.
#
#   sync(kind, doc_id)   -> undo whatever the document did before, then
#                           re-apply it from its current lines if it is
#                           CONFIRMED. Safe to call any number of times
#                           (save, edit, confirm, cancel all call it).
#   remove(kind, doc_id) -> undo everything (call before a delete).
#
# Rules (same for every document type):
#   draft      -> no stock movement, no journal
#   confirmed  -> stock moves + journal posts (+ cost of goods sold)
#   cancelled  -> everything reversed
#
# What a document did is recorded in inventory_transactions
# (reference_type / reference_id) and journal_entries (source_type /
# source_id), so undo is exact even after the lines change.
#
#   SALE     : Dr Cash/Bank/Customer | Cr Sales + Cr VAT (+/- round-off)
#              Dr Cost of Goods Sold | Cr Inventory     (at average cost)
#   PURCHASE : Dr Inventory + Dr VAT input | Cr Cash/Bank/Supplier
#   S.RETURN : Dr Sales Returns + Dr VAT | Cr Cash/Customer
#              Dr Inventory | Cr Cost of Goods Sold
#   P.RETURN : Dr Cash/Supplier | Cr Inventory + Cr VAT input
# ============================================================

import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db, TransactionLost

try:
    from config import settings as cfg
except Exception:            # pragma: no cover
    cfg = None


KINDS = {
    "sales": dict(table="sales_invoices", id="invoice_id",
                  lines="sales_invoice_lines", status="invoice_status",
                  date="invoice_date", number="invoice_number",
                  ref="sales_invoice", sign=-1, txn="sale",
                  journals=("sales", "pos", "cogs")),
    "purchase": dict(table="purchase_invoices", id="purchase_id",
                     lines="purchase_invoice_lines", status="invoice_status",
                     date="invoice_date", number="invoice_number",
                     ref="purchase_invoice", sign=+1, txn="purchase",
                     journals=("purchase",)),
    "sales_return": dict(table="sales_returns", id="return_id",
                         lines="sales_return_lines", status="return_status",
                         date="return_date", number="return_number",
                         ref="sales_return", sign=+1, txn="return_in",
                         journals=("sales_return", "cogs_return")),
    "purchase_return": dict(table="purchase_returns", id="return_id",
                            lines="purchase_return_lines", status="return_status",
                            date="return_date", number="return_number",
                            ref="purchase_return", sign=-1, txn="return_out",
                            journals=("purchase_return", "purchase_return_cost")),
    # v6.9.3: Consumable entry — stock the shop uses itself (staff food,
    # bakery / kitchen production, shop supplies): stock out at cost,
    # Dr the purpose's expense account, Cr Inventory
    "consumption": dict(table="consumption_entries", id="entry_id",
                        lines="consumption_lines", status="entry_status",
                        date="entry_date", number="entry_number",
                        ref="consumption", sign=-1, txn="consumption",
                        journals=("consumption",)),
}

# journal source_type -> document kind (used by doc_actions on delete)
SOURCE_TO_KIND = {"sales": "sales", "pos": "sales", "purchase": "purchase",
                  "sales_return": "sales_return",
                  "purchase_return": "purchase_return", "consumption": "consumption"}

last_warning = ""


def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _today():
    return date.today().strftime("%Y-%m-%d")


def _iso(v):
    if v is None or v == "":
        return _today()
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v)[:10]


# ── units & cost ──────────────────────────────────────────────
def unit_factor(product_id, unit_name):
    """Base units in one `unit_name` of the product (Box = 12 …).
    Unknown unit -> 1 (the base unit)."""
    if not product_id:
        return 1.0
    name = (unit_name or "").strip()
    try:
        if name:
            f = db.execute_scalar(
                "SELECT TOP 1 conversion_factor FROM product_units "
                "WHERE product_id=? AND unit_name_en=? "
                "ORDER BY is_active DESC", (product_id, name))
            if f and _f(f) > 0:
                return _f(f)
    except Exception:
        pass
    return 1.0


def unit_cost(product_id):
    """Cost of ONE base unit: average cost, else purchase price, else
    last purchase cost, else 0."""
    try:
        r = db.fetchone(
            "SELECT ISNULL(average_cost,0) AS a, ISNULL(purchase_price,0) AS p, "
            "ISNULL(last_purchase_cost,0) AS l FROM products WHERE product_id=?",
            (product_id,))
    except Exception:
        try:
            r = db.fetchone("SELECT ISNULL(purchase_price,0) AS p FROM products "
                            "WHERE product_id=?", (product_id,))
        except Exception:
            r = None
    if not r:
        return 0.0
    for k in ("a", "p", "l"):
        if _f(r.get(k)) > 0:
            return _f(r.get(k))
    return 0.0


def _is_stock_item(product_id):
    try:
        t = db.execute_scalar("SELECT ISNULL(product_type,'product') FROM products "
                              "WHERE product_id=?", (product_id,))
        return str(t or "product").lower() != "service"
    except Exception:
        return True


# ── stock movements ───────────────────────────────────────────
def _reverse_stock(kind, doc_id):
    """Undo every stock movement this document made. For purchases the
    weighted-average cost is un-averaged too."""
    k = KINDS[kind]
    try:
        rows = db.fetchall(
            "SELECT txn_id, product_id, ISNULL(qty_in_base,0) AS qin, "
            "ISNULL(qty_out_base,0) AS qout, ISNULL(unit_cost,0) AS cost "
            "FROM inventory_transactions WHERE reference_type=? AND reference_id=?",
            (k["ref"], int(doc_id))) or []
    except Exception:
        return 0
    for r in rows:
        delta = _f(r["qin"]) - _f(r["qout"])
        if not r.get("product_id") or not delta:
            continue
        if kind == "purchase" and delta > 0:
            _unaverage_cost(r["product_id"], delta, _f(r["cost"]))
        db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) - ? "
                   "WHERE product_id=?", (delta, r["product_id"]))
    if rows:
        db.execute("DELETE FROM inventory_transactions WHERE reference_type=? "
                   "AND reference_id=?", (k["ref"], int(doc_id)))
    try:                                   # v6.0: batches / expiry follow the document
        from modules import batches as _bt
        _bt.reverse(k["ref"], doc_id)
    except Exception:
        pass
    return len(rows)


def _doc_branch(kind, doc_id, header):
    """Branch a document belongs to (v6.0 stock per branch)."""
    b = header.get("branch_id")
    if not b:
        try:
            k = KINDS[kind]
            b = db.execute_scalar(f"SELECT branch_id FROM {k['table']} WHERE {k['id']}=?",
                                  (int(doc_id),))
        except Exception:
            b = None
    if not b:
        try:
            from modules import stock_branch as _sb
            b = _sb.here()
        except Exception:
            b = None
    return b


def _unaverage_cost(pid, qty_base, cost_base):
    """Take a purchase back out of the weighted-average cost."""
    try:
        r = db.fetchone("SELECT ISNULL(stock_quantity,0) AS q, ISNULL(average_cost,0) AS a "
                        "FROM products WHERE product_id=?", (pid,)) or {}
        q, a = _f(r.get("q")), _f(r.get("a"))
        rest = q - qty_base
        if cost_base > 0 and rest > 0 and a > 0:
            new_a = (q * a - qty_base * cost_base) / rest
            if new_a > 0:
                db.execute("UPDATE products SET average_cost=? WHERE product_id=?",
                           (round(new_a, 4), pid))
    except Exception:
        pass


def _apply_purchase_cost(pid, qty_base, cost_base):
    """Weighted-average cost + latest cost + purchase price
    (Settings ▸ Purchase: Auto Update Cost / Cost Basis)."""
    if cost_base <= 0:
        return
    try:
        r = db.fetchone("SELECT ISNULL(stock_quantity,0) AS q, ISNULL(average_cost,0) AS a "
                        "FROM products WHERE product_id=?", (pid,)) or {}
    except Exception:
        return
    old_q, old_a = _f(r.get("q")), _f(r.get("a"))
    new_q = old_q + qty_base
    if old_a <= 0 or old_q <= 0 or new_q <= 0:
        new_avg = cost_base
    else:
        new_avg = (old_q * old_a + qty_base * cost_base) / new_q
    auto = True if cfg is None else cfg.flag("auto_update_cost", True)
    try:
        if not auto:
            db.execute("UPDATE products SET last_purchase_cost=?, average_cost=? "
                       "WHERE product_id=?", (round(cost_base, 4), round(new_avg, 4), pid))
            return
        basis = str((cfg.get("cost_basis", "Last Purchase") if cfg else "") or "")
        pp = new_avg if basis.lower().startswith("average") else cost_base
        db.execute("UPDATE products SET purchase_price=?, last_purchase_cost=?, "
                   "average_cost=? WHERE product_id=?",
                   (round(pp, 2), round(cost_base, 4), round(new_avg, 4), pid))
    except Exception:
        # older DBs without the cost columns
        try:
            db.execute("UPDATE products SET purchase_price=? WHERE product_id=?",
                       (round(cost_base, 2), pid))
        except Exception:
            pass


def _apply_stock(kind, doc_id, header, lines):
    """Move stock for every product line; returns total cost of the
    movement (base qty × cost) used for the COGS / inventory journal."""
    if kind == "sales" and str(header.get("invoice_kind") or "").lower() == "debit":
        return 0.0                       # debit note: a price change, no goods move (v6.0)
    k = KINDS[kind]
    sign = k["sign"]
    tdate = _iso(header.get(k["date"]))
    total_cost = 0.0
    branch = _doc_branch(kind, doc_id, header)
    try:
        from modules import batches as _bt
    except Exception:
        _bt = None
    for ln in lines:
        pid = ln.get("product_id")
        if not pid or not _is_stock_item(pid):
            continue
        qty = _f(ln.get("quantity"))
        if not qty:
            continue
        uname = ln.get("unit_of_measure_en") or ""
        factor = unit_factor(pid, uname)
        qty_base = qty * factor
        if kind == "purchase":
            # net cost per base unit (after line discount, before VAT)
            amt = _f(ln.get("line_amount")) or qty * _f(ln.get("unit_price"))
            cost = amt / qty_base if qty_base else 0.0
            _apply_purchase_cost(pid, qty_base, cost)
        elif kind == "purchase_return":
            cost = unit_cost(pid)
        else:
            cost = unit_cost(pid)
        delta = sign * qty_base
        db.execute("UPDATE products SET stock_quantity = ISNULL(stock_quantity,0) + ? "
                   "WHERE product_id=?", (delta, pid))
        bal = _f(db.execute_scalar("SELECT ISNULL(stock_quantity,0) FROM products "
                                   "WHERE product_id=?", (pid,)))
        db.execute(
            "INSERT INTO inventory_transactions (product_id, txn_date, txn_type, "
            "reference_type, reference_id, unit_name, qty_in_units, qty_in_base, "
            "qty_out_units, qty_out_base, balance_base, unit_cost, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, tdate, k["txn"], k["ref"], int(doc_id), uname or "Unit",
             qty if sign > 0 else 0, qty_base if sign > 0 else 0,
             qty if sign < 0 else 0, qty_base if sign < 0 else 0,
             bal, round(cost, 4), str(header.get(k["number"]) or "")[:300]))
        total_cost += qty_base * cost
        if _bt is not None:                  # v6.0: batches + expiry (FEFO)
            if kind == "purchase":
                if ln.get("expiry_date") or ln.get("batch_no") or _bt.tracked(pid):
                    _bt.receive(pid, qty_base, k["ref"], doc_id, ln.get("batch_no"),
                                ln.get("expiry_date"), branch, cost, tdate)
            elif kind == "sales_return":
                _bt.give_back(pid, qty_base, k["ref"], doc_id, branch)
            else:                            # sales, purchase return
                _bt.consume(pid, qty_base, k["ref"], doc_id, branch)
    try:                                     # v6.0: the stock card knows the branch
        from modules import stock_branch as _sb
        _sb.stamp_doc(k["ref"], doc_id, branch)
    except Exception:
        pass
    return round(total_cost, 2)


# ── journals ──────────────────────────────────────────────────
def _delete_journals(kind, doc_id):
    for st in KINDS[kind]["journals"]:
        try:
            db.execute("DELETE FROM journal_lines WHERE journal_id IN (SELECT journal_id "
                       "FROM journal_entries WHERE source_type=? AND source_id=?)",
                       (st, int(doc_id)))
        except Exception:
            pass
        try:
            db.execute("DELETE FROM journal_entries WHERE source_type=? AND source_id=?",
                       (st, int(doc_id)))
        except Exception:
            pass


def _old_tenders(doc_id):
    """Cash / bank split of the sale's previous journal (so an edit or a
    re-confirm keeps a mixed cash + card payment). v6.0: the saved tender
    rows (cash, mada, STC Pay, Tabby …) win when there are any."""
    try:
        from modules import tenders as _td
        rows = _td.lines_for("sales", doc_id)
        if rows:
            return _td.for_posting(rows)
    except Exception:
        pass
    try:
        from modules import account_defaults as ad
        rows = db.fetchall(
            "SELECT jl.account_id, jl.debit FROM journal_lines jl JOIN journal_entries je "
            "ON je.journal_id=jl.journal_id WHERE je.source_type IN ('sales','pos') "
            "AND je.source_id=? AND jl.debit > 0", (int(doc_id),)) or []
        if not rows:
            return None
        cash_ids = {ad.cash()}
        bank_ids = {ad.bank(), ad.card()}
        cash = sum(_f(r["debit"]) for r in rows if r["account_id"] in cash_ids)
        bank = sum(_f(r["debit"]) for r in rows if r["account_id"] in bank_ids)
        if cash or bank:
            return {"cash": cash, "bank": bank}
    except Exception:
        pass
    return None


def _tenders_from_header(h, total):
    """Money received at the time of sale, from the saved header."""
    m = str(h.get("payment_method") or "cash").lower()
    if m == "credit":
        return {"cash": 0.0, "bank": 0.0}
    paid = h.get("paid_amount")
    paid = total if paid is None else min(_f(paid), total)
    try:   # receipts settled later are not money taken at the till
        from modules import allocation
        paid = max(0.0, paid - allocation.allocated_total("receipt", h.get("invoice_id")))
    except Exception:
        pass
    if paid <= 0 and str(h.get("payment_status") or "").lower() == "paid":
        paid = total
    if m in ("card", "bank", "bank_transfer", "cheque", "mada", "gateway", "online"):
        return {"cash": 0.0, "bank": paid}
    return {"cash": paid, "bank": 0.0}


def _post_cogs(kind, doc_id, h, cost):
    if cost <= 0:
        return None
    from modules import posting
    from modules import account_defaults as ad
    num = str(h.get(KINDS[kind]["number"]) or "")
    d = _iso(h.get(KINDS[kind]["date"]))
    if kind == "sales":
        lines = [(ad.cogs(), cost, 0, "Cost of goods sold"),
                 (ad.inventory(), 0, cost, "Stock out")]
        return posting.post_journal(d, f"Cost of Sales {num}".strip(), lines,
                                    "cogs", doc_id, reference=num)
    lines = [(ad.inventory(), cost, 0, "Stock back in"),
             (ad.cogs(), 0, cost, "Cost of goods sold reversed")]
    return posting.post_journal(d, f"Return Cost {num}".strip(), lines,
                                "cogs_return", doc_id, reference=num)


def _post_return_price_difference(doc_id, h, lines, cost):
    """A purchase return takes the goods out of Inventory at the return
    price, but the stock leaves at its average cost. The difference goes to
    Cost of Goods Sold, so the Inventory account keeps matching stock ×
    average cost (v5.26)."""
    try:
        from modules import posting
        from modules import account_defaults as ad
        amt_all = sum(_f(l.get("line_amount")) for l in lines)
        amt_stock = sum(_f(l.get("line_amount")) for l in lines
                        if l.get("product_id") and _is_stock_item(l.get("product_id")))
        taxable = _f(h.get("taxable_amount")) or _f(h.get("subtotal_amount"))
        if amt_all <= 0 or amt_stock <= 0 or taxable <= 0:
            return None
        value = round(taxable * amt_stock / amt_all, 2)   # stock goods' share, net of VAT
        diff = round(value - _f(cost), 2)
        if abs(diff) < 0.01 or cost <= 0:
            return None
        inv, cogs = ad.inventory(), ad.cogs()
        if not inv or not cogs:
            return None
        num = str(h.get("return_number") or "")
        if diff > 0:     # returned for more than the goods cost us
            lines_ = [(inv, diff, 0, "Return price above cost"),
                      (cogs, 0, diff, "Return price above cost")]
        else:
            lines_ = [(cogs, -diff, 0, "Return price below cost"),
                      (inv, 0, -diff, "Return price below cost")]
        return posting.post_journal(_iso(h.get("return_date")),
                                    f"Return Price Difference {num}".strip(), lines_,
                                    "purchase_return_cost", doc_id, reference=num)
    except Exception:
        return None


def _post_consumption(doc_id, h, cost, warn):
    """Consumable entry: Dr the purpose's expense, Cr Inventory — at the
    cost the stock really left with (so Inventory = stock × cost)."""
    from modules import posting
    cost = round(_f(cost), 2)
    try:
        db.execute("UPDATE consumption_entries SET total_cost=? WHERE entry_id=?",
                   (cost, int(doc_id)))
    except Exception:
        pass
    if not posting.enabled() or cost <= 0:
        return None
    exp = h.get("expense_account_id")
    if not exp:
        try:
            from modules import consumption as _cn
            exp = _cn.account_for(h.get("purpose"))
        except Exception:
            exp = None
    from modules import account_defaults as ad
    inv = ad.inventory()
    num = str(h.get("entry_number") or "")
    what = str(h.get("unit_name") or h.get("purpose") or "own use")
    jid = posting.post_journal(_iso(h.get("entry_date")), "Consumable %s · %s" % (num, what),
                               [(exp, cost, 0, "Used: %s" % what),
                                (inv, 0, cost, "Stock used by the shop")],
                               "consumption", int(doc_id), reference=num)
    if not jid:
        warn.append("journal not posted: %s" % (posting.last_error or "unknown reason"))
    return jid


def _post_doc(kind, doc_id, h, tenders):
    from modules import posting
    k = KINDS[kind]
    num = str(h.get(k["number"]) or "")
    d = _iso(h.get(k["date"]))
    taxable = _f(h.get("taxable_amount")) or _f(h.get("subtotal_amount"))
    vat = _f(h.get("vat_amount"))
    total = _f(h.get("total_amount"))
    method = str(h.get("payment_method") or "").lower()
    if kind == "sales":
        cust = h.get("customer_id")
        if cust:
            try:
                posting.ensure_party_account("customer", cust)
            except Exception:
                pass
        t = tenders or _tenders_from_header(h, total)
        return posting.post_sale(doc_id, d, cust, taxable, vat, total,
                                 cash=t.get("cash", 0), card=0,
                                 bank=t.get("bank", 0) + t.get("card", 0),
                                 invoice_number=num, others=t.get("other"))
    if kind == "purchase":
        sup = h.get("supplier_id")
        if sup:
            try:
                posting.ensure_party_account("supplier", sup)
            except Exception:
                pass
        cash = total if method == "cash" else 0
        bank = total if method in ("bank_transfer", "bank", "card", "cheque") else 0
        return posting.post_purchase(doc_id, d, sup, taxable, vat, total,
                                     cash=cash, bank=bank, invoice_number=num)
    if kind == "sales_return":
        return posting.post_sales_return(doc_id, d, h.get("customer_id"), taxable,
                                         vat, total, method=method or "cash",
                                         number=num)
    return posting.post_purchase_return(doc_id, d, h.get("supplier_id"), taxable,
                                        vat, total, method=method or "credit",
                                        number=num)


# ── public API ────────────────────────────────────────────────
def _unlink_payments(kind, doc_id):
    try:
        from modules import allocation
        if kind in ("sales", "purchase"):
            allocation.unlink_document("receipt" if kind == "sales" else "disbursement",
                                       doc_id)
        elif kind in ("sales_return", "purchase_return"):
            allocation.release_return(kind, doc_id)    # the bill owes it again
    except TransactionLost:
        raise
    except Exception:
        pass
    if kind in ("sales", "sales_return"):
        try:                                           # its loyalty points go too
            from modules import loyalty
            loyalty.remove(kind, doc_id)
        except TransactionLost:
            raise
        except Exception:
            pass


def remove(kind, doc_id):
    """Undo all stock movements, journals and receipt links of a
    document (call before a delete). All of it, or none (v5.27)."""
    if kind not in KINDS or not doc_id:
        return
    with db.transaction():
        _undo_stock(kind, doc_id)
        _delete_journals(kind, doc_id)
        _unlink_payments(kind, doc_id)


def _undo_stock(kind, doc_id):
    """Reverse the stock of a document as one step: if it fails half-way,
    the half that was done is undone again (savepoint)."""
    try:
        with db.transaction():
            _reverse_stock(kind, doc_id)
    except TransactionLost:
        raise
    except Exception:
        pass


def sync(kind, doc_id, tenders=None):
    """Bring stock + books in line with the document as saved now.
    tenders (sales only): {"cash": x, "bank": y} money taken at the till.
    Returns a short warning string ('' when everything posted)."""
    global last_warning
    last_warning = ""
    if kind not in KINDS or not doc_id:
        return ""
    # the whole re-post is ONE unit of work; inside a document save it is
    # a savepoint of that save's transaction (v5.27)
    from modules import posting
    with db.transaction():
        # v6.9.5: an edit re-posts with the journal numbers it had
        posting.remember_numbers(KINDS[kind]["journals"], doc_id)
        try:
            return _sync(kind, doc_id, tenders)
        finally:
            posting.forget_numbers(KINDS[kind]["journals"], doc_id)


def _sync(kind, doc_id, tenders):
    global last_warning
    k = KINDS[kind]
    h = db.fetchone(f"SELECT * FROM {k['table']} WHERE {k['id']}=?", (int(doc_id),))
    if not h:
        remove(kind, doc_id)
        return ""
    try:                                   # which branch / counter made it
        from modules import branches as _br
        _br.stamp(k["table"], doc_id)
    except Exception:
        pass
    if kind == "sales" and tenders is None:
        tenders = _old_tenders(doc_id)
    _undo_stock(kind, doc_id)
    _delete_journals(kind, doc_id)
    status = str(h.get(k["status"]) or "").lower()
    if status != "confirmed":
        _unlink_payments(kind, doc_id)       # cancelled → receipts become advances
        return ""
    lines = db.fetchall(f"SELECT * FROM {k['lines']} WHERE {k['id']}=? "
                        f"ORDER BY line_number", (int(doc_id),)) or []
    warn = []
    try:
        with db.transaction():         # all lines move, or none of them
            cost = _apply_stock(kind, doc_id, h, lines)
    except TransactionLost:
        raise
    except Exception as e:
        cost = 0.0
        warn.append("stock not updated: %s" % str(e)[:120])
    from modules import posting
    if kind == "consumption":
        _post_consumption(doc_id, h, cost, warn)
    elif posting.enabled():
        jid = _post_doc(kind, doc_id, h, tenders)
        if not jid and (_f(h.get("total_amount")) or _f(h.get("taxable_amount"))):
            warn.append("journal not posted: %s" % (posting.last_error or "unknown reason"))
        if kind in ("sales", "sales_return") and cost > 0:
            if not _post_cogs(kind, doc_id, h, cost):
                warn.append("cost of sales not posted: %s"
                            % (posting.last_error or "unknown reason"))
        if kind == "purchase_return" and jid:
            _post_return_price_difference(doc_id, h, lines, cost)
    if kind in ("sales", "sales_return"):
        try:              # loyalty points earned / spent / taken back (v6.9.2)
            from modules import loyalty
            if kind == "sales":
                loyalty.sync_sale(doc_id)
            else:
                loyalty.sync_return(doc_id)
        except TransactionLost:
            raise
        except Exception as e:
            warn.append("loyalty points not updated: %s" % str(e)[:120])
    if kind in ("sales_return", "purchase_return"):
        try:              # on the party's account → settles the bill it came from
            from modules import allocation
            allocation.apply_return(kind, doc_id)
        except TransactionLost:
            raise
        except Exception as e:
            warn.append("bill balance not updated: %s" % str(e)[:120])
    last_warning = "; ".join(warn)
    return last_warning


def notify(parent=None, warning=None):
    """Show a non-blocking warning if the last sync could not post."""
    w = last_warning if warning is None else warning
    if not w:
        return
    try:
        from tkinter import messagebox
        messagebox.showwarning("Accounts", "Saved, but: " + w +
                               "\n\nCheck Settings ▸ Default Accounts and the "
                               "financial year.", parent=parent)
    except Exception:
        pass


# ── manual stock changes (adjust / count / clear) ─────────────
def _stock_adjust_account():
    from modules import account_defaults as ad
    acc = ad.stock_adjust()
    if acc:
        return acc
    try:   # older DBs: create 5160 once
        db.execute("INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
                   "account_type) VALUES ('5160', 'Stock Adjustment', N'تسوية المخزون', "
                   "'expense')")
        ad.invalidate()
        return ad.stock_adjust()
    except Exception:
        return None


def post_stock_adjustment(product_id, delta_base, note="Stock adjustment",
                          when=None, reference="ADJ"):
    """Value a manual stock change at average cost and post it so the
    Inventory account keeps matching the stock valuation:
        gain -> Dr Inventory        | Cr Stock Adjustment
        loss -> Dr Stock Adjustment | Cr Inventory
    Returns journal_id or None (nothing to post / accounting off)."""
    from modules import posting
    from modules import account_defaults as ad
    try:
        if not delta_base or not posting.enabled() or not _is_stock_item(product_id):
            return None
        if cfg is not None and not cfg.flag("acc_post_stock_adjust", True):
            return None
        value = round(abs(_f(delta_base)) * unit_cost(product_id), 2)
        if value <= 0:
            return None
        adj = _stock_adjust_account()
        inv = ad.inventory()
        if delta_base > 0:
            lines = [(inv, value, 0, "Stock gain"), (adj, 0, value, note)]
        else:
            lines = [(adj, value, 0, note), (inv, 0, value, "Stock loss")]
        return posting.post_journal(when or _today(), note, lines, "stock_adjust",
                                    int(product_id), reference=reference)
    except Exception:
        return None


# ── one-off repair: cost of sales for bills saved before v5.7 ──
def post_missing_cogs(date_from=None, date_to=None):
    """Posts a Cost-of-Sales journal (Dr COGS / Cr Inventory) for every
    CONFIRMED sale that has none yet, at the product's current average
    cost. Does NOT move stock. Returns (count, amount)."""
    from modules import posting
    if not posting.enabled():
        return 0, 0.0
    where = ["si.invoice_status='confirmed'",
             "NOT EXISTS (SELECT 1 FROM journal_entries je WHERE je.source_type='cogs' "
             "AND je.source_id=si.invoice_id)"]
    params = []
    if date_from:
        where.append("si.invoice_date >= ?"); params.append(date_from)
    if date_to:
        where.append("si.invoice_date <= ?"); params.append(date_to)
    invs = db.fetchall("SELECT si.invoice_id, si.invoice_number, si.invoice_date "
                       "FROM sales_invoices si WHERE " + " AND ".join(where),
                       tuple(params)) or []
    n, amt = 0, 0.0
    for h in invs:
        lines = db.fetchall("SELECT product_id, quantity, unit_of_measure_en FROM "
                            "sales_invoice_lines WHERE invoice_id=?", (h["invoice_id"],)) or []
        cost = 0.0
        for ln in lines:
            pid = ln.get("product_id")
            if pid and _is_stock_item(pid):
                cost += _f(ln.get("quantity")) * unit_factor(pid, ln.get("unit_of_measure_en")) \
                        * unit_cost(pid)
        cost = round(cost, 2)
        if cost > 0 and _post_cogs("sales", h["invoice_id"], h, cost):
            n += 1
            amt += cost
    return n, round(amt, 2)
