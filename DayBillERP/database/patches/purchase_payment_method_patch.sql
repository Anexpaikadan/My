-- ============================================================
-- DayBill ERP - Fix: purchase_invoices missing payment_method
-- ------------------------------------------------------------
-- The Purchase Invoice screen writes a payment_method value, but the
-- column was never added to the table -> every save failed with a
-- "column missing" SQL error. Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('purchase_invoices','payment_method') IS NULL
    ALTER TABLE purchase_invoices ADD payment_method NVARCHAR(20) DEFAULT 'cash';
GO

PRINT '✅ purchase_invoices.payment_method added.';
GO
