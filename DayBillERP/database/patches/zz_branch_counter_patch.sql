-- ============================================================
-- DayBill ERP - Branches, counters (tills) and product key (v5.12)
-- ------------------------------------------------------------
-- * branches      : shops / locations (one shared stock)
-- * counters      : cash counters (POS / billing PCs) of a branch
-- * branch_id + counter_id stamped on sales, POS bills, returns,
--   purchases, receipts / payments and expenses → counter-wise and
--   branch-wise sales + day close.
-- * app_license   : trial start + product key, shared by every PC
--   that uses this database.
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('branches','U') IS NULL
CREATE TABLE branches (
    branch_id     INT IDENTITY(1,1) PRIMARY KEY,
    name_en       NVARCHAR(100) NOT NULL,
    name_ar       NVARCHAR(100),
    is_active     BIT DEFAULT 1
);
GO
IF COL_LENGTH('branches','code') IS NULL
    ALTER TABLE branches ADD code NVARCHAR(10) NULL;
GO
IF COL_LENGTH('branches','address') IS NULL
    ALTER TABLE branches ADD address NVARCHAR(200) NULL;
GO
IF COL_LENGTH('branches','phone') IS NULL
    ALTER TABLE branches ADD phone NVARCHAR(30) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM branches)
    INSERT INTO branches (name_en, name_ar, code, is_active) VALUES (N'Main Branch', N'الفرع الرئيسي', 'B1', 1);
GO

IF OBJECT_ID('counters','U') IS NULL
CREATE TABLE counters (
    counter_id     INT IDENTITY(1,1) PRIMARY KEY,
    branch_id      INT NOT NULL REFERENCES branches(branch_id),
    code           NVARCHAR(10) NOT NULL,
    name_en        NVARCHAR(60) NOT NULL,
    workstation    NVARCHAR(100) NULL,      -- PC name last used for it
    is_active      BIT DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM counters)
    INSERT INTO counters (branch_id, code, name_en, is_active)
    SELECT TOP 1 branch_id, 'C1', N'Counter 1', 1 FROM branches ORDER BY branch_id;
GO

IF COL_LENGTH('sales_invoices','branch_id') IS NULL
    ALTER TABLE sales_invoices ADD branch_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','counter_id') IS NULL
    ALTER TABLE sales_invoices ADD counter_id INT NULL;
GO
IF COL_LENGTH('sales_returns','branch_id') IS NULL
    ALTER TABLE sales_returns ADD branch_id INT NULL;
GO
IF COL_LENGTH('sales_returns','counter_id') IS NULL
    ALTER TABLE sales_returns ADD counter_id INT NULL;
GO
IF COL_LENGTH('purchase_invoices','branch_id') IS NULL
    ALTER TABLE purchase_invoices ADD branch_id INT NULL;
GO
IF COL_LENGTH('purchase_invoices','counter_id') IS NULL
    ALTER TABLE purchase_invoices ADD counter_id INT NULL;
GO
IF COL_LENGTH('purchase_returns','branch_id') IS NULL
    ALTER TABLE purchase_returns ADD branch_id INT NULL;
GO
IF COL_LENGTH('purchase_returns','counter_id') IS NULL
    ALTER TABLE purchase_returns ADD counter_id INT NULL;
GO
IF COL_LENGTH('payments','branch_id') IS NULL
    ALTER TABLE payments ADD branch_id INT NULL;
GO
IF COL_LENGTH('payments','counter_id') IS NULL
    ALTER TABLE payments ADD counter_id INT NULL;
GO
IF COL_LENGTH('expenses','branch_id') IS NULL
    ALTER TABLE expenses ADD branch_id INT NULL;
GO
IF COL_LENGTH('expenses','counter_id') IS NULL
    ALTER TABLE expenses ADD counter_id INT NULL;
GO

-- older data belongs to the first branch / counter
UPDATE sales_invoices SET branch_id = (SELECT TOP 1 branch_id FROM branches ORDER BY branch_id)
    WHERE branch_id IS NULL;
GO
UPDATE sales_invoices SET counter_id = (SELECT TOP 1 counter_id FROM counters ORDER BY counter_id)
    WHERE counter_id IS NULL;
GO

IF OBJECT_ID('app_license','U') IS NULL
CREATE TABLE app_license (
    id              INT NOT NULL PRIMARY KEY,
    install_id      NVARCHAR(40) NOT NULL,
    installed_at    DATE NOT NULL,
    product_key     NVARCHAR(1000) NULL,
    activated_at    DATETIME NULL,
    last_online     DATETIME NULL,
    online_status   NVARCHAR(20) NULL,       -- active / blocked / unknown
    online_message  NVARCHAR(300) NULL
);
GO

PRINT '✅ Branches, counters and product key tables ready.';
GO
