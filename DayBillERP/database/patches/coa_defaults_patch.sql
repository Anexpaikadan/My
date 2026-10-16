-- ============================================================
-- DayBill ERP - Standard chart of accounts (Saudi retail)
-- Adds the accounts a shop needs that were still missing and puts
-- every standard account under its group so the chart shows as a
-- tree. Only adds / fills blanks — never renames or moves an
-- account the user already set up. Safe to run many times.
-- ============================================================
DECLARE @acc TABLE (code NVARCHAR(20), en NVARCHAR(200), ar NVARCHAR(200),
                    typ NVARCHAR(30), parent NVARCHAR(20));
INSERT INTO @acc VALUES
 ('1000', N'Assets',                        N'الأصول',                     'asset',     NULL),
 ('1010', N'Current Assets',                N'الأصول المتداولة',            'asset',     '1000'),
 ('1100', N'Cash',                          N'النقد',                       'asset',     '1010'),
 ('1110', N'Bank',                          N'البنك',                       'asset',     '1010'),
 ('1120', N'Card / POS Clearing',           N'مقاصة البطاقات',              'asset',     '1010'),
 ('1130', N'Savings Account',               N'حساب التوفير',                'asset',     '1010'),
 ('1140', N'Online Payment Gateway',        N'بوابة الدفع الإلكتروني',      'asset',     '1010'),
 ('1150', N'Petty Cash',                    N'العهدة النقدية',              'asset',     '1010'),
 ('1200', N'Accounts Receivable',           N'حسابات القبض',                'asset',     '1010'),
 ('1300', N'Inventory',                     N'المخزون',                     'asset',     '1010'),
 ('1400', N'Advances & Prepaid Expenses',   N'دفعات مقدمة ومصروفات مدفوعة مقدماً', 'asset', '1010'),
 ('1500', N'Fixed Assets',                  N'الأصول الثابتة',              'asset',     '1000'),
 ('1510', N'Furniture & Fixtures',          N'الأثاث والتجهيزات',            'asset',     '1500'),
 ('1520', N'Equipment & Computers',         N'المعدات والحاسبات',            'asset',     '1500'),
 ('1530', N'Vehicles',                      N'السيارات',                     'asset',     '1500'),
 ('1590', N'Accumulated Depreciation',      N'مجمع الإهلاك',                'asset',     '1500'),
 ('2000', N'Liabilities',                   N'الخصوم',                      'liability', NULL),
 ('2100', N'Accounts Payable',              N'حسابات الدفع',                'liability', '2000'),
 ('2200', N'VAT Payable',                   N'ضريبة القيمة المضافة المستحقة', 'liability', '2000'),
 ('2210', N'VAT Collected (Output)',        N'ضريبة المخرجات',              'liability', '2200'),
 ('2220', N'VAT Paid (Input)',              N'ضريبة المدخلات',              'liability', '2200'),
 ('2300', N'Salaries Payable',              N'رواتب مستحقة',                'liability', '2000'),
 ('2310', N'GOSI Payable',                  N'تأمينات مستحقة',              'liability', '2000'),
 ('2330', N'End of Service Provision',      N'مخصص نهاية الخدمة',           'liability', '2000'),
 ('2400', N'Accrued Expenses',              N'مصروفات مستحقة',              'liability', '2000'),
 ('2500', N'Loans Payable',                 N'قروض',                        'liability', '2000'),
 ('3000', N'Equity',                        N'حقوق الملكية',                'equity',    NULL),
 ('3100', N'Owner''s Capital',              N'رأس المال',                   'equity',    '3000'),
 ('3200', N'Owner''s Drawings',             N'المسحوبات الشخصية',           'equity',    '3000'),
 ('3300', N'Retained Earnings',             N'الأرباح المبقاة',             'equity',    '3000'),
 ('3400', N'Opening Balance Equity',        N'أرصدة افتتاحية',              'equity',    '3000'),
 ('4000', N'Revenue',                       N'الإيرادات',                   'revenue',   NULL),
 ('4100', N'Sales Revenue',                 N'إيرادات المبيعات',            'revenue',   '4000'),
 ('4200', N'Sales Returns',                 N'مردودات المبيعات',            'revenue',   '4000'),
 ('4300', N'Other Income',                  N'إيرادات أخرى',               'revenue',   '4000'),
 ('4310', N'Discount Received',             N'خصم مكتسب',                   'revenue',   '4000'),
 ('5000', N'Expenses',                      N'المصروفات',                   'expense',   NULL),
 ('5100', N'Cost of Goods Sold',            N'تكلفة البضاعة المباعة',       'expense',   '5000'),
 ('5150', N'Purchase Returns',              N'مردودات المشتريات',           'expense',   '5000'),
 ('5160', N'Stock Adjustment',              N'تسوية المخزون',               'expense',   '5000'),
 ('5200', N'Salaries Expense',              N'مصروف الرواتب',               'expense',   '5000'),
 ('5210', N'GOSI Expense (Employer)',       N'مصروف التأمينات',             'expense',   '5000'),
 ('5220', N'End of Service Expense',        N'مصروف نهاية الخدمة',          'expense',   '5000'),
 ('5300', N'Rent Expense',                  N'مصروف الإيجار',               'expense',   '5000'),
 ('5310', N'Electricity Expense',           N'مصروف الكهرباء',              'expense',   '5000'),
 ('5320', N'Fuel Expense',                  N'مصروف الوقود',                'expense',   '5000'),
 ('5330', N'Office Expense',                N'مصروفات مكتبية',              'expense',   '5000'),
 ('5340', N'Water Expense',                 N'مصروف المياه',                'expense',   '5000'),
 ('5350', N'Telephone & Internet',          N'الهاتف والإنترنت',            'expense',   '5000'),
 ('5360', N'Maintenance & Repairs',         N'الصيانة والإصلاح',            'expense',   '5000'),
 ('5370', N'Transport & Delivery',          N'النقل والتوصيل',              'expense',   '5000'),
 ('5380', N'Advertising',                   N'الدعاية والإعلان',            'expense',   '5000'),
 ('5390', N'General Expense',               N'مصروفات عامة',                'expense',   '5000'),
 ('5400', N'Discount Allowed',              N'خصم مسموح به',                'expense',   '5000'),
 ('5410', N'Bank Charges',                  N'عمولات بنكية',                'expense',   '5000'),
 ('5420', N'Government Fees & Licences',    N'رسوم حكومية وتراخيص',         'expense',   '5000'),
 ('5430', N'Insurance Expense',             N'مصروف التأمين',               'expense',   '5000'),
 ('5440', N'Depreciation Expense',          N'مصروف الإهلاك',               'expense',   '5000'),
 ('5450', N'Cash Shortage / Excess',        N'عجز / زيادة الصندوق',          'expense',   '5000'),
 ('5900', N'Rounding Difference',           N'فروقات التقريب',              'expense',   '5000');

INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type)
SELECT a.code, a.en, a.ar, a.typ FROM @acc a
 WHERE NOT EXISTS (SELECT 1 FROM accounts x WHERE x.account_code = a.code);

UPDATE x SET parent_account_id = p.account_id
  FROM accounts x
  JOIN @acc a ON a.code = x.account_code
  JOIN accounts p ON p.account_code = a.parent
 WHERE x.parent_account_id IS NULL AND a.parent IS NOT NULL;
GO

IF EXISTS (SELECT 1 FROM sys.tables WHERE name='account_settings')
   AND NOT EXISTS (SELECT 1 FROM account_settings WHERE setting_key='default_opening_equity')
    INSERT INTO account_settings (setting_key, account_code)
    VALUES ('default_opening_equity', '3400');
GO
