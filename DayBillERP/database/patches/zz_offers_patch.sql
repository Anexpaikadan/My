-- ============================================================
-- DayBill ERP - Offers & Promotions (v5.20)
-- ------------------------------------------------------------
-- offers       : one offer (−20%, half price, special price,
--                SAR off, buy X get Y) with its date / time window
-- offer_items  : the products in the offer (special price per item)
-- sales_invoice_lines.offer_id / offer_text : which offer gave the
--                line its discount (printed on the bill, reports)
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO
IF OBJECT_ID('offers','U') IS NULL
CREATE TABLE offers (
    offer_id        INT IDENTITY(1,1) PRIMARY KEY,
    offer_name      NVARCHAR(150) NOT NULL,
    offer_name_ar   NVARCHAR(150) NULL,
    offer_type      VARCHAR(20)   NOT NULL,          -- percent | price | amount | buy_get
    offer_value     DECIMAL(18,4) NOT NULL DEFAULT 0, -- % off / SAR off per unit
    buy_qty         DECIMAL(18,3) NOT NULL DEFAULT 0, -- buy X ...
    get_qty         DECIMAL(18,3) NOT NULL DEFAULT 0, -- ... get Y
    get_pct         DECIMAL(9,4)  NOT NULL DEFAULT 100, -- the Y items: 100 = free, 50 = half
    min_qty         DECIMAL(18,3) NOT NULL DEFAULT 0, -- offer starts from this qty
    start_at        DATETIME NULL,
    end_at          DATETIME NULL,
    days_mask       VARCHAR(7)    NOT NULL DEFAULT '1111111', -- Mon..Sun
    time_from       VARCHAR(5)    NULL,               -- daily window 'HH:MM'
    time_to         VARCHAR(5)    NULL,
    for_pos         BIT NOT NULL DEFAULT 1,
    for_sales       BIT NOT NULL DEFAULT 1,
    is_active       BIT NOT NULL DEFAULT 1,
    notes           NVARCHAR(400) NULL,
    created_by      NVARCHAR(100) NULL,
    created_at      DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at      DATETIME NULL
);
GO
IF OBJECT_ID('offer_items','U') IS NULL
CREATE TABLE offer_items (
    offer_item_id   INT IDENTITY(1,1) PRIMARY KEY,
    offer_id        INT NOT NULL REFERENCES offers(offer_id) ON DELETE CASCADE,
    product_id      INT NOT NULL,
    unit_name       NVARCHAR(50)  NULL,               -- NULL = every unit
    offer_price     DECIMAL(18,4) NULL                -- special price (price offers)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_offer_items_product' AND object_id=OBJECT_ID('offer_items'))
    CREATE INDEX IX_offer_items_product ON offer_items(product_id);
GO
IF COL_LENGTH('sales_invoice_lines','offer_id') IS NULL
    ALTER TABLE sales_invoice_lines ADD offer_id INT NULL;
GO
IF COL_LENGTH('sales_invoice_lines','offer_text') IS NULL
    ALTER TABLE sales_invoice_lines ADD offer_text NVARCHAR(80) NULL;
GO
PRINT N'✅ Offers & promotions tables ready.';
GO
