# ============================================================
# DayBill ERP - Database Tool: bring another program's data into DayBill
# (v6.1)
# ------------------------------------------------------------
# Reads ANOTHER program's database (SQL Server, or a SQLite file such
# as Aronium POS) — never writes to it — and brings into a DayBill
# database:
#     categories, products (code, barcode, names AR/EN, unit, sell price,
#     cost, VAT), extra barcodes, customers, suppliers,
#     opening stock and opening customer / supplier balances
# Old invoices / history are NOT copied (every POS vendor does the same:
# master data + balances at a cut-over date). Old passwords are never
# copied — DayBill users get new passwords.
#
#   src = open_mssql(server_config, "OldShopDB")  /  open_sqlite(path)
#   m   = guess_mapping(src)          # built-in RMS / SAP B1 maps, a saved
#                                     # map, or a guess from names + values
#   plan = prepare(src, m, options)   # read + check (nothing written)
#   plan.preview("products"), plan.issues, plan.counts()
#   result = apply(plan, options, progress)   # writes into DayBill (db)
#
# The writing goes through DayBill's own code: products_import (same as
# the Excel import) and opening_balances (stock card + journals against
# Opening Balance Equity) — re-running never doubles stock or balances.
# ============================================================
import difflib
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# ── what DayBill wants for each kind of record ──────────────
FIELDS = {
    "products": [
        ("key", "Old record ID (links extra barcodes)"),
        ("code", "Product code *"),
        ("barcode", "Barcode"),
        ("name_en", "Name (English) *"),
        ("name_ar", "Name (Arabic)"),
        ("category", "Category / department"),
        ("unit", "Unit"),
        ("price", "Sell price"),
        ("cost", "Cost price"),
        ("vat", "VAT (% or S/Z/E)"),
        ("qty", "Stock on hand"),
        ("reorder", "Reorder level"),
        ("inactive", "Inactive (1 = not used)"),
    ],
    "barcodes": [
        ("item", "Product (old ID or code) *"),
        ("barcode", "Extra barcode *"),
    ],
    "customers": [
        ("code", "Customer code"),
        ("name_en", "Name (English) *"),
        ("name_ar", "Name (Arabic)"),
        ("phone", "Phone / mobile"),
        ("email", "E-mail"),
        ("vat_no", "VAT number"),
        ("address", "Address"),
        ("city", "City"),
        ("credit_limit", "Credit limit"),
        ("balance", "Balance (they owe us)"),
    ],
    "suppliers": [
        ("code", "Supplier code"),
        ("name_en", "Name (English) *"),
        ("name_ar", "Name (Arabic)"),
        ("phone", "Phone / mobile"),
        ("email", "E-mail"),
        ("vat_no", "VAT number"),
        ("address", "Address"),
        ("city", "City"),
        ("balance", "Balance (we owe them)"),
    ],
}
ENTITIES = ("products", "barcodes", "customers", "suppliers")
ENTITY_TITLES = {"products": "Products", "barcodes": "Extra barcodes",
                 "customers": "Customers", "suppliers": "Suppliers"}

# ── names other programs use (English, abbreviations, Arabic) ──
TABLE_SYNONYMS = {
    "products": ["item", "items", "product", "products", "goods", "material", "materials", "stock",
                 "stockitem", "stockitems", "inventory", "invitem", "invitems", "article", "articles",
                 "sku", "skus", "merchandise", "prod", "itm", "oitm", "itemmaster", "productmaster",
                 "صنف", "اصناف", "الاصناف", "مواد", "المواد", "منتجات", "المنتجات", "بضاعه", "بضائع",
                 "سلع", "السلع", "مخزون"],
    "barcodes": ["alias", "aliases", "barcode", "barcodes", "itembarcode", "itembarcodes",
                 "productbarcode", "productbarcodes", "itemalias", "ean", "upc", "obcd",
                 "باركود", "الباركود", "باركودات"],
    "customers": ["customer", "customers", "client", "clients", "cust", "custs", "debtor", "debtors",
                  "buyer", "buyers", "account", "accounts", "ocrd", "party", "parties",
                  "عميل", "عملاء", "العملاء", "زبون", "زبائن", "الزبائن"],
    "suppliers": ["supplier", "suppliers", "vendor", "vendors", "creditor", "creditors", "supp",
                  "provider", "providers", "ocrd", "party", "parties",
                  "مورد", "موردين", "الموردين", "موردون"],
}
FIELD_SYNONYMS = {
    "key": ["id", "itemid", "productid", "recid", "rowid", "pk", "serial", "itemkey",
            "productkey", "guid"],
    "code": ["code", "itemcode", "productcode", "itemlookupcode", "lookupcode", "sku", "itemno",
             "itemnumber", "productno", "productnumber", "partno", "partnumber", "ref", "reference",
             "accountnumber", "accountno", "custcode", "customercode", "suppliercode", "vendorcode",
             "cardcode", "no", "number", "itmno", "itmcode", "itemnum", "prodno", "prodcode",
             "custno", "customerno", "custnum", "clientno", "clientcode", "acctno", "accno",
             "vendno", "vendorno", "vendcode", "suppno", "supplierno", "supno", "supcode",
             "كود", "الكود", "رمز", "الرمز", "رقم الصنف", "كود الصنف",
             "رمز الصنف", "رقم العميل", "كود العميل", "رقم المورد", "كود المورد"],
    "barcode": ["barcode", "barcodes", "bar", "ean", "ean13", "upc", "gtin", "codebars", "alias",
                "scancode", "plu", "باركود", "الباركود", "رمز شريطي"],
    "name_en": ["name", "itemname", "productname", "description", "desc", "descr", "title",
                "namee", "nameen", "englishname", "enname", "latinname", "custname", "customername",
                "suppliername", "vendorname", "cardname", "companyname", "company", "fullname",
                "اسم", "الاسم", "اسم الصنف", "اسم انجليزي", "الاسم الانجليزي"],
    "name_ar": ["namear", "arabicname", "arname", "namea", "frgnname", "foreignname", "name2",
                "itemnamear", "productnamear", "اسم عربي", "الاسم العربي", "الاسم بالعربي",
                "اسم الصنف عربي", "اسم العميل", "اسم المورد"],
    "category": ["category", "categoryid", "categoryname", "catid", "cat", "group", "groupid",
                 "itemgroup", "itmsgrpcod", "itmsgrpnam", "department", "departmentid", "dept",
                 "deptid", "family", "class", "type", "section", "مجموعه", "المجموعه", "فئه",
                 "الفئه", "قسم", "القسم", "تصنيف", "التصنيف"],
    "unit": ["unit", "uom", "unitofmeasure", "units", "unitname", "invntryuom", "measure",
             "salesunit", "وحده", "الوحده", "وحده القياس"],
    "price": ["price", "saleprice", "salesprice", "sellprice", "sellingprice", "retailprice",
              "unitprice", "pricea", "price1", "listprice", "rprice", "sprice", "salprice",
              "سعر", "السعر", "سعر البيع", "سعر بيع", "سعر التجزئه"],
    "cost": ["cost", "costprice", "purchaseprice", "buyprice", "avgprice", "averagecost",
             "avgcost", "lastcost", "lastpurprc", "unitcost", "pprice", "purprice",
             "تكلفه", "التكلفه", "سعر التكلفه", "سعر الشراء", "سعر شراء"],
    "vat": ["vat", "tax", "taxid", "taxrate", "vatrate", "vatpercent", "taxpercent", "taxcode",
            "vatcode", "vatgroup", "vatgourpsa", "vatgroupsa", "taxable", "ضريبه", "الضريبه",
            "نسبه الضريبه", "القيمه المضافه"],
    "qty": ["qty", "quantity", "onhand", "stock", "stockqty", "balance", "qtyonhand", "currentstock",
            "instock", "available", "qtybalance", "كميه", "الكميه", "الرصيد", "المخزون",
            "الكميه المتاحه"],
    "reorder": ["reorder", "reorderlevel", "reorderpoint", "minstock", "minqty", "minimum",
                "حد الطلب", "الحد الادنى"],
    "inactive": ["inactive", "disabled", "isdeleted", "deleted", "discontinued", "blocked",
                 "frozenfor", "stopped", "موقوف", "متوقف", "محذوف"],
    "item": ["itemid", "productid", "itemcode", "productcode", "itemno", "item", "product",
             "parentid", "الصنف", "رقم الصنف", "كود الصنف"],
    "phone": ["phone", "phonenumber", "tel", "telephone", "mobile", "mobileno", "cell", "cellular",
              "phone1", "contactno", "whatsapp", "هاتف", "الهاتف", "جوال", "الجوال", "موبايل",
              "رقم الجوال"],
    "email": ["email", "emailaddress", "mail", "e_mail", "بريد", "البريد", "البريد الالكتروني"],
    "vat_no": ["vatno", "vatnumber", "taxnumber", "taxno", "trn", "vatregno", "vatreg",
               "vatregistrationno", "licttradnum", "lictradnum", "taxid", "taxregistration",
               "الرقم الضريبي", "رقم ضريبي", "رقم التسجيل الضريبي"],
    "address": ["address", "address1", "addr", "street", "streetaddress", "عنوان", "العنوان"],
    "city": ["city", "town", "مدينه", "المدينه"],
    "credit_limit": ["creditlimit", "creditline", "maxcredit", "limit", "حد الائتمان",
                     "الحد الائتماني"],
    "balance": ["balance", "accountbalance", "currentbalance", "openingbalance", "bal", "due",
                "amountdue", "outstanding", "debt", "الرصيد", "رصيد", "المستحق"],
}

_AR = re.compile(r"[؀-ۿ]")
_AR_DIAC = re.compile(r"[ً-ْـ]")


def norm_name(s):
    """'tbl_ItemLookupCode' → 'itemlookupcode'; Arabic letters unified."""
    s = str(s or "")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s).lower()
    s = _AR_DIAC.sub("", s)
    s = (s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")
         .replace("ى", "ي"))
    s = re.sub(r"^(tbl|tb|t|fld|f|col|c)[_\s]+", "", s)
    s = re.sub(r"[\s_\-\.\$\[\]]+", " ", s).strip()
    return s


def _flat(s):
    return norm_name(s).replace(" ", "")


def name_score(col, synonyms):
    """0..1 — how much a column / table name looks like one of the synonyms."""
    c = _flat(col)
    if not c:
        return 0.0
    best = 0.0
    for syn in synonyms:
        s = _flat(syn)
        if not s:
            continue
        if c == s:
            return 1.0
        if len(s) >= 3 and (c.endswith(s) or c.startswith(s)):
            best = max(best, 0.85 if len(s) >= 5 else 0.75)
        elif len(s) >= 4 and s in c:
            best = max(best, 0.7)
        elif len(c) >= 4 and c in s:
            best = max(best, 0.6)
        else:
            r = difflib.SequenceMatcher(None, c, s).ratio()
            if r >= 0.8:
                best = max(best, r * 0.75)
    return best


# ── values ──────────────────────────────────────────────────
def to_dec(v, default=None):
    if v is None:
        return default
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        return Decimal(int(v))
    if isinstance(v, (int, float)):
        try:
            return Decimal(str(v))
        except InvalidOperation:
            return default
    s = str(v).strip().replace(",", "").replace("%", "")
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789."))
    if not s:
        return default
    try:
        return Decimal(s)
    except InvalidOperation:
        return default


def money(v):
    return (to_dec(v, Decimal(0)) or Decimal(0)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def text(v, maxlen=None):
    if v is None:
        return ""
    if isinstance(v, bytes):
        try:
            v = v.decode("utf-8")
        except UnicodeDecodeError:
            v = v.decode("cp1256", "replace")
    s = re.sub(r"\s+", " ", str(v)).strip()
    if maxlen:
        s = s[:maxlen]
    return s


def arabic_ratio(s):
    s = str(s or "")
    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if _AR.match(ch)) / len(letters)


def ean_ok(code):
    """GS1 check digit for EAN-8 / UPC-A / EAN-13 / GTIN-14."""
    if not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    digits = [int(d) for d in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def clean_barcode(v):
    """→ (barcode, warning). Never turned into a number (keeps leading 0s)."""
    if v is None:
        return "", ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = re.sub(r"\s+", "", str(v)).strip().strip("*")
    if not s:
        return "", ""
    if s.isdigit() and len(s) in (8, 12, 13, 14) and not ean_ok(s):
        return s[:50], "check digit does not match (kept as an internal code)"
    return s[:50], ""


def clean_vat_no(v):
    d = re.sub(r"\D", "", str(v or ""))
    return d if re.match(r"^3\d{13}3$", d) else ""


def clean_phone(v):
    s = re.sub(r"[^\d+]", "", str(v or ""))
    return s[:20]


def vat_code(v):
    """Old program's VAT value → (DayBill code S/Z/E/O, warning)."""
    if v is None or str(v).strip() == "":
        return None, ""
    s = str(v).strip().lower()
    if s in ("s", "standard", "std", "vat", "yes", "y", "true", "taxable", "خاضع", "اساسي"):
        return "S", ""
    if s in ("z", "zero", "zero rated", "zero-rated", "صفر", "صفريه"):
        return "Z", ""
    if s in ("e", "exempt", "exempted", "معفى", "معفي", "معفاه"):
        return "E", ""
    if s in ("o", "out", "out of scope", "غير خاضع"):
        return "O", ""
    if s in ("n", "no", "false", "none", "non-taxable", "nontaxable"):
        return "Z", "marked 'not taxable' — set to zero-rated, please check"
    d = to_dec(v)
    if d is None:
        return "S", "VAT value '%s' not understood — set to 15%%" % str(v)[:20]
    if d < 1 and d > 0:
        d = d * 100
    d = d.quantize(Decimal("0.01"))
    if d == 15:
        return "S", ""
    if d == 0:
        return "Z", ""
    if d == 5:
        return "S", "old 5% VAT — set to 15%"
    return "S", "VAT %s%% is not a Saudi rate — set to 15%%" % d


def truthy(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "-1", "t", "on", "نعم")


# ── sources (read only) ─────────────────────────────────────
def _q(name):
    """[schema].[table] / [column] — safe quoting."""
    parts = str(name).split(".") if "." in str(name) and not str(name).startswith("[") else [str(name)]
    return ".".join("[%s]" % p.replace("]", "]]") for p in parts)


class SqliteSource:
    """A SQLite file (e.g. Aronium POS) — opened READ ONLY."""
    kind = "sqlite"

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        uri = "file:%s?mode=ro" % os.path.abspath(path).replace("\\", "/")
        self.cn = sqlite3.connect(uri, uri=True)

    def tables(self):
        out = []
        for (n,) in self.cn.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                                    "name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
            try:
                c = self.cn.execute('SELECT COUNT(*) FROM "%s"' % n.replace('"', '""')).fetchone()[0]
            except Exception:
                c = 0
            out.append((n, int(c or 0)))
        return out

    def columns(self, table):
        return [(r[1], str(r[2] or "").lower())
                for r in self.cn.execute('PRAGMA table_info("%s")' % table.replace('"', '""'))]

    def rows(self, table, cols, where=None, limit=None):
        qc = ", ".join('"%s"' % c.replace('"', '""') for c in cols)
        sql = 'SELECT %s FROM "%s"' % (qc, table.replace('"', '""'))
        params = ()
        if where:
            sql += ' WHERE "%s" = ?' % where[0].replace('"', '""')
            params = (where[1],)
        if limit:
            sql += " LIMIT %d" % int(limit)
        cur = self.cn.execute(sql, params)
        for r in cur:
            yield dict(zip(cols, r))

    def close(self):
        try:
            self.cn.close()
        except Exception:
            pass


class MssqlSource:
    """A database on SQL Server — only SELECTs are ever sent."""
    kind = "mssql"

    def __init__(self, conn, name):
        self.cn = conn
        self.name = name

    def _all(self, sql, params=()):
        cur = self.cn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def tables(self):
        rows = self._all(
            "SELECT s.name, t.name, SUM(p.rows) FROM sys.tables t JOIN sys.schemas s ON "
            "s.schema_id=t.schema_id JOIN sys.partitions p ON p.object_id=t.object_id AND "
            "p.index_id IN (0,1) WHERE t.is_ms_shipped=0 GROUP BY s.name, t.name ORDER BY t.name")
        return [((t if s == "dbo" else "%s.%s" % (s, t)), int(n or 0)) for s, t, n in rows]

    def columns(self, table):
        rows = self._all(
            "SELECT c.name, ty.name FROM sys.columns c JOIN sys.types ty ON "
            "ty.user_type_id=c.user_type_id WHERE c.object_id=OBJECT_ID(?) ORDER BY c.column_id",
            (_q(table if "." in table else "dbo." + table),))
        skip = ("geography", "geometry", "hierarchyid", "sql_variant", "image", "varbinary", "binary",
                "timestamp", "rowversion")
        return [(c, str(t or "").lower()) for c, t in rows if str(t or "").lower() not in skip]

    def rows(self, table, cols, where=None, limit=None):
        sql = "SELECT %s%s FROM %s" % (("TOP %d " % int(limit)) if limit else "",
                                       ", ".join(_q(c) for c in cols), _q(table))
        params = ()
        if where:
            sql += " WHERE %s = ?" % _q(where[0])
            params = (where[1],)
        cur = self.cn.cursor()
        try:
            cur.execute(sql, params)
            while True:
                chunk = cur.fetchmany(500)
                if not chunk:
                    break
                for r in chunk:
                    yield dict(zip(cols, r))
        finally:
            cur.close()

    def close(self):
        try:
            self.cn.close()
        except Exception:
            pass


def open_sqlite(path):
    return SqliteSource(path)


def open_mssql(config, database):
    """A read-only style connection to another database on the server."""
    import pyodbc
    from config.database import build_connection_string
    c = dict(config or {})
    c["database"] = database
    cs = build_connection_string(c) + "ApplicationIntent=ReadOnly;"
    cn = pyodbc.connect(cs, autocommit=True, timeout=15)
    try:
        cn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
    except Exception:
        pass
    return MssqlSource(cn, database)


# ── reading the shape of the old database ───────────────────
class Shape:
    def __init__(self, src, sample_rows=300):
        self.src = src
        self.tables = dict(src.tables())
        self._cols = {}
        self._sample = {}
        self.sample_rows = sample_rows

    def columns(self, t):
        if t not in self._cols:
            try:
                self._cols[t] = self.src.columns(t)
            except Exception:
                self._cols[t] = []
        return self._cols[t]

    def colnames(self, t):
        return [c for c, _ty in self.columns(t)]

    def sample(self, t):
        if t not in self._sample:
            cols = self.colnames(t)
            try:
                self._sample[t] = list(self.src.rows(t, cols, limit=self.sample_rows)) if cols else []
            except Exception:
                self._sample[t] = []
        return self._sample[t]

    def find_table(self, name):
        low = {k.lower(): k for k in self.tables}
        return low.get(str(name).lower()) or low.get("dbo." + str(name).lower())

    def find_col(self, t, name):
        low = {c.lower(): c for c in self.colnames(t)}
        return low.get(str(name).lower())

    def fingerprint(self):
        parts = sorted("%s.%s" % (t.lower(), c.lower()) for t in self.tables for c in self.colnames(t))
        return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


_NUM_TYPES = ("int", "bigint", "smallint", "tinyint", "decimal", "numeric", "money", "smallmoney",
              "float", "real", "double", "integer", "number")
_TEXT_TYPES = ("char", "varchar", "nchar", "nvarchar", "text", "ntext", "string", "varchar2", "")


def _is_num_type(ty):
    return any(ty.startswith(t) for t in _NUM_TYPES)


def value_score(field, values, ty):
    """0..1 — do the sample values look like this field?"""
    vals = [v for v in values if v is not None and str(v).strip() != ""]
    if not vals:
        return 0.0
    n = len(vals)
    sv = [str(v).strip() for v in vals]
    uniq = len(set(sv)) / n
    nums = [to_dec(v) for v in vals]
    num_share = sum(1 for d in nums if d is not None) / n
    if field in ("code", "key"):
        ds = [d for d in nums if d is not None]
        if ds and sum(1 for d in ds if d != d.to_integral_value()) > 0.2 * len(ds):
            return 0.0                       # 12.50, 7.25 … are amounts, not codes
        short = sum(1 for s in sv if len(s) <= 25) / n
        return round(0.5 * uniq + 0.3 * short + (0.2 if field == "key" and _is_num_type(ty) else 0.1), 3)
    if field == "barcode":
        bc = sum(1 for s in sv if s.isdigit() and len(s) in (8, 12, 13, 14)) / n
        good = sum(1 for s in sv if ean_ok(s)) / n
        return round(min(1.0, 0.5 * bc + 0.4 * good + 0.1 * uniq), 3)
    if field == "item":
        return round(0.6 * num_share + 0.4 * (1 - uniq) if n > 1 else 0.3, 3)
    if field in ("name_en", "name_ar", "category", "unit", "address", "city"):
        alpha = sum(1 for s in sv if any(ch.isalpha() for ch in s)) / n
        avg = sum(len(s) for s in sv) / n
        ar = sum(arabic_ratio(s) for s in sv) / n
        if field == "name_ar":
            return round(alpha * ar, 3)
        if field == "name_en":
            return round(alpha * (0.6 + 0.4 * min(1.0, avg / 12)) * (0.5 + 0.5 * uniq) * (1 - 0.5 * ar), 3)
        if field == "unit":
            return round(alpha * (1.0 if avg <= 8 else 0.4) * (1 - uniq if n > 3 else 0.5), 3)
        if field == "category":
            return round(0.6 * (1 - uniq if n > 3 else 0.3) + 0.4 * num_share, 3)
        return round(alpha * 0.6, 3)
    if field in ("price", "cost", "qty", "reorder", "credit_limit", "balance"):
        if num_share < 0.9:
            return 0.0
        ds = [d for d in nums if d is not None]
        frac = sum(1 for d in ds if d != d.to_integral_value()) / len(ds)
        nonneg = sum(1 for d in ds if d >= 0) / len(ds)
        if field in ("price", "cost"):
            return round(0.5 + 0.3 * frac + 0.2 * nonneg, 3)
        return round(0.6 + 0.2 * (1 - frac) + 0.2 * nonneg if field in ("qty", "reorder") else 0.7, 3)
    if field == "vat":
        ok = sum(1 for s in sv if vat_code(s)[0] and (not vat_code(s)[1] or vat_code(s)[1].startswith("old 5%"))) / n
        few = len(set(sv)) <= 4 or len(set(sv)) / n <= 0.5
        return round(ok * (0.9 if few else 0.5), 3)
    if field == "inactive":
        flags = sum(1 for s in sv if s.lower() in ("0", "1", "true", "false", "-1", "y", "n")) / n
        return round(flags * 0.8, 3)
    if field == "phone":
        ph = sum(1 for s in sv if 7 <= len(re.sub(r"\D", "", s)) <= 14) / n
        return round(ph * 0.9, 3)
    if field == "email":
        return round(sum(1 for s in sv if "@" in s) / n, 3)
    if field == "vat_no":
        return round(sum(1 for s in sv if clean_vat_no(s)) / n, 3)
    return 0.0


def _type_ok(field, ty):
    if field in ("price", "cost", "qty", "reorder", "credit_limit", "balance"):
        return 1.0 if _is_num_type(ty) else 0.3
    if field in ("name_en", "name_ar", "address", "city", "email", "unit"):
        return 0.0 if _is_num_type(ty) else 1.0
    if field in ("code", "key", "barcode"):
        if any(ty.startswith(t) for t in ("float", "real", "double", "decimal", "numeric", "money")):
            return 0.3
        return 0.8 if _is_num_type(ty) else 0.9
    return 0.6


# fields that can be found from their values alone (no name match)
VALUE_ONLY = ("name_en", "name_ar", "barcode", "price", "cost", "phone", "email", "vat_no", "code")
# fields whose values must agree with the name (an ID column called TaxID
# is not a VAT rate; a numeric ID is not a price)
VALUE_NEEDED = {"vat": 0.5, "barcode": 0.3, "price": 0.5, "cost": 0.5, "qty": 0.5,
                "balance": 0.5, "credit_limit": 0.5, "phone": 0.3, "email": 0.3, "vat_no": 0.3}


def looks_like_id(values):
    """1, 2, 3 … — a record number, not an amount."""
    ds = [to_dec(v) for v in values if v is not None and str(v).strip() != ""]
    ds = [d for d in ds if d is not None]
    if len(ds) < 3 or any(d != d.to_integral_value() for d in ds):
        return False
    if len(set(ds)) != len(ds):
        return False
    return (max(ds) - min(ds) + 1) <= len(ds) * 1.5


def score_columns(shape, table, entity):
    """{field: [(score, column, why)]} best first."""
    out = {}
    cols = shape.columns(table)
    sample = shape.sample(table)
    fields = [f for f, _l in FIELDS[entity]]
    # a column whose name IS another field's name belongs to that field
    exact = {}
    for col, _ty in cols:
        for f in fields:
            if name_score(col, FIELD_SYNONYMS.get(f, [])) >= 0.999:
                exact.setdefault(col, set()).add(f)
    for field in fields:
        syn = FIELD_SYNONYMS.get(field, [])
        lst = []
        for col, ty in cols:
            vals = [r.get(col) for r in sample]
            ns = name_score(col, syn)
            vs = value_score(field, vals, ty)
            if field in ("price", "cost", "qty", "reorder", "balance", "credit_limit") and \
                    looks_like_id(vals):
                vs = 0.0
            ts = _type_ok(field, ty)
            if ns > 0:
                s = 0.5 * ns + 0.35 * vs + 0.15 * ts
            elif field in VALUE_ONLY:
                s = 0.6 * vs * ts
            else:
                s = 0.0
            if field in VALUE_NEEDED and vs < VALUE_NEEDED[field]:
                s *= 0.4
            if field in ("name_en", "name_ar") and vs < 0.05:
                s *= 0.3
            if exact.get(col) and field not in exact[col]:
                s *= 0.5
            if s >= 0.25:
                lst.append((round(min(s, 1.0), 3), col,
                            "name %d%% · values %d%%" % (ns * 100, vs * 100)))
        lst.sort(reverse=True)
        out[field] = lst
    return out


def score_tables(shape, entity):
    """[(score, table)] best first."""
    out = []
    key_fields = {"products": ("code", "name_en", "price"), "barcodes": ("item", "barcode"),
                  "customers": ("name_en", "phone", "balance"),
                  "suppliers": ("name_en", "phone", "balance")}[entity]
    for t, n in shape.tables.items():
        if n <= 0:
            continue
        ns = name_score(t.split(".")[-1], TABLE_SYNONYMS[entity])
        if ns < 0.5 and len(shape.tables) > 25:
            # big databases: only look closely at tables whose name fits
            cols_fit = sum(1 for c in shape.colnames(t)
                           for f in key_fields if name_score(c, FIELD_SYNONYMS[f]) >= 0.85)
            if cols_fit < 2:
                continue
        sc = score_columns(shape, t, entity)
        cov = sum((sc[f][0][0] if sc.get(f) else 0) for f in key_fields) / len(key_fields)
        if entity == "barcodes" and len(shape.colnames(t)) > 8:
            cov *= 0.6                      # a barcode table is narrow
        out.append((round(0.45 * ns + 0.55 * cov, 3), t))
    out.sort(reverse=True)
    return out


def assign(scores, min_score=0.35):
    """One column per field, best scores first."""
    cand = [(s, f, c) for f, lst in scores.items() for s, c, _w in lst if s >= min_score]
    cand.sort(reverse=True)
    used_f, used_c, m = set(), set(), {}
    for s, f, c in cand:
        if f in used_f or c in used_c:
            continue
        m[f] = c
        used_f.add(f)
        used_c.add(c)
    return m


# ── built-in maps for programs whose tables are known ───────
PROFILES = {
    # Microsoft Dynamics RMS (Store Operations) / Dynamics POS 2009 —
    # Item / Alias / Supplier confirmed; the rest only used when the
    # column really exists in the database.
    "Microsoft RMS": {
        "detect": ["Item", "Alias", "Cashier", "Supplier"],
        "products": {"table": "Item", "fields": {
            "key": "ID", "code": "ItemLookupCode", "name_en": "Description",
            "price": "Price", "cost": "Cost", "qty": "Quantity", "reorder": "ReorderPoint",
            "inactive": "Inactive",
            "category": {"column": "DepartmentID",
                         "lookup": {"table": "Department", "key": "ID", "value": "Name"}}}},
        "barcodes": {"table": "Alias", "fields": {"item": "ItemID", "barcode": "Alias"}},
        "customers": {"table": "Customer", "fields": {
            "code": "AccountNumber", "name_en": ["FirstName", "LastName"], "phone": "PhoneNumber",
            "email": "EmailAddress", "address": "Address", "city": "City", "vat_no": "TaxNumber",
            "credit_limit": "CreditLimit", "balance": "AccountBalance"}},
        "suppliers": {"table": "Supplier", "fields": {
            "code": "Code", "name_en": "SupplierName", "phone": "PhoneNumber",
            "email": "EmailAddress", "address": "Address1", "city": "City",
            "vat_no": "TaxNumber"}},
    },
    # SAP Business One — OITM / OCRD / OITB (column names from SAP's SDK)
    "SAP Business One": {
        "detect": ["OITM", "OCRD", "OITB", "OUSR"],
        "products": {"table": "OITM", "fields": {
            "code": "ItemCode", "name_en": "ItemName", "name_ar": "FrgnName",
            "barcode": "CodeBars", "cost": "AvgPrice", "qty": "OnHand", "unit": "InvntryUom",
            "category": {"column": "ItmsGrpCod",
                         "lookup": {"table": "OITB", "key": "ItmsGrpCod", "value": "ItmsGrpNam"}},
            "price": {"column": "ItemCode",
                      "lookup": {"table": "ITM1", "key": "ItemCode", "value": "Price",
                                 "where": ["PriceList", 1]}}}},
        "barcodes": {"table": "OBCD", "fields": {"item": "ItemCode", "barcode": "BcdCode"}},
        "customers": {"table": "OCRD", "where": ["CardType", "C"], "fields": {
            "code": "CardCode", "name_en": "CardName", "phone": "Phone1", "email": "E_Mail",
            "vat_no": "LicTradNum", "credit_limit": "CreditLine", "balance": "Balance"}},
        "suppliers": {"table": "OCRD", "where": ["CardType", "S"], "fields": {
            "code": "CardCode", "name_en": "CardName", "phone": "Phone1", "email": "E_Mail",
            "vat_no": "LicTradNum", "balance": "Balance"}},
    },
}


def _profile_dir():
    try:
        from config.paths import config_file
        d = config_file("dbtool_profiles")
    except Exception:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config",
                         "dbtool_profiles")
    os.makedirs(d, exist_ok=True)
    return d


def save_mapping(shape, mapping, label=""):
    p = os.path.join(_profile_dir(), "%s.json" % shape.fingerprint())
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"label": label, "saved": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "mapping": mapping}, f, ensure_ascii=False, indent=1)
    return p


def saved_mapping(shape):
    p = os.path.join(_profile_dir(), "%s.json" % shape.fingerprint())
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("mapping")
    except Exception:
        return None


def _spec_cols(spec):
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, list):
        return list(spec)
    if isinstance(spec, dict) and spec.get("column"):
        return [spec["column"]]
    return []


def _fit_profile(shape, prof):
    """Keep only the tables / columns that really exist (real names)."""
    out = {}
    for ent in ENTITIES:
        e = prof.get(ent)
        if not e:
            continue
        t = shape.find_table(e["table"])
        if not t:
            continue
        fields = {}
        for f, spec in e["fields"].items():
            cols = [shape.find_col(t, c) for c in _spec_cols(spec)]
            if not cols or not all(cols):
                continue
            if isinstance(spec, dict) and spec.get("lookup"):
                lk = dict(spec["lookup"])
                lt = shape.find_table(lk["table"])
                if not lt or not shape.find_col(lt, lk["key"]) or not shape.find_col(lt, lk["value"]):
                    continue
                lk.update(table=lt, key=shape.find_col(lt, lk["key"]),
                          value=shape.find_col(lt, lk["value"]))
                if lk.get("where"):
                    wc = shape.find_col(lt, lk["where"][0])
                    if not wc:
                        continue
                    lk["where"] = [wc, lk["where"][1]]
                fields[f] = {"column": cols[0], "lookup": lk}
            elif isinstance(spec, list):
                fields[f] = cols
            else:
                fields[f] = cols[0]
        where = e.get("where")
        if where:
            wc = shape.find_col(t, where[0])
            where = [wc, where[1]] if wc else None
        out[ent] = {"table": t, "where": where, "fields": fields}
    return out


def detect_program(shape):
    for name, prof in PROFILES.items():
        if all(shape.find_table(t) for t in prof["detect"]):
            return name
    return ""


def guess_entity(shape, entity, table=None):
    if table is None:
        ranked = score_tables(shape, entity)
        if not ranked or ranked[0][0] < 0.2:
            return None
        table = ranked[0][1]
    m = assign(score_columns(shape, table, entity))
    if entity == "products" and m.get("category"):
        lk = find_lookup(shape, table, m["category"])
        if lk:
            m["category"] = {"column": m["category"], "lookup": lk}
    if entity in ("products", "customers", "suppliers") and "name_en" not in m and "name_ar" in m:
        pass
    # sell price is the bigger of two prices
    if entity == "products" and "price" in m and "cost" in m:
        smp = shape.sample(table)

        def avg(c):
            ds = [to_dec(r.get(c)) for r in smp]
            ds = [d for d in ds if d is not None]
            return sum(ds) / len(ds) if ds else Decimal(0)
        if avg(m["cost"]) > avg(m["price"]):
            m["price"], m["cost"] = m["cost"], m["price"]
    # one name column only, and it is Arabic → it is the Arabic name
    if entity != "barcodes" and "name_en" in m and "name_ar" not in m:
        vals = [r.get(m["name_en"]) for r in shape.sample(table)]
        if vals and sum(arabic_ratio(v) for v in vals) / len(vals) > 0.6:
            m["name_ar"] = m.pop("name_en")
    return {"table": table, "where": None, "fields": m}


def find_lookup(shape, table, col):
    """The values of `col` are numbers pointing into another table (a group
    / department list)? → {"table","key","value"} to show its name."""
    vals = {str(int(d)) for d in (to_dec(r.get(col)) for r in shape.sample(table))
            if d is not None and d == d.to_integral_value()}
    if not vals:
        return None
    best = None
    many = len(shape.tables) > 40
    for t, n in shape.tables.items():
        if t == table or n <= 0 or n > 20000:
            continue
        if many and name_score(t.split(".")[-1], FIELD_SYNONYMS["category"] +
                               ["groups", "categories", "departments", "classes", "families"]) < 0.5:
            continue                       # big databases: only list-like tables
        smp = shape.sample(t)
        for kc, _ty in shape.columns(t):
            keys = set()
            for r in smp:
                d = to_dec(r.get(kc))
                if d is not None and d == d.to_integral_value():
                    keys.add(str(int(d)))
            if not keys or len(vals & keys) < 0.9 * len(vals):
                continue
            for vc, vty in shape.columns(t):
                if vc == kc or _is_num_type(vty):
                    continue
                texts = [str(r.get(vc) or "") for r in smp]
                if not texts or sum(1 for x in texts if any(ch.isalpha() for ch in x)) < 0.8 * len(texts):
                    continue
                sc = 0.5 + 0.5 * name_score(vc, ["name", "title", "description", "desc"] +
                                            FIELD_SYNONYMS["category"] + ["اسم", "الاسم"])
                sc += 0.2 * name_score(t.split(".")[-1], FIELD_SYNONYMS["category"] +
                                       ["groups", "categories", "departments"])
                if best is None or sc > best[0]:
                    best = (sc, {"table": t, "key": kc, "value": vc})
    return best[1] if best else None


def guess_mapping(src_or_shape):
    """→ (mapping, how)  how: 'saved' | program name | 'guessed'."""
    shape = src_or_shape if isinstance(src_or_shape, Shape) else Shape(src_or_shape)
    m = saved_mapping(shape)
    if m:
        return m, "saved"
    prog = detect_program(shape)
    mapping = _fit_profile(shape, PROFILES[prog]) if prog else {}
    for ent in ENTITIES:
        if ent in mapping:
            # fill fields the profile could not confirm, from the guesser
            g = guess_entity(shape, ent, mapping[ent]["table"]) or {"fields": {}}
            used = {c for v in mapping[ent]["fields"].values() for c in _spec_cols(v)}
            for f, c in g["fields"].items():
                if f not in mapping[ent]["fields"] and c not in used:
                    mapping[ent]["fields"][f] = c
                    used.add(c)
            continue
        g = guess_entity(shape, ent)
        if g:
            mapping[ent] = g
    # the same table can't be both customers and suppliers when guessed
    if (not prog and mapping.get("customers") and mapping.get("suppliers")
            and mapping["customers"]["table"] == mapping["suppliers"]["table"]
            and not mapping["customers"].get("where")):
        ranked = [t for s, t in score_tables(shape, "suppliers")
                  if t != mapping["customers"]["table"] and s >= 0.3]
        if ranked:
            mapping["suppliers"] = guess_entity(shape, "suppliers", ranked[0])
        else:
            mapping.pop("suppliers")
    # the products table is never the barcodes table
    if mapping.get("barcodes") and mapping.get("products") and \
            mapping["barcodes"]["table"] == mapping["products"]["table"]:
        mapping.pop("barcodes")
    return mapping, (prog or "guessed")


# ── reading + checking (nothing is written) ─────────────────
class Issue:
    def __init__(self, level, entity, ref, code, text_):
        self.level, self.entity, self.ref, self.code, self.text = level, entity, ref, code, text_

    def row(self):
        return (self.level, ENTITY_TITLES.get(self.entity, self.entity), self.ref, self.code, self.text)


class Plan:
    def __init__(self):
        self.records = {e: [] for e in ENTITIES}
        self.issues = []
        self.source = ""
        self.program = ""

    def add(self, level, entity, ref, code, txt):
        self.issues.append(Issue(level, entity, str(ref)[:40], code, txt))

    def counts(self):
        c = {e: len(self.records[e]) for e in ENTITIES}
        c["errors"] = sum(1 for i in self.issues if i.level == "error")
        c["warnings"] = sum(1 for i in self.issues if i.level == "warning")
        c["stock_value"] = float(sum((r["qty"] or 0) * (r["cost"] or 0) for r in self.records["products"]
                                     if (r["qty"] or 0) > 0))
        c["receivable"] = float(sum(r["balance"] for r in self.records["customers"]))
        c["payable"] = float(sum(r["balance"] for r in self.records["suppliers"]))
        return c

    def preview(self, entity, n=30):
        return self.records.get(entity, [])[:n]

    def issues_csv(self, path):
        import csv
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Level", "Data", "Record", "Code", "Problem"])
            for i in self.issues:
                w.writerow(i.row())
        return path


def _lookup_table(src, lk):
    cols = [lk["key"], lk["value"]]
    out = {}
    for r in src.rows(lk["table"], cols, where=lk.get("where")):
        k = r.get(lk["key"])
        out[str(k).strip() if k is not None else ""] = r.get(lk["value"])
    return out


def _read(src, ent_map):
    """Rows of the old table with each field's value (lookups / joins done)."""
    fields = ent_map.get("fields") or {}
    cols = []
    for spec in fields.values():
        for c in _spec_cols(spec):
            if c not in cols:
                cols.append(c)
    if not cols:
        return []
    lookups = {}
    for f, spec in fields.items():
        if isinstance(spec, dict) and spec.get("lookup"):
            try:
                lookups[f] = _lookup_table(src, spec["lookup"])
            except Exception:
                lookups[f] = {}
    where = ent_map.get("where")
    out = []
    for r in src.rows(ent_map["table"], cols, where=tuple(where) if where else None):
        rec = {}
        for f, spec in fields.items():
            if isinstance(spec, list):
                rec[f] = " ".join(text(r.get(c)) for c in spec if text(r.get(c)))
            elif isinstance(spec, dict) and spec.get("const") is not None:
                rec[f] = spec["const"]
            elif isinstance(spec, dict):
                v = r.get(spec["column"])
                if f in lookups:
                    k = str(v).strip() if v is not None else ""
                    if isinstance(v, float) and v.is_integer():
                        k = str(int(v))
                    v = lookups[f].get(k)
                rec[f] = v
            else:
                rec[f] = r.get(spec)
        out.append(rec)
    return out


def _names(rec):
    en, ar = text(rec.get("name_en"), 200), text(rec.get("name_ar"), 200)
    if en and not ar and arabic_ratio(en) > 0.6:
        ar = en
    if ar and not en:
        en = ar
    if en and not ar:
        ar = en
    return en, ar


def prepare(src, mapping, options=None):
    """Read the old database and check everything → Plan (nothing written)."""
    o = dict(DEFAULT_OPTIONS)
    o.update(options or {})
    plan = Plan()
    plan.source = getattr(src, "name", "")
    from modules.product_lookup import norm_code

    # products
    seen_code, seen_bc, by_key = {}, {}, {}
    if mapping.get("products"):
        for i, r in enumerate(_read(src, mapping["products"]), 1):
            code = text(r.get("code"), 50) or text(r.get("key"), 50)
            en, ar = _names(r)
            ref = code or ("row %d" % i)
            if not code and not en:
                plan.add("error", "products", ref, "ITEM_EMPTY", "no code and no name — skipped")
                continue
            if not code:
                code = "IMP%05d" % i
                plan.add("warning", "products", en, "ITEM_NO_CODE", "no code — given %s" % code)
            if not en:
                en = ar = code
                plan.add("warning", "products", code, "ITEM_NO_NAME", "no name — the code is used")
            nk = norm_code(code)
            if nk in seen_code:
                new = "%s-%d" % (code[:46], 2)
                n2 = 2
                while norm_code(new) in seen_code:
                    n2 += 1
                    new = "%s-%d" % (code[:46], n2)
                plan.add("warning", "products", code, "ITEM_DUP_CODE",
                         "same code as another item — this one becomes %s" % new)
                code, nk = new, norm_code(new)
            seen_code[nk] = code
            bc, w = clean_barcode(r.get("barcode"))
            if not bc and o.get("code_as_barcode", True) and code.isdigit() and len(code) in (8, 12, 13, 14):
                bc, w = code, ""            # the scanned code (e.g. RMS Item Lookup Code)
            if w:
                plan.add("warning", "products", code, "BARCODE_BAD_CHECKDIGIT", "barcode %s: %s" % (bc, w))
            if bc:
                if bc in seen_bc and seen_bc[bc] != code:
                    plan.add("error", "products", code, "BARCODE_DUP",
                             "barcode %s already belongs to %s — not given to this item" % (bc, seen_bc[bc]))
                    bc = ""
                else:
                    seen_bc[bc] = code
            vc, w = vat_code(r.get("vat")) if "vat" in mapping["products"]["fields"] else (None, "")
            if w:
                plan.add("warning", "products", code, "VAT_UNKNOWN", w)
            vc = vc or o["default_vat"]
            price = to_dec(r.get("price"))
            cost = to_dec(r.get("cost"))
            if price is None or price < 0:
                if "price" in mapping["products"]["fields"]:
                    plan.add("warning", "products", code, "PRICE_MISSING", "no sell price — 0.00")
                price = Decimal(0)
            if not o["prices_include_vat"] and vc == "S":
                price = price * Decimal("1.15")
            if cost is None or cost < 0:
                cost = Decimal(0)
            qty = to_dec(r.get("qty"), Decimal(0)) or Decimal(0)
            if qty < 0:
                plan.add("warning", "products", code, "STOCK_NEGATIVE",
                         "stock %s is below zero — opening stock 0, please count it" % qty)
                qty = Decimal(0)
            plan.records["products"].append({
                "key": text(r.get("key")), "code": code, "name_en": en, "name_ar": ar,
                "barcode": bc, "category": text(r.get("category"), 100),
                "unit": text(r.get("unit"), 50) or o["default_unit"],
                "price": money(price), "cost": cost.quantize(Decimal("0.0001"), ROUND_HALF_UP),
                "vat": vc, "qty": qty.quantize(Decimal("0.0001"), ROUND_HALF_UP),
                "reorder": to_dec(r.get("reorder"), Decimal(0)) or Decimal(0),
                "active": not truthy(r.get("inactive"))})
            if r.get("key") not in (None, ""):
                k = r.get("key")
                by_key[str(int(k)) if isinstance(k, float) and k.is_integer() else str(k).strip()] = code
            by_key[str(code)] = code

    # extra barcodes
    if mapping.get("barcodes"):
        main_bc = {r["code"]: r["barcode"] for r in plan.records["products"]}
        for r in _read(src, mapping["barcodes"]):
            item = r.get("item")
            k = str(int(item)) if isinstance(item, float) and item.is_integer() else text(item)
            code = by_key.get(k)
            bc, w = clean_barcode(r.get("barcode"))
            if not bc:
                continue
            if not code:
                plan.add("warning", "barcodes", bc, "BARCODE_NO_ITEM", "its product (%s) was not found" % k)
                continue
            if bc == main_bc.get(code):
                continue
            if bc in seen_bc and seen_bc[bc] != code:
                plan.add("error", "barcodes", bc, "BARCODE_DUP",
                         "already the barcode of %s — skipped" % seen_bc[bc])
                continue
            if bc in seen_bc:
                continue
            if w:
                plan.add("warning", "barcodes", bc, "BARCODE_BAD_CHECKDIGIT", w)
            if norm_code(bc) in seen_code and seen_code[norm_code(bc)] != code:
                plan.add("warning", "barcodes", bc, "BARCODE_IS_A_CODE",
                         "the same as product code %s — skipped" % seen_code[norm_code(bc)])
                continue
            seen_bc[bc] = code
            plan.records["barcodes"].append({"code": code, "barcode": bc})

    # customers / suppliers
    for ent, prefix in (("customers", "C"), ("suppliers", "S")):
        if not mapping.get(ent):
            continue
        seen = set()
        for i, r in enumerate(_read(src, mapping[ent]), 1):
            en, ar = _names(r)
            code = text(r.get("code"), 20)
            if not en:
                if code:
                    plan.add("warning", ent, code, "PARTY_NO_NAME", "no name — skipped")
                continue
            if not code:
                code = "%s%05d" % (prefix, i)
            if code.upper() in seen:
                plan.add("warning", ent, code, "PARTY_DUP_CODE", "same code twice — the second is %s-2" % code)
                code = (code[:17] + "-2")
            seen.add(code.upper())
            vat_raw = text(r.get("vat_no"))
            vno = clean_vat_no(vat_raw)
            if vat_raw and not vno:
                plan.add("warning", ent, code, "VAT_NO_INVALID",
                         "VAT number '%s' is not 15 digits starting and ending with 3 — left empty" % vat_raw[:20])
            bal = money(r.get("balance")) if o["import_balances"] else Decimal("0.00")
            plan.records[ent].append({
                "code": code, "name_en": en, "name_ar": ar, "phone": clean_phone(r.get("phone")),
                "email": text(r.get("email"), 100), "vat_no": vno, "address": text(r.get("address"), 500),
                "city": text(r.get("city"), 100), "credit_limit": money(r.get("credit_limit")),
                "balance": bal})
    # suppliers kept as minus amounts in the old program (what we owe = credit)
    sup = [r for r in plan.records["suppliers"] if r["balance"]]
    if sup and sum(1 for r in sup if r["balance"] < 0) >= 0.7 * len(sup):
        for r in plan.records["suppliers"]:
            r["balance"] = -r["balance"]
        plan.add("warning", "suppliers", "all", "SUPPLIER_SIGN",
                 "the old program keeps what we owe as minus amounts — turned into plus (we owe them)")
    return plan


DEFAULT_OPTIONS = {
    "prices_include_vat": True,     # Saudi shelf prices include VAT
    "default_vat": "S",
    "default_unit": "PCs",
    "import_stock": True,
    "import_balances": True,
    "opening_date": "",             # '' = keep DayBill's opening date
}


# ── what will happen in the DayBill database ────────────────
def check_target(plan):
    """Compare with the DayBill database `db` is on (read only) →
    {"new": n, "update": n, "customers_update": n, "suppliers_update": n} and
    adds warnings for barcodes DayBill already uses for another product."""
    from config.database import db
    from modules.product_lookup import norm_code
    out = {"new": 0, "update": 0, "customers_update": 0, "suppliers_update": 0}
    codes = {norm_code(r["product_code"]): r["product_code"] for r in
             (db.fetchall("SELECT product_code FROM products") or [])}
    used_bc = {}
    for sql in ("SELECT p.product_code, u.barcode FROM product_units u JOIN products p ON "
                "p.product_id=u.product_id WHERE ISNULL(u.barcode,'')<>''",
                "SELECT p.product_code, b.barcode FROM product_unit_barcodes b JOIN products p ON "
                "p.product_id=b.product_id"):
        try:
            for r in db.fetchall(sql) or []:
                used_bc[str(r["barcode"]).strip()] = r["product_code"]
        except Exception:
            pass
    for r in plan.records["products"]:
        if norm_code(r["code"]) in codes:
            out["update"] += 1
        else:
            out["new"] += 1
        for bc in [r["barcode"]] + [x["barcode"] for x in plan.records["barcodes"] if x["code"] == r["code"]]:
            own = used_bc.get(bc)
            if bc and own and norm_code(own) != norm_code(r["code"]):
                plan.add("warning", "products", r["code"], "BARCODE_USED_IN_DAYBILL",
                         "barcode %s is already %s's in DayBill — it will not be added" % (bc, own))
        own = used_bc.get(r["code"])
        if own and norm_code(own) != norm_code(r["code"]):
            plan.add("warning", "products", r["code"], "CODE_IS_DAYBILL_BARCODE",
                     "this code is already the barcode of %s in DayBill" % own)
    for ent, tbl, col in (("customers", "customers", "customer"), ("suppliers", "suppliers", "supplier")):
        have = {str(r["c"]).upper() for r in
                (db.fetchall("SELECT %s_code AS c FROM %s" % (col, tbl)) or [])}
        out[ent + "_update"] = sum(1 for r in plan.records[ent] if r["code"].upper() in have)
    return out


# ── writing into DayBill ────────────────────────────────────
def apply(plan, options=None, progress=None, operator=""):
    """Write the plan into the DayBill database `db` is connected to.
    → {"inserted":…, "updated":…, "barcodes":…, "customers":…, "suppliers":…,
       "errors":[…], "equity":…, "log": path}"""
    from config.database import db
    from modules import products_import as PI, opening_balances as OB
    from modules.product_lookup import barcode_owner
    o = dict(DEFAULT_OPTIONS)
    o.update(options or {})
    say = progress or (lambda *_a: None)
    res = {"inserted": 0, "updated": 0, "barcodes": 0, "customers": 0, "suppliers": 0,
           "stock_lines": 0, "errors": []}
    if o.get("opening_date"):
        OB.set_opening_date(o["opening_date"])

    # categories (made when missing)
    cats = {str(r["category_name_en"]).strip().lower(): r["category_id"] for r in
            (db.fetchall("SELECT category_id, category_name_en FROM product_categories") or [])}
    for name in sorted({r["category"] for r in plan.records["products"] if r["category"]}):
        if name.lower() not in cats:
            db.execute("INSERT INTO product_categories (category_name_en, category_name_ar, is_active) "
                       "VALUES (?,?,1)", (name[:100], name[:100]))
            cats[name.lower()] = True
            res.setdefault("categories", 0)
            res["categories"] = res.get("categories", 0) + 1

    # products — the same code as the Excel import (upsert by code,
    # opening stock through the stock card and the books)
    prods = plan.records["products"]
    rows = []
    for r in prods:
        rows.append({
            "product_code": r["code"], "product_name_en": r["name_en"], "product_name_ar": r["name_ar"],
            "product_type": "product", "unit_price": float(r["price"]),
            "purchase_price": float(r["cost"]), "currency": "SAR",
            "unit_of_measure_en": r["unit"], "unit_of_measure_ar": r["unit"],
            "vat_code": r["vat"], "category_name": r["category"], "barcode": r["barcode"] or None,
            "track_inventory": 1,
            "stock_quantity": (float(r["qty"]) if o["import_stock"] else None),
            "reorder_level": float(r["reorder"]), "is_active": 1 if r["active"] else 0,
            "list_in_sales": 1, "list_in_purchase": 1})
    step = 200
    for i in range(0, len(rows), step):
        say("Products %d–%d of %d …" % (i + 1, min(i + step, len(rows)), len(rows)))
        ins, upd, errs = PI.import_rows(rows[i:i + step])
        res["inserted"] += ins
        res["updated"] += upd
        res["errors"] += errs
    if o["import_stock"]:
        res["stock_lines"] = sum(1 for r in prods if r["qty"] > 0)

    # extra barcodes (on the product's base unit)
    if plan.records["barcodes"]:
        say("Extra barcodes …")
        pid_by_code = {r["product_code"]: r["product_id"] for r in
                       (db.fetchall("SELECT product_id, product_code FROM products") or [])}
        for r in plan.records["barcodes"]:
            pid = pid_by_code.get(r["code"])
            if not pid or barcode_owner(r["barcode"]):
                continue
            unit = db.fetchone("SELECT unit_id FROM product_units WHERE product_id=? "
                               "ORDER BY conversion_factor, unit_id", (pid,))
            if not unit:
                p = db.fetchone("SELECT unit_of_measure_en, unit_price, purchase_price FROM products "
                                "WHERE product_id=?", (pid,)) or {}
                db.execute("INSERT INTO product_units (product_id, unit_name_en, conversion_factor, "
                           "selling_price, purchase_price, is_default, is_sales_unit, "
                           "is_purchase_unit, is_active) VALUES (?,?,1,?,?,1,1,1,1)",
                           (pid, p.get("unit_of_measure_en") or "PCs", p.get("unit_price") or 0,
                            p.get("purchase_price") or 0))
                unit = db.fetchone("SELECT unit_id FROM product_units WHERE product_id=? "
                                   "ORDER BY unit_id DESC", (pid,))
            try:
                db.execute("INSERT INTO product_unit_barcodes (product_id, unit_id, barcode, is_active) "
                           "VALUES (?,?,?,1)", (pid, unit["unit_id"], r["barcode"]))
                res["barcodes"] += 1
            except Exception as e:
                res["errors"].append("Barcode %s: %s" % (r["barcode"], str(e)[:80]))

    # customers / suppliers — upsert by code, opening balance re-posted
    for ent, tbl, col, ptype in (("customers", "customers", "customer", "customer"),
                                 ("suppliers", "suppliers", "supplier", "supplier")):
        recs = plan.records[ent]
        for n, r in enumerate(recs, 1):
            if n % 100 == 1:
                say("%s %d of %d …" % (ENTITY_TITLES[ent], n, len(recs)))
            try:
                pid = db.execute_scalar("SELECT %s_id FROM %s WHERE %s_code=?" % (col, tbl, col), (r["code"],))
                vals = {"%s_name_en" % col: r["name_en"], "%s_name_ar" % col: r["name_ar"],
                        "phone": r["phone"] or None, "email": r["email"] or None,
                        "vat_registration_no": r["vat_no"] or None, "address_en": r["address"] or None,
                        "city_en": r["city"] or None}
                if ent == "customers":
                    vals["credit_limit"] = float(r["credit_limit"])
                    vals["customer_type"] = "B2B" if r["vat_no"] else "B2C"
                if pid:
                    db.execute("UPDATE %s SET %s, updated_at=GETDATE() WHERE %s_id=?"
                               % (tbl, ", ".join("%s=?" % k for k in vals), col),
                               tuple(vals.values()) + (pid,))
                else:
                    vals["%s_code" % col] = r["code"]
                    vals["is_active"] = 1
                    db.execute("INSERT INTO %s (%s) VALUES (%s)" % (tbl, ", ".join(vals),
                                                                    ", ".join("?" * len(vals))),
                               tuple(vals.values()))
                    pid = db.execute_scalar("SELECT %s_id FROM %s WHERE %s_code=?" % (col, tbl, col),
                                            (r["code"],))
                res[ent] += 1
                if o["import_balances"]:
                    OB.set_party_opening(ptype, pid, float(r["balance"]))
            except Exception as e:
                res["errors"].append("%s %s: %s" % (ENTITY_TITLES[ent][:-1], r["code"], str(e)[:100]))
    res["equity"] = OB.equity_balance()
    res["log"] = write_log(plan, res, o, operator)
    say("Done.")
    return res


def write_log(plan, res, options, operator=""):
    try:
        from config.paths import log_file
        path = log_file("dbtool_%s.txt" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    except Exception:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "dbtool_%s.txt" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    c = plan.counts()
    lines = ["DayBill Database Tool — conversion log",
             "Date: %s" % datetime.now().strftime("%Y-%m-%d %H:%M"),
             "Done by: %s (confirmed: owner of the data or authorised by the owner)" % (operator or "-"),
             "From: %s (%s) — read only, not changed" % (plan.source, plan.program or "-"),
             "Options: %s" % json.dumps({k: v for k, v in options.items()}, default=str),
             "",
             "Products new %d, updated %d · extra barcodes %d · customers %d · suppliers %d"
             % (res.get("inserted", 0), res.get("updated", 0), res.get("barcodes", 0),
                res.get("customers", 0), res.get("suppliers", 0)),
             "Stock value %.2f · receivable %.2f · payable %.2f · Opening Balance Equity %.2f"
             % (c["stock_value"], c["receivable"], c["payable"], res.get("equity", 0) or 0),
             "", "Problems found before converting:"]
    lines += ["  %s | %s | %s | %s | %s" % i.row() for i in plan.issues] or ["  none"]
    lines += ["", "Errors while writing:"] + (["  " + e for e in res.get("errors", [])] or ["  none"])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


# ── the old program's users (password help) ─────────────────
USER_COLS = ["username", "user_name", "userid", "login", "loginname", "logon", "usr", "user", "name",
             "cashiername", "number", "اسم المستخدم", "المستخدم"]
PASS_COLS = ["password", "passwd", "pwd", "pass", "userpassword", "passwordhash", "password_hash",
             "pin", "secret", "كلمه المرور", "كلمه السر", "الرقم السري"]


def find_user_tables(shape):
    """[(table, user_col, pass_col)] — tables that hold sign-in details."""
    out = []
    for t in shape.tables:
        cols = shape.colnames(t)
        pc = max(((name_score(c, PASS_COLS), c) for c in cols), default=(0, None))
        if pc[0] < 0.75:
            continue
        uc = max(((name_score(c, USER_COLS), c) for c in cols if c != pc[1]), default=(0, None))
        if uc[0] < 0.6:
            continue
        out.append((t, uc[1], pc[1]))
    return out


def hash_kind(v):
    """What a stored password looks like (for information, never cracked)."""
    s = str(v or "")
    if not s:
        return "empty"
    if re.match(r"^\$2[aby]\$\d\d\$", s):
        return "bcrypt"
    if s.startswith("$argon2"):
        return "argon2 (can't be set here)"
    if s.startswith("AQAAAA"):
        return "ASP.NET Identity (can't be set here)"
    if re.match(r"^[0-9a-fA-F]{32}$", s):
        return "md5"
    if re.match(r"^[0-9a-fA-F]{40}$", s):
        return "sha1"
    if re.match(r"^[0-9a-fA-F]{64}$", s):
        return "sha256"
    if len(s) >= 16 and len(s) % 4 == 0 and re.match(r"^[A-Za-z0-9+/]+=*$", s):
        return "encoded (can't be set here)"
    if s.upper() == "RESET":
        return "reset"
    return "plain text?"


def new_password_value(kind, old, new):
    """The value to store for `new`, in the same format as `old`."""
    if kind == "bcrypt":
        import bcrypt
        pre = str(old)[:4]                       # $2a$ / $2b$ / $2y$
        h = bcrypt.hashpw(new.encode("utf-8"), bcrypt.gensalt(10)).decode()
        return pre + h[4:]
    if kind in ("md5", "sha1", "sha256"):
        h = getattr(hashlib, kind)(new.encode("utf-8")).hexdigest()
        return h.upper() if str(old).isupper() else h
    if kind in ("plain text?", "empty", "reset"):
        return new
    raise ValueError("This password format can't be set safely: %s" % kind)
