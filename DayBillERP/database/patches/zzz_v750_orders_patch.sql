-- ============================================================
-- DayBill ERP v7.5 — Sales Orders, partial delivery, print stations,
-- customer loyalty QR
--   sales_orders / sales_order_lines   customer orders → Sales Invoice
--   *_lines.delivered_qty              how much of an order line was
--                                      already invoiced (partial delivery)
--   print_stations                     Kitchen 1 / Warehouse 1 / Tailor …
--                                      each with its printer + template
--   print_station_map                  category / product → station
--   customers.loyalty_key_hash         the customer's QR card
-- ============================================================
IF OBJECT_ID('sales_orders','U') IS NULL
CREATE TABLE sales_orders (
    so_id                INT IDENTITY(1,1) PRIMARY KEY,
    so_number            NVARCHAR(50) NOT NULL UNIQUE,
    so_date              DATE NOT NULL,
    delivery_date        DATE NULL,
    customer_id          INT NULL REFERENCES customers(customer_id),
    customer_name_en     NVARCHAR(200),
    customer_name_ar     NVARCHAR(200),
    customer_vat_no      NVARCHAR(20),
    reference            NVARCHAR(100),
    subtotal_amount      DECIMAL(18,2) DEFAULT 0,
    discount_amount      DECIMAL(18,2) DEFAULT 0,
    taxable_amount       DECIMAL(18,2) DEFAULT 0,
    vat_amount           DECIMAL(18,2) DEFAULT 0,
    total_amount         DECIMAL(18,2) DEFAULT 0,
    status               NVARCHAR(20) DEFAULT 'open',
    converted_invoice_id INT NULL,
    notes_en             NVARCHAR(500),
    created_by           INT NULL,
    created_at           DATETIME DEFAULT GETDATE(),
    updated_at           DATETIME NULL
);
GO

IF OBJECT_ID('sales_order_lines','U') IS NULL
CREATE TABLE sales_order_lines (
    line_id              INT IDENTITY(1,1) PRIMARY KEY,
    so_id                INT NOT NULL REFERENCES sales_orders(so_id) ON DELETE CASCADE,
    line_number          INT NOT NULL,
    product_id           INT NULL REFERENCES products(product_id),
    product_code         NVARCHAR(50),
    product_name_en      NVARCHAR(300),
    product_name_ar      NVARCHAR(300),
    quantity             DECIMAL(18,4) DEFAULT 1,
    unit_of_measure_en   NVARCHAR(50),
    unit_price           DECIMAL(18,4) DEFAULT 0,
    discount_amount      DECIMAL(18,2) DEFAULT 0,
    line_amount          DECIMAL(18,2) DEFAULT 0,
    vat_category_id      INT NULL,
    vat_category_code    NVARCHAR(10),
    vat_rate             DECIMAL(5,2) DEFAULT 15,
    vat_amount           DECIMAL(18,2) DEFAULT 0,
    line_total           DECIMAL(18,2) DEFAULT 0,
    delivered_qty        DECIMAL(18,4) DEFAULT 0
);
GO

IF OBJECT_ID('quotation_lines','U') IS NOT NULL AND COL_LENGTH('quotation_lines','delivered_qty') IS NULL
    ALTER TABLE quotation_lines ADD delivered_qty DECIMAL(18,4) NOT NULL DEFAULT 0;
GO
IF OBJECT_ID('purchase_order_lines','U') IS NOT NULL AND COL_LENGTH('purchase_order_lines','delivered_qty') IS NULL
    ALTER TABLE purchase_order_lines ADD delivered_qty DECIMAL(18,4) NOT NULL DEFAULT 0;
GO

IF OBJECT_ID('print_stations','U') IS NULL
CREATE TABLE print_stations (
    station_id     INT IDENTITY(1,1) PRIMARY KEY,
    name           NVARCHAR(60) NOT NULL,
    kind           NVARCHAR(20) NOT NULL DEFAULT 'kitchen',   -- kitchen | warehouse | tailor | other
    printer_name   NVARCHAR(200) NULL,
    template       NVARCHAR(20) NOT NULL DEFAULT 'thermal80', -- thermal80 | thermal58 | a5 | a4
    copies         INT NOT NULL DEFAULT 1,
    employee_id    INT NULL,                                  -- tailor / picker it belongs to
    on_sales       BIT NOT NULL DEFAULT 1,
    on_pos         BIT NOT NULL DEFAULT 1,
    on_orders      BIT NOT NULL DEFAULT 1,
    show_prices    BIT NOT NULL DEFAULT 0,
    is_active      BIT NOT NULL DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('print_station_map','U') IS NULL
CREATE TABLE print_station_map (
    map_id         INT IDENTITY(1,1) PRIMARY KEY,
    station_id     INT NOT NULL REFERENCES print_stations(station_id) ON DELETE CASCADE,
    category_id    INT NULL,
    product_id     INT NULL
);
GO

IF OBJECT_ID('print_station_log','U') IS NULL
CREATE TABLE print_station_log (
    log_id         INT IDENTITY(1,1) PRIMARY KEY,
    station_id     INT NULL,
    doc_kind       NVARCHAR(30),
    doc_id         INT NULL,
    doc_number     NVARCHAR(50),
    lines          INT DEFAULT 0,
    printed        BIT DEFAULT 0,
    info           NVARCHAR(300),
    created_at     DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('customers','U') IS NOT NULL AND COL_LENGTH('customers','loyalty_key_hash') IS NULL
    ALTER TABLE customers ADD loyalty_key_hash NVARCHAR(64) NULL;
GO
