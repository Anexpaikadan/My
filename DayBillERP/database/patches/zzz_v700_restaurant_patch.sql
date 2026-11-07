-- ============================================================
-- DayBill ERP v7.0 — Restaurant module
--   rest_areas               dining areas (Hall, Family, Terrace …)
--   rest_tables              tables: name, area, seats, sort, active
--   rest_stations            kitchen stations (Kitchen, Grill, Drinks …)
--                            and the printer each one prints its KOT on
--   rest_station_categories  which product category goes to which station
--                            (station_id NULL = never sent to the kitchen)
--   rest_orders              one running or finished order: Dine-in /
--                            Takeaway / Delivery, table, guests, waiter,
--                            delivery customer + driver, status, the POS
--                            bill (sales_invoices.invoice_id) when paid
--   rest_order_lines         what the order holds while it is running
--                            (the POS screen of the table)
--   rest_kots / rest_kot_lines   kitchen order tickets; a line with a
--                            NEGATIVE quantity cancels an item sent before
-- The bill is a normal POS sale, written when the order is paid, so
-- stock, recipes (ingredients), VAT and the books post as for any sale.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('rest_areas','U') IS NULL
CREATE TABLE rest_areas (
    area_id         INT IDENTITY(1,1) PRIMARY KEY,
    area_name       NVARCHAR(100) NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('rest_tables','U') IS NULL
CREATE TABLE rest_tables (
    table_id        INT IDENTITY(1,1) PRIMARY KEY,
    table_name      NVARCHAR(50) NOT NULL,
    area_id         INT NULL,
    seats           INT NOT NULL DEFAULT 4,
    sort_order      INT NOT NULL DEFAULT 0,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_tables_area')
    CREATE INDEX IX_rest_tables_area ON rest_tables(area_id);
GO

IF OBJECT_ID('rest_stations','U') IS NULL
CREATE TABLE rest_stations (
    station_id      INT IDENTITY(1,1) PRIMARY KEY,
    station_name    NVARCHAR(100) NOT NULL,
    printer_name    NVARCHAR(200) NULL,          -- empty = the default kitchen printer
    paper_mm        INT NOT NULL DEFAULT 80,     -- 58 / 80
    copies          INT NOT NULL DEFAULT 1,
    sort_order      INT NOT NULL DEFAULT 0,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('rest_station_categories','U') IS NULL
CREATE TABLE rest_station_categories (
    category_id     INT NOT NULL PRIMARY KEY,
    station_id      INT NULL                     -- NULL = not sent to the kitchen
);
GO

IF OBJECT_ID('rest_orders','U') IS NULL
CREATE TABLE rest_orders (
    order_id            INT IDENTITY(1,1) PRIMARY KEY,
    order_no            INT NOT NULL,                -- running number of the day (#1, #2 …)
    order_date          DATE NOT NULL DEFAULT CAST(GETDATE() AS DATE),
    order_type          NVARCHAR(20) NOT NULL DEFAULT N'Dine-in',   -- Dine-in / Takeaway / Delivery
    table_id            INT NULL,
    guests              INT NULL,
    waiter_name         NVARCHAR(100) NULL,
    customer_name       NVARCHAR(200) NULL,          -- delivery / takeaway customer
    customer_phone      NVARCHAR(30) NULL,
    delivery_address    NVARCHAR(500) NULL,
    driver_name         NVARCHAR(100) NULL,
    status              NVARCHAR(20) NOT NULL DEFAULT N'open',      -- open / billed / closed / cancelled / merged
    invoice_id          INT NULL,                    -- the POS bill (sales_invoices) once paid
    merged_into         INT NULL,                    -- merged: the order it went into
    service_on          BIT NOT NULL DEFAULT 1,      -- dine-in service charge on this order
    running_total       DECIMAL(18,2) NOT NULL DEFAULT 0,
    bill_printed_at     DATETIME NULL,
    bill_total          DECIMAL(18,2) NULL,          -- total on the printed bill
    cancel_reason       NVARCHAR(200) NULL,
    notes               NVARCHAR(500) NULL,
    opened_at           DATETIME NOT NULL DEFAULT GETDATE(),
    closed_at           DATETIME NULL,
    opened_by           INT NULL,
    closed_by           INT NULL,
    version             INT NOT NULL DEFAULT 1,      -- +1 on every save (two PCs on one order)
    updated_at          DATETIME NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_orders_status')
    CREATE INDEX IX_rest_orders_status ON rest_orders(status, table_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_orders_invoice')
    CREATE INDEX IX_rest_orders_invoice ON rest_orders(invoice_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_orders_day')
    CREATE INDEX IX_rest_orders_day ON rest_orders(order_date, order_no);
GO

IF OBJECT_ID('rest_order_lines','U') IS NULL
CREATE TABLE rest_order_lines (
    line_id             INT IDENTITY(1,1) PRIMARY KEY,
    order_id            INT NOT NULL REFERENCES rest_orders(order_id) ON DELETE CASCADE,
    line_no             INT NOT NULL DEFAULT 0,
    product_id          INT NULL,
    product_code        NVARCHAR(50) NULL,
    product_name_en     NVARCHAR(200) NOT NULL,
    product_name_ar     NVARCHAR(200) NULL,
    unit_name           NVARCHAR(50) NULL,
    factor              DECIMAL(18,6) NOT NULL DEFAULT 1,
    quantity            DECIMAL(18,3) NOT NULL,
    unit_price          DECIMAL(18,4) NOT NULL DEFAULT 0,   -- the rate as typed on the POS
    price_incl          BIT NOT NULL DEFAULT 1,             -- that rate includes VAT
    price_typed         BIT NOT NULL DEFAULT 0,             -- the cashier typed the rate
    vat_rate            DECIMAL(5,2) NOT NULL DEFAULT 0,
    vat_code            NVARCHAR(5) NULL,
    vat_category_id     INT NULL,
    line_total          DECIMAL(18,2) NOT NULL DEFAULT 0,
    kitchen_note        NVARCHAR(200) NULL                  -- "no onion", "extra spicy"
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_order_lines_order')
    CREATE INDEX IX_rest_order_lines_order ON rest_order_lines(order_id);
GO

IF OBJECT_ID('rest_kots','U') IS NULL
CREATE TABLE rest_kots (
    kot_id              INT IDENTITY(1,1) PRIMARY KEY,
    kot_no              INT NOT NULL,                -- running number of the day
    kot_date            DATE NOT NULL DEFAULT CAST(GETDATE() AS DATE),
    order_id            INT NOT NULL,
    station_id          INT NULL,
    station_name        NVARCHAR(100) NULL,
    status              NVARCHAR(20) NOT NULL DEFAULT N'new',       -- new / preparing / ready / served
    sent_at             DATETIME NOT NULL DEFAULT GETDATE(),
    sent_by             INT NULL,
    started_at          DATETIME NULL,
    ready_at            DATETIME NULL,
    served_at           DATETIME NULL,
    print_count         INT NOT NULL DEFAULT 0,
    kot_note            NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_kots_order')
    CREATE INDEX IX_rest_kots_order ON rest_kots(order_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_kots_status')
    CREATE INDEX IX_rest_kots_status ON rest_kots(status, sent_at);
GO

IF OBJECT_ID('rest_kot_lines','U') IS NULL
CREATE TABLE rest_kot_lines (
    kot_line_id         INT IDENTITY(1,1) PRIMARY KEY,
    kot_id              INT NOT NULL REFERENCES rest_kots(kot_id) ON DELETE CASCADE,
    product_id          INT NULL,
    product_name        NVARCHAR(200) NOT NULL,
    product_name_ar     NVARCHAR(200) NULL,
    unit_name           NVARCHAR(50) NULL,
    quantity            DECIMAL(18,3) NOT NULL,      -- negative = CANCEL (item taken off)
    unit_price          DECIMAL(18,4) NULL,          -- price per unit with VAT (value of a cancel)
    kitchen_note        NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_rest_kot_lines_kot')
    CREATE INDEX IX_rest_kot_lines_kot ON rest_kot_lines(kot_id);
GO
