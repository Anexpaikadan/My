# ============================================================
# DayBill ERP - Masters (v7.10.0)
# ------------------------------------------------------------
# The short lists the rest of DayBill picks from, kept in one place:
#
#   Products    Brands · Sections · Group Categories · Units of Measure
#               · Tax (VAT / GST) Categories
#   Sales       Sales Routes / Areas · Salesmen (+ their routes)
#               · Vehicles · Party Categories
#   Accounts    Cost Centres · Currencies & Exchange Rates
#   Other       General Master (any list: colours, sizes, reasons …)
#
# Every list works the same way (ui/masters.py): search, New, Save,
# Delete, Active on / off. A row that is in use (a product has the
# brand, a bill has the salesman …) is never deleted — switch it off
# instead, so old bills and reports keep their names.
#
#   KINDS                  the lists and their fields
#   ready(kind)            the list's table exists (database updated)
#   rows(kind, search, active_only)
#   get(kind, rid)
#   save(kind, values, rid=None)  -> (ok, message, rid)
#   delete(kind, rid)              -> (ok, message)
#   usage(kind, rid)               -> [(count, "products")]
#   links / set_links      salesman ↔ routes, group ↔ categories
#   choices(kind)          [(id, label)] of the active rows (for pickers)
#   unit_names()           names for the product window's unit boxes
#   customer_links / set_customer_links / invoice_salesman / save_invoice_salesman
#   set_rate(currency_id, rate)    exchange rate + history
# ============================================================
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.database import db


class F:
    """One field of a master: column, label, kind, width, required."""

    def __init__(self, col, label, kind="text", width=22, required=False, options=None,
                 list_width=None, tip="", head=None):
        self.col, self.label, self.kind = col, label, kind
        self.head = head or label             # the table heading (shorter)
        self.width, self.required = width, required
        self.options = options or []          # choice: [(value, label)]
        self.list_width = list_width          # shown in the table when set
        self.tip = tip


GROUPS = ["Products", "Sales & Parties", "Accounts", "Other"]

_CARD_HELP = ("Cards the shop takes (Mada, Visa, MasterCard, STC Pay …): the bank / clearing "
              "account the money lands in and the bank's commission %.")
_MACHINE_HELP = ("The bank's card machines (POS terminals) in the shop: bank, terminal ID, "
                 "the account it pays into and the counter it stands at.")

KINDS = {
    # ── Products ───────────────────────────────────────────────
    "brands": dict(
        title="Brands", icon="🏷", group="Products", rights="products",
        table="product_brands", id="brand_id", name="brand_name_en",
        help="The maker or label of a product (Almarai, Nestlé, Samsung …). "
             "Product ▸ Brand picks from this list.",
        fields=[F("brand_code", "Code", "code", 10, list_width=80),
                F("brand_name_en", "Brand name (English)", "text", 22, True, list_width=220),
                F("brand_name_ar", "الاسم (عربي)", "ar", 18, list_width=180)],
        used=[("SELECT COUNT(*) FROM products WHERE brand_id=?", "products")]),
    "sections": dict(
        title="Sections", icon="🧺", group="Products", rights="products",
        table="product_sections", id="section_id", name="name_en",
        help="Departments of the shop: Dairy, Frozen, Bakery, Household … "
             "Product ▸ Section picks from this list.",
        fields=[F("section_code", "Code", "code", 10, list_width=80),
                F("name_en", "Section (English)", "text", 22, True, list_width=220),
                F("name_ar", "الاسم (عربي)", "ar", 18, list_width=180),
                F("notes", "Notes", "text", 30)],
        used=[("SELECT COUNT(*) FROM products WHERE section_id=?", "products")]),
    "group_categories": dict(
        title="Group Categories", icon="🗂", group="Products", rights="categories",
        table="product_group_categories", id="group_category_id", name="name_en",
        help="A group of product categories, e.g. 'Food' = Rice + Oil + Spices. "
             "Tick the categories that belong to the group on the right.",
        fields=[F("group_code", "Code", "code", 10, list_width=80),
                F("name_en", "Group (English)", "text", 22, True, list_width=220),
                F("name_ar", "الاسم (عربي)", "ar", 18, list_width=180),
                F("notes", "Notes", "text", 30)],
        used=[("SELECT COUNT(*) FROM product_categories WHERE group_category_id=?",
               "categories")],
        links=dict(title="Categories in this group",
                   all_sql="SELECT category_id AS id, category_name_en AS label, "
                           "group_category_id AS owner FROM product_categories "
                           "WHERE is_active=1 ORDER BY category_name_en",
                   mode="owner")),
    "units": dict(
        title="Units of Measure", icon="⚖", group="Products", rights="products",
        table="unit_master", id="unit_id", name="unit_name_en",
        help="The unit names offered in the product window (PCs, Box, Carton, Kg …). "
             "Tick 'Decimals' for units sold in parts (Kg, Liter, Metre).",
        fields=[F("unit_name_en", "Unit (English)", "text", 18, True, list_width=150),
                F("unit_name_ar", "الوحدة (عربي)", "ar", 18, list_width=130),
                F("short_name", "Short", "code", 8, list_width=60),
                F("allow_decimals", "Decimals (Kg, Liter …)", "bool", list_width=80,
                  head="Decimals"),
                F("sort_order", "Order", "int", 6, list_width=60)],
        used=[("SELECT COUNT(*) FROM product_units WHERE unit_name_en="
               "(SELECT unit_name_en FROM unit_master WHERE unit_id=?)", "product units")],
        order="sort_order, unit_name_en"),
    "tax_categories": dict(
        title="Tax Categories", icon="🧾", group="Products", rights="company_settings",
        right_action="settings",
        table="vat_categories", id="vat_category_id", name="category_name_en",
        help="VAT / GST rates a product can carry. The code and rate of a category "
             "that products already use are locked — make a new category for a new rate.",
        fields=[F("category_code", "Code (S, Z, E …)", "code", 8, True, list_width=70, head="Code"),
                F("category_name_en", "Name (English)", "text", 22, True, list_width=200),
                F("category_name_ar", "الاسم (عربي)", "ar", 18, list_width=160),
                F("vat_rate", "Rate %", "num", 8, True, list_width=70),
                F("zatca_code", "ZATCA / e-invoice code", "code", 10, list_width=100,
                  head="ZATCA code")],
        used=[("SELECT COUNT(*) FROM products WHERE vat_category_id=?", "products")],
        locked_when_used=("category_code", "vat_rate"),
        fallback={"category_name_ar": "category_name_en"},    # NOT NULL in vat_categories
        order="vat_rate DESC, category_code"),
    # ── Sales & parties ────────────────────────────────────────
    "routes": dict(
        title="Sales Routes / Areas", short="Routes / Areas", icon="🗺", group="Sales & Parties", rights="customers",
        table="sales_routes", id="route_id", name="name_en",
        help="The areas your salesmen and vans cover. Customer ▸ Route picks from this "
             "list; reports will show sales by route.",
        fields=[F("route_code", "Code", "code", 10, list_width=80),
                F("name_en", "Route (English)", "text", 22, True, list_width=200),
                F("name_ar", "الاسم (عربي)", "ar", 18, list_width=160),
                F("area", "Area / City", "text", 22, list_width=150),
                F("notes", "Notes", "text", 30)],
        used=[("SELECT COUNT(*) FROM customers WHERE route_id=?", "customers"),
              ("SELECT COUNT(*) FROM sales_invoices WHERE route_id=?", "sales bills"),
              ("SELECT COUNT(*) FROM salesman_routes WHERE route_id=?", "salesmen")]),
    "salesmen": dict(
        title="Salesmen", icon="🧑‍💼", group="Sales & Parties", rights="customers",
        table="salesmen", id="salesman_id", name="name_en",
        help="People who sell for the shop. The Sales Invoice saves the salesman of every "
             "bill; a customer can have his own salesman. Tick the routes he covers.",
        fields=[F("salesman_code", "Code", "code", 10, list_width=70),
                F("name_en", "Name (English)", "text", 22, True, list_width=170),
                F("name_ar", "الاسم (عربي)", "ar", 18),
                F("mobile", "Mobile", "text", 14, list_width=100),
                F("user_id", "DayBill user (sign-in)", "user", 18, list_width=100, head="User"),
                F("vehicle_id", "Vehicle", "vehicle", 18, list_width=110),
                F("commission_pct", "Commission %", "num", 8, list_width=70, head="Comm. %"),
                F("monthly_target", "Monthly target", "num", 12, list_width=90, head="Target"),
                F("notes", "Notes", "text", 30)],
        used=[("SELECT COUNT(*) FROM sales_invoices WHERE salesman_id=?", "sales bills"),
              ("SELECT COUNT(*) FROM customers WHERE salesman_id=?", "customers")],
        links=dict(title="Routes this salesman covers",
                   all_sql="SELECT route_id AS id, name_en AS label FROM sales_routes "
                           "WHERE is_active=1 ORDER BY name_en",
                   mode="table", link_table="salesman_routes",
                   my_col="salesman_id", other_col="route_id")),
    "vehicles": dict(
        title="Vehicles", icon="🚚", group="Sales & Parties", rights="inventory",
        table="vehicles", id="vehicle_id", name="vehicle_no",
        help="Delivery vans and cars. A salesman can be given a vehicle.",
        fields=[F("vehicle_no", "Plate / number", "code", 14, True, list_width=110, head="Plate"),
                F("vehicle_name", "Name", "text", 22, list_width=150),
                F("vehicle_type", "Type", "choice", 14, list_width=90,
                  options=[("Van", "Van"), ("Pickup", "Pickup"), ("Truck", "Truck"),
                           ("Car", "Car"), ("Motorbike", "Motorbike"), ("Other", "Other")]),
                F("driver_name", "Driver", "text", 20, list_width=140),
                F("driver_mobile", "Driver mobile", "text", 14, list_width=110),
                F("notes", "Notes", "text", 30)],
        used=[("SELECT COUNT(*) FROM salesmen WHERE vehicle_id=?", "salesmen")]),
    "party_categories": dict(
        title="Party Categories", icon="👥", group="Sales & Parties", rights="customers",
        table="party_categories", id="party_category_id", name="name_en",
        help="Kinds of customers and suppliers: Wholesale, Retail, VIP, Restaurant … "
             "Customer ▸ Category picks from this list.",
        fields=[F("name_en", "Category (English)", "text", 22, True, list_width=200),
                F("name_ar", "الاسم (عربي)", "ar", 18, list_width=160),
                F("applies_to", "For", "choice", 18, list_width=150,
                  options=[("both", "Customers & suppliers"), ("customer", "Customers"),
                           ("supplier", "Suppliers")]),
                F("notes", "Notes", "text", 30)],
        used=[("SELECT COUNT(*) FROM customers WHERE party_category_id=?", "customers"),
              ("SELECT COUNT(*) FROM suppliers WHERE party_category_id=?", "suppliers")]),
    # ── Accounts ───────────────────────────────────────────────
    "cost_centers": dict(
        title="Cost Centres", icon="🎯", group="Accounts", rights="accounts",
        table="cost_centers", id="cost_center_id", name="name_en",
        help="Parts of the business you want to see the costs of: a branch, a van, "
             "a project, a department. A cost centre can sit under another one.",
        fields=[F("cc_code", "Code", "code", 10, list_width=80),
                F("name_en", "Cost centre (English)", "text", 22, True, list_width=200),
                F("name_ar", "الاسم (عربي)", "ar", 18, list_width=160),
                F("parent_id", "Under", "parent", 22, list_width=150),
                F("notes", "Notes", "text", 30)],
        used=[("SELECT COUNT(*) FROM cost_centers WHERE parent_id=?", "cost centres under it")]),
    "currencies": dict(
        title="Currencies & Exchange Rates", short="Currencies & Rates", icon="💱", group="Accounts", rights="accounts",
        table="currencies", id="currency_id", name="currency_code",
        help="Other currencies the shop buys or sells in, and what 1 unit is worth in "
             "the shop's own currency. Every rate change is kept in the history.",
        fields=[F("currency_code", "Code (USD, EUR …)", "code", 8, True, list_width=70, head="Code"),
                F("name_en", "Name (English)", "text", 22, True, list_width=170),
                F("name_ar", "الاسم (عربي)", "ar", 18, list_width=120),
                F("symbol", "Symbol", "code", 6, list_width=60),
                F("rate_to_base", "Rate (1 = ? shop currency)", "rate", 12, True, list_width=90,
                  head="Rate"),
                F("rate_date", "Rate date", "date", 12, list_width=90),
                F("decimals", "Decimals", "int", 4, list_width=70)],
        used=[], order="is_base DESC, currency_code", extra_cols=["is_base"]),
    # v7.12: bank cards + card machines
    "bank_cards": dict(
        title="Bank Cards", icon="💳", group="Accounts", rights="accounts",
        table="bank_cards", id="card_id", name="card_name", help=_CARD_HELP,
        fields=[F("card_name", "Card (English)", "text", 22, True, list_width=160),
                F("card_name_ar", "الاسم (عربي)", "ar", 18, list_width=130),
                F("account_id", "Money goes to (account)", "account", 26, list_width=200,
                  head="Account"),
                F("commission_pct", "Bank commission %", "num", 8, list_width=90,
                  head="Comm. %"),
                F("notes", "Notes", "text", 30)],
        used=[]),
    "card_machines": dict(
        title="Card Machines (Bank POS)", short="Card Machines", icon="🏧", group="Accounts",
        rights="accounts", table="card_machines", id="machine_id", name="machine_name",
        help=_MACHINE_HELP,
        fields=[F("machine_name", "Machine name", "text", 22, True, list_width=150),
                F("bank_name", "Bank", "text", 18, list_width=130),
                F("terminal_id", "Terminal ID", "code", 14, list_width=110),
                F("account_id", "Pays into (account)", "account", 26, list_width=190,
                  head="Account"),
                F("counter_name", "Counter", "text", 14, list_width=100),
                F("notes", "Notes", "text", 30)],
        used=[]),
    # ── Other ──────────────────────────────────────────────────
    "general": dict(
        title="General Master", icon="📚", group="Other", rights="products",
        table="general_master", id="gm_id", name="name_en",
        help="Any short list you need — colours, sizes, return reasons, payment terms, "
             "delivery times … Type a new list name in 'List' to start a new list.",
        fields=[F("gm_type", "List", "type", 18, True, list_width=120),
                F("gm_code", "Code", "code", 10, list_width=80),
                F("name_en", "Value (English)", "text", 22, True, list_width=200),
                F("name_ar", "الاسم (عربي)", "ar", 18, list_width=160),
                F("sort_order", "Order", "int", 6, list_width=60),
                F("notes", "Notes", "text", 30)],
        used=[], order="gm_type, sort_order, name_en", unique_within="gm_type"),
    # v7.12: ready-made WhatsApp / SMS / e-mail texts (modules/msg_templates.py)
    "message_templates": dict(
        title="Message Templates", icon="💬", group="Other", rights="customers",
        table="message_templates", id="template_id", name="template_name",
        help="Ready-made WhatsApp / SMS / e-mail texts. Words in braces are filled in: "
             "{customer} {shop} {number} {date} {total} {due} {balance}. Type \\n for a "
             "new line. The WhatsApp send window offers these in its Template box.",
        fields=[F("template_name", "Name", "text", 22, True, list_width=150),
                F("channel", "Channel", "choice", 12, True, list_width=80,
                  options=[("whatsapp", "WhatsApp"), ("sms", "SMS"), ("email", "E-mail")]),
                F("purpose", "Used for", "choice", 14, list_width=90,
                  options=[("invoice", "Invoice"), ("statement", "Statement"),
                           ("reminder", "Payment reminder"), ("other", "Other")]),
                F("subject", "E-mail subject", "text", 30),
                F("body", "Message", "text", 74, True, list_width=380)],
        used=[]),
}

ORDER = ["brands", "sections", "group_categories", "units", "tax_categories",
         "routes", "salesmen", "vehicles", "party_categories",
         "cost_centers", "currencies", "bank_cards", "card_machines", "general",
         "message_templates"]


def kind(key):
    return KINDS[key]


def _num(v, default=0.0):
    try:
        s = str(v if v is not None else "").replace(",", "").strip()
        return float(s) if s else default
    except (TypeError, ValueError):
        return default


def _int(v, default=0):
    try:
        s = str(v if v is not None else "").replace(",", "").strip()
        return int(float(s)) if s else default
    except (TypeError, ValueError):
        return default


# ── schema ──────────────────────────────────────────────────
_READY = {}
_COLS = {}                     # (table, col) → True / False, asked once a session


def table_ok(table):
    """True when the table can be read (the database update ran)."""
    return col_ok(table, "*")


def _fresh():
    """A new connection (another company signed in): ask the tables again."""
    c = id(getattr(db, "_connection", None))
    if _COLS.get("_conn") != c:
        _COLS.clear()
        _READY.clear()
        _COLS["_conn"] = c


def col_ok(table, col):
    _fresh()
    key = (table, col)
    if key not in _COLS:
        try:
            db.fetchall("SELECT %s FROM %s WHERE 1=0" % (col, table))
            _COLS[key] = True
        except Exception:
            _COLS[key] = False
    return _COLS[key]


def ready(key):
    k = KINDS[key]
    _fresh()
    if key not in _READY:
        ok = table_ok(k["table"])
        if ok:
            # an older brands table has no code column until the v7.10 update
            ok = all(col_ok(k["table"], f.col) for f in k["fields"])
        _READY[key] = ok
    return _READY[key]


def forget():
    """After a database update: look at the tables again."""
    _READY.clear()
    _COLS.clear()


# ── reading ─────────────────────────────────────────────────
def _cols(k):
    return [k["id"]] + [f.col for f in k["fields"]] + ["is_active"] + list(k.get("extra_cols", []))


def rows(key, search="", active_only=False):
    k = KINDS[key]
    if not ready(key):
        return []
    where, params = [], []
    if active_only:
        where.append("is_active=1")
    s = str(search or "").strip()
    if s:
        txt = [f.col for f in k["fields"] if f.kind in ("text", "ar", "code", "type")]
        if txt:
            where.append("(" + " OR ".join("%s LIKE ?" % c for c in txt) + ")")
            params += ["%" + s + "%"] * len(txt)
    sql = "SELECT %s FROM %s" % (", ".join(_cols(k)), k["table"])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + k.get("order", k["name"])
    try:
        return [dict(r) for r in (db.fetchall(sql, tuple(params)) or [])]
    except Exception:
        return []


def get(key, rid):
    k = KINDS[key]
    if not rid or not ready(key):
        return None
    try:
        r = db.fetchone("SELECT %s FROM %s WHERE %s=?" % (", ".join(_cols(k)), k["table"], k["id"]),
                        (int(rid),))
        return dict(r) if r else None
    except Exception:
        return None


def usage(key, rid):
    """[(count, what)] for the places this row is used (only counts > 0)."""
    out = []
    for sql, what in KINDS[key].get("used", []):
        try:
            n = int(db.execute_scalar(sql, (int(rid),)) or 0)
        except Exception:
            n = 0                      # the other table is missing: not used
        if n:
            out.append((n, what))
    if key == "currencies":
        r = get(key, rid)
        if r and r.get("is_base"):
            out.append((None, "the shop (its own currency)"))
    return out


def usage_text(use):
    return ", ".join(("%d %s" % (n, w)) if n is not None else w for n, w in use)


def types():
    """General master: the list names already used."""
    if not ready("general"):
        return []
    try:
        return [r["gm_type"] for r in (db.fetchall(
            "SELECT DISTINCT gm_type FROM general_master ORDER BY gm_type") or [])
            if r.get("gm_type")]
    except Exception:
        return []


def accounts():
    """[(account_id, 'code — name')] — cash, bank and other asset accounts
    first (cards and card machines pay into one of them)."""
    try:
        rs = db.fetchall("SELECT account_id, account_code, account_name_en, account_type "
                         "FROM accounts WHERE ISNULL(is_active,1)=1 ORDER BY account_code") or []
    except Exception:
        try:
            rs = db.fetchall("SELECT account_id, account_code, account_name_en, account_type "
                             "FROM accounts ORDER BY account_code") or []
        except Exception:
            rs = []
    rs = sorted(rs, key=lambda r: (str(r.get("account_type") or "") != "asset",
                                   str(r.get("account_code") or "")))
    return [(r["account_id"], "%s — %s" % (r.get("account_code") or "", r.get("account_name_en") or ""))
            for r in rs]


def account_label(aid):
    if not aid:
        return ""
    try:
        r = db.fetchone("SELECT account_code, account_name_en FROM accounts WHERE account_id=?",
                        (int(aid),))
        return "%s — %s" % (r["account_code"], r["account_name_en"]) if r else ""
    except Exception:
        return ""


def users():
    """[(user_id, name)] for the salesman's sign-in user."""
    try:
        return [(r["user_id"], r["full_name_en"] or r["username"]) for r in (db.fetchall(
            "SELECT user_id, username, full_name_en FROM users WHERE is_active=1 "
            "ORDER BY full_name_en") or [])]
    except Exception:
        return []


def choices(key, include=None):
    """[(id, label)] of the active rows; `include` keeps one switched-off
    row in the list (the one a saved record still has)."""
    k = KINDS[key]
    out = []
    for r in rows(key, active_only=True):
        out.append((r[k["id"]], label(key, r)))
    if include and not any(i == include for i, _l in out):
        r = get(key, include)
        if r:
            out.append((r[k["id"]], label(key, r)))
    return out


def label(key, r):
    k = KINDS[key]
    if not r:
        return ""
    name = str(r.get(k["name"]) or "").strip()
    if key == "vehicles" and r.get("vehicle_name"):
        return "%s — %s" % (name, r["vehicle_name"])
    if key == "currencies" and r.get("name_en"):
        return "%s — %s" % (name, r["name_en"])
    if key == "tax_categories":
        return "%s - %s (%s%%)" % (r.get("category_code"), name, "%g" % _num(r.get("vat_rate")))
    code = None
    for f in k["fields"]:
        if f.kind == "code" and f.col != k["name"]:
            code = str(r.get(f.col) or "").strip()
            break
    return ("%s — %s" % (code, name)) if code else name


def label_of(key, rid):
    return label(key, get(key, rid)) if rid else ""


def id_of(key, text, pairs=None):
    """The id for a label shown in a picker (None for '— None —')."""
    t = str(text or "").strip()
    if not t or t.startswith("—"):
        return None
    for i, lbl in (pairs if pairs is not None else choices(key)):
        if lbl == t:
            return i
    return None


# ── writing ─────────────────────────────────────────────────
def _clean(key, values):
    k = KINDS[key]
    out = {}
    for f in k["fields"]:
        v = values.get(f.col)
        if f.kind == "bool":
            out[f.col] = 1 if (v in (True, 1, "1") or str(v).lower() == "true") else 0
        elif f.kind in ("num", "rate"):
            out[f.col] = round(_num(v), 6 if f.kind == "rate" else 3)
        elif f.kind == "int":
            out[f.col] = _int(v)
        elif f.kind in ("user", "vehicle", "parent", "account"):
            out[f.col] = _int(v) or None
        elif f.kind == "date":
            s = str(v or "").strip()[:10]
            out[f.col] = s or None
        elif f.kind == "code":
            s = str(v or "").strip()
            out[f.col] = (s.upper() if key in ("currencies", "tax_categories") else s) or None
        else:
            s = str(v or "").strip()
            out[f.col] = s or None
    return out


def _same(key, col, value, rid, extra=None):
    """Another row already has this value (case-insensitive)."""
    k = KINDS[key]
    sql = "SELECT COUNT(*) FROM %s WHERE UPPER(%s)=UPPER(?)" % (k["table"], col)
    params = [value]
    if rid:
        sql += " AND %s<>?" % k["id"]
        params.append(int(rid))
    if extra:
        sql += " AND %s=?" % extra[0]
        params.append(extra[1])
    try:
        return int(db.execute_scalar(sql, tuple(params)) or 0) > 0
    except Exception:
        return False


def check(key, values, rid=None):
    """'' when the values can be saved, else what is wrong."""
    k = KINDS[key]
    v = _clean(key, values)
    for f in k["fields"]:
        if f.required and (v.get(f.col) in (None, "") and f.kind not in ("num", "rate", "int")):
            return "%s is needed." % f.label
    extra = None
    if k.get("unique_within"):
        extra = (k["unique_within"], v.get(k["unique_within"]))
    name = v.get(k["name"])
    if name and _same(key, k["name"], name, rid, extra):
        return "'%s' is already in %s." % (name, k["title"])
    for f in k["fields"]:
        if f.kind == "code" and f.col != k["name"] and v.get(f.col):
            if _same(key, f.col, v[f.col], rid, extra):
                return "Code '%s' is already used in %s." % (v[f.col], k["title"])
    if key == "tax_categories":
        r = v.get("vat_rate")
        if r is None or r < 0 or r > 100:
            return "Rate % must be between 0 and 100."
    if key == "currencies":
        if not v.get("rate_to_base") or v["rate_to_base"] <= 0:
            return "Rate must be more than 0."
    if key in ("salesmen",) and (v.get("commission_pct") or 0) > 100:
        return "Commission % can't be more than 100."
    if key == "cost_centers" and rid and v.get("parent_id") == int(rid):
        return "A cost centre can't be under itself."
    if rid and k.get("locked_when_used"):
        old = get(key, rid) or {}
        if usage(key, rid):
            for c in k["locked_when_used"]:
                a, b = old.get(c), v.get(c)
                same = (_num(a) == _num(b)) if c == "vat_rate" else (
                    str(a or "").upper() == str(b or "").upper())
                if not same:
                    return ("Products already use this category, so its %s can't change.\n"
                            "Make a new category for the new rate." %
                            next(f.label for f in k["fields"] if f.col == c))
    return ""


def save(key, values, rid=None, active=True):
    """Insert or update one row → (ok, message, rid)."""
    k = KINDS[key]
    if not ready(key):
        return False, "This list needs the v7.10 database update (Updates ▸ Apply).", rid
    bad = check(key, values, rid)
    if bad:
        return False, bad, rid
    v = _clean(key, values)
    for col, src in k.get("fallback", {}).items():     # a must-fill column left empty
        if not v.get(col):
            v[col] = v.get(src)
    v["is_active"] = 1 if active else 0
    old = get(key, rid) if rid else None
    try:
        if rid:
            sets = ", ".join("%s=?" % c for c in v)
            db.execute("UPDATE %s SET %s WHERE %s=?" % (k["table"], sets, k["id"]),
                       tuple(v.values()) + (int(rid),))
        else:
            cols = ", ".join(v)
            db.execute("INSERT INTO %s (%s) VALUES (%s)" % (k["table"], cols,
                                                          ", ".join("?" * len(v))),
                       tuple(v.values()))
            rid = db.last_identity(k["table"], k["id"])
    except Exception as e:
        return False, "Could not save: %s" % str(e)[:160], rid
    if key == "currencies" and rid:
        o = _num((old or {}).get("rate_to_base"), None) if old else None
        if o is None or abs(o - _num(v.get("rate_to_base"))) > 1e-9:
            _rate_history(rid, o, v.get("rate_to_base"), v.get("rate_date"))
    _audit("edit" if old else "create", key, rid, v.get(k["name"]))
    return True, "%s saved." % (v.get(k["name"]) or k["title"]), rid


def set_active(key, rid, on):
    k = KINDS[key]
    if key == "currencies" and not on:
        r = get(key, rid)
        if r and r.get("is_base"):
            return False, "The shop's own currency can't be switched off."
    try:
        db.execute("UPDATE %s SET is_active=? WHERE %s=?" % (k["table"], k["id"]),
                   (1 if on else 0, int(rid)))
    except Exception as e:
        return False, str(e)[:160]
    _audit("edit", key, rid, "active" if on else "switched off")
    return True, "Switched on." if on else "Switched off — kept for old bills and reports."


def delete(key, rid):
    k = KINDS[key]
    use = usage(key, rid)
    if use:
        return False, ("It is used by %s, so it can't be deleted.\n"
                       "Untick 'Active' instead — it stays on old bills but is no longer "
                       "offered." % usage_text(use))
    r = get(key, rid)
    try:
        if k.get("links", {}).get("mode") == "table":
            L = k["links"]
            db.execute("DELETE FROM %s WHERE %s=?" % (L["link_table"], L["my_col"]), (int(rid),))
        db.execute("DELETE FROM %s WHERE %s=?" % (k["table"], k["id"]), (int(rid),))
    except Exception as e:
        return False, "Could not delete: %s" % str(e)[:160]
    _audit("delete", key, rid, (r or {}).get(k["name"]))
    return True, "Deleted."


def _audit(action, key, rid, text):
    try:
        from modules import audit
        audit.log(action, "masters", rid, "%s: %s" % (KINDS[key]["title"], text or ""))
    except Exception:
        pass


# ── links: salesman ↔ routes, group ↔ categories ────────────
def link_options(key):
    """[(id, label, owner)] — owner: the group a category is in now."""
    L = KINDS[key].get("links")
    if not L:
        return []
    try:
        out = []
        for r in db.fetchall(L["all_sql"]) or []:
            out.append((r["id"], r["label"], r.get("owner")))
        return out
    except Exception:
        return []


def links(key, rid):
    L = KINDS[key].get("links")
    if not L or not rid:
        return set()
    try:
        if L["mode"] == "table":
            return {r[L["other_col"]] for r in (db.fetchall(
                "SELECT %s FROM %s WHERE %s=?" % (L["other_col"], L["link_table"], L["my_col"]),
                (int(rid),)) or [])}
        return {i for i, _l, owner in link_options(key) if owner == int(rid)}
    except Exception:
        return set()


def set_links(key, rid, ids):
    L = KINDS[key].get("links")
    if not L or not rid:
        return False
    ids = {int(i) for i in ids}
    try:
        if L["mode"] == "table":
            db.execute("DELETE FROM %s WHERE %s=?" % (L["link_table"], L["my_col"]), (int(rid),))
            for i in sorted(ids):
                db.execute("INSERT INTO %s (%s, %s) VALUES (?, ?)"
                           % (L["link_table"], L["my_col"], L["other_col"]), (int(rid), i))
        else:                          # group categories: product_categories.group_category_id
            db.execute("UPDATE product_categories SET group_category_id=NULL "
                       "WHERE group_category_id=?", (int(rid),))
            for i in sorted(ids):
                db.execute("UPDATE product_categories SET group_category_id=? "
                           "WHERE category_id=?", (int(rid), i))
        return True
    except Exception:
        return False


# ── used by other screens ───────────────────────────────────
DEFAULT_UNITS = ["PCs", "Box", "Carton", "Dozen", "Kg", "Gram",
                 "Liter", "Pack", "Bag", "Bundle", "Unit"]


def unit_names():
    """Unit names for the product window (the Units of Measure list),
    or None when the list is not there yet."""
    if not ready("units"):
        return None
    names = [str(r["unit_name_en"]).strip() for r in rows("units", active_only=True)
             if str(r.get("unit_name_en") or "").strip()]
    return names or None


def add_unit(name):
    """A unit typed in the product window ('➕ Add New Unit…') joins the list."""
    name = str(name or "").strip()
    if not name or not ready("units"):
        return False
    if _same("units", "unit_name_en", name, None):
        return True
    ok, _m, _r = save("units", {"unit_name_en": name, "sort_order": 99})
    return ok


def customer_links(cid):
    """{'route_id', 'party_category_id', 'salesman_id'} of a customer."""
    out = {"route_id": None, "party_category_id": None, "salesman_id": None}
    if not cid:
        return out
    for c in out:
        if col_ok("customers", c):
            try:
                out[c] = db.execute_scalar("SELECT %s FROM customers WHERE customer_id=?" % c,
                                           (int(cid),))
            except Exception:
                pass
    return out


def set_customer_links(cid, **vals):
    if not cid:
        return
    for c, v in vals.items():
        if c in ("route_id", "party_category_id", "salesman_id") and col_ok("customers", c):
            try:
                db.execute("UPDATE customers SET %s=? WHERE customer_id=?" % c,
                           (v if v else None, int(cid)))
            except Exception:
                pass


def salesman_list():
    """Sales Invoice ▸ Salesman: (names, {name: salesman_id}). The
    Salesmen list when it has people, else the DayBill users (as before)."""
    pairs = choices("salesmen") if ready("salesmen") else []
    if pairs:
        return [l for _i, l in pairs], {l: i for i, l in pairs}
    try:
        rows_ = db.fetchall("SELECT full_name_en AS full_name FROM users "
                            "WHERE is_active=1 ORDER BY full_name_en") or []
        return [r["full_name"] for r in rows_ if r.get("full_name")], {}
    except Exception:
        return [], {}


def save_invoice_salesman(inv_id, salesman_id, route_id=None):
    if not inv_id or not col_ok("sales_invoices", "salesman_id"):
        return False
    try:
        db.execute("UPDATE sales_invoices SET salesman_id=?, route_id=? WHERE invoice_id=?",
                   (salesman_id or None, route_id or None, int(inv_id)))
        return True
    except Exception:
        return False


def invoice_salesman(inv_id):
    if not inv_id or not col_ok("sales_invoices", "salesman_id"):
        return None
    try:
        return db.execute_scalar("SELECT salesman_id FROM sales_invoices WHERE invoice_id=?",
                                 (int(inv_id),))
    except Exception:
        return None


# ── currencies ──────────────────────────────────────────────
def ensure_base_currency():
    """The shop's own currency is row 1 (rate 1, can't be switched off)."""
    if not ready("currencies"):
        return
    try:
        if int(db.execute_scalar("SELECT COUNT(*) FROM currencies WHERE is_base=1") or 0):
            return
        from modules import country as _c
        p = _c.profile()
        code = p.get("currency") or "SAR"
        have = db.execute_scalar("SELECT currency_id FROM currencies WHERE currency_code=?", (code,))
        if have:
            db.execute("UPDATE currencies SET is_base=1, rate_to_base=1, is_active=1 "
                       "WHERE currency_id=?", (int(have),))
        else:
            db.execute("INSERT INTO currencies (currency_code, name_en, symbol, rate_to_base, "
                       "decimals, is_base, is_active) VALUES (?, ?, ?, 1, 2, 1, 1)",
                       (code, p.get("currency_name") or code, p.get("symbol") or code))
    except Exception:
        pass


def base_currency():
    try:
        return db.execute_scalar("SELECT currency_code FROM currencies WHERE is_base=1") or ""
    except Exception:
        return ""


def _rate_history(cid, old, new, rate_date=None):
    try:
        from modules import audit as _a
        who = (getattr(_a, "_user", {}) or {}).get("username")
    except Exception:
        who = None
    try:
        db.execute("INSERT INTO currency_rate_history (currency_id, old_rate, new_rate, rate_date, "
                   "changed_by) VALUES (?, ?, ?, ?, ?)",
                   (int(cid), old, _num(new), rate_date or None, who))
    except Exception:
        pass


def rate_history(cid, limit=20):
    try:
        rs = db.fetchall("SELECT old_rate, new_rate, rate_date, changed_by, changed_at "
                         "FROM currency_rate_history WHERE currency_id=? "
                         "ORDER BY history_id DESC", (int(cid),)) or []
        return [dict(r) for r in rs][:limit]
    except Exception:
        return []


def to_base(amount, currency_id):
    """amount in that currency → the shop's currency."""
    r = get("currencies", currency_id)
    return round(_num(amount) * _num((r or {}).get("rate_to_base"), 1.0), 2)
