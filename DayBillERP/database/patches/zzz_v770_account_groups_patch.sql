-- ============================================================
-- DayBill ERP v7.7 — the full set of default account GROUPS
--   Assets      › Current Assets › Cash-in-Hand · Bank Accounts ·
--                 Sundry Debtors · Stock-in-Hand · Loans & Advances ·
--                 Deposits;  Fixed Assets;  Investments
--   Liabilities › Current Liabilities › Sundry Creditors · Duties &
--                 Taxes · Provisions & Payroll;  Loans (Liability)
--   Equity      › Capital Account · Reserves & Surplus
--   Revenue     › Sales Accounts · Direct Income · Indirect Income
--   Expenses    › Direct Expenses (Cost of Sales) · Employee Costs ·
--                 Administrative Expenses · Selling & Distribution ·
--                 Financial Charges
-- Account codes never change (postings use them). A default ledger is
-- moved into its new group ONLY while it still sits where DayBill put
-- it — a ledger you moved yourself stays where you put it. Safe to run
-- again (Chart of Accounts ▸ Add default groups).
-- ============================================================
SET NOCOUNT ON;
IF OBJECT_ID('accounts','U') IS NOT NULL AND COL_LENGTH('accounts','is_group') IS NOT NULL
BEGIN
    DECLARE @g TABLE (ord INT, code NVARCHAR(20), en NVARCHAR(100), ar NVARCHAR(100),
                      typ NVARCHAR(20), parent NVARCHAR(20));
    INSERT INTO @g VALUES
    ( 1, N'1000', N'Assets',                      N'الأصول',                     N'asset',     NULL),
    ( 2, N'1010', N'Current Assets',              N'الأصول المتداولة',           N'asset',     N'1000'),
    ( 3, N'1011', N'Cash-in-Hand',                N'النقدية في الصندوق',         N'asset',     N'1010'),
    ( 4, N'1012', N'Bank Accounts',               N'الحسابات البنكية',           N'asset',     N'1010'),
    ( 5, N'1013', N'Sundry Debtors',              N'المدينون',                   N'asset',     N'1010'),
    ( 6, N'1014', N'Stock-in-Hand',               N'المخزون',                    N'asset',     N'1010'),
    ( 7, N'1015', N'Loans & Advances (Asset)',    N'القروض والسلف',              N'asset',     N'1010'),
    ( 8, N'1016', N'Deposits (Asset)',            N'التأمينات والودائع',         N'asset',     N'1010'),
    ( 9, N'1500', N'Fixed Assets',                N'الأصول الثابتة',             N'asset',     N'1000'),
    (10, N'1600', N'Investments',                 N'الاستثمارات',                N'asset',     N'1000'),
    (11, N'2000', N'Liabilities',                 N'الخصوم',                     N'liability', NULL),
    (12, N'2001', N'Current Liabilities',         N'الخصوم المتداولة',           N'liability', N'2000'),
    (13, N'2002', N'Sundry Creditors',            N'الدائنون',                   N'liability', N'2001'),
    (14, N'2003', N'Duties & Taxes',              N'الرسوم والضرائب',            N'liability', N'2001'),
    (15, N'2004', N'Provisions & Payroll',        N'المخصصات والرواتب المستحقة', N'liability', N'2001'),
    (16, N'2005', N'Loans (Liability)',           N'القروض',                     N'liability', N'2000'),
    (17, N'3000', N'Equity',                      N'حقوق الملكية',               N'equity',    NULL),
    (18, N'3001', N'Capital Account',             N'حساب رأس المال',             N'equity',    N'3000'),
    (19, N'3002', N'Reserves & Surplus',          N'الاحتياطيات والأرباح المبقاة', N'equity',  N'3000'),
    (20, N'4000', N'Revenue',                     N'الإيرادات',                  N'revenue',   NULL),
    (21, N'4001', N'Sales Accounts',              N'حسابات المبيعات',            N'revenue',   N'4000'),
    (22, N'4002', N'Direct Income',               N'الإيرادات المباشرة',         N'revenue',   N'4000'),
    (23, N'4003', N'Indirect Income',             N'الإيرادات الأخرى',           N'revenue',   N'4000'),
    (24, N'5000', N'Expenses',                    N'المصروفات',                  N'expense',   NULL),
    (25, N'5001', N'Direct Expenses (Cost of Sales)', N'المصروفات المباشرة (تكلفة المبيعات)', N'expense', N'5000'),
    (26, N'5002', N'Employee Costs',              N'تكاليف الموظفين',            N'expense',   N'5000'),
    (27, N'5003', N'Administrative Expenses',     N'المصروفات الإدارية',         N'expense',   N'5000'),
    (28, N'5004', N'Selling & Distribution',      N'مصروفات البيع والتوزيع',     N'expense',   N'5000'),
    (29, N'5005', N'Financial Charges',           N'المصروفات المالية',          N'expense',   N'5000');

    -- 1) the groups (parents first); a code already used by something else is left alone
    DECLARE @ord INT = 1, @n INT = (SELECT MAX(ord) FROM @g);
    WHILE @ord <= @n
    BEGIN
        DECLARE @code NVARCHAR(20), @en NVARCHAR(100), @ar NVARCHAR(100), @typ NVARCHAR(20), @par NVARCHAR(20);
        SELECT @code = code, @en = en, @ar = ar, @typ = typ, @par = parent FROM @g WHERE ord = @ord;
        IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code = @code)
            INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type,
                                  parent_account_id, is_active, is_group)
            VALUES (@code, @en, @ar, @typ,
                    (SELECT account_id FROM accounts WHERE account_code = @par), 1, 1);
        ELSE IF EXISTS (SELECT 1 FROM accounts WHERE account_code = @code AND account_name_en = @en)
            UPDATE accounts SET is_group = 1, is_active = 1 WHERE account_code = @code;
        SET @ord = @ord + 1;
    END;

    -- 2) default ledgers into their group — only while still in DayBill's place
    --    (old parent code, or no parent at all)
    DECLARE @m TABLE (ledger NVARCHAR(20), grp NVARCHAR(20), oldp NVARCHAR(20));
    INSERT INTO @m VALUES
    (N'1100', N'1011', N'1010'), (N'1150', N'1011', N'1010'),
    (N'1110', N'1012', N'1010'), (N'1120', N'1012', N'1010'), (N'1130', N'1012', N'1010'),
    (N'1140', N'1012', N'1010'),
    (N'1200', N'1013', N'1010'), (N'1300', N'1014', N'1010'),
    (N'1400', N'1015', N'1010'), (N'2320', N'1015', N'2000'),
    (N'2100', N'2002', N'2000'), (N'2200', N'2003', N'2000'),
    (N'2300', N'2004', N'2000'), (N'2310', N'2004', N'2000'), (N'2330', N'2004', N'2000'),
    (N'2400', N'2004', N'2000'), (N'2500', N'2005', N'2000'),
    (N'3100', N'3001', N'3000'), (N'3200', N'3001', N'3000'), (N'3400', N'3001', N'3000'),
    (N'3300', N'3002', N'3000'),
    (N'4100', N'4001', N'4000'), (N'4200', N'4001', N'4000'),
    (N'4300', N'4003', N'4000'), (N'4310', N'4003', N'4000'),
    (N'5100', N'5001', N'5000'), (N'5150', N'5001', N'5000'), (N'5160', N'5001', N'5000'),
    (N'5250', N'5001', N'5000'), (N'5470', N'5001', N'5000'),
    (N'5200', N'5002', N'5000'), (N'5210', N'5002', N'5000'), (N'5220', N'5002', N'5000'),
    (N'5460', N'5002', N'5000'),
    (N'5300', N'5003', N'5000'), (N'5310', N'5003', N'5000'), (N'5320', N'5003', N'5000'),
    (N'5330', N'5003', N'5000'), (N'5340', N'5003', N'5000'), (N'5350', N'5003', N'5000'),
    (N'5360', N'5003', N'5000'), (N'5390', N'5003', N'5000'), (N'5420', N'5003', N'5000'),
    (N'5430', N'5003', N'5000'), (N'5440', N'5003', N'5000'), (N'5480', N'5003', N'5000'),
    (N'5370', N'5004', N'5000'), (N'5380', N'5004', N'5000'), (N'5400', N'5004', N'5000'),
    (N'5490', N'5004', N'5000'),
    (N'5410', N'5005', N'5000'), (N'5450', N'5005', N'5000'), (N'5900', N'5005', N'5000');

    UPDATE a SET parent_account_id = grp.account_id
    FROM accounts a
    JOIN @m m ON m.ledger = a.account_code
    JOIN @g g ON g.code = m.grp
    JOIN accounts grp ON grp.account_code = m.grp AND grp.account_name_en = g.en
    LEFT JOIN accounts p ON p.account_id = a.parent_account_id
    WHERE grp.account_id <> a.account_id
      AND (a.parent_account_id IS NULL OR p.account_code = m.oldp);

    -- Employee Loans is money staff owe the shop: an asset (it was filed as one, outside any group)
    UPDATE accounts SET account_type = N'asset' WHERE account_code = N'2320' AND account_type <> N'asset';
END;
GO
