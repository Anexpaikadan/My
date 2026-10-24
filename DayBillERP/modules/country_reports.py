# ============================================================
# DayBill ERP - tax returns of the UAE and India (v7.0)
# ------------------------------------------------------------
# Registered in the Report Center (report_center imports this file).
# Each report shows only for its country (needs="country:AE" / "IN");
# the Saudi ZATCA VAT return stays in report_center (vat_return).
#
#   UAE   uae_vat201     VAT 201 return — boxes 1a-1g (standard rated
#                        sales by emirate) … 14 payable tax
#   India gstr3b         GSTR-3B summary: 3.1 outward supplies, 3.2
#                        inter-state B2C by state, 4 ITC, 5 exempt
#                        inward, 6.1 tax payable after ITC set-off
#         gstr1_b2b      GSTR-1 4A  invoices to registered buyers
#         gstr1_b2cl     GSTR-1 5   big inter-state invoices to
#                                   unregistered buyers (> limit)
#         gstr1_b2cs     GSTR-1 7   other B2C, by state and rate
#         gstr1_cdnr     GSTR-1 9B  credit / debit notes
#         gstr1_hsn      GSTR-1 12  HSN summary (B2B and B2C)
#         gstr1_docs     GSTR-1 13  documents issued
#
# Rules (same as the rest of the Report Center): confirmed documents
# only; credit notes and returns reduce the period they are dated in;
# India's place of supply = the bill's own, else the party's state, else
# 96 for a party abroad, else the company's state.
# ============================================================

from collections import OrderedDict

from modules.report_center import (report, col, _result, _sum_totals, _q, _q1, _f, _d,
                                   _has_table, _has_col)

GROUP_GST = "GST (India)"
GROUP_AE = "VAT 201 (UAE)"
EXPORT = "96"
UTGST = {"04", "26", "31", "35", "38"}
EMIRATES = OrderedDict([("AZ", "Abu Dhabi"), ("DU", "Dubai"), ("SH", "Sharjah"), ("AJ", "Ajman"),
                        ("UQ", "Umm Al Quwain"), ("RK", "Ras Al Khaimah"), ("FU", "Fujairah")])


def R(x):
    return round(_f(x), 2) + 0.0


# ── shared ────────────────────────────────────────────────────
def _company():
    return _q1("SELECT TOP 1 * FROM company ORDER BY company_id") or {}


def _home():
    c = _company()
    st = str(c.get("state_code") or "").strip()
    if not st:
        g = str(c.get("vat_registration_no") or "").strip()
        st = g[:2] if g[:2].isdigit() else ""
    return st


def _kinds():
    """{vat_category_id: kind, 'code:<code>': kind} from vat_categories."""
    out = {}
    has_kind = _has_col("vat_categories", "tax_kind")
    for r in _q("SELECT vat_category_id, category_code, vat_rate%s FROM vat_categories"
                % (", tax_kind" if has_kind else "")):
        k = str(r.get("tax_kind") or "") or _kind_of(r.get("category_code"), r.get("vat_rate"))
        out[r["vat_category_id"]] = k
        out["code:" + str(r.get("category_code") or "").upper()] = k
    return out


def _kind_of(code, rate):
    c = str(code or "").upper()[:1]
    if c == "Z":
        return "zero"
    if c == "E":
        return "exempt"
    if c == "O":
        return "oos"
    return "std" if _f(rate) > 0 else "nil"


def _line_kind(kinds, ln):
    k = kinds.get(ln.get("vat_category_id")) if ln.get("vat_category_id") is not None else None
    if not k:
        k = kinds.get("code:" + str(ln.get("vat_category_code") or "").upper())
    if not k:
        k = _kind_of(ln.get("vat_category_code"), ln.get("vat_rate"))
    if k == "std" and abs(_f(ln.get("vat_amount"))) < 0.005 and _f(ln.get("vat_rate")) <= 0:
        k = "nil"
    return k


def _pos(doc, party):
    """India place of supply of a document joined with its party."""
    p = str(doc.get("place_of_supply") or "").strip()
    if p:
        return p
    st = str(party.get("state_code") or "").strip()
    if st:
        return st
    ctry = str(party.get("country_code") or "").strip().upper()
    if ctry and ctry not in ("IN", "IND"):
        return EXPORT
    g = str(party.get("vat_registration_no") or doc.get("customer_vat_no") or doc.get("supplier_vat_no") or "")
    if g[:2].isdigit():
        return g[:2]
    return _home()


def _split(tax, pos, home):
    tax = R(tax)
    if pos and home and pos != home:
        return {"igst": tax, "cgst": 0.0, "sgst": 0.0}
    c = round(tax / 2.0, 2)
    return {"igst": 0.0, "cgst": c, "sgst": R(tax - c)}


def _state_name(code):
    try:
        from modules import country as C
        return C.state_name(code, "IN")
    except Exception:
        return str(code or "")


def _pos_label(code):
    return ("%s-%s" % (code, _state_name(code))) if code else ""


def _parties(kind):
    t = "customers" if kind == "customer" else "suppliers"
    if not _has_table(t):
        return {}
    cols = ["%s_id" % kind, "country_code", "vat_registration_no"]
    if _has_col(t, "state_code"):
        cols.append("state_code")
    nm = "%s_name_en" % kind
    cols.append(nm)
    return {r["%s_id" % kind]: r for r in _q("SELECT %s FROM %s" % (", ".join(cols), t))}


def _sales_docs(f, t):
    """Every confirmed outward document line of the period, signed:
    invoices +, credit notes (type 381) and sales returns −, debit notes +.
    [{doc fields…, line fields…, sign, doc_type}]"""
    out = []
    pos_col = ", si.place_of_supply" if _has_col("sales_invoices", "place_of_supply") else ""
    kind_col = ", si.invoice_kind" if _has_col("sales_invoices", "invoice_kind") else ""
    br_col = ", si.branch_id" if _has_col("sales_invoices", "branch_id") else ""
    rows = _q("SELECT sil.*, si.invoice_id AS doc_id, si.invoice_number AS doc_no, si.invoice_date AS doc_date, "
              "si.customer_id, si.customer_name_en, si.customer_vat_no, si.total_amount AS doc_total, "
              "si.invoice_type_code%s%s%s FROM sales_invoice_lines sil "
              "JOIN sales_invoices si ON si.invoice_id=sil.invoice_id "
              "WHERE si.invoice_status='confirmed' AND si.invoice_date BETWEEN ? AND ?"
              % (pos_col, kind_col, br_col), (f, t))
    for r in rows:
        typ = str(r.get("invoice_type_code") or "388")
        d = dict(r)
        if typ == "381":
            d.update(sign=-1, doc_type="credit")
        elif typ == "383" or str(r.get("invoice_kind") or "").lower() == "debit":
            d.update(sign=1, doc_type="debit")
        else:
            d.update(sign=1, doc_type="invoice")
        out.append(d)
    if _has_table("sales_returns"):
        pos_col = ", r.place_of_supply" if _has_col("sales_returns", "place_of_supply") else ""
        br_col = ", r.branch_id" if _has_col("sales_returns", "branch_id") else ""
        for r in _q("SELECT l.*, r.return_id AS doc_id, r.return_number AS doc_no, r.return_date AS doc_date, "
                    "r.customer_id, r.customer_name_en, r.customer_vat_no, r.total_amount AS doc_total%s%s "
                    "FROM sales_return_lines l JOIN sales_returns r ON r.return_id=l.return_id "
                    "WHERE ISNULL(r.return_status,'confirmed')='confirmed' AND r.return_date BETWEEN ? AND ?"
                    % (pos_col, br_col), (f, t)):
            d = dict(r)
            d.update(sign=-1, doc_type="return")
            out.append(d)
    return out


def _purchase_docs(f, t):
    out = []
    pos_col = ", pi.place_of_supply" if _has_col("purchase_invoices", "place_of_supply") else ""
    for r in _q("SELECT pil.*, pi.purchase_id AS doc_id, pi.invoice_number AS doc_no, pi.invoice_date AS doc_date, "
                "pi.supplier_id, pi.supplier_name_en, pi.supplier_vat_no%s FROM purchase_invoice_lines pil "
                "JOIN purchase_invoices pi ON pi.purchase_id=pil.purchase_id "
                "WHERE pi.invoice_status='confirmed' AND pi.invoice_date BETWEEN ? AND ?" % pos_col, (f, t)):
        d = dict(r)
        d.update(sign=1, doc_type="purchase")
        out.append(d)
    if _has_table("purchase_returns"):
        pos_col = ", r.place_of_supply" if _has_col("purchase_returns", "place_of_supply") else ""
        for r in _q("SELECT l.*, r.return_id AS doc_id, r.return_number AS doc_no, r.return_date AS doc_date, "
                    "r.supplier_id, r.supplier_name_en, r.supplier_vat_no%s FROM purchase_return_lines l "
                    "JOIN purchase_returns r ON r.return_id=l.return_id "
                    "WHERE ISNULL(r.return_status,'confirmed')='confirmed' AND r.return_date BETWEEN ? AND ?"
                    % pos_col, (f, t)):
            d = dict(r)
            d.update(sign=-1, doc_type="purchase_return")
            out.append(d)
    return out


def _expenses(f, t):
    if not _has_table("expenses"):
        return []
    sup = ", supplier_id" if _has_col("expenses", "supplier_id") else ""
    return _q("SELECT expense_id, expense_date, amount, vat_amount%s FROM expenses "
              "WHERE ISNULL(vat_amount,0) <> 0 AND expense_date BETWEEN ? AND ?" % sup, (f, t))


def _foreign(party, home_country):
    c = str((party or {}).get("country_code") or "").strip().upper()
    return bool(c) and c not in home_country


# ════════════════════════════════════════════════════════════
#  UAE — VAT 201
# ════════════════════════════════════════════════════════════
def vat201_data(date_from, date_to):
    f, t = date_from, date_to
    kinds = _kinds()
    comp = _company()
    home_em = str(comp.get("state_code") or "DU").strip().upper() or "DU"
    branch_em = {}
    if _has_table("branches") and _has_col("branches", "state_code"):
        branch_em = {r["branch_id"]: str(r.get("state_code") or "").strip().upper()
                     for r in _q("SELECT branch_id, state_code FROM branches")}
    em = OrderedDict((k, {"amt": 0.0, "vat": 0.0, "adj": 0.0}) for k in EMIRATES)
    zero = {"amt": 0.0, "adj": 0.0}
    exempt = {"amt": 0.0, "adj": 0.0}
    custs = _parties("customer")
    for ln in _sales_docs(f, t):
        k = _line_kind(kinds, ln)
        sg = ln["sign"]
        amt, vat = _f(ln.get("line_amount")), _f(ln.get("vat_amount"))
        if k == "std":
            e = branch_em.get(ln.get("branch_id")) or home_em
            e = e if e in em else home_em
            if sg > 0:
                em[e]["amt"] += amt
                em[e]["vat"] += vat
            else:
                em[e]["adj"] -= amt
                em[e]["vat"] -= vat
        elif k == "zero" or _foreign(custs.get(ln.get("customer_id")), ("AE", "ARE")):
            if sg > 0:
                zero["amt"] += amt
            else:
                zero["adj"] -= amt
        elif k in ("exempt", "nil"):
            if sg > 0:
                exempt["amt"] += amt
            else:
                exempt["adj"] -= amt
    sups = _parties("supplier")
    std_exp = {"amt": 0.0, "vat": 0.0, "adj": 0.0}
    imp = {"amt": 0.0, "vat": 0.0}
    for ln in _purchase_docs(f, t):
        k = _line_kind(kinds, ln)
        amt, vat = _f(ln.get("line_amount")), _f(ln.get("vat_amount"))
        if _foreign(sups.get(ln.get("supplier_id")), ("AE", "ARE")):
            # goods imported: VAT under reverse charge (box 6 due, box 10 recovered)
            v = vat if abs(vat) > 0.004 else (amt * 0.05 if k != "exempt" else 0.0)
            imp["amt"] += ln["sign"] * amt
            imp["vat"] += ln["sign"] * v
            continue
        if k == "std":
            if ln["sign"] > 0:
                std_exp["amt"] += amt
                std_exp["vat"] += vat
            else:
                std_exp["adj"] -= amt
                std_exp["vat"] -= vat
    exp_n = {"amt": 0.0, "vat": 0.0}
    for e in _expenses(f, t):
        exp_n["amt"] += _f(e.get("amount"))
        exp_n["vat"] += _f(e.get("vat_amount"))
    std_exp["amt"] += exp_n["amt"]
    std_exp["vat"] += exp_n["vat"]

    boxes = []

    def box(no, label, amt=None, vat=None, adj=None, style=""):
        boxes.append({"box": no, "label": label, "amount": None if amt is None else R(amt),
                      "vat": None if vat is None else R(vat), "adjustment": None if adj is None else R(adj),
                      "_style": style})
    letters = "abcdefg"
    for i, (k, nm) in enumerate(EMIRATES.items()):
        d = em[k]
        box("1" + letters[i], "Standard rated supplies in %s" % nm, d["amt"], d["vat"], d["adj"],
            "hi" if (d["amt"] or d["adj"]) else "")
    box("2", "Tax refunds provided to tourists (Tax Refunds for Tourists Scheme)", 0, 0, 0)
    box("3", "Supplies subject to the reverse charge provisions", 0, 0, None)
    box("4", "Zero rated supplies", zero["amt"], None, zero["adj"])
    box("5", "Exempt supplies", exempt["amt"], None, exempt["adj"])
    box("6", "Goods imported into the UAE", imp["amt"], imp["vat"], None)
    box("7", "Adjustments to goods imported into the UAE", 0, 0, None)
    out_amt = sum(d["amt"] for d in em.values()) + zero["amt"] + exempt["amt"] + imp["amt"]
    out_adj = sum(d["adj"] for d in em.values()) + zero["adj"] + exempt["adj"]
    out_vat = sum(d["vat"] for d in em.values()) + imp["vat"]
    box("8", "Totals (sales and all other outputs)", out_amt, out_vat, out_adj, "total")
    box("9", "Standard rated expenses (purchases + expenses)", std_exp["amt"], std_exp["vat"],
        std_exp["adj"], "hi")
    box("10", "Supplies subject to the reverse charge provisions (imports)", imp["amt"], imp["vat"], None)
    in_amt = std_exp["amt"] + imp["amt"]
    in_vat = std_exp["vat"] + imp["vat"]
    box("11", "Totals (expenses and all other inputs)", in_amt, in_vat, std_exp["adj"], "total")
    box("12", "Total value of due tax for the period", None, out_vat, None, "total")
    box("13", "Total value of recoverable tax for the period", None, in_vat, None, "total")
    payable = R(out_vat - in_vat)
    box("14", "Payable tax for the period" if payable >= 0 else "Tax refundable for the period",
        None, payable, None, "grand")
    return {"boxes": boxes, "due": R(out_vat), "recoverable": R(in_vat), "payable": payable,
            "imports": {k: R(v) for k, v in imp.items()}, "expenses": {k: R(v) for k, v in exp_n.items()},
            "home_emirate": home_em}


@report("uae_vat201", GROUP_AE, "VAT 201 Return",
        desc="UAE FTA VAT return: standard rated sales by emirate (1a-1g), zero rated, exempt, "
             "imports under reverse charge, standard rated expenses, payable tax.",
        needs="country:AE")
def r_uae_vat201(date_from, date_to, **_):
    d = vat201_data(date_from, date_to)
    cols = [col("box", "Box", width=50), col("label", "Description", width=380),
            col("amount", "Amount (AED)", "money"), col("vat", "VAT amount (AED)", "money"),
            col("adjustment", "Adjustment (AED)", "money")]
    summ = [("Due tax", d["due"], "money"), ("Recoverable tax", d["recoverable"], "money"),
            ("Payable tax" if d["payable"] >= 0 else "Refundable", abs(d["payable"]), "money")]
    notes = ["Sales are shown in the emirate of the branch that made them (Branches ▸ emirate), else "
             "the company's emirate (%s)." % EMIRATES.get(d["home_emirate"], d["home_emirate"]),
             "Credit notes and sales returns are in the Adjustment column of their emirate.",
             "Purchases from suppliers outside the UAE are imports: VAT 5%% under reverse charge is in box 6 "
             "and recovered in box 10 (%s)." % format(d["imports"]["vat"], ",.2f"),
             "Expenses with VAT included in box 9: %s (VAT %s)." % (format(d["expenses"]["amt"], ",.2f"),
                                                                    format(d["expenses"]["vat"], ",.2f")),
             "Boxes 2, 3 and 7 are not tracked by DayBill — type them on the FTA portal if you have them.",
             "Check the figures with your documents before you file on EmaraTax."]
    return _result("VAT 201 Return", cols, [dict(b) for b in d["boxes"]], None, summ, notes)


# ════════════════════════════════════════════════════════════
#  INDIA — GSTR-3B and GSTR-1
# ════════════════════════════════════════════════════════════
def _gst_rows(f, t):
    """Outward lines with place of supply, registration and split."""
    kinds = _kinds()
    home = _home()
    custs = _parties("customer")
    out = []
    for ln in _sales_docs(f, t):
        party = custs.get(ln.get("customer_id")) or {}
        pos = _pos(ln, party)
        gstin = str(ln.get("customer_vat_no") or party.get("vat_registration_no") or "").strip().upper()
        k = _line_kind(kinds, ln)
        if pos == EXPORT and k == "std":
            k = "export_paid"                  # export with IGST paid
        elif pos == EXPORT:
            k = "zero"
        d = dict(ln, pos=pos, gstin=gstin, kind=k, taxable=_f(ln.get("line_amount")),
                 tax=_f(ln.get("vat_amount")), rate=_f(ln.get("vat_rate")))
        d.update(_split(d["tax"], pos, home) if k in ("std",) else
                 ({"igst": d["tax"], "cgst": 0.0, "sgst": 0.0} if k == "export_paid" else
                  {"igst": 0.0, "cgst": 0.0, "sgst": 0.0}))
        out.append(d)
    return out, home


def gstr3b_data(date_from, date_to):
    f, t = date_from, date_to
    rows, home = _gst_rows(f, t)
    s31 = OrderedDict((k, {"taxable": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0})
                      for k in ("a", "b", "c", "d", "e"))
    s32 = OrderedDict()
    for r in rows:
        sg = r["sign"]
        k = r["kind"]
        key = {"std": "a", "export_paid": "b", "zero": "b", "nil": "c", "exempt": "c", "oos": "e"}.get(k, "a")
        b = s31[key]
        b["taxable"] += sg * r["taxable"]
        for h in ("igst", "cgst", "sgst"):
            b[h] += sg * r[h]
        if k == "std" and not r["gstin"] and r["pos"] not in (home, EXPORT):
            x = s32.setdefault(r["pos"], {"taxable": 0.0, "igst": 0.0})
            x["taxable"] += sg * r["taxable"]
            x["igst"] += sg * r["igst"]
    # ── ITC ──
    kinds = _kinds()
    sups = _parties("supplier")
    itc = OrderedDict((k, {"igst": 0.0, "cgst": 0.0, "sgst": 0.0}) for k in ("import", "other", "reversed"))
    inward = {"inter": 0.0, "intra": 0.0}
    for ln in _purchase_docs(f, t):
        party = sups.get(ln.get("supplier_id")) or {}
        k = _line_kind(kinds, ln)
        tax = _f(ln.get("vat_amount"))
        if k in ("nil", "exempt", "oos", "zero") and abs(tax) < 0.005:
            pos = _pos(ln, party)
            inward["inter" if pos != home else "intra"] += ln["sign"] * _f(ln.get("line_amount"))
            continue
        if _foreign(party, ("IN", "IND")):
            sp = {"igst": tax, "cgst": 0.0, "sgst": 0.0}
            bucket = "import"
        else:
            sp = _split(tax, _pos(ln, party), home)
            bucket = "other"
        if ln["sign"] < 0:
            bucket = "reversed"
        for h in sp:
            itc[bucket][h] += sp[h]
    for e in _expenses(f, t):
        party = sups.get(e.get("supplier_id")) or {}
        sp = _split(e.get("vat_amount"), _pos({}, party) if party else home, home)
        for h in sp:
            itc["other"][h] += sp[h]
    net = {h: itc["import"][h] + itc["other"][h] - itc["reversed"][h] for h in ("igst", "cgst", "sgst")}
    liab = {h: s31["a"][h] + s31["b"][h] for h in ("igst", "cgst", "sgst")}
    setoff = _setoff(liab, net)
    return {"s31": s31, "s32": s32, "itc": itc, "itc_net": net, "inward": inward,
            "liability": liab, "setoff": setoff, "home": home}


def _setoff(liab, credit):
    """ITC set-off (Rule 88A): IGST credit first — on IGST, then CGST,
    then SGST; then CGST credit on CGST then IGST; then SGST credit on
    SGST then IGST. CGST never pays SGST and SGST never pays CGST.
    Returns {head: {"liability", "igst", "cgst", "sgst", "cash"}} and the
    credit left over."""
    L = {h: max(R(liab[h]), 0.0) for h in liab}
    Cr = {h: max(R(credit[h]), 0.0) for h in credit}
    used = {h: {"igst": 0.0, "cgst": 0.0, "sgst": 0.0} for h in L}

    def use(src, dst):
        x = min(Cr[src], L[dst])
        if x > 0:
            Cr[src] = R(Cr[src] - x)
            L[dst] = R(L[dst] - x)
            used[dst][src] = R(used[dst][src] + x)
    for dst in ("igst", "cgst", "sgst"):
        use("igst", dst)
    use("cgst", "cgst")
    use("cgst", "igst")
    use("sgst", "sgst")
    use("sgst", "igst")
    out = {h: {"liability": R(liab[h]), "igst": used[h]["igst"], "cgst": used[h]["cgst"],
               "sgst": used[h]["sgst"], "cash": L[h]} for h in L}
    return {"heads": out, "left": Cr}


@report("gstr3b", GROUP_GST, "GSTR-3B Summary",
        desc="Monthly GST summary: 3.1 outward supplies, 3.2 inter-state supplies to unregistered "
             "persons, 4 eligible ITC, 5 exempt inward supplies, 6.1 tax payable after ITC set-off.",
        needs="country:IN")
def r_gstr3b(date_from, date_to, **_):
    d = gstr3b_data(date_from, date_to)
    rows = []

    def sec(title):
        no, _, text = title.partition("  ")
        rows.append({"sec": no, "label": text.upper(), "_style": "total"})

    def row(no, label, b, style=""):
        rows.append({"sec": no, "label": label, "taxable": None if b.get("taxable") is None else R(b.get("taxable")),
                     "igst": R(b.get("igst")), "cgst": R(b.get("cgst")), "sgst": R(b.get("sgst")),
                     "cess": 0.0, "_style": style})
    sec("3.1  Outward supplies and inward supplies liable to reverse charge")
    s = d["s31"]
    row("(a)", "Outward taxable supplies (other than zero rated, nil rated and exempted)", s["a"], "hi")
    row("(b)", "Outward taxable supplies (zero rated)", s["b"])
    row("(c)", "Other outward supplies (nil rated, exempted)", s["c"])
    row("(d)", "Inward supplies (liable to reverse charge)", s["d"])
    row("(e)", "Non-GST outward supplies", s["e"])
    sec("3.2  Inter-state supplies to unregistered persons (place of supply)")
    for pos, x in d["s32"].items():
        row("", _pos_label(pos), {"taxable": x["taxable"], "igst": x["igst"]})
    if not d["s32"]:
        rows.append({"sec": "", "label": "— none —"})
    sec("4  Eligible ITC")
    it = d["itc"]
    row("(A)(1)", "Import of goods", it["import"])
    row("(A)(5)", "All other ITC (purchases and expenses)", it["other"])
    row("(B)(2)", "ITC reversed — others (purchase returns)", it["reversed"])
    row("(C)", "Net ITC available (A − B)", dict(d["itc_net"], taxable=None), "hi")
    sec("5  Values of exempt, nil-rated and non-GST inward supplies")
    rows.append({"sec": "", "label": "Inter-state supplies", "taxable": R(d["inward"]["inter"])})
    rows.append({"sec": "", "label": "Intra-state supplies", "taxable": R(d["inward"]["intra"])})
    sec("6.1  Payment of tax (ITC set-off, then cash)")
    so = d["setoff"]["heads"]
    for h in ("igst", "cgst", "sgst"):
        x = so[h]
        rows.append({"sec": h.upper(), "label": "Tax payable %s · paid by ITC: IGST %s, CGST %s, SGST %s"
                     % (format(x["liability"], ",.2f"), format(x["igst"], ",.2f"), format(x["cgst"], ",.2f"),
                        format(x["sgst"], ",.2f")),
                     "taxable": None, h: R(x["cash"]), "_style": "hi" if x["cash"] else ""})
    cols = [col("sec", "Table", width=70), col("label", "Nature of supplies", width=380),
            col("taxable", "Taxable value", "money"), col("igst", "Integrated tax", "money"),
            col("cgst", "Central tax", "money"), col("sgst", "State / UT tax", "money"),
            col("cess", "Cess", "money", 70)]
    cash = sum(so[h]["cash"] for h in so)
    left = d["setoff"]["left"]
    summ = [("Tax on outward supplies", sum(d["liability"].values()), "money"),
            ("Net ITC", sum(d["itc_net"].values()), "money"),
            ("Pay in cash", cash, "money"),
            ("ITC carried forward", sum(left.values()), "money")]
    notes = ["Place of supply: the bill's own (Sales Invoice ▸ Supply to), else the customer's state, "
             "else 96 for customers abroad, else the company's state (%s)." % _pos_label(d["home"]),
             "Same state → CGST + SGST (UTGST in a Union Territory); another state or abroad → IGST.",
             "Credit notes and sales returns reduce the period they are dated in.",
             "6.1 follows Rule 88A: IGST credit is used first (IGST, then CGST, then SGST); CGST credit "
             "never pays SGST and SGST credit never pays CGST.",
             "Reverse charge, ISD and cess are not tracked by DayBill — add them on the GST portal if you have them.",
             "Check the figures with your books before you file GSTR-3B."]
    return _result("GSTR-3B Summary", cols, rows, None, summ, notes)


def _limit():
    try:
        from config import settings as cfg
        return _f(cfg.get("gst_b2cl_limit", 100000)) or 100000.0
    except Exception:
        return 100000.0


def _by_doc_rate(rows, keep):
    """Group outward lines by (document, rate)."""
    g = OrderedDict()
    for r in rows:
        if not keep(r):
            continue
        key = (r["doc_type"], r["doc_id"], r["rate"])
        x = g.get(key)
        if x is None:
            x = g[key] = dict(r, taxable=0.0, tax=0.0, igst=0.0, cgst=0.0, sgst=0.0)
        for k in ("taxable", "tax", "igst", "cgst", "sgst"):
            x[k] += r[k]
    return list(g.values())


@report("gstr1_b2b", GROUP_GST, "GSTR-1 · B2B Invoices (4A)",
        desc="Invoices to registered buyers (with a GSTIN): one row per invoice and rate.",
        needs="country:IN")
def r_gstr1_b2b(date_from, date_to, **_):
    rows, home = _gst_rows(date_from, date_to)
    out = []
    for x in _by_doc_rate(rows, lambda r: r["gstin"] and r["doc_type"] in ("invoice",)
                          and r["kind"] in ("std", "zero", "nil", "exempt", "export_paid")):
        out.append({"gstin": x["gstin"], "name": x.get("customer_name_en") or "", "no": x["doc_no"],
                    "date": _d(x["doc_date"]), "value": R(x.get("doc_total")), "pos": _pos_label(x["pos"]),
                    "rc": "N", "type": "SEZ / Export" if x["pos"] == EXPORT else "Regular B2B",
                    "rate": x["rate"], "taxable": R(x["taxable"]), "igst": R(x["igst"]),
                    "cgst": R(x["cgst"]), "sgst": R(x["sgst"]), "cess": 0.0})
    cols = [col("gstin", "GSTIN/UIN of Recipient", width=150), col("name", "Receiver Name", width=170),
            col("no", "Invoice Number", width=100), col("date", "Invoice date", "date", 90),
            col("value", "Invoice Value", "money"), col("pos", "Place Of Supply", width=150),
            col("rc", "Reverse Charge", width=70), col("type", "Invoice Type", width=100),
            col("rate", "Rate", "pct", 60), col("taxable", "Taxable Value", "money"),
            col("igst", "IGST", "money", 90), col("cgst", "CGST", "money", 90), col("sgst", "SGST", "money", 90),
            col("cess", "Cess Amount", "money", 80)]
    tot = _sum_totals(out, ("taxable", "igst", "cgst", "sgst"), "gstin")
    n = len({r["no"] for r in out})
    return _result("GSTR-1 · B2B Invoices", cols, out, tot,
                   [("Invoices", n, "int"), ("Taxable value", tot["taxable"], "money"),
                    ("Tax", R(tot["igst"] + tot["cgst"] + tot["sgst"]), "money")],
                   ["Export: Report Center ▸ Excel — the columns follow the GST offline tool (b2b sheet)."])


@report("gstr1_b2cl", GROUP_GST, "GSTR-1 · B2C Large (5)",
        desc="Inter-state invoices to unregistered buyers above the B2CL limit (₹1,00,000).",
        needs="country:IN")
def r_gstr1_b2cl(date_from, date_to, **_):
    rows, home = _gst_rows(date_from, date_to)
    lim = _limit()
    out = []
    for x in _by_doc_rate(rows, lambda r: not r["gstin"] and r["doc_type"] == "invoice" and r["kind"] == "std"
                          and r["pos"] not in (home, EXPORT) and _f(r.get("doc_total")) > lim):
        out.append({"no": x["doc_no"], "date": _d(x["doc_date"]), "value": R(x.get("doc_total")),
                    "pos": _pos_label(x["pos"]), "rate": x["rate"], "taxable": R(x["taxable"]),
                    "igst": R(x["igst"]), "cess": 0.0})
    cols = [col("no", "Invoice Number", width=110), col("date", "Invoice date", "date", 90),
            col("value", "Invoice Value", "money"), col("pos", "Place Of Supply", width=170),
            col("rate", "Rate", "pct", 60), col("taxable", "Taxable Value", "money"),
            col("igst", "IGST", "money"), col("cess", "Cess Amount", "money", 80)]
    tot = _sum_totals(out, ("taxable", "igst"), "no")
    return _result("GSTR-1 · B2C Large", cols, out, tot,
                   [("Invoices", len({r["no"] for r in out}), "int"), ("Taxable value", tot["taxable"], "money")],
                   ["Limit: invoice value above %s (Settings ▸ company option gst_b2cl_limit)." % format(lim, ",.0f")])


@report("gstr1_b2cs", GROUP_GST, "GSTR-1 · B2C Small (7)",
        desc="All other sales to unregistered buyers, net of their credit notes, by place of supply and rate.",
        needs="country:IN")
def r_gstr1_b2cs(date_from, date_to, **_):
    rows, home = _gst_rows(date_from, date_to)
    lim = _limit()
    g = OrderedDict()
    for r in rows:
        if r["gstin"] or r["kind"] != "std" or r["pos"] == EXPORT:
            continue
        big = r["doc_type"] == "invoice" and r["pos"] != home and _f(r.get("doc_total")) > lim
        if big:
            continue
        key = (r["pos"], r["rate"])
        x = g.setdefault(key, {"type": "OE", "pos": _pos_label(r["pos"]), "rate": r["rate"],
                               "taxable": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0})
        sg = r["sign"]
        x["taxable"] += sg * r["taxable"]
        for h in ("igst", "cgst", "sgst"):
            x[h] += sg * r[h]
    out = [dict(x, taxable=R(x["taxable"]), igst=R(x["igst"]), cgst=R(x["cgst"]), sgst=R(x["sgst"]))
           for x in g.values()]
    cols = [col("type", "Type", width=50), col("pos", "Place Of Supply", width=200), col("rate", "Rate", "pct", 60),
            col("taxable", "Taxable Value", "money"), col("igst", "IGST", "money"), col("cgst", "CGST", "money"),
            col("sgst", "SGST / UTGST", "money"), col("cess", "Cess Amount", "money", 80)]
    tot = _sum_totals(out, ("taxable", "igst", "cgst", "sgst"), "type")
    return _result("GSTR-1 · B2C Small", cols, out, tot,
                   [("Taxable value", tot["taxable"], "money"),
                    ("Tax", R(tot["igst"] + tot["cgst"] + tot["sgst"]), "money")],
                   ["OE = other than e-commerce. Credit notes / returns to unregistered buyers are taken off here."])


@report("gstr1_cdnr", GROUP_GST, "GSTR-1 · Credit / Debit Notes (9B)",
        desc="Credit notes, sales returns and debit notes to registered buyers.",
        needs="country:IN")
def r_gstr1_cdnr(date_from, date_to, **_):
    rows, home = _gst_rows(date_from, date_to)
    out = []
    for x in _by_doc_rate(rows, lambda r: r["gstin"] and r["doc_type"] in ("credit", "return", "debit")):
        out.append({"gstin": x["gstin"], "name": x.get("customer_name_en") or "", "no": x["doc_no"],
                    "date": _d(x["doc_date"]), "ntype": "D" if x["doc_type"] == "debit" else "C",
                    "pos": _pos_label(x["pos"]), "rc": "N", "value": R(x.get("doc_total")),
                    "rate": x["rate"], "taxable": R(x["taxable"]), "igst": R(x["igst"]),
                    "cgst": R(x["cgst"]), "sgst": R(x["sgst"]), "cess": 0.0})
    cols = [col("gstin", "GSTIN/UIN of Recipient", width=150), col("name", "Receiver Name", width=160),
            col("no", "Note Number", width=100), col("date", "Note Date", "date", 90),
            col("ntype", "Note Type", width=60), col("pos", "Place Of Supply", width=150),
            col("rc", "Reverse Charge", width=70), col("value", "Note Value", "money"),
            col("rate", "Rate", "pct", 60), col("taxable", "Taxable Value", "money"),
            col("igst", "IGST", "money", 90), col("cgst", "CGST", "money", 90), col("sgst", "SGST", "money", 90),
            col("cess", "Cess Amount", "money", 80)]
    tot = _sum_totals(out, ("taxable", "igst", "cgst", "sgst"), "gstin")
    return _result("GSTR-1 · Credit / Debit Notes", cols, out, tot,
                   [("Notes", len({r["no"] for r in out}), "int"), ("Taxable value", tot["taxable"], "money")],
                   ["C = credit note (sales return), D = debit note. Amounts are shown positive, as the portal wants."])


@report("gstr1_hsn", GROUP_GST, "GSTR-1 · HSN Summary (12)",
        desc="Outward supplies by HSN / SAC code and rate, split B2B and B2C, net of returns.",
        needs="country:IN")
def r_gstr1_hsn(date_from, date_to, **_):
    rows, home = _gst_rows(date_from, date_to)
    hsn = {}
    if _has_col("products", "hsn_code"):
        hsn = {r["product_id"]: (str(r.get("hsn_code") or "").strip(), r.get("product_name_en") or "",
                                 r.get("unit_of_measure_en") or "")
               for r in _q("SELECT product_id, hsn_code, product_name_en, unit_of_measure_en FROM products")}
    try:
        from config import settings as cfg
        digits = int(cfg.get("gst_hsn_digits", 4) or 4)
    except Exception:
        digits = 4
    g = OrderedDict()
    missing = 0
    for r in rows:
        if r["kind"] in ("oos",):
            continue
        h, nm, uqc = hsn.get(r.get("product_id"), ("", r.get("product_name_en") or "", ""))
        if not h:
            missing += 1
        code = h[:max(digits, 4)] if h else "—"
        key = ("B2B" if r["gstin"] else "B2C", code, r["rate"])
        x = g.setdefault(key, {"supply": key[0], "hsn": code, "desc": nm if h else "(no HSN code)",
                               "uqc": (r.get("unit_of_measure_en") or uqc or "OTH").upper()[:3],
                               "qty": 0.0, "value": 0.0, "rate": r["rate"], "taxable": 0.0,
                               "igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0})
        sg = r["sign"]
        x["qty"] += sg * _f(r.get("quantity"))
        x["value"] += sg * (_f(r.get("line_total")) or r["taxable"] + r["tax"])
        x["taxable"] += sg * r["taxable"]
        for k in ("igst", "cgst", "sgst"):
            x[k] += sg * r[k]
    out = [dict(x, qty=round(x["qty"], 3), value=R(x["value"]), taxable=R(x["taxable"]), igst=R(x["igst"]),
                cgst=R(x["cgst"]), sgst=R(x["sgst"])) for x in g.values()]
    out.sort(key=lambda x: (x["supply"], x["hsn"], x["rate"]))
    cols = [col("supply", "B2B / B2C", width=70), col("hsn", "HSN", width=80), col("desc", "Description", width=180),
            col("uqc", "UQC", width=50), col("qty", "Total Quantity", "qty", 90), col("value", "Total Value", "money"),
            col("rate", "Rate", "pct", 60), col("taxable", "Taxable Value", "money"),
            col("igst", "Integrated Tax Amount", "money"), col("cgst", "Central Tax Amount", "money"),
            col("sgst", "State/UT Tax Amount", "money"), col("cess", "Cess Amount", "money", 80)]
    tot = _sum_totals(out, ("value", "taxable", "igst", "cgst", "sgst"), "supply")
    notes = ["HSN digits: %d (turnover up to ₹5 crore: 4 digits; above: 6 digits — company option gst_hsn_digits)."
             % digits]
    if missing:
        notes.append("⚠ %d sold line(s) have no HSN / SAC code — add it in Products ▸ Price & Tax." % missing)
    return _result("GSTR-1 · HSN Summary", cols, out, tot,
                   [("HSN rows", len(out), "int"), ("Taxable value", tot["taxable"], "money")], notes)


@report("gstr1_docs", GROUP_GST, "GSTR-1 · Documents Issued (13)",
        desc="Number series of invoices, credit notes and debit notes issued in the period, with cancelled ones.",
        needs="country:IN")
def r_gstr1_docs(date_from, date_to, **_):
    out = []

    def series(nature, rows, cancelled):
        nums = [str(r.get("n") or "") for r in rows if r.get("n")]
        if not nums:
            return

        def keyf(s):
            digits = "".join(ch for ch in s if ch.isdigit())
            return (len(digits), digits, s)
        nums.sort(key=keyf)
        out.append({"nature": nature, "from": nums[0], "to": nums[-1], "total": len(nums),
                    "cancelled": cancelled, "net": len(nums) - cancelled})
    inv = _q("SELECT invoice_number AS n, invoice_status AS s, invoice_type_code AS t FROM sales_invoices "
             "WHERE invoice_date BETWEEN ? AND ? AND invoice_status IN ('confirmed','cancelled')",
             (date_from, date_to))
    series("Invoices for outward supply", [r for r in inv if str(r.get("t") or "388") == "388"],
           sum(1 for r in inv if str(r.get("t") or "388") == "388" and r.get("s") == "cancelled"))
    series("Debit Note", [r for r in inv if str(r.get("t")) == "383"],
           sum(1 for r in inv if str(r.get("t")) == "383" and r.get("s") == "cancelled"))
    cn = [r for r in inv if str(r.get("t")) == "381"]
    if _has_table("sales_returns"):
        cn += _q("SELECT return_number AS n, return_status AS s FROM sales_returns WHERE return_date BETWEEN ? AND ? "
                 "AND ISNULL(return_status,'confirmed') IN ('confirmed','cancelled')", (date_from, date_to))
    series("Credit Note", cn, sum(1 for r in cn if r.get("s") == "cancelled"))
    cols = [col("nature", "Nature of Document", width=230), col("from", "Sr. No. From", width=110),
            col("to", "Sr. No. To", width=110), col("total", "Total Number", "int", 90),
            col("cancelled", "Cancelled", "int", 80), col("net", "Net issued", "int", 80)]
    return _result("GSTR-1 · Documents Issued", cols, out, None,
                   [("Documents", sum(r["total"] for r in out), "int")], [])
