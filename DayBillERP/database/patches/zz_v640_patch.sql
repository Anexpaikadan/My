-- ============================================================
-- DayBill ERP - v6.4.0 database update
-- ------------------------------------------------------------
--  Stock count  every counted item (phone / desktop) with the system
--               quantity, the counted quantity, the difference and its
--               value — the cycle-count plan (A weekly, B monthly,
--               C quarterly) knows what was counted when
--  POS          removed lines / cleared bills (cashier watch)
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('stock_count_log','U') IS NULL
CREATE TABLE stock_count_log (
    log_id        INT IDENTITY(1,1) PRIMARY KEY,
    product_id    INT NOT NULL,
    branch_id     INT NULL,
    counted_at    DATETIME DEFAULT GETDATE(),
    count_date    DATE NULL,
    system_qty    DECIMAL(18,4) DEFAULT 0,
    counted_qty   DECIMAL(18,4) DEFAULT 0,
    diff_qty      DECIMAL(18,4) DEFAULT 0,
    unit_cost     DECIMAL(18,4) DEFAULT 0,
    diff_value    DECIMAL(18,2) DEFAULT 0,
    status        NVARCHAR(20) DEFAULT 'applied',
    doc_id        INT NULL,
    source        NVARCHAR(20) NULL,
    counted_by    INT NULL,
    approved_by   INT NULL,
    note          NVARCHAR(300) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_stock_count_log_product')
    CREATE INDEX IX_stock_count_log_product ON stock_count_log(product_id, count_date);
GO

IF OBJECT_ID('pos_voids','U') IS NULL
CREATE TABLE pos_voids (
    void_id       INT IDENTITY(1,1) PRIMARY KEY,
    void_at       DATETIME DEFAULT GETDATE(),
    void_date     DATE NULL,
    user_id       INT NULL,
    shift_id      INT NULL,
    counter_id    INT NULL,
    kind          NVARCHAR(20) NOT NULL,          -- line | clear | qty_down
    product_id    INT NULL,
    product_name  NVARCHAR(300) NULL,
    quantity      DECIMAL(18,4) DEFAULT 0,
    amount        DECIMAL(18,2) DEFAULT 0
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_pos_voids_date')
    CREATE INDEX IX_pos_voids_date ON pos_voids(void_date, user_id);
GO

PRINT 'DayBill v6.4.0 database update applied (stock count log, POS voids).';
GO
