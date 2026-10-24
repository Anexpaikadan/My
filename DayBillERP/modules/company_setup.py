# ============================================================
# DayBill ERP - set up a company for its country (v7.0)
# ------------------------------------------------------------
# The New Company wizard makes an empty DayBill database (the all-in-one
# install script) and then calls setup() here, which makes the company
# work the way its country works:
#
#   company row      name, address, tax number, country, state / emirate,
#                    currency + symbol, business modules, financial year
#   tax categories   SA: S 15 % · Z · E · O
#                    AE: S 5 % · Z · E · O
#                    IN: S 18 % · G5 · G40 · G3 · G0 nil · Z · E · O
#                        (12 % / 28 % kept, switched off)
#   tax accounts     SA / AE: VAT Output 2210 · VAT Input 2220
#                    IN: Output CGST 2211 · SGST 2212 · IGST 2213
#                        Input  CGST 2221 · SGST 2222 · IGST 2223
#   financial year   India April – March (the current one is replaced
#                    while the database is still empty)
#   options          currency symbol, round-off, price with / without
#                    tax, business-module settings (company_options)
#
#   setup(info)        → (ok, message)   info = dict, see NEW_COMPANY
#   is_empty()         True while the database has no documents yet
#   change_country(c)  allowed only while the database is empty
# ============================================================

from datetime import date

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

from modules import country as C
from modules import business as B

# what the wizard hands over
NEW_COMPANY = {
    "company_name_en": "", "company_name_ar": "", "country": "SA", "state": "",
    "tax_no": "", "cr_number": "", "address": "", "city": "", "phone": "", "email": "",
    "currency_symbol": "", "modules": ["retail"], "fiscal_start": "",
    "price_incl_tax": True, "language": "en",
}

# account code, English, Arabic, type, parent code
TAX_ACCOUNTS = {
    "SA": [
        ("2200", "VAT Payable", "ضريبة القيمة المضافة المستحقة", "liability", "2000"),
        ("2210", "VAT Collected (Output)", "ضريبة المخرجات", "liability", "2200"),
        ("2220", "VAT Paid (Input)", "ضريبة المدخلات", "liability", "2200"),
    ],
    "AE": [
        ("2200", "VAT Payable (FTA)", "ضريبة القيمة المضافة المستحقة", "liability", "2000"),
        ("2210", "Output VAT 5%", "ضريبة المخرجات", "liability", "2200"),
        ("2220", "Input VAT (recoverable)", "ضريبة المدخلات القابلة للاسترداد", "liability", "2200"),
    ],
    "IN": [
        ("2200", "GST Payable", "GST Payable", "liability", "2000"),
        ("2210", "Output GST", "Output GST", "liability", "2200"),
        ("2211", "Output CGST", "Output CGST", "liability", "2210"),
        ("2212", "Output SGST / UTGST", "Output SGST", "liability", "2210"),
        ("2213", "Output IGST", "Output IGST", "liability", "2210"),
        ("2220", "Input GST (ITC)", "Input GST", "liability", "2200"),
        ("2221", "Input CGST", "Input CGST", "liability", "2220"),
        ("2222", "Input SGST / UTGST", "Input SGST", "liability", "2220"),
        ("2223", "Input IGST", "Input IGST", "liability", "2220"),
    ],
}
GST_ROLES = [("default_cgst_output", "2211"), ("default_sgst_output", "2212"),
             ("default_igst_output", "2213"), ("default_cgst_input", "2221"),
             ("default_sgst_input", "2222"), ("default_igst_input", "2223")]

DOC_TABLES = ("sales_invoices", "purchase_invoices", "sales_returns", "purchase_returns",
              "journal_entries", "payments", "expenses")


def _scalar(sql, params=()):
    try:
        return db.execute_scalar(sql, params)
    except Exception:
        return None


def _has_table(t):
    return bool(_scalar("SELECT CASE WHEN OBJECT_ID(?, 'U') IS NULL THEN 0 ELSE 1 END", (t,)))


def _has_col(t, c):
    return _scalar("SELECT COL_LENGTH(?, ?)", (t, c)) is not None


def is_empty():
    """No documents and no journals yet — the country may still change."""
    for t in DOC_TABLES:
        if _has_table(t) and (_scalar("SELECT COUNT(*) FROM %s" % t) or 0):
            return False
    return True


# ── pieces ────────────────────────────────────────────────────
def _company(info, ctry):
    p = C.profile(ctry)
    sym = (info.get("currency_symbol") or "").strip() or p["symbol"]
    fy = (info.get("fiscal_start") or "").strip() or p["fiscal_start"]
    vals = {
        "company_name_en": (info.get("company_name_en") or "").strip() or "My Company",
        "company_name_ar": (info.get("company_name_ar") or "").strip()
        or (info.get("company_name_en") or "").strip() or "My Company",
        "vat_registration_no": "".join(str(info.get("tax_no") or "").split()).upper()[:15],
        "cr_number": (info.get("cr_number") or "")[:20],
        "address_en": (info.get("address") or "")[:500],
        "city_en": (info.get("city") or "")[:100],
        "phone": (info.get("phone") or "")[:20],
        "email": (info.get("email") or "")[:100],
        "currency": p["currency"], "currency_symbol": sym[:10],
        "country_code": ctry, "state_code": (info.get("state") or "")[:10],
        "business_modules": B.text(info.get("modules") or ["retail"]),
        "fiscal_year_start": fy, "default_language": (info.get("language") or p["language"])[:5],
    }
    vals = {k: v for k, v in vals.items() if _has_col("company", k)}
    cid = _scalar("SELECT TOP 1 company_id FROM company ORDER BY company_id")
    if cid:
        db.execute("UPDATE company SET %s, updated_at=GETDATE() WHERE company_id=?" %
                   ", ".join("%s=?" % k for k in vals), tuple(vals.values()) + (cid,))
    else:
        db.execute("INSERT INTO company (%s) VALUES (%s)" % (", ".join(vals), ", ".join("?" for _ in vals)),
                   tuple(vals.values()))


def _tax_categories(ctry):
    kind_col = _has_col("vat_categories", "tax_kind")
    wanted = C.categories(ctry)
    codes = [c[0] for c in wanted]
    for code, en, ar, rate, kind, active in wanted:
        row = _scalar("SELECT vat_category_id FROM vat_categories WHERE category_code=?", (code,))
        zcode = code if ctry == "SA" else (code if code in ("S", "Z", "E", "O") else ("S" if rate > 0 else "Z"))
        desc = "%s %g%%" % (C.tax_name(ctry), rate) if rate else en
        if row:
            db.execute("UPDATE vat_categories SET category_name_en=?, category_name_ar=?, vat_rate=?, "
                       "zatca_code=?, description_en=?, description_ar=?, is_active=? WHERE vat_category_id=?",
                       (en, ar, rate, zcode, desc, desc, active, row))
        else:
            db.execute("INSERT INTO vat_categories (category_code, category_name_en, category_name_ar, "
                       "vat_rate, zatca_code, description_en, description_ar, is_active) "
                       "VALUES (?,?,?,?,?,?,?,?)", (code, en, ar, rate, zcode, desc, desc, active))
        if kind_col:
            db.execute("UPDATE vat_categories SET tax_kind=? WHERE category_code=?", (kind, code))
    # categories of another country are switched off (a new, empty database)
    try:
        q = "UPDATE vat_categories SET is_active=0 WHERE category_code NOT IN (%s)" % ",".join("?" for _ in codes)
        db.execute(q, tuple(codes))
    except Exception:
        pass


def _accounts(ctry):
    if not _has_table("accounts"):
        return
    for code, en, ar, typ, parent in TAX_ACCOUNTS.get(ctry, []):
        pid = _scalar("SELECT account_id FROM accounts WHERE account_code=?", (parent,))
        aid = _scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
        if aid:
            db.execute("UPDATE accounts SET account_name_en=?, account_name_ar=?, is_active=1 "
                       "WHERE account_id=?", (en, ar, aid))
            if pid and _has_col("accounts", "parent_account_id"):
                db.execute("UPDATE accounts SET parent_account_id=? WHERE account_id=?", (pid, aid))
        else:
            if pid and _has_col("accounts", "parent_account_id"):
                db.execute("INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
                           "account_type, parent_account_id, is_active) VALUES (?,?,?,?,?,1)",
                           (code, en, ar, typ, pid))
            else:
                db.execute("INSERT INTO accounts (account_code, account_name_en, account_name_ar, "
                           "account_type, is_active) VALUES (?,?,?,?,1)", (code, en, ar, typ))
    if ctry == "IN" and _has_table("account_settings"):
        cols = {r["COLUMN_NAME"].lower() for r in (db.fetchall(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='account_settings'") or [])}
        for key, code in GST_ROLES:
            aid = _scalar("SELECT account_id FROM accounts WHERE account_code=?", (code,))
            if not aid:
                continue
            if _scalar("SELECT COUNT(*) FROM account_settings WHERE setting_key=?", (key,)):
                db.execute("UPDATE account_settings SET account_code=?%s WHERE setting_key=?" %
                           (", account_id=?" if "account_id" in cols else ""),
                           ((code, aid, key) if "account_id" in cols else (code, key)))
            else:
                if "account_id" in cols:
                    db.execute("INSERT INTO account_settings (setting_key, account_code, account_id) "
                               "VALUES (?,?,?)", (key, code, aid))
                else:
                    db.execute("INSERT INTO account_settings (setting_key, account_code) VALUES (?,?)",
                               (key, code))
    try:
        from modules import account_defaults as ad
        ad.invalidate()
    except Exception:
        pass


def fiscal_bounds(fy_start, today=None):
    """(start, end) of the financial year that holds today, for a start
    like '04-01'."""
    today = today or date.today()
    try:
        mm, dd = [int(x) for x in str(fy_start or "01-01").split("-")[:2]]
        date(2001, mm, dd)
    except Exception:
        mm, dd = 1, 1
    y = today.year if (today.month, today.day) >= (mm, dd) else today.year - 1
    start = date(y, mm, dd)
    try:
        nxt = date(y + 1, mm, dd)
    except ValueError:
        nxt = date(y + 1, mm, 28)
    from datetime import timedelta
    return start, nxt - timedelta(days=1)


def _financial_year(fy_start):
    if not _has_table("financial_years"):
        return
    s, e = fiscal_bounds(fy_start)
    label = ("FY %d" % s.year) if (s.month, s.day) == (1, 1) else ("FY %d-%s" % (s.year, str(e.year)[-2:]))
    if (_scalar("SELECT COUNT(*) FROM financial_years WHERE start_date=? AND end_date=?",
                (s.isoformat(), e.isoformat())) or 0):
        return
    if is_empty():                      # the install script's calendar year → the country's year
        try:
            if _has_table("fy_opening_balances"):
                db.execute("DELETE FROM fy_opening_balances")
            db.execute("DELETE FROM financial_years")
        except Exception:
            pass
    db.execute("INSERT INTO financial_years (label, start_date, end_date, is_closed) VALUES (?,?,?,0)",
               (label, s.isoformat(), e.isoformat()))


def _country_default(t, ctry):
    """New customers / suppliers made anywhere (forms, import, POS quick
    add) belong to the company's country, not Saudi Arabia."""
    if not _has_col(t, "country_code"):
        return
    try:
        name = _scalar("SELECT dc.name FROM sys.default_constraints dc JOIN sys.columns c "
                       "ON c.object_id=dc.parent_object_id AND c.column_id=dc.parent_column_id "
                       "WHERE dc.parent_object_id=OBJECT_ID(?) AND c.name='country_code'", (t,))
        if name:
            db.execute("ALTER TABLE %s DROP CONSTRAINT [%s]" % (t, str(name).replace("]", "]]")))
        db.execute("ALTER TABLE %s ADD CONSTRAINT DF_%s_country DEFAULT N'%s' FOR country_code"
                   % (t, t, ctry.replace("'", "")))
    except Exception:
        pass


def _parties(ctry, state):
    for t in ("customers", "suppliers"):
        if not _has_table(t):
            continue
        _country_default(t, ctry)
        sets, vals = [], []
        if _has_col(t, "country_code"):
            sets.append("country_code=?"); vals.append(ctry)
        if _has_col(t, "state_code") and state:
            sets.append("state_code=?"); vals.append(state)
        if sets:
            try:
                db.execute("UPDATE %s SET %s WHERE country_code IS NULL OR country_code IN ('SA','') "
                           "OR country_code=?" % (t, ", ".join(sets)), tuple(vals) + (ctry,))
            except Exception:
                pass


def _options(info, ctry):
    p = C.profile(ctry)
    opts = {"currency_symbol": (info.get("currency_symbol") or "").strip() or p["symbol"],
            "currency_symbol_after": "1" if p["symbol_after"] else "0",
            "sales_price_tax_mode": "inclusive" if info.get("price_incl_tax", True) else "exclusive",
            "tax_sales_rate": str(p["std_rate"])}
    if ctry == "IN":
        opts.update(round_off_enabled="1", round_off_method=p["round"])
    if ctry != "SA":
        opts["fiscal_year_start"] = (info.get("fiscal_start") or "").strip() or p["fiscal_start"]
    for k, v in B.defaults_for(info.get("modules") or []).items():
        opts[k] = "1" if v is True else ("0" if v is False else str(v))
    for k, v in opts.items():
        C.set_option(k, v)


# ── public ────────────────────────────────────────────────────
def validate(info):
    """List of problems with the wizard's answers (empty = fine)."""
    errs = []
    ctry = str(info.get("country") or "").upper()
    if ctry not in C.COUNTRIES:
        errs.append("Pick the country.")
        return errs
    if not str(info.get("company_name_en") or "").strip():
        errs.append("Type the company name.")
    ok, msg = C.valid_tax_no(info.get("tax_no"), ctry)
    if not ok:
        errs.append(msg)
    st = str(info.get("state") or "").strip()
    if ctry == "IN":
        if not st:
            errs.append("Pick the company's state (GST needs it for CGST / SGST or IGST).")
        tax = "".join(str(info.get("tax_no") or "").split()).upper()
        if tax and st and tax[:2] != st:
            errs.append("The GSTIN starts with %s but the state picked is %s." % (tax[:2], st))
    if ctry == "AE" and not st:
        errs.append("Pick the emirate (the VAT 201 return lists sales by emirate).")
    return errs


def setup(info):
    """Make the open (new) database work for the company's country and
    business modules. Returns (ok, message)."""
    info = dict(NEW_COMPANY, **(info or {}))
    errs = validate(info)
    if errs:
        return False, "\n".join(errs)
    ctry = str(info["country"]).upper()
    if not info.get("state") and ctry == "IN":
        info["state"] = C.state_from_tax_no(info.get("tax_no"))
    try:
        _company(info, ctry)
        C.invalidate()
        _tax_categories(ctry)
        _accounts(ctry)
        _financial_year((info.get("fiscal_start") or "").strip() or C.profile(ctry)["fiscal_start"])
        _parties(ctry, info.get("state") or "")
        _options(info, ctry)
    except Exception as e:
        return False, "Company setup stopped: %s" % str(e)[:300]
    B.invalidate()
    C.apply()
    return True, "%s company ready: %s, %s." % (C.profile(ctry)["name"], C.tax_name(ctry),
                                                 B.summary(info.get("modules")))


def change_country(info):
    """Settings ▸ Company: a different country is allowed only while the
    database has no documents yet (else tax history would not match)."""
    if not is_empty():
        return False, ("This company already has bills and journals. The country cannot change now — "
                       "make a new company (database) for the other country.")
    return setup(info)
