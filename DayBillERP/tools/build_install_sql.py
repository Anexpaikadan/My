# ============================================================
# Build INSTALL_DayBillERP_AllInOne.sql
# ------------------------------------------------------------
# Concatenates the base setup + every patch in database/patches/ into ONE
# idempotent script for a brand-new installation:
#
#     python tools/build_install_sql.py
#
# Writes  database/INSTALL_DayBillERP_AllInOne.sql
# Order: tools/sql_base/DayBillERP_Full_Setup.sql (schema + seed) first,
# then all database/patches/*_patch.sql alphabetically (each is idempotent),
# with clear section banners and GO separators between files.
# ============================================================

import os, sys, glob
from datetime import datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(BASE, "database", "INSTALL_DayBillERP_AllInOne.sql")
BASE_SETUP = os.path.join(BASE, "tools", "sql_base", "DayBillERP_Full_Setup.sql")

SKIP = {"units_reset_optional.sql",      # destructive — optional by hand
        "REPAIR_product_keys.sql",       # repair tool, not an installer
        "RESET_user_password.sql"}       # by hand only: forgotten password (v6.0.2)


def read(p):
    with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read().rstrip() + "\n"


def main():
    parts = []
    parts.append("""-- ============================================================
-- DayBill ERP — FULL DATABASE INSTALLER  (clean new installation)
-- generated %s  ·  ONE file = the whole database
-- ------------------------------------------------------------
-- WHAT IT MAKES
--   • the DayBillERP database (Arabic collation) and EVERY table,
--     view, procedure and index the app uses
--   • only the starting data a new shop needs:
--       admin user (you set the password at the first sign-in),
--       roles Administrator / Manager / Cashier, chart of accounts,
--       default account mapping, VAT categories (S/Z/E/O 15%%),
--       Cash Customer + Cash Supplier, Main Branch + Counter 1,
--       this year's financial year, invoice / barcode numbering,
--       default print templates and themes
--   • NO sample products, customers, invoices or test data
--   • the company is EMPTY ('Your Company Name', no VAT number):
--     fill it in DayBill ▸ Settings ▸ Company — the first-run
--     wizard opens for that on the first sign-in.
--
-- HOW TO RUN (pick one)
--   A. DayBill login ▸ ⚙ Database Settings ▸ Create New Database…
--      (any database name — runs this file for you)
--   B. SSMS: open this file ▸ Execute (F5). It creates the database
--      DayBillERP itself — no need to create it first.
--   C. sqlcmd -S .\\SQLEXPRESS -E -i database\\INSTALL_DayBillERP_AllInOne.sql
--
-- Safe to run again on an existing DayBill database: tables, indexes
-- and starting data are only added when missing, nothing is deleted.
-- Regenerate after adding patches:  python tools/build_install_sql.py
-- ============================================================

""" % datetime.now().strftime("%Y-%m-%d %H:%M"))

    base_setup = BASE_SETUP
    if not os.path.exists(base_setup):                     # older layout
        base_setup = os.path.join(BASE, "DayBillERP_Full_Setup.sql")
    if os.path.exists(base_setup):
        parts.append("-- ▼▼▼  BASE: DayBillERP_Full_Setup.sql  ▼▼▼\n")
        parts.append(read(base_setup))
        parts.append("\nGO\n\n")

    patch_dir = os.path.join(BASE, "database", "patches")
    for p in sorted(glob.glob(os.path.join(patch_dir, "*_patch.sql"))):
        name = os.path.basename(p)
        if os.path.abspath(p) == os.path.abspath(OUT):
            continue                                       # this installer itself
        if name in SKIP:
            parts.append("-- (skipped optional/repair script: %s)\n\n" % name)
            continue
        parts.append("-- ▼▼▼  PATCH: %s  ▼▼▼\n" % name)
        parts.append(read(p))
        parts.append("\nGO\n\n")

    parts.append("""-- ============================================================
-- FINAL CHECK — what the database has now
-- ============================================================
SET NOCOUNT ON;
DECLARE @t INT = (SELECT COUNT(*) FROM sys.tables);
DECLARE @a INT = (SELECT COUNT(*) FROM accounts);
DECLARE @u INT = (SELECT COUNT(*) FROM users);
DECLARE @p INT = (SELECT COUNT(*) FROM products);
PRINT N'------------------------------------------------------------';
PRINT N'DayBill ERP database ready:  ' + DB_NAME();
PRINT N'  tables            : ' + CAST(@t AS NVARCHAR(10));
PRINT N'  chart of accounts : ' + CAST(@a AS NVARCHAR(10)) + N' accounts';
PRINT N'  users             : ' + CAST(@u AS NVARCHAR(10)) + N'  (admin — set the password at first sign-in)';
PRINT N'  products          : ' + CAST(@p AS NVARCHAR(10));
PRINT N'Next: open DayBill ▸ sign in as admin ▸ Settings ▸ Company.';
PRINT N'------------------------------------------------------------';
GO
""")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print("Wrote", OUT, "(%.0f KB)" % (os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
