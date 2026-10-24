-- ============================================================
-- DayBill ERP v5.8 — Price change log (for shelf labels)
-- Every selling-price change (and every new priced item) is logged
-- so Inventory ▸ Price Change Labels can reprint the shelf labels.
-- ============================================================

IF OBJECT_ID('price_change_log','U') IS NULL
CREATE TABLE price_change_log (
    log_id          INT IDENTITY(1,1) PRIMARY KEY,
    product_id      INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    unit_id         INT NULL,
    unit_name       NVARCHAR(50),
    barcode         NVARCHAR(100),
    old_price       DECIMAL(18,4) NULL,
    new_price       DECIMAL(18,4) NOT NULL,
    source          NVARCHAR(30),
    changed_by      INT NULL,
    changed_at      DATETIME DEFAULT GETDATE(),
    label_printed   BIT DEFAULT 0,
    printed_at      DATETIME NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_price_change_pending')
    CREATE INDEX IX_price_change_pending ON price_change_log(label_printed, changed_at);
GO

PRINT 'Price change log patch applied.';
GO
