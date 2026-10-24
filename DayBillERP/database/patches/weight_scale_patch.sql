-- ============================================================
-- DayBill ERP - Weight Scale support for products
-- Adds fields for items sold by weight (e.g. vegetables, meat,
-- sweets sold per kg) and for scale-printed barcodes.
-- Run anytime after the core schema.
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='is_weighed')
    ALTER TABLE products ADD is_weighed BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='weight_unit')
    ALTER TABLE products ADD weight_unit NVARCHAR(10) DEFAULT 'kg';
GO
-- Scale barcodes embed a PLU code that the scale prints onto the label.
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='scale_plu')
    ALTER TABLE products ADD scale_plu NVARCHAR(20) NULL;
GO
PRINT 'Weight scale columns ready.';
GO
