-- ============================================================
-- DayBill ERP - v7.16.0: cost centre on purchases, expenses, sales
-- Idempotent. Nothing existing is changed.
-- ============================================================
USE DayBillERP;
GO
IF COL_LENGTH('purchase_invoices','cost_center_id') IS NULL
    ALTER TABLE purchase_invoices ADD cost_center_id INT NULL;
GO
IF COL_LENGTH('expenses','cost_center_id') IS NULL
    ALTER TABLE expenses ADD cost_center_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','cost_center_id') IS NULL
    ALTER TABLE sales_invoices ADD cost_center_id INT NULL;
GO
PRINT 'DayBill v7.16.0 patch applied.';
GO
