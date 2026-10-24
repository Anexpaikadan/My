-- ============================================================
-- DayBill ERP v7.0 — Textiles & Garments: size / colour variants
--   products.variant_parent_id   the style (main product) a size /
--                                colour belongs to (NULL = not a variant)
--   products.variant_size        its size   ('' when the style has no sizes)
--   products.variant_colour      its colour ('' when the style has no colours)
-- Every variant is a normal product (own code, own 5-digit system
-- barcode, own stock), so sales, purchases, POS, stock and reports work
-- as before; these columns only link it to its style.
-- No foreign key on purpose: deleting a style never fails because of
-- its variants (they stay as normal products).
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','variant_parent_id') IS NULL
    EXEC(N'ALTER TABLE products ADD variant_parent_id INT NULL');
GO
IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','variant_size') IS NULL
    EXEC(N'ALTER TABLE products ADD variant_size NVARCHAR(40) NULL');
GO
IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','variant_colour') IS NULL
    EXEC(N'ALTER TABLE products ADD variant_colour NVARCHAR(40) NULL');
GO

-- the variants of a style, fast
IF COL_LENGTH('products','variant_parent_id') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_products_variant_parent'
                   AND object_id = OBJECT_ID('products'))
    EXEC(N'CREATE INDEX IX_products_variant_parent ON products(variant_parent_id)
           INCLUDE (variant_size, variant_colour)');
GO

-- one product per style + size + colour (adding sizes later never
-- makes a second "Shirt - M - Red")
IF COL_LENGTH('products','variant_parent_id') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_products_variant'
                   AND object_id = OBJECT_ID('products'))
    EXEC(N'CREATE UNIQUE INDEX UX_products_variant
           ON products(variant_parent_id, variant_size, variant_colour)
           WHERE variant_parent_id IS NOT NULL');
GO
