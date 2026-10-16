-- ============================================================
-- DayBill ERP v6.9.0 — repairs (runs LAST: zzz_ sorts after zz_zatca2)
-- Databases made by the older one-file installer missed three things
-- because some patches ran before the table they change existed.
-- Idempotent: safe on every database, changes nothing that is right.
-- ============================================================

-- ZATCA Phase 2: an e-invoicing unit per counter (till)
IF OBJECT_ID('zatca_egs','U') IS NOT NULL AND COL_LENGTH('zatca_egs','counter_id') IS NULL
    EXEC(N'ALTER TABLE zatca_egs ADD counter_id INT NULL');
GO

-- Opening Balance Equity account used by Opening Balances
IF OBJECT_ID('account_settings','U') IS NOT NULL
    EXEC(N'IF NOT EXISTS (SELECT 1 FROM account_settings WHERE setting_key=''default_opening_equity'')
             INSERT INTO account_settings (setting_key, account_code)
             VALUES (''default_opening_equity'', ''3400'');');
GO

-- the company row (empty — the first-run wizard asks for the details)
IF OBJECT_ID('company','U') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM company)
    INSERT INTO company (company_name_en, company_name_ar, vat_registration_no)
    VALUES (N'Your Company Name', N'اسم شركتك', N'');
GO
