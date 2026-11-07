-- ============================================================
-- DayBill ERP - Masters (v7.10.0): brands, sections, group categories,
-- units of measure, vehicles, sales routes, salesmen, party categories,
-- cost centres, currencies & exchange rates, general master
-- ------------------------------------------------------------
-- Idempotent: every table / column is guarded, safe to run again.
-- Nothing is deleted or changed in existing data.
-- ============================================================
USE DayBillERP;
GO

-- ── Brands (the table came with product_extras_patch) ────────
IF OBJECT_ID('product_brands','U') IS NULL
CREATE TABLE product_brands (
    brand_id       INT IDENTITY(1,1) PRIMARY KEY,
    brand_name_en  NVARCHAR(80) NOT NULL,
    brand_name_ar  NVARCHAR(80) NULL,
    is_active      BIT DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);
GO
IF COL_LENGTH('product_brands','brand_code') IS NULL
    ALTER TABLE product_brands ADD brand_code NVARCHAR(20) NULL;
GO
IF COL_LENGTH('products','brand_id') IS NULL
    ALTER TABLE products ADD brand_id INT NULL;
GO

-- ── Sections (shop departments: Dairy, Frozen, Bakery …) ─────
IF OBJECT_ID('product_sections','U') IS NULL
CREATE TABLE product_sections (
    section_id     INT IDENTITY(1,1) PRIMARY KEY,
    section_code   NVARCHAR(20) NULL,
    name_en        NVARCHAR(100) NOT NULL,
    name_ar        NVARCHAR(100) NULL,
    notes          NVARCHAR(300) NULL,
    is_active      BIT NOT NULL DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);
GO
IF COL_LENGTH('products','section_id') IS NULL
    ALTER TABLE products ADD section_id INT NULL;
GO

-- ── Group categories (a group of product categories) ─────────
IF OBJECT_ID('product_group_categories','U') IS NULL
CREATE TABLE product_group_categories (
    group_category_id INT IDENTITY(1,1) PRIMARY KEY,
    group_code        NVARCHAR(20) NULL,
    name_en           NVARCHAR(100) NOT NULL,
    name_ar           NVARCHAR(100) NULL,
    notes             NVARCHAR(300) NULL,
    is_active         BIT NOT NULL DEFAULT 1,
    created_at        DATETIME DEFAULT GETDATE()
);
GO
IF COL_LENGTH('product_categories','group_category_id') IS NULL
    ALTER TABLE product_categories ADD group_category_id INT NULL;
GO

-- ── Units of measure (the names offered in the product window) ─
IF OBJECT_ID('unit_master','U') IS NULL
CREATE TABLE unit_master (
    unit_id         INT IDENTITY(1,1) PRIMARY KEY,
    unit_name_en    NVARCHAR(50) NOT NULL,
    unit_name_ar    NVARCHAR(50) NULL,
    short_name      NVARCHAR(10) NULL,
    allow_decimals  BIT NOT NULL DEFAULT 0,
    sort_order      INT NOT NULL DEFAULT 0,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM unit_master)
INSERT INTO unit_master (unit_name_en, unit_name_ar, short_name, allow_decimals, sort_order) VALUES
    (N'PCs',    N'حبة',   N'pc',  0, 1),
    (N'Box',    N'علبة',  N'box', 0, 2),
    (N'Carton', N'كرتون', N'ctn', 0, 3),
    (N'Dozen',  N'درزن',  N'dz',  0, 4),
    (N'Kg',     N'كيلو',  N'kg',  1, 5),
    (N'Gram',   N'جرام',  N'g',   1, 6),
    (N'Liter',  N'لتر',   N'l',   1, 7),
    (N'Pack',   N'باكيت', N'pk',  0, 8),
    (N'Bag',    N'كيس',   N'bag', 0, 9),
    (N'Bundle', N'حزمة',  N'bdl', 0, 10),
    (N'Unit',   N'وحدة',  N'u',   0, 11);
GO

-- ── Vehicles (delivery / van sales) ──────────────────────────
IF OBJECT_ID('vehicles','U') IS NULL
CREATE TABLE vehicles (
    vehicle_id      INT IDENTITY(1,1) PRIMARY KEY,
    vehicle_no      NVARCHAR(30) NOT NULL,
    vehicle_name    NVARCHAR(100) NULL,
    vehicle_type    NVARCHAR(40) NULL,
    driver_name     NVARCHAR(100) NULL,
    driver_mobile   NVARCHAR(20) NULL,
    notes           NVARCHAR(300) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

-- ── Sales routes / areas ─────────────────────────────────────
IF OBJECT_ID('sales_routes','U') IS NULL
CREATE TABLE sales_routes (
    route_id        INT IDENTITY(1,1) PRIMARY KEY,
    route_code      NVARCHAR(20) NULL,
    name_en         NVARCHAR(100) NOT NULL,
    name_ar         NVARCHAR(100) NULL,
    area            NVARCHAR(100) NULL,
    notes           NVARCHAR(300) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF COL_LENGTH('customers','route_id') IS NULL
    ALTER TABLE customers ADD route_id INT NULL;
GO

-- ── Salesmen + the routes each one covers ────────────────────
IF OBJECT_ID('salesmen','U') IS NULL
CREATE TABLE salesmen (
    salesman_id     INT IDENTITY(1,1) PRIMARY KEY,
    salesman_code   NVARCHAR(20) NULL,
    name_en         NVARCHAR(100) NOT NULL,
    name_ar         NVARCHAR(100) NULL,
    mobile          NVARCHAR(20) NULL,
    user_id         INT NULL,
    vehicle_id      INT NULL,
    commission_pct  DECIMAL(9,3) NOT NULL DEFAULT 0,
    monthly_target  DECIMAL(18,2) NOT NULL DEFAULT 0,
    notes           NVARCHAR(300) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('salesman_routes','U') IS NULL
CREATE TABLE salesman_routes (
    salesman_id     INT NOT NULL,
    route_id        INT NOT NULL,
    CONSTRAINT PK_salesman_routes PRIMARY KEY (salesman_id, route_id)
);
GO
IF COL_LENGTH('customers','salesman_id') IS NULL
    ALTER TABLE customers ADD salesman_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','salesman_id') IS NULL
    ALTER TABLE sales_invoices ADD salesman_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','route_id') IS NULL
    ALTER TABLE sales_invoices ADD route_id INT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sales_invoices_salesman')
    CREATE INDEX IX_sales_invoices_salesman ON sales_invoices(salesman_id);
GO

-- ── Party categories (Wholesale, Retail, VIP, Restaurant …) ──
IF OBJECT_ID('party_categories','U') IS NULL
CREATE TABLE party_categories (
    party_category_id INT IDENTITY(1,1) PRIMARY KEY,
    name_en           NVARCHAR(100) NOT NULL,
    name_ar           NVARCHAR(100) NULL,
    applies_to        NVARCHAR(10) NOT NULL DEFAULT 'both',   -- customer | supplier | both
    notes             NVARCHAR(300) NULL,
    is_active         BIT NOT NULL DEFAULT 1,
    created_at        DATETIME DEFAULT GETDATE()
);
GO
IF COL_LENGTH('customers','party_category_id') IS NULL
    ALTER TABLE customers ADD party_category_id INT NULL;
GO
IF COL_LENGTH('suppliers','party_category_id') IS NULL
    ALTER TABLE suppliers ADD party_category_id INT NULL;
GO

-- ── Cost centres ─────────────────────────────────────────────
IF OBJECT_ID('cost_centers','U') IS NULL
CREATE TABLE cost_centers (
    cost_center_id  INT IDENTITY(1,1) PRIMARY KEY,
    cc_code         NVARCHAR(20) NULL,
    name_en         NVARCHAR(100) NOT NULL,
    name_ar         NVARCHAR(100) NULL,
    parent_id       INT NULL,
    notes           NVARCHAR(300) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

-- ── Currencies & exchange rates ──────────────────────────────
IF OBJECT_ID('currencies','U') IS NULL
CREATE TABLE currencies (
    currency_id     INT IDENTITY(1,1) PRIMARY KEY,
    currency_code   NVARCHAR(5) NOT NULL,
    name_en         NVARCHAR(60) NOT NULL,
    name_ar         NVARCHAR(60) NULL,
    symbol          NVARCHAR(10) NULL,
    rate_to_base    DECIMAL(18,6) NOT NULL DEFAULT 1,     -- 1 unit of this = rate × the shop's currency
    decimals        INT NOT NULL DEFAULT 2,
    is_base         BIT NOT NULL DEFAULT 0,
    rate_date       DATE NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_currencies_code')
    CREATE UNIQUE INDEX UX_currencies_code ON currencies(currency_code);
GO
IF OBJECT_ID('currency_rate_history','U') IS NULL
CREATE TABLE currency_rate_history (
    history_id      INT IDENTITY(1,1) PRIMARY KEY,
    currency_id     INT NOT NULL,
    old_rate        DECIMAL(18,6) NULL,
    new_rate        DECIMAL(18,6) NOT NULL,
    rate_date       DATE NULL,
    changed_by      NVARCHAR(60) NULL,
    changed_at      DATETIME DEFAULT GETDATE()
);
GO

-- ── General master (any short list: colours, sizes, reasons …) ─
IF OBJECT_ID('general_master','U') IS NULL
CREATE TABLE general_master (
    gm_id           INT IDENTITY(1,1) PRIMARY KEY,
    gm_type         NVARCHAR(40) NOT NULL,
    gm_code         NVARCHAR(20) NULL,
    name_en         NVARCHAR(150) NOT NULL,
    name_ar         NVARCHAR(150) NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    notes           NVARCHAR(300) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_general_master_type')
    CREATE INDEX IX_general_master_type ON general_master(gm_type);
GO

PRINT 'DayBill v7.10.0 masters patch applied.';
GO
