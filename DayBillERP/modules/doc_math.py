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
# ============================================================


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
