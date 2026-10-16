# ============================================================
# DayBill ERP - document maths shared by the transaction windows (v6.9)
# ------------------------------------------------------------
# spread_bill_adjustment(lines, amount, tax_inclusive)
#
#   A bill discount (and the Round box) used to change only the total on
#   the screen — the saved invoice, the journal, the print and ZATCA kept
#   the lines' total. Now the amount is spread over the lines BEFORE VAT:
#
#     • each line takes a share in proportion to its value (VAT included);
#       the last line takes the cents that are left, so the shares add up
#       exactly to the amount
#     • the share is added to the line's discount (on the price basis:
#       VAT-inclusive prices → the share itself, exclusive → share / 1.15)
#     • the line's taxable amount and VAT are worked out again, so
#       taxable + VAT = total on every line and on the bill
#
#   amount > 0  takes money off (bill discount, rounding down)
#   amount < 0  adds money (rounding up)
#   The lines given are not changed — new dicts are returned.
#
# doc_totals(lines, inclusive)          (v6.9.2)
#
#   The bill's taxable / VAT / total the ZATCA way: every line's taxable
#   amount is rounded to 2 decimals, then the VAT is worked out ONCE per
#   VAT rate on their sum. That is the number the ZATCA XML and the
#   Phase 2 QR carry, so the printed VAT, the books and the e-invoice all
#   agree (adding up each line's rounded VAT could be a few halalas off).
#     inclusive (prices with VAT): total = what the lines add up to,
#                                  taxable = total - VAT
#     exclusive (prices without):  taxable = the lines' taxable amounts,
#                                  total = taxable + VAT
#
# round_lines(lines)  → each line's taxable / VAT / total in halalas,
#   adding up exactly (taxable + VAT = total), the total kept.
# ============================================================

from decimal import Decimal, ROUND_HALF_UP


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def spread_bill_adjustment(lines, amount, tax_inclusive=True):
    out = [dict(l) for l in (lines or [])]
    amount = round(_f(amount), 2)
    base = [l for l in out if _f(l.get("line_total")) > 0]
    total = round(sum(_f(l.get("line_total")) for l in base), 2)
    if abs(amount) < 0.005 or total <= 0:
        return out
    amount = min(amount, total)                    # a bill never goes below zero
    left = amount
    for i, ln in enumerate(base):
        old_total = _f(ln.get("line_total"))
        if i == len(base) - 1:
            share = round(left, 2)
        else:
            share = round(amount * old_total / total, 2)
        left = round(left - share, 2)
        net0 = _f(ln.get("line_amount"))
        rate = (_f(ln.get("vat_amount")) / net0) if net0 else 0.0   # this line's real VAT rate
        new_total = round(old_total - share, 2)
        new_net = round(new_total / (1 + rate), 2) if rate else new_total
        new_vat = round(new_total - new_net, 2)
        disc_add = share if (tax_inclusive or not rate) else share / (1 + rate)
        disc = round(_f(ln.get("discount_amount")) + disc_add, 4)
        qty, price = _f(ln.get("quantity")), _f(ln.get("unit_price"))
        ln.update(discount_amount=disc, line_amount=new_net, vat_amount=new_vat,
                  line_total=new_total,
                  discount_percent=round(disc * 100.0 / (qty * price), 2) if qty * price else 0.0,
                  bill_share=share)
    return out


def r2(v):
    """Round to 2 decimals, half up (the ZATCA way — float round() is not).
    3 × 3.335 is 10.004999… as a float: it is cleaned to 10.005 first."""
    try:
        return float(Decimal(repr(round(float(v or 0), 9))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (TypeError, ValueError, ArithmeticError):
        return 0.0


def _line_rate(ln, rate_key, vat_key, code_key):
    """The VAT rate a line really carries (0 for zero-rated / exempt /
    out of scope, and for a line saved without VAT)."""
    if abs(_f(ln.get(vat_key))) < 0.005:
        return 0.0
    code = str(ln.get(code_key) or "S").strip().upper()[:1]
    if code in ("Z", "E", "O"):
        return 0.0
    return _f(ln.get(rate_key)) or 15.0


def doc_totals(lines, inclusive=True, net="line_amount", vat="vat_amount",
               total="line_total", rate="vat_rate", code="vat_category_code"):
    """{"taxable", "vat", "total"} of a bill, the ZATCA way (see top)."""
    by_rate, tot = {}, 0.0
    for ln in lines or []:
        n = r2(ln.get(net))
        rt = _line_rate(ln, rate, vat, code)
        by_rate[rt] = by_rate.get(rt, 0.0) + n
        tot += r2(ln.get(total))
    v = r2(sum(r2(base * rt / 100.0) for rt, base in by_rate.items()))
    if inclusive:
        t = r2(tot)
        return {"taxable": r2(t - v), "vat": v, "total": t}
    tx = r2(sum(by_rate.values()))
    return {"taxable": tx, "vat": v, "total": r2(tx + v)}


def round_lines(lines, net="line_amount", vat="vat_amount", total="line_total"):
    """New dicts: each line in halalas with taxable + VAT = total."""
    out = []
    for ln in lines or []:
        d = dict(ln)
        n, t = r2(d.get(net)), r2(d.get(total))
        d[net], d[total] = n, t
        d[vat] = r2(t - n)
        out.append(d)
    return out
