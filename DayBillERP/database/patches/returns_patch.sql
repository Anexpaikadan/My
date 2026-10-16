-- ============================================================
-- DayBill ERP - Sales Return & Purchase Return tables
-- Safe to run repeatedly (guarded with IF NOT EXISTS).
-- ============================================================

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='sales_returns' AND xtype='U')
CREATE TABLE sales_returns (
    return_id           INT IDENTITY(1,1) PRIMARY KEY,
    return_number       NVARCHAR(30) NOT NULL,
    return_date         NVARCHAR(20),
    original_invoice_no NVARCHAR(30),
    customer_id         INT,
    customer_name_en    NVARCHAR(200),
    customer_name_ar    NVARCHAR(200),
    customer_vat_no     NVARCHAR(20),
    subtotal_amount     DECIMAL(18,2) DEFAULT 0,
    discount_amount     DECIMAL(18,2) DEFAULT 0,
    taxable_amount      DECIMAL(18,2) DEFAULT 0,
    vat_amount          DECIMAL(18,2) DEFAULT 0,
    total_amount        DECIMAL(18,2) DEFAULT 0,
    payment_method      NVARCHAR(20),
    notes_en            NVARCHAR(500),
    return_status       NVARCHAR(20) DEFAULT 'confirmed',
    created_at          DATETIME DEFAULT GETDATE()
);

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='sales_return_lines' AND xtype='U')
CREATE TABLE sales_return_lines (
    line_id             INT IDENTITY(1,1) PRIMARY KEY,
    return_id           INT NOT NULL,
    line_number         INT,
    product_id          INT,
    product_code        NVARCHAR(50),
    product_name_en     NVARCHAR(200),
    product_name_ar     NVARCHAR(200),
    quantity            DECIMAL(18,3) DEFAULT 0,
    unit_of_measure_en  NVARCHAR(50),
    unit_price          DECIMAL(18,2) DEFAULT 0,
    discount_amount     DECIMAL(18,2) DEFAULT 0,
    line_amount         DECIMAL(18,2) DEFAULT 0,
    vat_category_code   NVARCHAR(5) DEFAULT 'S',
    vat_rate            DECIMAL(5,2) DEFAULT 15,
    vat_amount          DECIMAL(18,2) DEFAULT 0,
    line_total          DECIMAL(18,2) DEFAULT 0
);

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='purchase_returns' AND xtype='U')
CREATE TABLE purchase_returns (
    return_id           INT IDENTITY(1,1) PRIMARY KEY,
    return_number       NVARCHAR(30) NOT NULL,
    return_date         NVARCHAR(20),
    original_purchase_no NVARCHAR(30),
    supplier_id         INT,
    supplier_name_en    NVARCHAR(200),
    supplier_name_ar    NVARCHAR(200),
    supplier_vat_no     NVARCHAR(20),
    subtotal_amount     DECIMAL(18,2) DEFAULT 0,
    discount_amount     DECIMAL(18,2) DEFAULT 0,
    taxable_amount      DECIMAL(18,2) DEFAULT 0,
    vat_amount          DECIMAL(18,2) DEFAULT 0,
    total_amount        DECIMAL(18,2) DEFAULT 0,
    payment_method      NVARCHAR(20),
    notes_en            NVARCHAR(500),
    return_status       NVARCHAR(20) DEFAULT 'confirmed',
    created_at          DATETIME DEFAULT GETDATE()
);

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='purchase_return_lines' AND xtype='U')
CREATE TABLE purchase_return_lines (
    line_id             INT IDENTITY(1,1) PRIMARY KEY,
    return_id           INT NOT NULL,
    line_number         INT,
    product_id          INT,
    product_code        NVARCHAR(50),
    product_name_en     NVARCHAR(200),
    product_name_ar     NVARCHAR(200),
    quantity            DECIMAL(18,3) DEFAULT 0,
    unit_of_measure_en  NVARCHAR(50),
    unit_price          DECIMAL(18,2) DEFAULT 0,
    discount_amount     DECIMAL(18,2) DEFAULT 0,
    line_amount         DECIMAL(18,2) DEFAULT 0,
    vat_category_code   NVARCHAR(5) DEFAULT 'S',
    vat_rate            DECIMAL(5,2) DEFAULT 15,
    vat_amount          DECIMAL(18,2) DEFAULT 0,
    line_total          DECIMAL(18,2) DEFAULT 0
);
PRINT 'Returns tables ready.';
