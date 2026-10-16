# ============================================================
# DayBill ERP - Software & Database Update Engine
# One-click database updates. Tracks which patches are applied
# so updates are safe to run repeatedly.
# ============================================================

import os
import re

try:                                    # one version for the whole app (config/version.py)
    from config.version import VERSION as APP_VERSION
except Exception:
    APP_VERSION = "6.9.2"

# Ordered list of database patches shipped with the app.
# (filename relative to project root, human description, version)
# NOTE: INSTALL_DayBillERP_AllInOne.sql is the full build, NOT a patch.
# It must never be re-applied here — doing so re-runs CREATE/queries
# against an existing DB and fails. Only incremental patches belong below.
PATCHES = [
    ("database/zatca_phase2_patch.sql",        "ZATCA Phase 2 — XML, UUID, crypto stamp", "1.1.0"),
    ("database/accounting_payroll_patch.sql",  "Accounting & Payroll — journals, GOSI, EOS", "1.2.0"),
    ("database/inventory_units_patch.sql",     "Inventory & Multi-Units — stock, barcodes", "1.3.0"),
    ("database/search_listing_patch.sql",      "Smart search & sales/purchase listing flags", "1.4.0"),
    ("database/multi_barcode_patch.sql",       "Multiple barcodes per unit", "1.4.1"),
    ("database/weight_scale_patch.sql",        "Weight scale items (sold per kg)", "1.4.1"),
    ("database/user_roles_patch.sql",          "User roles — Manager & Cashier", "1.5.0"),
    ("database/user_rights_patch.sql",          "Per-user rights — Master/Reports/Edit/Delete", "1.6.0"),
    ("database/report_designer_patch.sql",      "Report Designer — templates, themes, printer", "1.7.0"),
    ("database/barcode_designer_patch.sql",      "Barcode Designer — templates, sequences, labels", "1.7.0"),
    ("database/returns_patch.sql",               "Sales & Purchase Return tables", "1.9.2"),
    ("database/product_master_patch.sql",        "Product master extra columns", "2.0.1"),
    ("database/party_ledger_patch.sql",          "Party Ledgers + Accounting Integration", "1.7.0"),
]

# What changed in each version (shown in the Updates panel)
CHANGELOG = [
    ("6.9.2", ["⭐ Loyalty points: customers earn on every bill and spend points as a discount "
               "(Sales Invoice ▸ ⭐ Pts box, POS ▸ ⭐ Points / F10); Customers ▸ ⭐ Points shows "
               "the history and gives / takes points; Report Center ▸ ⭐ Loyalty Points. "
               "Switch on in Settings ▸ Customer",
               "🧾 VAT the ZATCA way on every bill: worked out once per rate on the bill total — "
               "the printed VAT, the books, the e-invoice XML and its QR now always agree "
               "(van sales were up to a few halalas off)",
               "↩ Returning part of a discounted line gives back only that part's discount "
               "(a 1-of-3 return kept the whole line discount and refunded too little)",
               "🌐 The three Tally forms are live: customer registration, supplier "
               "registration, How was your visit?"]),
    ("6.9.1", ["↩ A return put on the customer's / supplier's account now comes off the bill "
               "it was made from: the bill shows Partial / Paid, the Receipt and Payment "
               "windows ask only for what is still owed (older returns are linked once by "
               "the update)",
               "↩ Loading a bill into a return picks the Payment Type for you: credit when the "
               "bill is still open, else money back the way it was paid",
               "✅ Whole trading cycle checked on a real SQL Server: purchase, sale with bill "
               "discount, returns, quotation → invoice, receipt, supplier payment, trial "
               "balance, stock value and all 57 reports"]),
    ("6.9.0", ["📒 Account Ledger / statements: double-click a line to open its transaction; "
               "right-click Open · Edit · Delete · Voucher · New — follows each user's rights",
               "🔗 Every transaction window: New · Edit · Delete · Voucher in its one title line; "
               "Ledger ▸ Connectors shows what each kind of line opens and your rights",
               "🛠 Database Tool: FROM and TO boxes that work, swap, double-click a database; "
               "copy one DayBill company into another",
               "🧹 Clean folders (docs, database/patches, database/tools, extras); one-click "
               "INSTALL.bat (libraries, database, desktop icon)",
               "🩹 New database installer fixed: company row, ZATCA counter column and the "
               "opening-equity account were missing; sqlcmd re-runs work",
               "🩹 Salesman list on the sales invoice, supplier aging with purchase returns",
               "🏢 Several companies on one server: database updates (and the session) stay "
               "on the company's own database — they went to DayBillERP before",
               "🧾 Bill discount saved: spread over the lines before VAT (invoice, journal, "
               "print and ZATCA match the screen); POS round-off the same way",
               "📐 Sales, purchase, return, quotation windows: small header and footer, "
               "much bigger item area"]),
    ("6.8.0", ["Tally-style entry boxes: grey example inside an empty box, one clear border that turns "
               "blue while typing, red * for must-fill boxes, a red note right under a wrong box "
               "(mobile, email, VAT, CR, postal code, IBAN …) that goes away when fixed; Save opens the "
               "page of the first wrong box and puts the cursor in it; Enter moves to the next box",
               "Online forms (Tally): customer registration, supplier registration and a 'How was your "
               "visit?' form. Customers ▸ 🌐 Online forms brings the answers in; 'Review and add' opens "
               "the Customer / Supplier window filled in; same mobile / VAT → linked, not doubled",
               "Feedback: stars, comment and the bill number (QR on the POS receipt); 30-day average "
               "and 1–2 star answers in red; reply on WhatsApp",
               "Settings ▸ Online forms (Tally API key, form links, automatic hourly check, receipt QR); "
               "Settings ▸ System ▸ Tally-style entry boxes"]),
    ("6.7.0", ["Minimum header on Purchase / Return windows: all fields on ONE row (≈ 250 → 90 px "
               "above the item grid), 🔍 next to ▲▼ instead of a Find line; Sales invoice and Quotation "
               "headers tighter",
               "Every window's coloured title strip slimmer (40–48 → 30 px)",
               "Clear edges: page windows, dialogs and pop-ups get a visible 1 px border; page windows a "
               "soft shadow; on Windows dialogs and lists / calendars / messages get a shadow too",
               "Settings ▸ System ▸ 'Compact window headers + clear edges' (on; off = the old look)"]),
    ("6.6.0", ["👔 HR & Payroll by the Saudi Labour Law: overtime = hourly actual wage + 50 % basic "
               "(art. 107), sick-leave pay 30 full / 60 ¾ / 30 unpaid (art. 117), annual leave earned "
               "from the join date and carried on, 2025 leave days (marriage 5, father 3, maternity 12 weeks)",
               "Payroll months: generate again safely, change a line, ① approve → ② pay salaries → ③ pay "
               "GOSI, reopen; loans in the books; WPS / Mudad bank file; payslips PDF / WhatsApp",
               "Final settlement: end-of-service award (arts. 84/85), unused leave, loans taken back, "
               "notice not given (arts. 75–76), art. 77 compensation; unpaid leave over 20 days is not "
               "service (art. 116)",
               "Ramadan hours (6 a day, art. 98) for overtime; probation up to 180 days with an alert; "
               "resignation dates (withdraw 7 days, accepted by law after 30)",
               "Employee documents (Iqama, passport, insurance, contract) with alerts; HR reports",
               "Cleaner HR screens: payroll steps in order, one Print / export menu, settlement breakdown, "
               "IBAN / Iqama checked while typing"]),
    ("6.5.0", ["🩺 ZATCA readiness: do you have to connect (25th wave — sales over 187,500 SAR in "
               "2022–2025 → Phase 2 from 1 Feb 2027), data check (shop details, B2B customer "
               "addresses, VAT numbers, product VAT), and 'How to fix' for every rejected bill",
               "📲 Evening report: English or Arabic, sent as a PDF with its own approved WhatsApp "
               "template (delivered every day); without a template it says it reaches the owner only "
               "inside the 24-hour window; from Day Close a failed send opens WhatsApp instead",
               "📊 WhatsApp Cloud API message count + cost per month (Meta charges every message "
               "since 1 Oct 2026); the 'missing items' list to a supplier opens WhatsApp (free)",
               "AI: Claude Haiku 5.5 for names / spelling (older saved model moved over)",
               "Arabic menu names for Stock Count and Price Updates"]),
    ("6.4.0", ["📤 One-tap supplier orders: reorder plan → saved Purchase Orders → PDF to each "
               "supplier on WhatsApp; 📦 Receive (scan) the goods against the order — missing / "
               "short / extra, tell the supplier, make the Purchase Invoice",
               "🧮 Stock Count with the phone: today's ABC list (A weekly, B monthly, C quarterly), "
               "phones scan, the owner approves (untick = recount), history + accuracy",
               "📈 Price Updates: cost went up → new prices that keep your margin (Box prices too); "
               "shelf labels wait in Price Change Labels",
               "👀 Cashier Watch report: discounts, returns, items removed, bills cleared, deleted "
               "documents, cash short — warnings when one cashier is far above the others",
               "📲 Owner's evening report on WhatsApp (sales vs last week, cash short, best items, "
               "stock + cashier alerts) — automatic at a set time, or Day Close ▸ 📲",
               "☁ Nightly cloud backup into Google Drive / OneDrive / Dropbox (zipped, keeps the "
               "newest N, alert when the last copy is old)"]),
    ("6.3.0", ["Slimmer header: more room for every page (one-line window titles)",
               "AI inventory: stock health score + what to do now, forecast (run-out date), "
               "ABC, expiry that will not sell in time, branch transfers, bought together, "
               "supplier prices, data check — Smart Insights tabs",
               "💬 Ask AI about your stock in plain words (Claude API key)",
               "Claude connector: 12 new inventory tools (36) + 7 ready-made prompts"]),
    ("6.2.1", ["Reports Center: the report groups are on top (each a drop-down with all its "
               "reports) + Find a report — the table now uses the full page width",
               "Cleaner report page: name + Excel / PDF / Print / Columns on one line, one filter "
               "line, totals in one strip",
               "🎨 Theme in the top bar: pick a theme (new: Teal, Graphite, Maroon, Desert Sand) or "
               "your own colour — the whole app changes at once",
               "Fixed: Settings ▸ Theme only changed after a restart"]),
    ("6.2.0", ["Output VAT Register (sales VAT) and Input VAT Register (purchase VAT) — totals "
               "match the VAT Return; Sales / Purchase Register item details; VAT No. and "
               "Discount on every register",
               "Columns tool on every table (reports, entry forms, lists): right-click a heading "
               "or ☰ to hide / show, move, set or fit the width; drag edges and headings; "
               "remembered per table",
               "Excel / PDF / Print / Copy use the columns you see"]),
    ("6.1.0", ["DayBill Database Tool (Start menu, or DayBillERP.exe --dbtool): find the server, "
               "list databases, make a new DayBill database",
               "Convert another program's database into DayBill: products, barcodes, categories, "
               "customers, suppliers, opening stock and balances — Microsoft RMS and SAP Business One "
               "recognised, other programs guessed and checked by you; the old database is only read",
               "Reset passwords: DayBill users, and another program's users in the same format "
               "(backup first, owner confirms)"]),
    ("6.0.2", ["Login ▸ 🔑 Forgot password?: reset by another admin, or a safe SQL query "
               "(database\\tools\\RESET_user_password.sql) — then DayBill asks for a new password",
               "Database Settings ▸ 🔍 Find: finds SQL Server on this PC and the network",
               "🗂 List marks DayBill databases ✓; a wrong database offers to switch to DayBill's",
               "Clear message when the saved SQL password was locked on another PC"]),
    ("6.0.1", ["Restore Database looks inside the backup first: another program's backup is never "
               "put over a database, and a safety copy is saved before any restore",
               "Sign-in says clearly when the database is not a DayBill database (was: 'user_id')",
               "DayBill never runs its updates on another program's database"]),
    ("6.0.0", ["Every save is all-or-nothing (no half-saved bills); passwords and ZATCA keys locked",
               "ZATCA Wave 25: one e-invoicing unit per till, debit notes, 24-hour warning, 700 number",
               "VAT return boxes 2, 4, 8, 9, 14, 15 filled; out-of-scope sales left out",
               "POS: STC Pay / Tabby / Tamara / vouchers, cashier shifts, price lists",
               "Stock per branch, transfers, batches with expiry dates (first expiry first out)",
               "Bank reconciliation, year-end closing entry, GOSI new-system rates, leave & attendance",
               "Suggested purchase order from low stock; one database-update engine",
               "POS keeps selling when the server is briefly gone (bills kept on the till, sent later)"]),
    ("5.8 – 5.26", ["Accounting: opening balances, aging, day report, Excel / PDF on every report",
                    "Windows 11 look, calendar on every date, bigger text, folding menu",
                    "Mobile / PDT scanners and van sales over the internet",
                    "Barcodes for every unit, label printing, invoice designer",
                    "ZATCA Phase 2 easy connect; offers & promotions",
                    "Branches, tills, product key; edit / delete saved bills"]),
    ("1.4.0", ["Smart abbreviation search (\"pe co 25\" → Pepsi Cola 250 ml)",
               "Alias name search across all products",
               "Auto-fill Arabic product name from English",
               "Activate/deactivate products per Sales and per Purchase"]),
    ("1.3.0", ["Multi-units per product (Piece / Box / Carton…)",
               "EAN-13 barcode auto-generation + label printing",
               "Full inventory: stock levels, movements, low-stock alerts",
               "Purchases auto-update stock; sales deduct stock"]),
    ("1.2.0", ["Double-entry accounting: journals, ledger, trial balance",
               "Profit & Loss and Balance Sheet reports",
               "Saudi payroll: GOSI, overtime, loans, end-of-service",
               "WPS bank file + bilingual payslip PDF"]),
    ("1.1.0", ["ZATCA Phase 2 e-invoicing (XML, signing)",
               "VAT return report"]),
    ("1.0.0", ["Initial release: customers, products, sales, purchases, POS",
               "ZATCA Phase 1 QR codes, bilingual invoices"]),
]


def _project_root():
    """Folder that contains main.py / the patches."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def split_sql_batches(sql_text: str) -> list:
    """
    Split a .sql script into batches on lines containing only GO
    (the SSMS batch separator, which pyodbc does not understand).
    """
    parts = re.split(r'(?im)^[ \t]*GO[ \t]*;?[ \t]*$', sql_text)
    return [p.strip() for p in parts if p.strip()]


def ensure_migrations_table(db):
    """Create the tracking table if missing."""
    db.execute(
        "IF OBJECT_ID('schema_migrations','U') IS NULL "
        "CREATE TABLE schema_migrations ("
        "patch_name NVARCHAR(200) PRIMARY KEY, "
        "applied_at DATETIME DEFAULT GETDATE())")


def is_applied(db, patch_name: str) -> bool:
    try:
        n = db.execute_scalar(
            "SELECT COUNT(*) FROM schema_migrations WHERE patch_name=?",
            (patch_name,))
        return bool(n)
    except Exception:
        return False


def _find_patch_file(fname: str):
    """Find a patch file across likely locations; return full path or None."""
    root = _project_root()
    candidates = [
        os.path.join(root, fname),
        os.path.join(root, os.path.basename(fname)),
        os.path.join(root, "database", "patches", os.path.basename(fname)),
        os.path.join(root, "database", os.path.basename(fname)),
        os.path.join(os.getcwd(), fname),
        os.path.join(os.getcwd(), os.path.basename(fname)),
        os.path.join(os.getcwd(), "database", os.path.basename(fname)),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def patch_status(db) -> list:
    """
    Return [{name, description, version, file_exists, applied}] for every patch.
    """
    ensure_migrations_table(db)
    out = []
    for fname, desc, ver in PATCHES:
        path = _find_patch_file(fname)
        out.append({
            "name": fname,
            "description": desc,
            "version": ver,
            "file_exists": (path is not None) or (fname in INLINE_SQL),
            "applied": is_applied(db, fname),
        })
    return out


# Inline SQL fallback for the newest patches, used when the .sql file
# isn't found on disk (e.g. the user copied only the .py files on update).
INLINE_SQL = {
    "database/weight_scale_patch.sql": """
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='is_weighed')
    ALTER TABLE products ADD is_weighed BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='weight_unit')
    ALTER TABLE products ADD weight_unit NVARCHAR(10) DEFAULT 'kg';
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='scale_plu')
    ALTER TABLE products ADD scale_plu NVARCHAR(20) NULL;
GO
""",
    "database/multi_barcode_patch.sql": """
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='product_unit_barcodes')
BEGIN
    CREATE TABLE product_unit_barcodes (
        barcode_id  INT IDENTITY(1,1) PRIMARY KEY,
        unit_id     INT NOT NULL REFERENCES product_units(unit_id) ON DELETE CASCADE,
        product_id  INT NOT NULL REFERENCES products(product_id),
        barcode     NVARCHAR(50) NOT NULL UNIQUE,
        is_active   BIT DEFAULT 1,
        created_at  DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_unit_barcodes_unit ON product_unit_barcodes(unit_id);
    CREATE INDEX IX_unit_barcodes_barcode ON product_unit_barcodes(barcode);
END
GO
""",
    "database/user_roles_patch.sql": """
IF NOT EXISTS (SELECT 1 FROM roles WHERE role_name_en='Manager')
INSERT INTO roles (role_name_en, role_name_ar, can_view_dashboard, can_manage_customers,
    can_manage_products, can_create_invoice, can_approve_invoice, can_view_reports,
    can_manage_users, can_manage_settings, can_zatca_submit)
VALUES ('Manager', N'مدير', 1, 1, 1, 1, 1, 1, 0, 0, 1);
GO
IF NOT EXISTS (SELECT 1 FROM roles WHERE role_name_en='Cashier')
INSERT INTO roles (role_name_en, role_name_ar, can_view_dashboard, can_manage_customers,
    can_manage_products, can_create_invoice, can_approve_invoice, can_view_reports,
    can_manage_users, can_manage_settings, can_zatca_submit)
VALUES ('Cashier', N'كاشير', 1, 0, 0, 1, 0, 0, 0, 0, 0);
GO
""",
    "database/search_listing_patch.sql": """
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='alias_name')
    ALTER TABLE products ADD alias_name NVARCHAR(200) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='list_in_sales')
    ALTER TABLE products ADD list_in_sales BIT DEFAULT 1;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='list_in_purchase')
    ALTER TABLE products ADD list_in_purchase BIT DEFAULT 1;
GO
""",
    "database/user_rights_patch.sql": """
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_master')
    ALTER TABLE users ADD can_master BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_reports')
    ALTER TABLE users ADD can_reports BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_edit')
    ALTER TABLE users ADD can_edit BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_delete')
    ALTER TABLE users ADD can_delete BIT DEFAULT 0;
GO
UPDATE users SET can_master=1, can_reports=1, can_edit=1, can_delete=1 WHERE username='admin';
GO
""",
}


def apply_patch(db, patch_name: str) -> tuple:
    """
    Apply a single patch file. Returns (success, message).
    Special return: ("skip", reason) when the file isn't present —
    older patches may be missing on disk but already applied in the DB,
    so a missing file should NOT fail the whole update run.
    Idempotent: patches use IF NOT EXISTS guards, and 'already exists'
    errors are tolerated so re-running is safe.
    """
    path = _find_patch_file(patch_name)
    if not path:
        # Fall back to embedded SQL for the newest patches so features
        # still install even if the .sql file wasn't copied on update.
        inline = INLINE_SQL.get(patch_name)
        if inline:
            sql = inline
            return _run_sql(db, patch_name, sql)
        return "skip", f"File not on disk: {patch_name} (skipped)"

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sql = f.read()
    except Exception as e:
        return False, f"Cannot read {patch_name}: {e}"
    return _run_sql(db, patch_name, sql)


def _run_sql(db, patch_name: str, sql: str) -> tuple:
    """Execute a SQL script (split on GO), tolerate 'already exists',
    then record the patch as applied. Returns (True, msg) or (False, msg)."""
    from modules.db_migrate import strip_use      # v6.9: never switch company database
    batches = split_sql_batches(strip_use(sql))
    tolerated = ("already an object", "already exists", "there is already",
                 "duplicate", "column names in each table must be unique")
    for batch in batches:
        try:
            db.execute(batch)
        except Exception as e:
            msg = str(e).lower()
            if any(t in msg for t in tolerated):
                continue          # object already there — safe to ignore
            return False, f"Error in {patch_name}: {str(e)[:160]}"

    try:
        ensure_migrations_table(db)
        if not is_applied(db, patch_name):
            db.execute("INSERT INTO schema_migrations (patch_name) VALUES (?)",
                       (patch_name,))
    except Exception:
        pass
    return True, f"Applied {patch_name}"


def apply_all_pending(db) -> dict:
    """
    Apply every patch that hasn't been applied yet (in order).
    Returns {applied: [...], skipped: [...], failed: [(name,msg)...]}.
    A missing patch file is skipped (not failed) so the run continues
    and the genuinely new patches still install.
    """
    ensure_migrations_table(db)
    result = {"applied": [], "skipped": [], "failed": []}
    for fname, desc, ver in PATCHES:
        if is_applied(db, fname):
            result["skipped"].append(fname)
            continue
        ok, msg = apply_patch(db, fname)
        if ok == "skip":
            result["skipped"].append(fname)
            continue
        if ok:
            result["applied"].append(fname)
        else:
            result["failed"].append((fname, msg))
            break    # stop only on a REAL error, keeps DB consistent
    return result


# ── v6.0: ONE update engine ─────────────────────────────────
# DayBill applies database/patches/*_patch.sql at every start (modules/db_migrate).
# The Updates screen now shows and runs exactly that list, so the two
# engines can never disagree. (PATCHES above stays for older callers.)
def _desc_of(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            for line in fh.read(1500).splitlines():
                t = line.strip("-= \t")
                if t.startswith("DayBill ERP"):
                    return t.split(" - ", 1)[-1].strip() or os.path.basename(path)
    except Exception:
        pass
    return os.path.basename(path).replace("_patch.sql", "").replace("_", " ").strip().title()


def _ver_of(path):
    """The app version a patch came with: the old list, else 'v5.21' in its
    first lines, else '—'."""
    name = os.path.basename(path)
    for fname, _desc, ver in PATCHES:
        if os.path.basename(fname) == name:
            return ver
    try:
        import re as _re
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            head = "".join(fh.readline() for _ in range(6))
        m = _re.search(r"\bv(\d+\.\d+(?:\.\d+)?)", head)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "—"


def patch_status(db) -> list:
    import glob
    from modules import db_migrate as M
    try:
        M._ensure_table()
    except Exception:
        pass
    done = M._applied()
    try:
        ensure_migrations_table(db)
        old = {os.path.basename(r["patch_name"]) for r in
               (db.fetchall("SELECT patch_name FROM schema_migrations") or [])}
    except Exception:
        old = set()
    out = []
    for path in M.patch_files():
        name = os.path.basename(path)
        ver = _ver_of(path)
        out.append({"name": name, "description": _desc_of(path), "version": ver,
                    "file_exists": True, "applied": name in done or name in old})
    return out


def apply_all_pending(db) -> dict:
    from modules import db_migrate as M
    before = len(M._applied())
    applied, errors = M.run_pending()
    skipped = max(0, before)
    return {"applied": applied, "skipped": ["(already applied)"] * skipped,
            "failed": [(n, m) for n, m in errors]}


# ── Self-test (pure functions only) ────────────────────────────
if __name__ == "__main__":
    sample = "CREATE TABLE a(id INT);\nGO\nINSERT INTO a VALUES(1);\nGO\n"
    batches = split_sql_batches(sample)
    print("Batches:", batches)
    assert len(batches) == 2
    print("Version:", APP_VERSION)
    print("Patches:", len(PATCHES), "| Changelog versions:", len(CHANGELOG))
    print("Updater OK ✅")
