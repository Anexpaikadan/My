-- ============================================================
-- DayBill ERP - Fix: Company settings missing columns
-- ------------------------------------------------------------
-- Settings -> Company writes business_type, country, state_en,
-- timezone, date_format, time_format, and language, but these
-- columns were never added to the company table — every save from
-- that page failed with "Invalid column name" errors. Idempotent.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('company','business_type') IS NULL
    ALTER TABLE company ADD business_type NVARCHAR(30);
GO
IF COL_LENGTH('company','country') IS NULL
    ALTER TABLE company ADD country NVARCHAR(50) DEFAULT 'Saudi Arabia';
GO
IF COL_LENGTH('company','state_en') IS NULL
    ALTER TABLE company ADD state_en NVARCHAR(100);
GO
IF COL_LENGTH('company','timezone') IS NULL
    ALTER TABLE company ADD timezone NVARCHAR(40) DEFAULT 'Asia/Riyadh';
GO
IF COL_LENGTH('company','date_format') IS NULL
    ALTER TABLE company ADD date_format NVARCHAR(20) DEFAULT 'dd/MM/yyyy';
GO
IF COL_LENGTH('company','time_format') IS NULL
    ALTER TABLE company ADD time_format NVARCHAR(20) DEFAULT '24-hour';
GO
IF COL_LENGTH('company','language') IS NULL
    ALTER TABLE company ADD language NVARCHAR(5) DEFAULT 'en';
GO

PRINT '✅ Company settings columns added.';
GO
