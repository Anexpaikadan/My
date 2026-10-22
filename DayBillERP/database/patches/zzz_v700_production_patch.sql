-- ============================================================
-- DayBill ERP v7.0 — Production (manufacturing)
--   production_entries   one production run: the product made, how
--                        many, status (draft / confirmed / cancelled)
--                        and what it cost (materials + labour +
--                        overhead = total, cost of one unit)
--   production_lines     the materials of a run: planned (from the
--                        bill of materials) and really used, unit,
--                        cost each, line cost
--   account 5250         Production Labour & Overheads Applied — the
--                        credit side of labour and overhead put into
--                        the finished goods' cost
--   journal voucher type PRD (Production)
-- Confirming an entry moves the stock and posts the journal
-- (modules/production.py); a draft moves nothing.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('production_entries','U') IS NULL
CREATE TABLE production_entries (
    entry_id          INT IDENTITY(1,1) PRIMARY KEY,
    entry_number      NVARCHAR(30) NOT NULL UNIQUE,
    entry_date        DATE NOT NULL,
    product_id        INT NOT NULL,                 -- the finished product made
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    bom_id            INT NULL,                     -- the bill of materials used
    quantity          DECIMAL(18,4) NOT NULL DEFAULT 0,   -- made, in unit_name
    unit_name         NVARCHAR(50) NULL,
    unit_factor       DECIMAL(18,6) NOT NULL DEFAULT 1,   -- base units in one unit_name
    qty_base          DECIMAL(18,4) NOT NULL DEFAULT 0,   -- made, in base units
    entry_status      NVARCHAR(20) NOT NULL DEFAULT 'draft',
    material_cost     DECIMAL(18,2) NOT NULL DEFAULT 0,
    labour_cost       DECIMAL(18,2) NOT NULL DEFAULT 0,
    overhead_cost     DECIMAL(18,2) NOT NULL DEFAULT 0,
    total_cost        DECIMAL(18,2) NOT NULL DEFAULT 0,
    unit_cost         DECIMAL(18,6) NOT NULL DEFAULT 0,   -- cost of one unit_name
    branch_id         INT NULL,
    counter_id        INT NULL,
    notes             NVARCHAR(500) NULL,
    -- what confirming did to the finished product's average cost, so
    -- cancel / edit can put it back exactly
    fg_avg_before     DECIMAL(18,4) NULL,
    fg_avg_after      DECIMAL(18,4) NULL,
    fg_stock_after    DECIMAL(18,4) NULL,
    created_by        INT NULL,
    created_at        DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at        DATETIME NULL,
    confirmed_at      DATETIME NULL,
    cancelled_at      DATETIME NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_entries_date')
    CREATE INDEX IX_production_entries_date ON production_entries(entry_date, entry_status);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_entries_product')
    CREATE INDEX IX_production_entries_product ON production_entries(product_id);
GO

IF OBJECT_ID('production_lines','U') IS NULL
CREATE TABLE production_lines (
    line_id           INT IDENTITY(1,1) PRIMARY KEY,
    entry_id          INT NOT NULL REFERENCES production_entries(entry_id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    component_id      INT NOT NULL,                 -- the material
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    qty_planned       DECIMAL(18,4) NOT NULL DEFAULT 0,   -- from the bill of materials
    qty_used          DECIMAL(18,4) NOT NULL DEFAULT 0,   -- really used (can differ)
    unit_name         NVARCHAR(50) NULL,
    unit_factor       DECIMAL(18,6) NOT NULL DEFAULT 1,
    is_stock          BIT NOT NULL DEFAULT 1,       -- 0 = a service: cost only, no stock
    cost_each         DECIMAL(18,6) NOT NULL DEFAULT 0,   -- one unit_name, at its average cost
    line_cost         DECIMAL(18,2) NOT NULL DEFAULT 0,
    notes             NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_lines_entry')
    CREATE INDEX IX_production_lines_entry ON production_lines(entry_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_lines_component')
    CREATE INDEX IX_production_lines_component ON production_lines(component_id);
GO

-- the account labour + overhead are applied to (only added when missing)
IF OBJECT_ID('accounts','U') IS NOT NULL
BEGIN
    DECLARE @p INT = (SELECT account_id FROM accounts WHERE account_code='5000');
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5250')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5250', N'Production Labour & Overheads Applied',
                N'تكاليف العمالة والمصاريف المحملة على الإنتاج', 'expense', @p);
END
GO
