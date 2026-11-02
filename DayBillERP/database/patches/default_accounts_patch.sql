-- ============================================================
-- DayBill ERP - Default Cash Account & Auto-Posting Patch
-- ------------------------------------------------------------
-- Adds the master Cash Account, the missing ledger accounts the
-- posting engine already references, a configurable default-account
-- map, per-payment-method ledger mapping, branch-wise cash mapping,
-- a fund-transfer (banking) table and a simple expenses table.
--
-- Idempotent: safe to run multiple times.
-- ============================================================

USE DayBillERP;
GO

-- ============================================================
-- PART A — CHART OF ACCOUNTS ADDITIONS
-- ------------------------------------------------------------
-- The posting engine references 1110 (Bank) and 1120 (Card) but the
-- base schema never created them, so card/bank legs were being
-- dropped and journals stored UNBALANCED. These inserts fix that and
-- add the remaining accounts the spec calls for.
-- ============================================================

-- Current Assets group (under 1000 Assets)
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1010')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
SELECT '1010', 'Current Assets', N'الأصول المتداولة', 'asset', a.account_id
FROM accounts a WHERE a.account_code='1000';
GO

-- Make the existing Cash account the MASTER "Cash Account" under Current Assets.
-- (Code stays 1100 so existing postings/history keep resolving. To use the
--  spec code 100001 instead, uncomment the optional block at the bottom.)
UPDATE accounts
   SET account_name_en = 'Cash Account',
       account_name_ar = N'حساب النقد',
       parent_account_id = (SELECT account_id FROM accounts WHERE account_code='1010')
 WHERE account_code='1100';
GO

-- Banking / tender accounts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1110')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1110', 'Main Bank Account',          N'الحساب البنكي الرئيسي', 'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1120')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1120', 'Card / Credit Card Clearing', N'حساب تسوية البطاقات',   'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1130')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1130', 'Savings Account',            N'حساب التوفير',          'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1140')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1140', 'Online Payment Gateway',     N'بوابة الدفع الإلكتروني', 'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1150')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1150', 'Petty Cash',                 N'النثرية',               'asset');
GO

-- Returns (contra) accounts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='4200')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('4200', 'Sales Returns',              N'مردودات المبيعات',      'revenue');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5150')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5150', 'Purchase Returns',           N'مردودات المشتريات',     'expense');
GO

-- Expense accounts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5300')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5300', 'Rent Expense',               N'مصروف الإيجار',         'expense'),
('5310', 'Electricity Expense',        N'مصروف الكهرباء',        'expense'),
('5320', 'Fuel Expense',               N'مصروف الوقود',          'expense'),
('5330', 'Office Expense',             N'مصروفات مكتبية',        'expense'),
('5390', 'General Expense',            N'مصروفات عامة',          'expense'),
('5400', 'Discount Allowed',           N'الخصم المسموح به',      'expense'),
('5900', 'Rounding Difference',        N'فروقات التقريب',        'expense');
GO

-- ============================================================
-- PART B — DEFAULT ACCOUNT MAP (key -> account)
-- ------------------------------------------------------------
-- A DB-resident copy of the default-account selections. The app
-- reads/writes these through config/account_defaults.py; this table
-- keeps the mapping available to SQL/reporting too.
-- ============================================================
IF OBJECT_ID('account_settings','U') IS NULL
CREATE TABLE account_settings (
    setting_key   NVARCHAR(50) NOT NULL PRIMARY KEY,
    account_id    INT NULL REFERENCES accounts(account_id),
    account_code  NVARCHAR(20) NULL,
    updated_at    DATETIME DEFAULT GETDATE()
);
GO

-- Seed the map from the codes above (only rows that are missing).
MERGE account_settings AS tgt
USING (VALUES
    ('default_cash',            '1100'),
    ('default_bank',            '1110'),
    ('default_card',            '1120'),
    ('default_savings',         '1130'),
    ('default_gateway',         '1140'),
    ('default_petty_cash',      '1150'),
    ('default_sales',           '4100'),
    ('default_purchase',        '1300'),
    ('default_inventory',       '1300'),
    ('default_receivable',      '1200'),
    ('default_payable',         '2100'),
    ('default_tax_payable',     '2210'),
    ('default_tax_receivable',  '2220'),
    ('default_cogs',            '5100'),
    ('default_salary_expense',  '5200'),
    ('default_discount',        '5400'),
    ('default_round_off',       '5900'),
    ('default_sales_return',    '4200'),
    ('default_purchase_return', '5150')
) AS src(setting_key, account_code)
ON tgt.setting_key = src.setting_key
WHEN NOT MATCHED THEN
    INSERT (setting_key, account_code, account_id)
    VALUES (src.setting_key, src.account_code,
            (SELECT account_id FROM accounts WHERE account_code = src.account_code));
GO

-- ============================================================
-- PART C — PAYMENT METHOD -> LEDGER MAPPING
-- ============================================================
IF OBJECT_ID('payment_method_accounts','U') IS NULL
CREATE TABLE payment_method_accounts (
    method_code   NVARCHAR(20) NOT NULL PRIMARY KEY,
    label_en      NVARCHAR(50),
    account_id    INT NULL REFERENCES accounts(account_id),
    is_active     BIT DEFAULT 1
);
GO

MERGE payment_method_accounts AS tgt
USING (VALUES
    ('cash',          'Cash',          '1100'),
    ('card',          'Card',          '1120'),
    ('bank_transfer', 'Bank Transfer', '1110'),
    ('gateway',       'Online Gateway','1140')
) AS src(method_code, label_en, code)
ON tgt.method_code = src.method_code
WHEN NOT MATCHED THEN
    INSERT (method_code, label_en, account_id)
    VALUES (src.method_code, src.label_en,
            (SELECT account_id FROM accounts WHERE account_code = src.code));
GO

-- ============================================================
-- PART D — BRANCHES + BRANCH-WISE CASH MAPPING
-- ============================================================
IF OBJECT_ID('branches','U') IS NULL
CREATE TABLE branches (
    branch_id     INT IDENTITY(1,1) PRIMARY KEY,
    name_en       NVARCHAR(100) NOT NULL,
    name_ar       NVARCHAR(100),
    is_active     BIT DEFAULT 1
);
GO

IF OBJECT_ID('branch_cash_accounts','U') IS NULL
CREATE TABLE branch_cash_accounts (
    branch_id            INT NOT NULL PRIMARY KEY REFERENCES branches(branch_id),
    cash_account_id      INT NULL REFERENCES accounts(account_id),
    petty_cash_account_id INT NULL REFERENCES accounts(account_id),
    bank_account_id      INT NULL REFERENCES accounts(account_id)
);
GO

-- ============================================================
-- PART E — BANKING: FUND TRANSFERS
-- ============================================================
IF OBJECT_ID('bank_transfers','U') IS NULL
CREATE TABLE bank_transfers (
    transfer_id     INT IDENTITY(1,1) PRIMARY KEY,
    transfer_date   DATE NOT NULL,
    from_account_id INT NOT NULL REFERENCES accounts(account_id),
    to_account_id   INT NOT NULL REFERENCES accounts(account_id),
    amount          DECIMAL(18,2) NOT NULL,
    reference       NVARCHAR(100),
    notes           NVARCHAR(300),
    journal_id      INT NULL REFERENCES journal_entries(journal_id),
    created_at      DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- PART F — EXPENSES (immediate-pay expense vouchers)
-- ============================================================
IF OBJECT_ID('expenses','U') IS NULL
CREATE TABLE expenses (
    expense_id      INT IDENTITY(1,1) PRIMARY KEY,
    expense_date    DATE NOT NULL,
    expense_account_id INT NOT NULL REFERENCES accounts(account_id),
    amount          DECIMAL(18,2) NOT NULL,
    vat_amount      DECIMAL(18,2) DEFAULT 0,
    payment_method  NVARCHAR(20) DEFAULT 'cash',  -- cash/bank/card/gateway
    paid_from_account_id INT NULL REFERENCES accounts(account_id),
    reference       NVARCHAR(100),
    description     NVARCHAR(300),
    journal_id      INT NULL REFERENCES journal_entries(journal_id),
    created_by      INT,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

PRINT '✅ Default accounts & auto-posting patch applied.';
GO

-- ============================================================
-- PART G — DEFAULT "CASH" WALK-IN CUSTOMER
-- ------------------------------------------------------------
-- The new-invoice screen auto-selects this customer. Its ledger
-- points at the master Cash account, so an unpaid "cash sale"
-- never lands in receivables. (Fully-paid cash sales debit Cash
-- regardless.) Guarded for whether party_ledger_patch has added
-- the account_id column yet.
-- ============================================================
IF EXISTS (SELECT 1 FROM sys.columns
           WHERE object_id=OBJECT_ID('customers') AND name='account_id')
BEGIN
    IF NOT EXISTS (SELECT 1 FROM customers WHERE customer_code='CASH')
        INSERT INTO customers (customer_code, customer_name_en, customer_name_ar,
            customer_type, country_code, account_id)
        VALUES ('CASH', 'Cash Customer', N'عميل نقدي', 'B2C', 'SA',
                (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100'));

    UPDATE customers
       SET account_id = (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100')
     WHERE customer_code='CASH';
END
ELSE
BEGIN
    IF NOT EXISTS (SELECT 1 FROM customers WHERE customer_code='CASH')
        INSERT INTO customers (customer_code, customer_name_en, customer_name_ar,
            customer_type, country_code)
        VALUES ('CASH', 'Cash Customer', N'عميل نقدي', 'B2C', 'SA');
END
GO

PRINT '✅ Cash walk-in customer ready.';
GO

-- ============================================================
-- OPTIONAL: switch the master cash code 1100 -> 100001
-- (spec asked for an editable 100001). Uncomment to apply.
-- The app resolves cash by the configured code, so postings follow.
-- ------------------------------------------------------------
-- UPDATE accounts        SET account_code='100001' WHERE account_code='1100';
-- UPDATE account_settings SET account_code='100001' WHERE setting_key='default_cash';
-- UPDATE payment_method_accounts
--    SET account_id=(SELECT account_id FROM accounts WHERE account_code='100001')
--  WHERE method_code='cash';
-- GO
