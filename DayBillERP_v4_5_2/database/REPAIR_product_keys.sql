-- ============================================================
-- REPAIR: ensure products has a PRIMARY KEY on product_id
-- Run this in SSMS against DayBillERP, then re-run
-- inventory_units_patch.sql
-- ============================================================
USE DayBillERP;
GO

-- 1) Show whether products currently has a primary key
PRINT '--- Checking products primary key ---';
SELECT kc.name AS pk_name
FROM sys.key_constraints kc
WHERE kc.parent_object_id = OBJECT_ID('products') AND kc.type = 'PK';
GO

-- 2) If there is NO primary key on products, add one on product_id
IF NOT EXISTS (
    SELECT 1 FROM sys.key_constraints
    WHERE parent_object_id = OBJECT_ID('products') AND type = 'PK'
)
BEGIN
    PRINT 'No PK found on products -> adding PRIMARY KEY on product_id';
    -- product_id must be NOT NULL to be a primary key
    ALTER TABLE products ALTER COLUMN product_id INT NOT NULL;
    ALTER TABLE products ADD CONSTRAINT PK_products PRIMARY KEY (product_id);
    PRINT 'Primary key added.';
END
ELSE
    PRINT 'products already has a primary key - nothing to do.';
GO

-- 3) Confirm
PRINT '--- After repair ---';
SELECT kc.name AS pk_name, c.name AS column_name
FROM sys.key_constraints kc
JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE kc.parent_object_id = OBJECT_ID('products') AND kc.type = 'PK';
GO
