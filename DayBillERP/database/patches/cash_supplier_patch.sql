-- ============================================================
-- DayBill ERP - Default "CASH" Walk-in Supplier
-- ------------------------------------------------------------
-- Mirrors the existing Cash Customer (default_accounts_patch.sql
-- Part G): the new-purchase screen auto-selects this supplier for
-- spot/cash purchases so a supplier doesn't have to be picked first.
-- Its ledger points at the master Cash account. Idempotent.
-- ============================================================
USE DayBillERP;
GO

IF EXISTS (SELECT 1 FROM sys.columns
           WHERE object_id=OBJECT_ID('suppliers') AND name='account_id')
BEGIN
    IF NOT EXISTS (SELECT 1 FROM suppliers WHERE supplier_code='CASH')
        INSERT INTO suppliers (supplier_code, supplier_name_en, supplier_name_ar,
            country_code, account_id)
        VALUES ('CASH', 'Cash Supplier', N'مورد نقدي', 'SA',
                (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100'));

    UPDATE suppliers
       SET account_id = (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100')
     WHERE supplier_code='CASH' AND account_id IS NULL;
END
ELSE
BEGIN
    IF NOT EXISTS (SELECT 1 FROM suppliers WHERE supplier_code='CASH')
        INSERT INTO suppliers (supplier_code, supplier_name_en, supplier_name_ar,
            country_code)
        VALUES ('CASH', 'Cash Supplier', N'مورد نقدي', 'SA');
END
GO

PRINT '✅ Cash walk-in supplier ready.';
GO
