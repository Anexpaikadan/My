-- ============================================================
-- DayBill ERP v6.9.3
--   journal_entries.voucher_type   SI / POS / SR / PI / PR / CR / BR /
--                                   CP / BP / EX / CT / JV / OB / ADJ / CE …
--   consumption_entries / _lines    Consumable entry: stock used by the shop
--                                   itself (staff food, bakery production …)
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('journal_entries','U') IS NOT NULL AND COL_LENGTH('journal_entries','voucher_type') IS NULL
    EXEC(N'ALTER TABLE journal_entries ADD voucher_type NVARCHAR(10) NULL');
GO

-- older journals get their type once (receipts / payments: cash first)
IF COL_LENGTH('journal_entries','voucher_type') IS NOT NULL
EXEC(N'
UPDATE journal_entries SET voucher_type = CASE LOWER(ISNULL(source_type, ''''))
    WHEN ''sales'' THEN ''SI''            WHEN ''pos'' THEN ''POS''
    WHEN ''sales_return'' THEN ''SR''     WHEN ''debit_note'' THEN ''DN''
    WHEN ''cogs'' THEN ''COS''            WHEN ''cogs_return'' THEN ''COS''
    WHEN ''purchase'' THEN ''PI''         WHEN ''purchase_return'' THEN ''PR''
    WHEN ''purchase_return_cost'' THEN ''PR''
    WHEN ''receipt'' THEN ''CR''          WHEN ''payment'' THEN ''CP''
    WHEN ''expense'' THEN CASE WHEN source_id IS NULL THEN ''CP'' ELSE ''EX'' END
    WHEN ''transfer'' THEN ''CT''
    WHEN ''opening'' THEN ''OB''          WHEN ''opening_accounts'' THEN ''OB''
    WHEN ''opening_stock'' THEN ''OB''
    WHEN ''adjustment'' THEN CASE WHEN UPPER(ISNULL(reference,'''')) LIKE ''OPEN%'' THEN ''OB'' ELSE ''JV'' END
    WHEN ''stock_adjust'' THEN ''ADJ''    WHEN ''cycle_count'' THEN ''ADJ''
    WHEN ''consumption'' THEN ''CE''
    WHEN ''payroll'' THEN ''PY''          WHEN ''salary_payment'' THEN ''SAL''
    WHEN ''gosi_payment'' THEN ''GOSI''   WHEN ''eos'' THEN ''EOS''
    WHEN ''employee_loan'' THEN ''LN''    WHEN ''day_close'' THEN ''DC''
    WHEN ''shift'' THEN ''SH''
    ELSE ''JV'' END
WHERE voucher_type IS NULL;');
GO

-- receipts / payments that never touched a cash account → bank
IF COL_LENGTH('journal_entries','voucher_type') IS NOT NULL AND OBJECT_ID('account_settings','U') IS NOT NULL
EXEC(N'
DECLARE @cash TABLE (account_id INT PRIMARY KEY);
INSERT INTO @cash (account_id)
SELECT DISTINCT a.account_id FROM accounts a
WHERE a.account_code IN (SELECT account_code FROM account_settings
                         WHERE setting_key IN (''default_cash'', ''default_petty_cash''))
   OR a.account_code IN (''1100'', ''1150'');
IF OBJECT_ID(''payment_method_accounts'', ''U'') IS NOT NULL
    INSERT INTO @cash (account_id)
    SELECT DISTINCT p.account_id FROM payment_method_accounts p
    WHERE p.method_code = ''cash'' AND p.account_id IS NOT NULL
      AND p.account_id NOT IN (SELECT account_id FROM @cash);
UPDATE j SET voucher_type = CASE j.voucher_type WHEN ''CR'' THEN ''BR'' ELSE ''BP'' END
FROM journal_entries j
WHERE j.voucher_type IN (''CR'', ''CP'')
  AND NOT EXISTS (SELECT 1 FROM journal_lines l JOIN @cash c ON c.account_id = l.account_id
                  WHERE l.journal_id = j.journal_id);');
GO

IF OBJECT_ID('journal_entries','U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_voucher_type'
                   AND object_id=OBJECT_ID('journal_entries'))
   AND COL_LENGTH('journal_entries','voucher_type') IS NOT NULL
    EXEC(N'CREATE INDEX IX_journal_voucher_type ON journal_entries(voucher_type)');
GO

-- ── Consumable entry ─────────────────────────────────────────
IF OBJECT_ID('consumption_entries','U') IS NULL
CREATE TABLE consumption_entries (
    entry_id          INT IDENTITY(1,1) PRIMARY KEY,
    entry_number      NVARCHAR(30) NOT NULL UNIQUE,
    entry_date        DATE NOT NULL,
    purpose           NVARCHAR(30) NOT NULL DEFAULT 'staff_food',
    expense_account_id INT NULL,
    unit_name         NVARCHAR(100) NULL,          -- room / production unit (e.g. Bakery)
    warehouse_id      INT NULL,
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
IF OBJECT_ID('consumption_lines','U') IS NULL
CREATE TABLE consumption_lines (
    line_id           INT IDENTITY(1,1) PRIMARY KEY,
    entry_id          INT NOT NULL REFERENCES consumption_entries(entry_id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    product_id        INT NOT NULL,
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    product_name_ar   NVARCHAR(300) NULL,
    quantity          DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_of_measure_en NVARCHAR(50) NULL,
    unit_cost         DECIMAL(18,4) NOT NULL DEFAULT 0,
    line_total        DECIMAL(18,2) NOT NULL DEFAULT 0
);
GO

-- expense accounts a consumable entry posts to (only added when missing)
IF OBJECT_ID('accounts','U') IS NOT NULL
BEGIN
    DECLARE @p INT = (SELECT account_id FROM accounts WHERE account_code='5000');
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5460')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5460', N'Staff Food & Welfare', N'طعام ورعاية الموظفين', 'expense', @p);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5470')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5470', N'Production Materials Used', N'مواد مستهلكة في الإنتاج', 'expense', @p);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5480')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5480', N'Shop Supplies Used', N'مستلزمات المحل المستهلكة', 'expense', @p);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5490')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5490', N'Samples & Tasting', N'عينات وتذوق', 'expense', @p);
END
GO

-- user rights for the new Consumable entry: the same as each role has for
-- Stock Adjustment (the administrator can change them in Users & Rights)
IF OBJECT_ID('permissions','U') IS NOT NULL AND OBJECT_ID('role_permissions','U') IS NOT NULL
BEGIN
    INSERT INTO permissions (module_key, action_key)
    SELECT 'consumption', a.action_key FROM (SELECT DISTINCT action_key FROM permissions) a
    WHERE NOT EXISTS (SELECT 1 FROM permissions p WHERE p.module_key='consumption'
                      AND p.action_key=a.action_key);
    INSERT INTO role_permissions (role_id, permission_id, allowed)
    SELECT rp.role_id, pc.permission_id, rp.allowed
    FROM role_permissions rp
    JOIN permissions ps ON ps.permission_id=rp.permission_id AND ps.module_key='stock_adjustment'
    JOIN permissions pc ON pc.module_key='consumption' AND pc.action_key=ps.action_key
    WHERE NOT EXISTS (SELECT 1 FROM role_permissions x WHERE x.role_id=rp.role_id
                      AND x.permission_id=pc.permission_id);
END
GO

IF OBJECT_ID('consumption_entries','U') IS NOT NULL AND COL_LENGTH('consumption_entries','branch_id') IS NULL
    EXEC(N'ALTER TABLE consumption_entries ADD branch_id INT NULL, counter_id INT NULL');
GO
