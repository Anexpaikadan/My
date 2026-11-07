-- ============================================================
-- DayBill ERP - Stock Journal (v7.11.0): Damage Entry, Excess Stock,
-- Shortage Stock — each its own numbered document
-- ------------------------------------------------------------
--   damage    stock out at cost   Dr Damaged Stock Written Off | Cr Inventory
--   shortage  stock out at cost   Dr Stock Shortage            | Cr Inventory
--   excess    stock in at cost    Dr Inventory                 | Cr Stock Excess (Gain)
-- Idempotent: every table / column / account is guarded.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('stock_journals','U') IS NULL
CREATE TABLE stock_journals (
    entry_id          INT IDENTITY(1,1) PRIMARY KEY,
    entry_number      NVARCHAR(30) NOT NULL UNIQUE,
    entry_type        NVARCHAR(20) NOT NULL DEFAULT 'damage',   -- damage | excess | shortage
    entry_date        DATE NOT NULL,
    reason            NVARCHAR(100) NULL,
    account_id        INT NULL,                                -- the other side of Inventory
    branch_id         INT NULL,
    counter_id        INT NULL,
    total_cost        DECIMAL(18,2) NOT NULL DEFAULT 0,
    notes             NVARCHAR(500) NULL,
    entry_status      NVARCHAR(20) NOT NULL DEFAULT 'confirmed',
    created_by        INT NULL,
    created_at        DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at        DATETIME NULL
);
GO
IF OBJECT_ID('stock_journal_lines','U') IS NULL
CREATE TABLE stock_journal_lines (
    line_id           INT IDENTITY(1,1) PRIMARY KEY,
    entry_id          INT NOT NULL REFERENCES stock_journals(entry_id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    product_id        INT NOT NULL,
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    product_name_ar   NVARCHAR(300) NULL,
    quantity          DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_of_measure_en NVARCHAR(50) NULL,
    unit_cost         DECIMAL(18,4) NOT NULL DEFAULT 0,
    line_total        DECIMAL(18,2) NOT NULL DEFAULT 0,
    remarks           NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_stock_journals_type_date')
    CREATE INDEX IX_stock_journals_type_date ON stock_journals(entry_type, entry_date);
GO

-- the accounts a stock journal posts to (only added when missing)
IF OBJECT_ID('accounts','U') IS NOT NULL
BEGIN
    DECLARE @dx INT = COALESCE((SELECT account_id FROM accounts WHERE account_code='5001'),
                               (SELECT account_id FROM accounts WHERE account_code='5000'));
    DECLARE @ii INT = COALESCE((SELECT account_id FROM accounts WHERE account_code='4003'),
                               (SELECT account_id FROM accounts WHERE account_code='4000'));
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5165')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5165', N'Damaged Stock Written Off', N'بضاعة تالفة مشطوبة', 'expense', @dx);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5166')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5166', N'Stock Shortage', N'عجز المخزون', 'expense', @dx);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='4320')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('4320', N'Stock Excess (Gain)', N'زيادة المخزون', 'revenue', @ii);
END
GO

-- user rights for the Stock Journal: the same as each role has for
-- Stock Adjustment (the administrator can change them in Users & Rights)
IF OBJECT_ID('permissions','U') IS NOT NULL AND OBJECT_ID('role_permissions','U') IS NOT NULL
BEGIN
    INSERT INTO permissions (module_key, action_key)
    SELECT 'stock_journal', a.action_key FROM (SELECT DISTINCT action_key FROM permissions) a
    WHERE NOT EXISTS (SELECT 1 FROM permissions p WHERE p.module_key='stock_journal'
                      AND p.action_key=a.action_key);
    INSERT INTO role_permissions (role_id, permission_id, allowed)
    SELECT rp.role_id, pc.permission_id, rp.allowed
    FROM role_permissions rp
    JOIN permissions ps ON ps.permission_id=rp.permission_id AND ps.module_key='stock_adjustment'
    JOIN permissions pc ON pc.module_key='stock_journal' AND pc.action_key=ps.action_key
    WHERE NOT EXISTS (SELECT 1 FROM role_permissions x WHERE x.role_id=rp.role_id
                      AND x.permission_id=pc.permission_id);
END
GO

PRINT 'DayBill v7.11.0 stock journal patch applied.';
GO
