-- ============================================================
-- DayBill ERP - POS part-cash / part-card payment (v5.15)
-- ------------------------------------------------------------
-- A POS bill can be paid partly in cash and partly by card.
-- cash_paid / card_paid keep that split so reports can show it
-- (the accounts are posted from the same amounts).
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO
IF COL_LENGTH('sales_invoices','cash_paid') IS NULL
    ALTER TABLE sales_invoices ADD cash_paid DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('sales_invoices','card_paid') IS NULL
    ALTER TABLE sales_invoices ADD card_paid DECIMAL(18,2) NULL;
GO
PRINT '✅ POS cash + card split columns ready.';
GO
