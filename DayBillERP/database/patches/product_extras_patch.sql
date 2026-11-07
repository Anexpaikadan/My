-- ============================================================
-- DayBill ERP - Product Brands, Barcode Type/Default, Images
-- ------------------------------------------------------------
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- ── Brands ──────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='product_brands')
CREATE TABLE product_brands (
    brand_id       INT IDENTITY(1,1) PRIMARY KEY,
    brand_name_en  NVARCHAR(80) NOT NULL,
    brand_name_ar  NVARCHAR(80) NULL,
    is_active      BIT DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);
GO

IF COL_LENGTH('products','brand_id') IS NULL
    ALTER TABLE products ADD brand_id INT NULL;
GO

-- ── Barcode type + default flag (per-unit multi-barcode) ─────
IF COL_LENGTH('product_unit_barcodes','barcode_type') IS NULL
    ALTER TABLE product_unit_barcodes ADD barcode_type NVARCHAR(15) DEFAULT 'EAN-13';
GO
IF COL_LENGTH('product_unit_barcodes','is_default') IS NULL
    ALTER TABLE product_unit_barcodes ADD is_default BIT DEFAULT 0;
GO
-- make the first barcode of each unit the default, if none is set yet
IF EXISTS (SELECT 1 FROM product_unit_barcodes WHERE is_default=1)
    PRINT 'Default barcodes already set.';
ELSE
BEGIN
    ;WITH first_bc AS (
        SELECT barcode_id, ROW_NUMBER() OVER (PARTITION BY unit_id ORDER BY barcode_id) AS rn
        FROM product_unit_barcodes
    )
    UPDATE b SET b.is_default = 1
    FROM product_unit_barcodes b
    JOIN first_bc f ON f.barcode_id = b.barcode_id AND f.rn = 1;
END
GO

-- ── Per-product accounting overrides (optional; blank = use Default Accounts) ──
IF COL_LENGTH('products','sales_account_id') IS NULL
    ALTER TABLE products ADD sales_account_id INT NULL;
GO
IF COL_LENGTH('products','purchase_account_id') IS NULL
    ALTER TABLE products ADD purchase_account_id INT NULL;
GO
IF COL_LENGTH('products','inventory_account_id') IS NULL
    ALTER TABLE products ADD inventory_account_id INT NULL;
GO
IF COL_LENGTH('products','tax_account_id') IS NULL
    ALTER TABLE products ADD tax_account_id INT NULL;
GO

-- ── Multiple product images ───────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='product_images')
CREATE TABLE product_images (
    image_id     INT IDENTITY(1,1) PRIMARY KEY,
    product_id   INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    image_path   NVARCHAR(400) NOT NULL,
    is_default   BIT DEFAULT 0,
    sort_order   INT DEFAULT 0,
    created_at   DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_product_images_product')
    CREATE INDEX IX_product_images_product ON product_images(product_id);
GO

PRINT '✅ Product brand/barcode/accounting/image patch applied.';
GO
