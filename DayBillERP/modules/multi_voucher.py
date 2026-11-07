# ============================================================
# DayBill ERP - Multi-line vouchers (v7.1)
# ------------------------------------------------------------
# One window, many lines:
#   receipt  - Cash / Bank Receipt   each line: from whom + received in
#   payment  - Cash / Bank Payment   each line: to whom + paid from (+ VAT)
#   contra   - cash ↔ bank           each line: to account + from account
#   journal  - Journal Voucher       each line: account / party + Dr / Cr
# A line's money account can be cash on one line and bank on the next.
# With split=True a receipt / payment is saved as one voucher per kind
# of money (CR + BR, CP + BP) so each keeps its own numbering.
#
# Line (dict):
#   target       ("customer"|"supplier"|"account", id)
#   account_id   the target's ledger (filled at save for a party)
#   amount       receipt / payment / contra amount (before VAT)
#   money        cash / bank account id (receipt, payment, contra-from)
#   vat          input VAT on a payment line
#   cheque, cheque_date
#   debit, credit   journal lines
#   description  line narration
# ============================================================

import json
import re

from config.database import db
from modules import posting
from modules import account_defaults as ad

KINDS = ("receipt", "payment", "contra", "journal")
SOURCE = {"receipt": "receipt", "payment": "payment", "contra": "transfer",
          "journal": "manual"}
RIGHT = {"receipt": "receipt", "payment": "payment", "contra": "journal",
         "journal": "journal"}
TITLES = {"receipt": "Receipt Voucher", "payment": "Payment Voucher",
          "contra": "Contra Voucher (CT)", "journal": "Journal Voucher (JV)"}
KIND_OF_CODE = {"CR": "receipt", "BR": "receipt", "CP": "payment", "BP": "payment",
                "CT": "contra", "JV": "journal"}
_CHQ = re.compile(r"Chq\s+(\S+)(?:\s+dt\s+(\S+))?")


def f2(v):
    try:
        return round(float(str(v if v is not None else 0).replace(",", "") or 0), 2)
    except (TypeError, ValueError):
        return 0.0


# ── money accounts (cash / bank / card …) ─────────────────────
def _cash_ids():
    try:
        from modules import voucher_types as vt
        return vt._cash_ids()
    except Exception:
        return set(a for a in (ad.cash(),) if a)


def money_accounts():
    """[{account_id, code, name, kind 'cash'|'bank'}] — the defaults
    (cash, petty cash, bank, card, savings, gateway, tender accounts) and
    every ledger beside them in the same group (a 2nd bank account …)."""
    cash = _cash_ids()
    ids = set(cash)
    for fn in (ad.bank, ad.card, ad.savings, ad.gateway, ad.petty_cash):
        try:
            a = fn()
            if a:
                ids.add(a)
        except Exception:
            pass
    try:
        for r in db.fetchall("SELECT account_id FROM payment_method_accounts "
                             "WHERE is_active=1") or []:
            if r.get("account_id"):
                ids.add(r["account_id"])
    except Exception:
        pass
    try:
        rows = db.fetchall("SELECT account_id, account_code, account_name_en, account_type, "
                           "parent_account_id, ISNULL(is_active,1) AS act FROM accounts") or []
    except Exception:
        rows = []
    by = {r["account_id"]: r for r in rows}
    parents = set(by[a]["parent_account_id"] for a in ids
                  if a in by and by[a].get("parent_account_id"))
    kids = set(r["parent_account_id"] for r in rows if r.get("parent_account_id"))
    try:                             # party ledgers sit under receivable — never money
        party = set(r["account_id"] for r in db.fetchall(
            "SELECT account_id FROM customers WHERE account_id IS NOT NULL UNION "
            "SELECT account_id FROM suppliers WHERE account_id IS NOT NULL") or [])
    except Exception:
        party = set()
    for r in rows:
        if (r["parent_account_id"] in parents and r["account_type"] == "asset"
                and r["account_id"] not in kids and r["account_id"] not in party):
            nm = str(r["account_name_en"] or "").lower()
            if any(w in nm for w in ("cash", "bank", "petty", "wallet", "card", "mada",
                                     "till", "safe", "saving", "gateway", "current a")):
                ids.add(r["account_id"])
    out = []
    for a in ids:
        r = by.get(a)
        if not r or not r["act"]:
            continue
        nm = str(r["account_name_en"] or "")
        kind = "cash" if (a in cash or any(w in nm.lower() for w in ("cash", "petty", "till", "safe"))) \
            else "bank"
        out.append({"account_id": a, "code": str(r["account_code"] or ""), "name": nm, "kind": kind})
    out.sort(key=lambda x: (x["kind"] != "cash", x["code"]))
    return out


def money_kind(account_id, accounts=None):
    for m in accounts if accounts is not None else money_accounts():
        if m["account_id"] == account_id:
            return m["kind"]
    return "cash" if account_id in _cash_ids() else "bank"


def default_money(mode="cash", accounts=None):
    accs = accounts if accounts is not None else money_accounts()
    want = ad.bank() if mode == "bank" else ad.cash()
    if want and any(m["account_id"] == want for m in accs):
        return want
    return next((m["account_id"] for m in accs if m["kind"] == mode),
                accs[0]["account_id"] if accs else want)


# ── parties / targets ─────────────────────────────────────────
def target_account(target):
    kind, pid = (target or (None, None))[:2]
    if kind in ("customer", "supplier"):
        return posting._party_ledger(kind, pid)
    return pid


def party_of_account(account_id, money_ids=None):
    """('customer', id, name) / ('supplier', …) for a party ledger, else None.
    A cash / bank account is never a party (the Cash Customer and Cash
    Supplier may be booked straight to the cash account)."""
    if not account_id:
        return None
    if money_ids is None:
        money_ids = set(m["account_id"] for m in money_accounts())
    if account_id in money_ids:
        return None
    for kind, t, nm in (("customer", "customers", "customer_name_en"),
                        ("supplier", "suppliers", "supplier_name_en")):
        try:
            r = db.fetchone("SELECT TOP 1 %s_id AS id, %s AS name FROM %s WHERE account_id=?"
                            % (kind, nm, t), (account_id,))
        except Exception:
            r = None
        if r:
            return kind, r["id"], r["name"]
    return None


def balance(target_or_account):
    """Ledger balance (Dr − Cr, posted vouchers) of a party / account."""
    acc = target_or_account
    if isinstance(acc, (tuple, list)):
        kind, pid = acc[:2]
        if kind == "customer":
            acc = posting._customer_account(pid)
        elif kind == "supplier":
            acc = posting._supplier_account(pid)
        else:
            acc = pid
    if not acc:
        return 0.0
    try:
        return f2(db.execute_scalar(
            "SELECT ISNULL(SUM(jl.debit - jl.credit),0) FROM journal_lines jl "
            "JOIN journal_entries je ON je.journal_id=jl.journal_id "
            "WHERE je.is_posted=1 AND jl.account_id=?", (acc,)))
    except Exception:
        return 0.0


def balance_text(value):
    v = f2(value)
    if not v:
        return "0.00"
    return "%s %s" % ("{:,.2f}".format(abs(v)), "Dr" if v > 0 else "Cr")


# ── lines → journal lines ─────────────────────────────────────
def _cheque_text(ln):
    chq = str(ln.get("cheque") or "").strip()
    if not chq:
        return ""
    d = str(ln.get("cheque_date") or "").strip()
    return " · Chq %s%s" % (chq, (" dt " + d) if d else "")


def _desc(kind, ln, name=""):
    d = str(ln.get("description") or "").strip()
    if d:
        return d
    who = name or _plain(ln.get("label"))
    return {"receipt": "Received from %s", "payment": "Paid to %s",
            "contra": "Transfer to %s"}.get(kind, "%s") % who if who else ""


def _plain(label):
    """'👤 Alpha Trading' / '5330 · Office Expense' → 'Alpha Trading' / 'Office Expense'."""
    t = str(label or "").split(" · ")[-1].strip()
    for pre in ("👤", "🏭"):
        if t.startswith(pre):
            t = t[len(pre):].strip()
    return t


def _input_tax_lines(vat):
    out = []
    posting._tax(out, vat, posting._gst_lines("in", vat), ad.tax_receivable(),
                 "VAT input", credit=False)
    return out


def journal_lines(kind, lines):
    """[(account_id, debit, credit, description)] for one voucher."""
    out = []
    for ln in lines:
        acc = ln.get("account_id") or target_account(ln.get("target"))
        ln["account_id"] = acc
        desc = _desc(kind, ln)
        if kind == "journal":
            dr, cr = f2(ln.get("debit")), f2(ln.get("credit"))
            if dr or cr:
                out.append((acc, dr, cr, desc))
            continue
        amt, vat, money = f2(ln.get("amount")), f2(ln.get("vat")), ln.get("money")
        if not amt:
            continue
        mdesc = desc + _cheque_text(ln)
        if kind == "receipt":
            out.append((money, amt, 0, mdesc))
            out.append((acc, 0, amt, desc))
        elif kind == "payment":
            out.append((acc, amt, 0, desc))
            out.extend((a, d, c, l) for a, d, c, l in _input_tax_lines(vat))
            out.append((money, 0, round(amt + vat, 2), mdesc))
        else:                                   # contra: Dr to, Cr from
            out.append((acc, amt, 0, desc))
            out.append((money, 0, amt, mdesc))
    return out


def totals(kind, lines, accounts=None):
    """{'cash', 'bank', 'total', 'vat', 'debit', 'credit', 'diff', 'count'}"""
    t = {"cash": 0.0, "bank": 0.0, "total": 0.0, "vat": 0.0, "debit": 0.0, "credit": 0.0,
         "diff": 0.0, "count": 0}
    accs = accounts if accounts is not None else money_accounts()
    for ln in lines:
        if kind == "journal":
            t["debit"] += f2(ln.get("debit"))
            t["credit"] += f2(ln.get("credit"))
        else:
            gross = f2(ln.get("amount")) + f2(ln.get("vat"))
            t["vat"] += f2(ln.get("vat"))
            t["total"] += gross
            if kind != "contra":
                t[money_kind(ln.get("money"), accs)] += gross
        t["count"] += 1
    for k in t:
        if k != "count":
            t[k] = round(t[k], 2)
    if kind == "journal":
        t["diff"] = round(t["debit"] - t["credit"], 2)
        t["total"] = t["debit"]
    return t


def validate(kind, lines, accounts=None):
    """List of problems ([] = fine)."""
    errs = []
    if kind not in KINDS:
        return ["Unknown voucher type."]
    real = [l for l in lines if (f2(l.get("debit")) or f2(l.get("credit"))
                                 if kind == "journal" else f2(l.get("amount")))]
    if not real:
        return ["Add at least one line with an amount."]
    money_ids = set(m["account_id"] for m in (accounts if accounts is not None else money_accounts()))
    for i, l in enumerate(real, 1):
        if not l.get("target") and not l.get("account_id"):
            errs.append("Line %d: pick a party or account." % i)
        if kind == "journal":
            if f2(l.get("debit")) and f2(l.get("credit")):
                errs.append("Line %d: a line is either Dr or Cr, not both." % i)
            if f2(l.get("debit")) < 0 or f2(l.get("credit")) < 0:
                errs.append("Line %d: amounts cannot be negative." % i)
            continue
        if f2(l.get("amount")) < 0 or f2(l.get("vat")) < 0:
            errs.append("Line %d: amounts cannot be negative." % i)
        if not l.get("money"):
            errs.append("Line %d: pick the cash / bank account." % i)
        acc = l.get("account_id") or (l.get("target") or (None, None))[1]
        tk = (l.get("target") or ("account",))[0]
        if kind == "contra":
            if tk != "account" or acc not in money_ids:
                errs.append("Line %d: a contra moves money between cash / bank accounts." % i)
            elif acc == l.get("money"):
                errs.append("Line %d: From and To are the same account." % i)
        elif tk == "account" and acc == l.get("money"):
            errs.append("Line %d: the account and the cash / bank account are the same." % i)
    if kind == "journal":
        t = totals(kind, real, accounts)
        if abs(t["diff"]) > 0.009:
            errs.append("Debit %s and Credit %s do not match (difference %s)."
                        % ("{:,.2f}".format(t["debit"]), "{:,.2f}".format(t["credit"]),
                           "{:,.2f}".format(abs(t["diff"]))))
    return errs


def groups(kind, lines, split=True, accounts=None):
    """The vouchers a save makes: [(label, [lines])]. A receipt / payment
    with split=True → one per kind of money (cash, bank)."""
    if kind in ("journal", "contra") or not split:
        return [("", list(lines))]
    accs = accounts if accounts is not None else money_accounts()
    out = {}
    for ln in lines:
        out.setdefault(money_kind(ln.get("money"), accs), []).append(ln)
    return [(k, out[k]) for k in ("cash", "bank") if k in out]


def preview_codes(kind, lines, split=True, accounts=None):
    """['CR', 'BR'] — the voucher types a save will make."""
    accs = accounts if accounts is not None else money_accounts()
    codes = []
    for k, ls in groups(kind, lines, split, accs):
        if kind == "journal":
            codes.append("JV")
        elif kind == "contra":
            codes.append("CT")
        else:
            cash = any(money_kind(l.get("money"), accs) == "cash" for l in ls)
            codes.append(("C" if cash else "B") + ("R" if kind == "receipt" else "P"))
    return codes


# ── save ──────────────────────────────────────────────────────
class VoucherError(Exception):
    pass


def post(kind, entry_date, lines, narration="", reference="", split=True):
    """Save the voucher(s). Returns [(journal_id, number)]. All or none."""
    accs = money_accounts()
    errs = validate(kind, lines, accs)
    if errs:
        raise VoucherError("\n".join(errs))
    lines = [l for l in lines if (f2(l.get("debit")) or f2(l.get("credit"))
                                  if kind == "journal" else f2(l.get("amount")))]
    try:
        from modules import financial_year as fy
        msg = fy.guard_active(str(entry_date)[:10])
    except Exception:
        msg = ""
    if msg:
        raise VoucherError(msg)
    made = []
    with db.transaction():
        for _k, ls in groups(kind, lines, split, accs):
            jl = journal_lines(kind, ls)
            text = narration or _auto_narration(kind, ls)
            jid = posting.post_journal(entry_date, text, jl, SOURCE[kind], None,
                                       reference=reference or None)
            if not jid:
                raise VoucherError(posting.last_error or "The voucher could not be saved.")
            made.append(jid)
    out = []
    for jid in made:
        num = db.execute_scalar("SELECT journal_number FROM journal_entries WHERE journal_id=?",
                                (jid,)) or ""
        out.append((jid, num))
    return out


def _auto_narration(kind, lines):
    names = []
    for l in lines:
        n = _plain(l.get("label"))
        if n and n not in names:
            names.append(n)
    head = {"receipt": "Received from", "payment": "Paid to", "contra": "Transfer to",
            "journal": "Journal"}[kind]
    if not names:
        return TITLES[kind]
    more = " + %d more" % (len(names) - 2) if len(names) > 2 else ""
    return "%s %s%s" % (head, ", ".join(names[:2]), more)


def update(journal_id, kind, entry_date, lines, narration="", reference=""):
    """Change a saved voucher in place (same number while its type stays)."""
    accs = money_accounts()
    errs = validate(kind, lines, accs)
    if errs:
        raise VoucherError("\n".join(errs))
    lines = [l for l in lines if (f2(l.get("debit")) or f2(l.get("credit"))
                                  if kind == "journal" else f2(l.get("amount")))]
    old = db.fetchone("SELECT * FROM journal_entries WHERE journal_id=?", (journal_id,))
    if not old:
        raise VoucherError("This voucher no longer exists.")
    try:
        from modules import financial_year as fy
        msg = fy.guard_active(str(entry_date)[:10]) or \
            fy.guard_active(str(old.get("entry_date"))[:10])
    except Exception:
        msg = ""
    if msg:
        raise VoucherError(msg)
    with db.transaction():
        jl = [l for l in journal_lines(kind, lines) if l[0] and (l[1] or l[2])]
        if any(a is None for a, *_r in journal_lines(kind, lines)):
            raise VoucherError("An account could not be found (Settings ▸ Default Accounts).")
        td = round(sum(l[1] for l in jl), 2)
        tc = round(sum(l[2] for l in jl), 2)
        if abs(td - tc) > 0.009 or not td:
            raise VoucherError("Unbalanced entry: debit %s != credit %s" % (td, tc))
        src = old.get("source_type") or SOURCE[kind]
        if src in ("receipt", "payment", "transfer", "manual", "journal", "voucher",
                   "expense", "adjustment", "blank") and src != SOURCE[kind]:
            if not (src == "expense" and kind == "payment") and \
                    not (src == "adjustment" and kind == "journal"):
                src = SOURCE[kind]
        from modules import voucher_types as vt
        code = vt.code_for(src, [l[0] for l in jl], old.get("source_id"), old.get("reference"))
        num = old.get("journal_number")
        if code and str(old.get("voucher_type") or "").upper() not in ("", code):
            num = vt.next_number(code)        # CR ↔ BR: the number follows the type
        db.execute("UPDATE journal_entries SET entry_date=?, description_en=?, reference=?, "
                   "total_debit=?, total_credit=?, source_type=?, journal_number=? "
                   "WHERE journal_id=?",
                   (entry_date, narration or _auto_narration(kind, lines), reference or None,
                    td, tc, src, num, journal_id))
        try:
            with db.savepoint():
                db.execute("UPDATE journal_entries SET voucher_type=? WHERE journal_id=?",
                           (code, journal_id))
        except Exception:
            pass
        db.execute("DELETE FROM journal_lines WHERE journal_id=?", (journal_id,))
        for i, (acc, dr, cr, desc) in enumerate(jl, 1):
            db.execute("INSERT INTO journal_lines (journal_id, line_number, account_id, "
                       "debit, credit, description) VALUES (?,?,?,?,?,?)",
                       (journal_id, i, acc, round(dr or 0, 2), round(cr or 0, 2), desc))
    try:
        from modules.doc_actions import audit
        audit("edit", "voucher", journal_id, "%s Dr %.2f Cr %.2f" % (num, td, tc))
    except Exception:
        pass
    return num


# ── load a saved voucher back into lines ──────────────────────
def kind_of(journal_id):
    r = db.fetchone("SELECT * FROM journal_entries WHERE journal_id=?", (journal_id,)) or {}
    code = str(r.get("voucher_type") or "").upper()
    if code in KIND_OF_CODE:
        return KIND_OF_CODE[code]
    src = str(r.get("source_type") or "").lower()
    return {"receipt": "receipt", "payment": "payment", "expense": "payment",
            "transfer": "contra"}.get(src, "journal")


def _target_for(account_id, names, money_ids=None):
    p = party_of_account(account_id, money_ids)
    if p:
        return (p[0], p[1]), p[2]
    a = names.get(account_id) or {}
    return ("account", account_id), ("%s · %s" % (a.get("account_code") or "",
                                                  a.get("account_name_en") or "")).strip(" ·")


def load(journal_id, kind=None):
    """{kind, date, narration, reference, number, lines} of a saved voucher."""
    h = db.fetchone("SELECT * FROM journal_entries WHERE journal_id=?", (journal_id,))
    if not h:
        return None
    kind = kind or kind_of(journal_id)
    rows = db.fetchall("SELECT jl.account_id, jl.debit, jl.credit, jl.description, "
                       "a.account_code, a.account_name_en FROM journal_lines jl "
                       "LEFT JOIN accounts a ON a.account_id=jl.account_id "
                       "WHERE jl.journal_id=? ORDER BY jl.line_number", (journal_id,)) or []
    names = {r["account_id"]: r for r in rows}
    money_ids = set(m["account_id"] for m in money_accounts())
    d = h.get("entry_date")
    out = {"kind": kind, "number": h.get("journal_number") or "",
           "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")[:10],
           "narration": h.get("description_en") or "", "reference": h.get("reference") or "",
           "lines": []}
    if kind == "journal":
        for r in rows:
            tgt, lab = _target_for(r["account_id"], names, money_ids)
            out["lines"].append({"target": tgt, "account_id": r["account_id"], "label": lab,
                                 "debit": f2(r["debit"]), "credit": f2(r["credit"]),
                                 "description": r.get("description") or ""})
        return out
    tax_ids = set(a for a in [ad.tax_receivable()] if a)
    try:
        for h_ in ("cgst", "sgst", "igst", "utgst"):
            a = ad.gst_account("in", h_)
            if a:
                tax_ids.add(a)
    except Exception:
        pass
    entries, loose = [], []
    if kind == "contra":                        # pairs: Dr to, Cr from
        drs = [r for r in rows if f2(r["debit"])]
        crs = [r for r in rows if f2(r["credit"])]
        for i, r in enumerate(drs):
            m = crs[i] if i < len(crs) else (crs[-1] if crs else None)
            tgt, lab = _target_for(r["account_id"], names, money_ids)
            ln = {"target": tgt, "account_id": r["account_id"], "label": lab,
                  "amount": f2(r["debit"]), "vat": 0.0, "money": m and m["account_id"],
                  "description": r.get("description") or ""}
            _read_cheque(ln, m and m.get("description"))
            if ln["description"] == _desc(kind, {"label": lab}):
                ln["description"] = ""
            entries.append(ln)
        out["lines"] = entries
        return out
    for r in rows:
        acc = r["account_id"]
        if acc in money_ids and (f2(r["debit"]) if kind == "receipt" else f2(r["credit"])):
            pending = next((e for e in entries if not e.get("money")), None)
            if pending is not None:
                pending["money"] = acc
                _read_cheque(pending, r.get("description"))
            else:
                loose.append(r)
            continue
        if kind == "payment" and acc in tax_ids and entries and f2(r["debit"]):
            entries[-1]["vat"] = round(f2(entries[-1].get("vat")) + f2(r["debit"]), 2)
            continue
        tgt, lab = _target_for(acc, names, money_ids)
        amt = f2(r["credit"]) if kind == "receipt" else f2(r["debit"])
        if not amt:                               # a reverse line: keep it negative-free
            amt = f2(r["debit"]) if kind == "receipt" else f2(r["credit"])
        ln = {"target": tgt, "account_id": acc, "label": lab, "amount": amt, "vat": 0.0,
              "money": None, "description": r.get("description") or ""}
        if loose:                                 # money line came first (older vouchers)
            m = loose.pop(0)
            ln["money"] = m["account_id"]
            _read_cheque(ln, m.get("description"))
        entries.append(ln)
    for e in entries:                           # an automatic line text is made again at save
        if e.get("description") == _desc(kind, {"label": e.get("label")}):
            e["description"] = ""
    one_money = list(set(e["money"] for e in entries if e.get("money")))
    for e in entries:
        if not e.get("money") and len(one_money) == 1:
            e["money"] = one_money[0]
    out["lines"] = entries
    return out


def _read_cheque(ln, text):
    m = _CHQ.search(str(text or ""))
    if m:
        ln["cheque"] = m.group(1)
        ln["cheque_date"] = m.group(2) or ""


# ── templates (rent, salaries, monthly bills …) ───────────────
_TPL = "vtpl:"


def templates(kind=None):
    """{name: {kind, narration, lines}} kept in the company database."""
    try:
        from modules import country
        opts = country.options()
    except Exception:
        return {}
    out = {}
    for k, v in sorted(opts.items()):
        if not str(k).startswith(_TPL) or not v:
            continue
        try:
            t = json.loads(v)
        except Exception:
            continue
        if kind is None or t.get("kind") == kind:
            out[k[len(_TPL):]] = t
    return out


def save_template(name, kind, lines, narration=""):
    name = str(name or "").strip()[:80]
    if not name:
        return False
    keep = []
    for l in lines:
        d = {k: l.get(k) for k in ("account_id", "label", "amount", "money", "vat", "debit",
                                   "credit", "description") if l.get(k) not in (None, "")}
        tg = l.get("target")
        if tg:
            d["target"] = [tg[0], tg[1]]
        keep.append(d)
    from modules import country
    return country.set_option(_TPL + name, json.dumps(
        {"kind": kind, "narration": narration, "lines": keep}, default=str))


def template_lines(t):
    out = []
    for d in (t or {}).get("lines") or []:
        l = dict(d)
        if l.get("target"):
            l["target"] = tuple(l["target"])
        if l["target"][0] == "account" if l.get("target") else False:
            ok = db.execute_scalar("SELECT COUNT(*) FROM accounts WHERE account_id=? AND "
                                   "ISNULL(is_active,1)=1", (l["target"][1],))
            if not ok:
                continue
        if (l.get("target") or ("",))[0] in ("customer", "supplier"):
            l["account_id"] = None                # a party's ledger is looked up at save
        out.append(l)
    return out


def delete_template(name):
    try:
        db.execute("DELETE FROM company_options WHERE opt_key=?", (_TPL + str(name),))
        from modules import country
        country._STATE.get("opts", {}).pop(_TPL + str(name), None)
        return True
    except Exception:
        return False
