-- ============================================================
-- DayBill ERP - Financial Year Management
-- ------------------------------------------------------------
-- Backs Settings -> Financial Year (create/close/lock, opening
-- balances). Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='financial_years')
CREATE TABLE financial_years (
    fy_id       INT IDENTITY(1,1) PRIMARY KEY,
    label       NVARCHAR(40) NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    is_closed   BIT DEFAULT 0,
    locked      BIT DEFAULT 0,
    created_at  DATETIME DEFAULT GETDATE(),
    closed_at   DATETIME NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='fy_opening_balances')
CREATE TABLE fy_opening_balances (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    fy_id       INT NOT NULL REFERENCES financial_years(fy_id),
    account_id  INT NOT NULL,
    amount      DECIMAL(18,2) DEFAULT 0,
    side        NVARCHAR(6) DEFAULT 'debit',   -- debit / credit
    created_at  DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_fy_dates')
    CREATE INDEX IX_fy_dates ON financial_years(start_date, end_date);
GO

-- seed the current calendar year if the table is empty, so the app
-- always has at least one open financial year to post into
IF NOT EXISTS (SELECT 1 FROM financial_years)
INSERT INTO financial_years (label, start_date, end_date, is_closed)
VALUES (CONCAT('FY ', YEAR(GETDATE())),
        CAST(CONCAT(YEAR(GETDATE()), '-01-01') AS DATE),
        CAST(CONCAT(YEAR(GETDATE()), '-12-31') AS DATE), 0);
GO

PRINT '✅ Financial year patch applied.';
GO
