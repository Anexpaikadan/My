-- ============================================================
-- DayBill ERP - Inventory & Multi-Units Schema Patch
-- Runs after the base schema (INSTALL_DayBillERP_AllInOne.sql)
-- Safe to re-run.
-- ============================================================

USE DayBillERP;
GO

-- ── Add purchase price + reorder level to products ───────────
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='purchase_price')
    ALTER TABLE products ADD purchase_price DECIMAL(18,2) DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='reorder_level')
    ALTER TABLE products ADD reorder_level DECIMAL(18,4) DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='stock_quantity')
    ALTER TABLE products ADD stock_quantity DECIMAL(18,4) DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='default_unit_id')
    ALTER TABLE products ADD default_unit_id INT NULL;
GO

-- ── Product Units ─────────────────────────────────────────────
-- Each product can have unlimited units (Piece, Box of 12, Carton of 144…)
-- conversion_factor = how many BASE units make 1 of THIS unit
-- e.g. base=Piece, Box=12 pieces → conversion_factor=12
IF OBJECT_ID('product_units','U') IS NULL
CREATE TABLE product_units (
    unit_id             INT IDENTITY(1,1) PRIMARY KEY,
    product_id          INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    unit_name_en        NVARCHAR(50) NOT NULL,
    unit_name_ar        NVARCHAR(50),
    conversion_factor   DECIMAL(18,6) NOT NULL DEFAULT 1,
    purchase_price      DECIMAL(18,2) DEFAULT 0,
    selling_price       DECIMAL(18,2) DEFAULT 0,
    barcode             NVARCHAR(20),
    is_default          BIT DEFAULT 0,
    is_purchase_unit    BIT DEFAULT 1,
    is_sales_unit       BIT DEFAULT 1,
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE(),
    CONSTRAINT UQ_product_unit_barcode UNIQUE (barcode)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_product_units_product')
    CREATE INDEX IX_product_units_product ON product_units(product_id);
GO

-- ── Inventory Transactions (full ledger) ──────────────────────
IF OBJECT_ID('inventory_transactions','U') IS NULL
CREATE TABLE inventory_transactions (
    txn_id              INT IDENTITY(1,1) PRIMARY KEY,
    product_id          INT NOT NULL REFERENCES products(product_id),
    txn_date            DATE NOT NULL DEFAULT GETDATE(),
    txn_type            NVARCHAR(30) NOT NULL,
    -- Types: opening / purchase / sale / adjustment_in / adjustment_out / return_in / return_out
    reference_type      NVARCHAR(30),          -- purchase_invoice / sales_invoice / manual
    reference_id        INT,
    unit_id             INT REFERENCES product_units(unit_id),
    unit_name           NVARCHAR(50),
    qty_in_units        DECIMAL(18,4) DEFAULT 0,   -- quantity in the referenced unit
    qty_in_base         DECIMAL(18,4) DEFAULT 0,   -- converted to base unit
    qty_out_units       DECIMAL(18,4) DEFAULT 0,
    qty_out_base        DECIMAL(18,4) DEFAULT 0,
    balance_base        DECIMAL(18,4) DEFAULT 0,   -- running balance in base units
    unit_cost           DECIMAL(18,2) DEFAULT 0,   -- cost per base unit at time of txn
    notes               NVARCHAR(300),
    created_at          DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inventory_product')
    CREATE INDEX IX_inventory_product ON inventory_transactions(product_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inventory_date')
    CREATE INDEX IX_inventory_date ON inventory_transactions(txn_date);
GO

PRINT '✅ Inventory & Multi-Units patch applied.';
GO
