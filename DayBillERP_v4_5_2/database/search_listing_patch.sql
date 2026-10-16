-- ============================================================
-- DayBill ERP - Product Search & Listing Flags Patch
-- Adds alias name + per-channel active flags (sales / purchase)
-- Runs after the base schema (INSTALL_DayBillERP_AllInOne.sql). Safe to re-run.
-- ============================================================

USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='alias_name')
    ALTER TABLE products ADD alias_name NVARCHAR(100) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='list_in_sales')
    ALTER TABLE products ADD list_in_sales BIT DEFAULT 1;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='list_in_purchase')
    ALTER TABLE products ADD list_in_purchase BIT DEFAULT 1;
GO

-- Existing products: list in both channels by default
UPDATE products SET list_in_sales = 1 WHERE list_in_sales IS NULL;
UPDATE products SET list_in_purchase = 1 WHERE list_in_purchase IS NULL;
GO

PRINT '✅ Product search & listing flags patch applied.';
GO
