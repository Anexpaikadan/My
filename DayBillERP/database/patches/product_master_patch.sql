-- ============================================================
-- DayBill ERP - Product Master extra columns
-- Adds pricing / inventory-level / notes fields. Safe to re-run.
-- ============================================================

IF COL_LENGTH('products','purchase_price') IS NULL
    ALTER TABLE products ADD purchase_price DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','wholesale_price') IS NULL
    ALTER TABLE products ADD wholesale_price DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','last_purchase_cost') IS NULL
    ALTER TABLE products ADD last_purchase_cost DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','average_cost') IS NULL
    ALTER TABLE products ADD average_cost DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','min_stock') IS NULL
    ALTER TABLE products ADD min_stock DECIMAL(18,3) DEFAULT 0;
IF COL_LENGTH('products','max_stock') IS NULL
    ALTER TABLE products ADD max_stock DECIMAL(18,3) DEFAULT 0;
IF COL_LENGTH('products','reorder_quantity') IS NULL
    ALTER TABLE products ADD reorder_quantity DECIMAL(18,3) DEFAULT 0;
IF COL_LENGTH('products','storage_location') IS NULL
    ALTER TABLE products ADD storage_location NVARCHAR(100) NULL;
IF COL_LENGTH('products','internal_notes') IS NULL
    ALTER TABLE products ADD internal_notes NVARCHAR(500) NULL;
IF COL_LENGTH('products','sales_notes') IS NULL
    ALTER TABLE products ADD sales_notes NVARCHAR(500) NULL;
IF COL_LENGTH('products','purchase_notes') IS NULL
    ALTER TABLE products ADD purchase_notes NVARCHAR(500) NULL;
PRINT 'Product master extra columns ready.';
