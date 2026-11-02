-- ============================================================
-- DayBill ERP v5.8 — Sales Quotations and Purchase Orders
-- ------------------------------------------------------------
-- Quotation : price offer to a customer  → convert to Sales Invoice
-- Purchase Order : order to a supplier    → convert to Purchase Invoice
-- Neither moves stock nor posts to accounts (only the invoice does).
-- Safe to run more than once.
-- ============================================================

IF OBJECT_ID('quotations','U') IS NULL
CREATE TABLE quotations (
    quote_id             INT IDENTITY(1,1) PRIMARY KEY,
    quote_number         NVARCHAR(50) NOT NULL UNIQUE,
    quote_date           DATE NOT NULL,
    valid_until          DATE NULL,
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

IF OBJECT_ID('quotation_lines','U') IS NULL
CREATE TABLE quotation_lines (
    line_id              INT IDENTITY(1,1) PRIMARY KEY,
    quote_id             INT NOT NULL REFERENCES quotations(quote_id) ON DELETE CASCADE,
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
    line_total           DECIMAL(18,2) DEFAULT 0
);
GO

IF OBJECT_ID('purchase_orders','U') IS NULL
CREATE TABLE purchase_orders (
    po_id                INT IDENTITY(1,1) PRIMARY KEY,
    po_number            NVARCHAR(50) NOT NULL UNIQUE,
    po_date              DATE NOT NULL,
    expected_date        DATE NULL,
    supplier_id          INT NULL REFERENCES suppliers(supplier_id),
    supplier_name_en     NVARCHAR(200),
    supplier_name_ar     NVARCHAR(200),
    supplier_vat_no      NVARCHAR(20),
    reference            NVARCHAR(100),
    subtotal_amount      DECIMAL(18,2) DEFAULT 0,
    discount_amount      DECIMAL(18,2) DEFAULT 0,
    taxable_amount       DECIMAL(18,2) DEFAULT 0,
    vat_amount           DECIMAL(18,2) DEFAULT 0,
    total_amount         DECIMAL(18,2) DEFAULT 0,
    status               NVARCHAR(20) DEFAULT 'open',
    converted_purchase_id INT NULL,
    notes_en             NVARCHAR(500),
    created_by           INT NULL,
    created_at           DATETIME DEFAULT GETDATE(),
    updated_at           DATETIME NULL
);
GO

IF OBJECT_ID('purchase_order_lines','U') IS NULL
CREATE TABLE purchase_order_lines (
    line_id              INT IDENTITY(1,1) PRIMARY KEY,
    po_id                INT NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
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
    line_total           DECIMAL(18,2) DEFAULT 0
);
GO

PRINT 'Quotations & Purchase Orders patch applied.';
GO
