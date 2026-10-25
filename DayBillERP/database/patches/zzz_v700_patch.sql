-- ============================================================
-- DayBill ERP v7.0 — countries and business modules
--   company.country_code      SA Saudi Arabia · AE UAE · IN India
--   company.state_code        region / emirate / GST state of the company
--   company.currency_symbol   what prints next to amounts (SAR, AED, ₹ …)
--   company.business_modules  retail,supermarket,restaurant,textiles,production
--   company_options           company settings kept in the company database
--   customers / suppliers .state_code   (GST place of supply, emirate)
--   products.hsn_code         India HSN / SAC code
--   *.place_of_supply         India: the state a bill belongs to
--   vat_categories.tax_kind   std / zero / exempt / nil / oos
--   bom_headers / bom_lines   recipes and bills of materials
-- A database made before v7.0 is a Saudi retail + supermarket company.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','country_code') IS NULL
    EXEC(N'ALTER TABLE company ADD country_code NVARCHAR(2) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','state_code') IS NULL
    EXEC(N'ALTER TABLE company ADD state_code NVARCHAR(10) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','currency_symbol') IS NULL
    EXEC(N'ALTER TABLE company ADD currency_symbol NVARCHAR(10) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','business_modules') IS NULL
    EXEC(N'ALTER TABLE company ADD business_modules NVARCHAR(200) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL
    EXEC(N'UPDATE company SET country_code = N''SA'' WHERE country_code IS NULL OR country_code = N''''');
GO
IF OBJECT_ID('company','U') IS NOT NULL
    EXEC(N'UPDATE company SET business_modules = N''retail,supermarket''
           WHERE business_modules IS NULL OR business_modules = N''''');
GO

IF OBJECT_ID('company_options','U') IS NULL
CREATE TABLE company_options (
    opt_key     NVARCHAR(100) NOT NULL PRIMARY KEY,
    opt_value   NVARCHAR(MAX) NULL,
    updated_at  DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('customers','U') IS NOT NULL AND COL_LENGTH('customers','state_code') IS NULL
    EXEC(N'ALTER TABLE customers ADD state_code NVARCHAR(10) NULL');
GO
IF OBJECT_ID('suppliers','U') IS NOT NULL AND COL_LENGTH('suppliers','state_code') IS NULL
    EXEC(N'ALTER TABLE suppliers ADD state_code NVARCHAR(10) NULL');
GO
IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','hsn_code') IS NULL
    EXEC(N'ALTER TABLE products ADD hsn_code NVARCHAR(20) NULL');
GO
IF OBJECT_ID('branches','U') IS NOT NULL AND COL_LENGTH('branches','state_code') IS NULL
    EXEC(N'ALTER TABLE branches ADD state_code NVARCHAR(10) NULL');
GO

IF OBJECT_ID('sales_invoices','U') IS NOT NULL AND COL_LENGTH('sales_invoices','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE sales_invoices ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('purchase_invoices','U') IS NOT NULL AND COL_LENGTH('purchase_invoices','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE purchase_invoices ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('sales_returns','U') IS NOT NULL AND COL_LENGTH('sales_returns','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE sales_returns ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('purchase_returns','U') IS NOT NULL AND COL_LENGTH('purchase_returns','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE purchase_returns ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('quotations','U') IS NOT NULL AND COL_LENGTH('quotations','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE quotations ADD place_of_supply NVARCHAR(10) NULL');
GO

IF OBJECT_ID('vat_categories','U') IS NOT NULL AND COL_LENGTH('vat_categories','tax_kind') IS NULL
    EXEC(N'ALTER TABLE vat_categories ADD tax_kind NVARCHAR(10) NULL');
GO
IF COL_LENGTH('vat_categories','tax_kind') IS NOT NULL
    EXEC(N'UPDATE vat_categories SET tax_kind =
              CASE WHEN UPPER(LEFT(category_code,1)) = N''Z'' THEN N''zero''
                   WHEN UPPER(LEFT(category_code,1)) = N''E'' THEN N''exempt''
                   WHEN UPPER(LEFT(category_code,1)) = N''O'' THEN N''oos''
                   WHEN ISNULL(vat_rate,0) > 0 THEN N''std'' ELSE N''nil'' END
           WHERE tax_kind IS NULL');
GO

-- ── recipes / bills of materials ────────────────────────────
IF OBJECT_ID('bom_headers','U') IS NULL
CREATE TABLE bom_headers (
    bom_id          INT IDENTITY(1,1) PRIMARY KEY,
    product_id      INT NOT NULL,
    bom_name        NVARCHAR(200) NULL,
    output_qty      DECIMAL(18,4) NOT NULL DEFAULT 1,
    output_unit     NVARCHAR(50) NULL,
    labour_cost     DECIMAL(18,4) NOT NULL DEFAULT 0,
    overhead_cost   DECIMAL(18,4) NOT NULL DEFAULT 0,
    deduct_on_sale  BIT NOT NULL DEFAULT 0,      -- restaurant: selling the dish uses up the recipe
    is_default      BIT NOT NULL DEFAULT 1,
    is_active       BIT NOT NULL DEFAULT 1,
    notes           NVARCHAR(500) NULL,
    created_at      DATETIME DEFAULT GETDATE(),
    updated_at      DATETIME NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bom_headers_product')
    CREATE INDEX IX_bom_headers_product ON bom_headers(product_id);
GO

IF OBJECT_ID('bom_lines','U') IS NULL
CREATE TABLE bom_lines (
    line_id         INT IDENTITY(1,1) PRIMARY KEY,
    bom_id          INT NOT NULL,
    component_id    INT NOT NULL,
    quantity        DECIMAL(18,4) NOT NULL,
    unit_name       NVARCHAR(50) NULL,
    waste_pct       DECIMAL(9,3) NOT NULL DEFAULT 0,
    notes           NVARCHAR(200) NULL,
    sort_order      INT NOT NULL DEFAULT 0
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bom_lines_bom')
    CREATE INDEX IX_bom_lines_bom ON bom_lines(bom_id);
GO
