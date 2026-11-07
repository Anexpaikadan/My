-- ============================================================
-- DayBill ERP - Expenses with VAT + asset purchases (v5.11)
-- ------------------------------------------------------------
-- The Expenses screen can now also record ASSET purchases (shop
-- furniture, equipment, computers, vehicles) with their input VAT,
-- and remembers the supplier, VAT rate and price-includes-VAT choice
-- so an entry can be opened and edited later.
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('expenses','expense_kind') IS NULL
    ALTER TABLE expenses ADD expense_kind NVARCHAR(10) DEFAULT 'expense';
GO
IF COL_LENGTH('expenses','supplier_id') IS NULL
    ALTER TABLE expenses ADD supplier_id INT NULL;
GO
IF COL_LENGTH('expenses','vat_rate') IS NULL
    ALTER TABLE expenses ADD vat_rate DECIMAL(5,2) NULL;
GO
IF COL_LENGTH('expenses','price_incl_vat') IS NULL
    ALTER TABLE expenses ADD price_incl_vat BIT DEFAULT 0;
GO
IF COL_LENGTH('expenses','supplier_vat_no') IS NULL
    ALTER TABLE expenses ADD supplier_vat_no NVARCHAR(20) NULL;
GO

PRINT '✅ expenses: asset purchases + VAT details added.';
GO
