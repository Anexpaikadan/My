-- ============================================================
-- DayBill ERP v6.9.2 — customer loyalty points
--   loyalty_ledger  one row per movement: earned on a sale (+), spent on
--                   a bill (−), taken back by a return (−), by hand (±)
--   sales_invoices.loyalty_points_redeemed  points spent on that bill
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('loyalty_ledger','U') IS NULL
CREATE TABLE loyalty_ledger (
    entry_id     INT IDENTITY(1,1) PRIMARY KEY,
    customer_id  INT NOT NULL,
    source_type  NVARCHAR(20) NOT NULL,          -- sales | sales_return | adjust
    source_id    INT NULL,
    points       INT NOT NULL,
    amount       DECIMAL(18,2) NULL,             -- SAR value of points spent
    note         NVARCHAR(200) NULL,
    entry_date   DATETIME NOT NULL DEFAULT GETDATE()
);
GO
IF OBJECT_ID('loyalty_ledger','U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_loyalty_customer'
                   AND object_id=OBJECT_ID('loyalty_ledger'))
    CREATE INDEX IX_loyalty_customer ON loyalty_ledger(customer_id);
GO
IF OBJECT_ID('loyalty_ledger','U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_loyalty_source'
                   AND object_id=OBJECT_ID('loyalty_ledger'))
    CREATE INDEX IX_loyalty_source ON loyalty_ledger(source_type, source_id);
GO
IF OBJECT_ID('sales_invoices','U') IS NOT NULL
   AND COL_LENGTH('sales_invoices','loyalty_points_redeemed') IS NULL
    EXEC(N'ALTER TABLE sales_invoices ADD loyalty_points_redeemed INT NULL');
GO
