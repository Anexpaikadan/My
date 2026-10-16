-- ============================================================================
-- DayBill ERP - COMPLETE DATABASE SETUP (single file)
-- ============================================================================
-- This ONE file builds the entire DayBill ERP database from scratch.
--
-- HOW TO RUN:
--   FRESH INSTALL (recommended): run on a server that does NOT yet have a
--   DayBillERP database. Open in SSMS, press F5. It creates the database
--   and everything in it.
--
--   IF DayBillERP ALREADY EXISTS:
--   Safe to run again. Every table, index and starting row is only added
--   when it is missing (IF OBJECT_ID ... IS NULL / IF NOT EXISTS), so
--   nothing is duplicated and no data is deleted.
--   To start completely clean on an existing DB, first:
--       USE master; DROP DATABASE DayBillERP;   -- WARNING: deletes all data
--   then run this file.
--
--   NOTE: Sample product seed data is NOT included. Add products via the
--         app or the Excel import.
--
-- Sections (dependency order):
--   1. Core schema            7. Weight scale items
--   2. ZATCA Phase 2          8. User roles
--   3. Accounting & Payroll   9. Per-user rights
--   4. Inventory & Units     10. Report Designer
--   5. Search & listing      11. Barcode Designer
--   6. Multiple barcodes     12. Party Ledgers + Accounting integration
-- ============================================================================



-- ============================================================================
-- SECTION: 1. CORE SCHEMA
-- ============================================================================

-- ============================================================
-- SAUDI ARABIA BILLING ERP - COMPLETE MS SQL SCHEMA
-- ZATCA Phase 1 & Phase 2 Compliant
-- Bilingual: Arabic & English
-- VAT 15% - Standard, Zero-rated, Exempt
-- ============================================================

USE master;
GO

-- Create Database
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'DayBillERP')
BEGIN
    CREATE DATABASE DayBillERP
    COLLATE Arabic_CI_AS;  -- Arabic collation support
END
GO

USE DayBillERP;
GO

-- ============================================================
-- 1. SYSTEM SETTINGS & COMPANY
-- ============================================================

IF OBJECT_ID('company','U') IS NULL
CREATE TABLE company (
    company_id          INT IDENTITY(1,1) PRIMARY KEY,
    -- English Fields
    company_name_en     NVARCHAR(200) NOT NULL,
    address_en          NVARCHAR(500),
    city_en             NVARCHAR(100),
    -- Arabic Fields
    company_name_ar     NVARCHAR(200) NOT NULL,
    address_ar          NVARCHAR(500),
    city_ar             NVARCHAR(100),
    -- ZATCA Required Fields
    vat_registration_no NVARCHAR(15) NOT NULL,        -- 15 digits VAT number
    cr_number           NVARCHAR(20),                 -- Commercial Registration
    building_number     NVARCHAR(10),
    street_name_en      NVARCHAR(200),
    street_name_ar      NVARCHAR(200),
    district_en         NVARCHAR(100),
    district_ar         NVARCHAR(100),
    postal_code         NVARCHAR(10),
    -- Contact
    phone               NVARCHAR(20),
    email               NVARCHAR(100),
    website             NVARCHAR(200),
    -- ZATCA Phase 2
    zatca_env           NVARCHAR(20) DEFAULT 'sandbox', -- sandbox / production
    zatca_cert          NVARCHAR(MAX),                 -- Cryptographic certificate
    zatca_private_key   NVARCHAR(MAX),
    zatca_otp           NVARCHAR(10),
    -- Logo
    logo_path           NVARCHAR(500),
    -- Settings
    default_language    NVARCHAR(5) DEFAULT 'en',     -- en / ar
    currency            NVARCHAR(5) DEFAULT 'SAR',
    fiscal_year_start   NVARCHAR(5) DEFAULT '01-01',  -- MM-DD
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 2. USERS & ROLES
-- ============================================================

IF OBJECT_ID('roles','U') IS NULL
CREATE TABLE roles (
    role_id             INT IDENTITY(1,1) PRIMARY KEY,
    role_name_en        NVARCHAR(50) NOT NULL,
    role_name_ar        NVARCHAR(50) NOT NULL,
    -- Permissions (JSON-like flags)
    can_view_dashboard  BIT DEFAULT 1,
    can_manage_customers BIT DEFAULT 0,
    can_manage_products BIT DEFAULT 0,
    can_create_invoice  BIT DEFAULT 0,
    can_approve_invoice BIT DEFAULT 0,
    can_view_reports    BIT DEFAULT 0,
    can_manage_users    BIT DEFAULT 0,
    can_manage_settings BIT DEFAULT 0,
    can_zatca_submit    BIT DEFAULT 0,
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('users','U') IS NULL
CREATE TABLE users (
    user_id             INT IDENTITY(1,1) PRIMARY KEY,
    username            NVARCHAR(50) NOT NULL UNIQUE,
    password_hash       NVARCHAR(256) NOT NULL,       -- bcrypt hash
    full_name_en        NVARCHAR(100) NOT NULL,
    full_name_ar        NVARCHAR(100),
    email               NVARCHAR(100),
    phone               NVARCHAR(20),
    role_id             INT NOT NULL REFERENCES roles(role_id),
    preferred_language  NVARCHAR(5) DEFAULT 'en',     -- en / ar
    is_active           BIT DEFAULT 1,
    last_login          DATETIME,
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 3. VAT RATES (ZATCA Compliant)
-- ============================================================

IF OBJECT_ID('vat_categories','U') IS NULL
CREATE TABLE vat_categories (
    vat_category_id     INT IDENTITY(1,1) PRIMARY KEY,
    category_code       NVARCHAR(5) NOT NULL UNIQUE,  -- S=Standard, Z=Zero, E=Exempt, O=Out of scope
    category_name_en    NVARCHAR(100) NOT NULL,
    category_name_ar    NVARCHAR(100) NOT NULL,
    vat_rate            DECIMAL(5,2) NOT NULL,        -- 15.00, 0.00
    zatca_code          NVARCHAR(10),                 -- ZATCA tax category code
    description_en      NVARCHAR(500),
    description_ar      NVARCHAR(500),
    is_active           BIT DEFAULT 1
);
GO

-- Insert default VAT categories
IF NOT EXISTS (SELECT 1 FROM vat_categories)
INSERT INTO vat_categories (category_code, category_name_en, category_name_ar, vat_rate, zatca_code, description_en, description_ar)
VALUES 
('S',   'Standard Rate',        N'المعدل القياسي',           15.00, 'S',  'Standard VAT 15%',         N'ضريبة القيمة المضافة القياسية 15٪'),
('Z',   'Zero Rate',            N'معدل صفري',                 0.00,  'Z',  'Zero rated supplies',      N'الإمدادات ذات المعدل الصفري'),
('E',   'Exempt',               N'معفى',                      0.00,  'E',  'Exempt from VAT',          N'معفى من ضريبة القيمة المضافة'),
('O',   'Out of Scope',         N'خارج النطاق',               0.00,  'O',  'Out of VAT scope',         N'خارج نطاق ضريبة القيمة المضافة');
GO

-- ============================================================
-- 4. PRODUCT CATEGORIES
-- ============================================================

IF OBJECT_ID('product_categories','U') IS NULL
CREATE TABLE product_categories (
    category_id         INT IDENTITY(1,1) PRIMARY KEY,
    category_name_en    NVARCHAR(100) NOT NULL,
    category_name_ar    NVARCHAR(100) NOT NULL,
    parent_category_id  INT REFERENCES product_categories(category_id),
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 5. PRODUCTS / SERVICES
-- ============================================================

IF OBJECT_ID('products','U') IS NULL
CREATE TABLE products (
    product_id          INT IDENTITY(1,1) PRIMARY KEY,
    product_code        NVARCHAR(50) NOT NULL UNIQUE,
    product_name_en     NVARCHAR(200) NOT NULL,
    product_name_ar     NVARCHAR(200) NOT NULL,
    description_en      NVARCHAR(500),
    description_ar      NVARCHAR(500),
    category_id         INT REFERENCES product_categories(category_id),
    product_type        NVARCHAR(20) DEFAULT 'product', -- product / service
    -- Pricing
    unit_price          DECIMAL(18,2) NOT NULL DEFAULT 0,
    currency            NVARCHAR(5) DEFAULT 'SAR',
    unit_of_measure_en  NVARCHAR(50) DEFAULT 'Unit',
    unit_of_measure_ar  NVARCHAR(50) DEFAULT N'وحدة',
    -- VAT
    vat_category_id     INT REFERENCES vat_categories(vat_category_id),
    -- Inventory (for products)
    track_inventory     BIT DEFAULT 0,
    stock_quantity      DECIMAL(18,3) DEFAULT 0,
    reorder_level       DECIMAL(18,3) DEFAULT 0,
    -- Barcode
    barcode             NVARCHAR(50),
    -- Status
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 6. CUSTOMERS
-- ============================================================

IF OBJECT_ID('customers','U') IS NULL
CREATE TABLE customers (
    customer_id         INT IDENTITY(1,1) PRIMARY KEY,
    customer_code       NVARCHAR(20) NOT NULL UNIQUE,
    -- English
    customer_name_en    NVARCHAR(200) NOT NULL,
    address_en          NVARCHAR(500),
    city_en             NVARCHAR(100),
    -- Arabic
    customer_name_ar    NVARCHAR(200),
    address_ar          NVARCHAR(500),
    city_ar             NVARCHAR(100),
    -- ZATCA Required for B2B
    customer_type       NVARCHAR(10) DEFAULT 'B2C',   -- B2B / B2C
    vat_registration_no NVARCHAR(15),                 -- Required for B2B
    cr_number           NVARCHAR(20),
    -- ZATCA Address Fields (Required for Phase 2 B2B)
    building_number     NVARCHAR(10),
    street_name_en      NVARCHAR(200),
    street_name_ar      NVARCHAR(200),
    district_en         NVARCHAR(100),
    district_ar         NVARCHAR(100),
    postal_code         NVARCHAR(10),
    country_code        NVARCHAR(3) DEFAULT 'SA',
    -- Contact
    contact_person_en   NVARCHAR(100),
    contact_person_ar   NVARCHAR(100),
    phone               NVARCHAR(20),
    email               NVARCHAR(100),
    -- Financials
    credit_limit        DECIMAL(18,2) DEFAULT 0,
    payment_terms_days  INT DEFAULT 30,
    opening_balance     DECIMAL(18,2) DEFAULT 0,
    -- Status
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 7. SUPPLIERS
-- ============================================================

IF OBJECT_ID('suppliers','U') IS NULL
CREATE TABLE suppliers (
    supplier_id         INT IDENTITY(1,1) PRIMARY KEY,
    supplier_code       NVARCHAR(20) NOT NULL UNIQUE,
    supplier_name_en    NVARCHAR(200) NOT NULL,
    supplier_name_ar    NVARCHAR(200),
    address_en          NVARCHAR(500),
    address_ar          NVARCHAR(500),
    city_en             NVARCHAR(100),
    city_ar             NVARCHAR(100),
    vat_registration_no NVARCHAR(15),
    cr_number           NVARCHAR(20),
    contact_person_en   NVARCHAR(100),
    contact_person_ar   NVARCHAR(100),
    phone               NVARCHAR(20),
    email               NVARCHAR(100),
    payment_terms_days  INT DEFAULT 30,
    opening_balance     DECIMAL(18,2) DEFAULT 0,
    country_code        NVARCHAR(3) DEFAULT 'SA',
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 8. INVOICE COUNTER (ZATCA Sequential Numbering)
-- ============================================================

IF OBJECT_ID('invoice_counters','U') IS NULL
CREATE TABLE invoice_counters (
    counter_id          INT IDENTITY(1,1) PRIMARY KEY,
    invoice_type        NVARCHAR(20) NOT NULL UNIQUE, -- SALES, PURCHASE, CREDIT, DEBIT
    prefix              NVARCHAR(10) DEFAULT 'INV',
    last_number         INT DEFAULT 0,
    current_year        INT DEFAULT YEAR(GETDATE()),
    format_pattern      NVARCHAR(50) DEFAULT '{PREFIX}-{YEAR}-{NUM:6}'
);
GO

IF NOT EXISTS (SELECT 1 FROM invoice_counters)
INSERT INTO invoice_counters (invoice_type, prefix, last_number) VALUES
('SALES',    'INV',  0),
('PURCHASE', 'PUR',  0),
('CREDIT',   'CRN',  0),
('DEBIT',    'DBN',  0);
GO

-- ============================================================
-- 9. SALES INVOICES (ZATCA Compliant - Phase 1 & 2)
-- ============================================================

IF OBJECT_ID('sales_invoices','U') IS NULL
CREATE TABLE sales_invoices (
    invoice_id              INT IDENTITY(1,1) PRIMARY KEY,
    -- Invoice Identity
    invoice_number          NVARCHAR(50) NOT NULL UNIQUE,  -- Sequential number
    invoice_uuid            UNIQUEIDENTIFIER DEFAULT NEWID(), -- ZATCA required UUID
    invoice_type_code       NVARCHAR(10) DEFAULT '388',   -- UBL type: 388=Tax Invoice, 381=Credit Note, 383=Debit Note
    invoice_subtype         NVARCHAR(10) DEFAULT '0100000', -- ZATCA subtype
    -- Dates
    invoice_date            DATE NOT NULL,
    invoice_time            TIME NOT NULL DEFAULT CONVERT(TIME, GETDATE()),
    supply_date             DATE,                          -- Actual supply date
    due_date                DATE,
    -- Customer
    customer_id             INT REFERENCES customers(customer_id),
    -- Customer Snapshot (ZATCA requires at invoice time)
    customer_name_en        NVARCHAR(200),
    customer_name_ar        NVARCHAR(200),
    customer_vat_no         NVARCHAR(15),
    customer_cr_no          NVARCHAR(20),
    customer_address_en     NVARCHAR(500),
    customer_address_ar     NVARCHAR(500),
    customer_building_no    NVARCHAR(10),
    customer_street_en      NVARCHAR(200),
    customer_street_ar      NVARCHAR(200),
    customer_district_en    NVARCHAR(100),
    customer_district_ar    NVARCHAR(100),
    customer_postal_code    NVARCHAR(10),
    customer_city_en        NVARCHAR(100),
    customer_city_ar        NVARCHAR(100),
    customer_country_code   NVARCHAR(3) DEFAULT 'SA',
    -- Amounts
    subtotal_amount         DECIMAL(18,2) NOT NULL DEFAULT 0, -- Before discount & VAT
    discount_amount         DECIMAL(18,2) DEFAULT 0,
    taxable_amount          DECIMAL(18,2) NOT NULL DEFAULT 0, -- After discount, before VAT
    vat_amount              DECIMAL(18,2) NOT NULL DEFAULT 0,
    total_amount            DECIMAL(18,2) NOT NULL DEFAULT 0, -- Including VAT
    -- Currency
    currency_code           NVARCHAR(3) DEFAULT 'SAR',
    exchange_rate           DECIMAL(18,6) DEFAULT 1.000000,
    -- Payment
    payment_method          NVARCHAR(30),                  -- cash/card/bank_transfer/credit
    payment_status          NVARCHAR(20) DEFAULT 'unpaid', -- unpaid/partial/paid
    paid_amount             DECIMAL(18,2) DEFAULT 0,
    -- Reference
    po_number               NVARCHAR(50),                  -- Purchase Order ref
    reference_number        NVARCHAR(50),                  -- External reference
    -- For Credit/Debit Notes
    original_invoice_id     INT REFERENCES sales_invoices(invoice_id),
    -- Notes
    notes_en                NVARCHAR(1000),
    notes_ar                NVARCHAR(1000),
    -- Status
    invoice_status          NVARCHAR(20) DEFAULT 'draft',  -- draft/confirmed/cancelled
    -- ZATCA Phase 1
    qr_code_data            NVARCHAR(MAX),                 -- Base64 TLV encoded QR
    -- ZATCA Phase 2
    zatca_status            NVARCHAR(20) DEFAULT 'pending', -- pending/reported/cleared/rejected
    zatca_submission_id     NVARCHAR(100),
    zatca_response          NVARCHAR(MAX),
    zatca_clearance_stamp   NVARCHAR(MAX),
    zatca_xml               NVARCHAR(MAX),                 -- Generated UBL XML
    zatca_invoice_hash      NVARCHAR(256),                 -- SHA-256 hash
    zatca_submitted_at      DATETIME,
    -- Audit
    created_by              INT REFERENCES users(user_id),
    confirmed_by            INT REFERENCES users(user_id),
    created_at              DATETIME DEFAULT GETDATE(),
    updated_at              DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 10. SALES INVOICE LINES
-- ============================================================

IF OBJECT_ID('sales_invoice_lines','U') IS NULL
CREATE TABLE sales_invoice_lines (
    line_id             INT IDENTITY(1,1) PRIMARY KEY,
    invoice_id          INT NOT NULL REFERENCES sales_invoices(invoice_id) ON DELETE CASCADE,
    line_number         INT NOT NULL,
    -- Product
    product_id          INT REFERENCES products(product_id),
    -- Snapshot at invoice time
    product_code        NVARCHAR(50),
    product_name_en     NVARCHAR(200) NOT NULL,
    product_name_ar     NVARCHAR(200),
    description_en      NVARCHAR(500),
    description_ar      NVARCHAR(500),
    -- Quantities & Pricing
    quantity            DECIMAL(18,3) NOT NULL,
    unit_of_measure_en  NVARCHAR(50),
    unit_of_measure_ar  NVARCHAR(50),
    unit_price          DECIMAL(18,2) NOT NULL,
    discount_percent    DECIMAL(5,2) DEFAULT 0,
    discount_amount     DECIMAL(18,2) DEFAULT 0,
    line_amount         DECIMAL(18,2) NOT NULL,    -- qty * unit_price - discount
    -- VAT
    vat_category_id     INT REFERENCES vat_categories(vat_category_id),
    vat_category_code   NVARCHAR(5),              -- S/Z/E/O
    vat_rate            DECIMAL(5,2) DEFAULT 15.00,
    vat_amount          DECIMAL(18,2) DEFAULT 0,
    line_total          DECIMAL(18,2) NOT NULL,   -- line_amount + vat_amount
    -- ZATCA exemption reason (for Z/E/O)
    vat_exemption_code  NVARCHAR(20),
    vat_exemption_reason_en NVARCHAR(200),
    vat_exemption_reason_ar NVARCHAR(200)
);
GO

-- ============================================================
-- 11. PURCHASE INVOICES
-- ============================================================

IF OBJECT_ID('purchase_invoices','U') IS NULL
CREATE TABLE purchase_invoices (
    purchase_id         INT IDENTITY(1,1) PRIMARY KEY,
    invoice_number      NVARCHAR(50) NOT NULL UNIQUE,
    supplier_invoice_no NVARCHAR(50),              -- Supplier's own invoice number
    invoice_date        DATE NOT NULL,
    due_date            DATE,
    supplier_id         INT REFERENCES suppliers(supplier_id),
    -- Supplier Snapshot
    supplier_name_en    NVARCHAR(200),
    supplier_name_ar    NVARCHAR(200),
    supplier_vat_no     NVARCHAR(15),
    -- Amounts
    subtotal_amount     DECIMAL(18,2) DEFAULT 0,
    discount_amount     DECIMAL(18,2) DEFAULT 0,
    taxable_amount      DECIMAL(18,2) DEFAULT 0,
    vat_amount          DECIMAL(18,2) DEFAULT 0,
    total_amount        DECIMAL(18,2) DEFAULT 0,
    -- Payment
    payment_status      NVARCHAR(20) DEFAULT 'unpaid',
    paid_amount         DECIMAL(18,2) DEFAULT 0,
    -- Notes
    notes_en            NVARCHAR(1000),
    notes_ar            NVARCHAR(1000),
    invoice_status      NVARCHAR(20) DEFAULT 'draft',
    -- Audit
    created_by          INT REFERENCES users(user_id),
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('purchase_invoice_lines','U') IS NULL
CREATE TABLE purchase_invoice_lines (
    line_id             INT IDENTITY(1,1) PRIMARY KEY,
    purchase_id         INT NOT NULL REFERENCES purchase_invoices(purchase_id) ON DELETE CASCADE,
    line_number         INT NOT NULL,
    product_id          INT REFERENCES products(product_id),
    product_code        NVARCHAR(50),
    product_name_en     NVARCHAR(200) NOT NULL,
    product_name_ar     NVARCHAR(200),
    quantity            DECIMAL(18,3) NOT NULL,
    unit_of_measure_en  NVARCHAR(50),
    unit_price          DECIMAL(18,2) NOT NULL,
    discount_amount     DECIMAL(18,2) DEFAULT 0,
    line_amount         DECIMAL(18,2) NOT NULL,
    vat_category_id     INT REFERENCES vat_categories(vat_category_id),
    vat_rate            DECIMAL(5,2) DEFAULT 15.00,
    vat_amount          DECIMAL(18,2) DEFAULT 0,
    line_total          DECIMAL(18,2) NOT NULL
);
GO

-- ============================================================
-- 12. PAYMENTS (Receipts & Disbursements)
-- ============================================================

IF OBJECT_ID('payments','U') IS NULL
CREATE TABLE payments (
    payment_id          INT IDENTITY(1,1) PRIMARY KEY,
    payment_number      NVARCHAR(50) NOT NULL UNIQUE,
    payment_type        NVARCHAR(20) NOT NULL,     -- receipt / disbursement
    payment_date        DATE NOT NULL,
    -- Party
    customer_id         INT REFERENCES customers(customer_id),
    supplier_id         INT REFERENCES suppliers(supplier_id),
    party_name_en       NVARCHAR(200),
    party_name_ar       NVARCHAR(200),
    -- Amount
    amount              DECIMAL(18,2) NOT NULL,
    currency_code       NVARCHAR(3) DEFAULT 'SAR',
    -- Payment Method
    payment_method      NVARCHAR(30) NOT NULL,     -- cash/card/bank_transfer/cheque
    bank_name           NVARCHAR(100),
    cheque_number       NVARCHAR(50),
    reference_number    NVARCHAR(50),
    -- Notes
    notes_en            NVARCHAR(500),
    notes_ar            NVARCHAR(500),
    -- Audit
    created_by          INT REFERENCES users(user_id),
    created_at          DATETIME DEFAULT GETDATE()
);
GO

-- Payment allocation to invoices
IF OBJECT_ID('payment_allocations','U') IS NULL
CREATE TABLE payment_allocations (
    allocation_id       INT IDENTITY(1,1) PRIMARY KEY,
    payment_id          INT NOT NULL REFERENCES payments(payment_id),
    invoice_id          INT REFERENCES sales_invoices(invoice_id),
    purchase_id         INT REFERENCES purchase_invoices(purchase_id),
    allocated_amount    DECIMAL(18,2) NOT NULL,
    allocated_at        DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 13. ZATCA SUBMISSION LOG
-- ============================================================

IF OBJECT_ID('zatca_submissions','U') IS NULL
CREATE TABLE zatca_submissions (
    submission_id       INT IDENTITY(1,1) PRIMARY KEY,
    invoice_id          INT REFERENCES sales_invoices(invoice_id),
    invoice_number      NVARCHAR(50),
    invoice_uuid        NVARCHAR(36),
    submission_type     NVARCHAR(20),              -- reporting / clearance
    zatca_env           NVARCHAR(20),              -- sandbox / production
    -- Request
    request_xml         NVARCHAR(MAX),
    invoice_hash        NVARCHAR(256),
    -- Response
    http_status_code    INT,
    zatca_status        NVARCHAR(20),              -- REPORTED/CLEARED/ERROR
    response_body       NVARCHAR(MAX),
    warnings            NVARCHAR(MAX),
    errors              NVARCHAR(MAX),
    -- Timing
    submitted_at        DATETIME DEFAULT GETDATE(),
    submitted_by        INT REFERENCES users(user_id)
);
GO

-- ============================================================
-- 14. VAT RETURNS
-- ============================================================

IF OBJECT_ID('vat_returns','U') IS NULL
CREATE TABLE vat_returns (
    return_id           INT IDENTITY(1,1) PRIMARY KEY,
    period_from         DATE NOT NULL,
    period_to           DATE NOT NULL,
    return_year         INT NOT NULL,
    return_quarter      INT NOT NULL,              -- 1,2,3,4
    -- Sales VAT Summary
    total_sales_standard    DECIMAL(18,2) DEFAULT 0,
    total_sales_zero        DECIMAL(18,2) DEFAULT 0,
    total_sales_exempt      DECIMAL(18,2) DEFAULT 0,
    total_vat_collected     DECIMAL(18,2) DEFAULT 0,
    -- Purchase VAT Summary
    total_purchases         DECIMAL(18,2) DEFAULT 0,
    total_vat_paid          DECIMAL(18,2) DEFAULT 0,
    -- Net VAT
    net_vat_payable         DECIMAL(18,2) DEFAULT 0,  -- collected - paid
    -- Status
    return_status           NVARCHAR(20) DEFAULT 'draft', -- draft/submitted/paid
    submission_date         DATE,
    payment_date            DATE,
    -- Notes
    notes                   NVARCHAR(1000),
    created_by              INT REFERENCES users(user_id),
    created_at              DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- 15. CHART OF ACCOUNTS (Basic)
-- ============================================================

IF OBJECT_ID('accounts','U') IS NULL
CREATE TABLE accounts (
    account_id          INT IDENTITY(1,1) PRIMARY KEY,
    account_code        NVARCHAR(20) NOT NULL UNIQUE,
    account_name_en     NVARCHAR(200) NOT NULL,
    account_name_ar     NVARCHAR(200) NOT NULL,
    account_type        NVARCHAR(30) NOT NULL,    -- asset/liability/equity/revenue/expense
    parent_account_id   INT REFERENCES accounts(account_id),
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE()
);
GO

-- Basic Saudi accounts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1100')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1000', 'Assets',                      N'الأصول',                   'asset'),
('1100', 'Cash',                        N'النقد',                     'asset'),
('1200', 'Accounts Receivable',         N'حسابات القبض',              'asset'),
('1300', 'Inventory',                   N'المخزون',                   'asset'),
('2000', 'Liabilities',                 N'الخصوم',                    'liability'),
('2100', 'Accounts Payable',            N'حسابات الدفع',              'liability'),
('2200', 'VAT Payable',                 N'ضريبة القيمة المضافة المستحقة', 'liability'),
('2210', 'VAT Collected (Output)',      N'ضريبة المخرجات',            'liability'),
('2220', 'VAT Paid (Input)',            N'ضريبة المدخلات',            'liability'),
('3000', 'Equity',                      N'حقوق الملكية',              'equity'),
('4000', 'Revenue',                     N'الإيرادات',                 'revenue'),
('4100', 'Sales Revenue',               N'إيرادات المبيعات',          'revenue'),
('5000', 'Expenses',                    N'المصروفات',                 'expense'),
('5100', 'Cost of Goods Sold',          N'تكلفة البضاعة المباعة',     'expense');
GO

-- ============================================================
-- 16. AUDIT LOG
-- ============================================================

IF OBJECT_ID('audit_log','U') IS NULL
CREATE TABLE audit_log (
    log_id              INT IDENTITY(1,1) PRIMARY KEY,
    user_id             INT REFERENCES users(user_id),
    action              NVARCHAR(50) NOT NULL,     -- CREATE/UPDATE/DELETE/LOGIN
    table_name          NVARCHAR(50),
    record_id           INT,
    old_values          NVARCHAR(MAX),             -- JSON
    new_values          NVARCHAR(MAX),             -- JSON
    ip_address          NVARCHAR(50),
    created_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- STORED PROCEDURES
-- ============================================================

-- SP: Get Next Invoice Number
CREATE OR ALTER PROCEDURE sp_get_next_invoice_number
    @invoice_type   NVARCHAR(20),
    @invoice_number NVARCHAR(50) OUTPUT
AS
BEGIN
    DECLARE @prefix         NVARCHAR(10)
    DECLARE @last_number    INT
    DECLARE @current_year   INT = YEAR(GETDATE())
    DECLARE @stored_year    INT

    SELECT @prefix = prefix, @last_number = last_number, @stored_year = current_year
    FROM invoice_counters
    WHERE invoice_type = @invoice_type

    -- Reset counter if new year
    IF @stored_year <> @current_year
    BEGIN
        SET @last_number = 0
        UPDATE invoice_counters SET current_year = @current_year WHERE invoice_type = @invoice_type
    END

    SET @last_number = @last_number + 1

    UPDATE invoice_counters
    SET last_number = @last_number
    WHERE invoice_type = @invoice_type

    -- Format: INV-2025-000001
    SET @invoice_number = @prefix + '-' + CAST(@current_year AS NVARCHAR(4)) + '-' + RIGHT('000000' + CAST(@last_number AS NVARCHAR(10)), 6)
END
GO

-- SP: Calculate Invoice Totals
CREATE OR ALTER PROCEDURE sp_calculate_invoice_totals
    @invoice_id INT
AS
BEGIN
    DECLARE @subtotal   DECIMAL(18,2)
    DECLARE @discount   DECIMAL(18,2)
    DECLARE @taxable    DECIMAL(18,2)
    DECLARE @vat        DECIMAL(18,2)
    DECLARE @total      DECIMAL(18,2)

    SELECT
        @subtotal = SUM(quantity * unit_price),
        @discount = SUM(discount_amount),
        @taxable  = SUM(line_amount),
        @vat      = SUM(vat_amount),
        @total    = SUM(line_total)
    FROM sales_invoice_lines
    WHERE invoice_id = @invoice_id

    UPDATE sales_invoices
    SET
        subtotal_amount = ISNULL(@subtotal, 0),
        discount_amount = ISNULL(@discount, 0),
        taxable_amount  = ISNULL(@taxable, 0),
        vat_amount      = ISNULL(@vat, 0),
        total_amount    = ISNULL(@total, 0),
        updated_at      = GETDATE()
    WHERE invoice_id = @invoice_id
END
GO

-- SP: Get VAT Summary for Return
CREATE OR ALTER PROCEDURE sp_get_vat_summary
    @date_from  DATE,
    @date_to    DATE
AS
BEGIN
    -- Sales VAT
    SELECT
        vc.category_code,
        vc.category_name_en,
        vc.category_name_ar,
        vc.vat_rate,
        SUM(sil.line_amount)    AS taxable_amount,
        SUM(sil.vat_amount)     AS vat_amount,
        COUNT(DISTINCT si.invoice_id) AS invoice_count
    FROM sales_invoices si
    JOIN sales_invoice_lines sil ON si.invoice_id = sil.invoice_id
    JOIN vat_categories vc ON sil.vat_category_id = vc.vat_category_id
    WHERE si.invoice_date BETWEEN @date_from AND @date_to
      AND si.invoice_status = 'confirmed'
    GROUP BY vc.category_code, vc.category_name_en, vc.category_name_ar, vc.vat_rate

    -- Purchase VAT (Input Tax)
    SELECT
        SUM(pil.line_amount)    AS total_purchases,
        SUM(pil.vat_amount)     AS input_vat
    FROM purchase_invoices pi
    JOIN purchase_invoice_lines pil ON pi.purchase_id = pil.purchase_id
    WHERE pi.invoice_date BETWEEN @date_from AND @date_to
      AND pi.invoice_status = 'confirmed'
END
GO

-- ============================================================
-- VIEWS
-- ============================================================

-- View: Invoice with Customer details
CREATE OR ALTER VIEW vw_sales_invoices AS
SELECT
    si.invoice_id,
    si.invoice_number,
    si.invoice_uuid,
    si.invoice_date,
    si.invoice_type_code,
    si.customer_id,
    si.customer_name_en,
    si.customer_name_ar,
    si.customer_vat_no,
    si.subtotal_amount,
    si.discount_amount,
    si.taxable_amount,
    si.vat_amount,
    si.total_amount,
    si.payment_status,
    si.paid_amount,
    si.total_amount - si.paid_amount AS balance_due,
    si.invoice_status,
    si.zatca_status,
    si.qr_code_data,
    si.created_at,
    u.full_name_en AS created_by_name
FROM sales_invoices si
LEFT JOIN users u ON si.created_by = u.user_id;
GO

-- View: Customer Balance
CREATE OR ALTER VIEW vw_customer_balance AS
SELECT
    c.customer_id,
    c.customer_code,
    c.customer_name_en,
    c.customer_name_ar,
    c.vat_registration_no,
    ISNULL(SUM(si.total_amount), 0)     AS total_invoiced,
    ISNULL(SUM(si.paid_amount), 0)      AS total_paid,
    ISNULL(SUM(si.total_amount - si.paid_amount), 0) AS balance_due
FROM customers c
LEFT JOIN sales_invoices si ON c.customer_id = si.customer_id
    AND si.invoice_status = 'confirmed'
GROUP BY c.customer_id, c.customer_code, c.customer_name_en, c.customer_name_ar, c.vat_registration_no;
GO

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sales_invoices_date' AND object_id=OBJECT_ID('sales_invoices'))
CREATE INDEX IX_sales_invoices_date        ON sales_invoices(invoice_date);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sales_invoices_customer' AND object_id=OBJECT_ID('sales_invoices'))
CREATE INDEX IX_sales_invoices_customer    ON sales_invoices(customer_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sales_invoices_status' AND object_id=OBJECT_ID('sales_invoices'))
CREATE INDEX IX_sales_invoices_status      ON sales_invoices(invoice_status);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sales_invoices_zatca' AND object_id=OBJECT_ID('sales_invoices'))
CREATE INDEX IX_sales_invoices_zatca       ON sales_invoices(zatca_status);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_invoice_lines_invoice' AND object_id=OBJECT_ID('sales_invoice_lines'))
CREATE INDEX IX_invoice_lines_invoice      ON sales_invoice_lines(invoice_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_payments_customer' AND object_id=OBJECT_ID('payments'))
CREATE INDEX IX_payments_customer          ON payments(customer_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_audit_log_user' AND object_id=OBJECT_ID('audit_log'))
CREATE INDEX IX_audit_log_user             ON audit_log(user_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_audit_log_date' AND object_id=OBJECT_ID('audit_log'))
CREATE INDEX IX_audit_log_date             ON audit_log(created_at);
GO

-- ============================================================
-- DEFAULT DATA
-- ============================================================

-- Default Role
IF NOT EXISTS (SELECT 1 FROM roles WHERE role_name_en='Administrator')
INSERT INTO roles (role_name_en, role_name_ar, can_view_dashboard, can_manage_customers,
    can_manage_products, can_create_invoice, can_approve_invoice, can_view_reports,
    can_manage_users, can_manage_settings, can_zatca_submit)
VALUES ('Administrator', N'مدير النظام', 1, 1, 1, 1, 1, 1, 1, 1, 1);
GO

-- Default Admin User — no password yet: DayBill asks you to set one the
-- first time you sign in as "admin" (the hash below is only a placeholder).
IF NOT EXISTS (SELECT 1 FROM users WHERE username='admin')
INSERT INTO users (username, password_hash, full_name_en, full_name_ar, role_id)
VALUES ('admin', '$2b$12$placeholder_hash_change_this', 'System Administrator', N'مدير النظام', 1);
GO

-- Default Company — EMPTY on purpose (clean install). Fill it in DayBill:
-- Settings ▸ Company (name, address, 15-digit VAT number, CR, logo).
-- The first-run wizard opens while the name is still 'Your Company Name'.
IF NOT EXISTS (SELECT 1 FROM company)
INSERT INTO company (
    company_name_en, company_name_ar, vat_registration_no, country_code
) VALUES (
    N'Your Company Name', N'اسم شركتك', N'', 'SA'
);
GO

PRINT N'✅ Saudi Arabia ERP Database Schema Created Successfully!';
PRINT N'📋 Tables: 18 tables created';
PRINT N'🔧 Procedures: 3 stored procedures created';
PRINT N'👁️ Views: 2 views created';
PRINT N'📊 Indexes: 8 indexes created';
PRINT N'⚠️  IMPORTANT: Update company info and admin password before use!';
GO
GO


-- ============================================================================
-- SECTION: 2. ZATCA PHASE 2
-- ============================================================================

-- ============================================================
-- SAUDI ERP - ZATCA Phase 2 Schema Patch (Step 6)
-- Adds columns needed for cryptographic stamping & hash chain.
-- Safe to run multiple times (checks existence first).
-- ============================================================

USE DayBillERP;
GO

-- ── company: store onboarding CSID credentials ──────────────
IF COL_LENGTH('company', 'zatca_csid_token') IS NULL
    ALTER TABLE company ADD zatca_csid_token NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_csid_secret') IS NULL
    ALTER TABLE company ADD zatca_csid_secret NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_compliance_token') IS NULL
    ALTER TABLE company ADD zatca_compliance_token NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_compliance_secret') IS NULL
    ALTER TABLE company ADD zatca_compliance_secret NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_compliance_request_id') IS NULL
    ALTER TABLE company ADD zatca_compliance_request_id NVARCHAR(100);
GO
IF COL_LENGTH('company', 'zatca_csr') IS NULL
    ALTER TABLE company ADD zatca_csr NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_onboarded') IS NULL
    ALTER TABLE company ADD zatca_onboarded BIT DEFAULT 0;
GO

-- ── sales_invoices: hash chain + signed XML ─────────────────
IF COL_LENGTH('sales_invoices', 'zatca_previous_hash') IS NULL
    ALTER TABLE sales_invoices ADD zatca_previous_hash NVARCHAR(256);
GO
IF COL_LENGTH('sales_invoices', 'zatca_signed_xml') IS NULL
    ALTER TABLE sales_invoices ADD zatca_signed_xml NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_signature') IS NULL
    ALTER TABLE sales_invoices ADD zatca_signature NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_qr_phase2') IS NULL
    ALTER TABLE sales_invoices ADD zatca_qr_phase2 NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_cleared_xml') IS NULL
    ALTER TABLE sales_invoices ADD zatca_cleared_xml NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_warnings') IS NULL
    ALTER TABLE sales_invoices ADD zatca_warnings NVARCHAR(MAX);
GO

PRINT N'✅ ZATCA Phase 2 schema patch applied.';
GO
GO


-- ============================================================================
-- SECTION: 3. ACCOUNTING & PAYROLL
-- ============================================================================

-- ============================================================
-- DayBill ERP - Accounting & Payroll Schema Patch
-- Double-entry journals + Saudi payroll system
-- Safe to run multiple times.
-- ============================================================

USE DayBillERP;
GO

-- ============================================================
-- PART A — DOUBLE-ENTRY ACCOUNTING
-- ============================================================

-- Journal entries (header)
IF OBJECT_ID('journal_entries','U') IS NULL
CREATE TABLE journal_entries (
    journal_id          INT IDENTITY(1,1) PRIMARY KEY,
    journal_number      NVARCHAR(30) NOT NULL UNIQUE,
    entry_date          DATE NOT NULL,
    reference           NVARCHAR(100),
    description_en      NVARCHAR(500),
    description_ar      NVARCHAR(500),
    source_type         NVARCHAR(30),         -- manual/sales/purchase/payment/payroll
    source_id           INT,                  -- link to originating record
    total_debit         DECIMAL(18,2) DEFAULT 0,
    total_credit        DECIMAL(18,2) DEFAULT 0,
    is_posted           BIT DEFAULT 0,        -- draft vs posted
    created_by          INT,
    created_at          DATETIME DEFAULT GETDATE(),
    posted_at           DATETIME
);
GO

-- Journal lines (debit/credit per account)
IF OBJECT_ID('journal_lines','U') IS NULL
CREATE TABLE journal_lines (
    line_id             INT IDENTITY(1,1) PRIMARY KEY,
    journal_id          INT NOT NULL REFERENCES journal_entries(journal_id) ON DELETE CASCADE,
    line_number         INT NOT NULL,
    account_id          INT NOT NULL REFERENCES accounts(account_id),
    debit               DECIMAL(18,2) DEFAULT 0,
    credit              DECIMAL(18,2) DEFAULT 0,
    description         NVARCHAR(300)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_lines_account' AND object_id=OBJECT_ID('journal_lines'))
CREATE INDEX IX_journal_lines_account ON journal_lines(account_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_entries_date' AND object_id=OBJECT_ID('journal_entries'))
CREATE INDEX IX_journal_entries_date ON journal_entries(entry_date);
GO

-- ============================================================
-- PART B — EMPLOYEES
-- ============================================================

IF OBJECT_ID('departments','U') IS NULL
CREATE TABLE departments (
    department_id       INT IDENTITY(1,1) PRIMARY KEY,
    name_en             NVARCHAR(100) NOT NULL,
    name_ar             NVARCHAR(100),
    is_active           BIT DEFAULT 1
);
GO

IF OBJECT_ID('employees','U') IS NULL
CREATE TABLE employees (
    employee_id         INT IDENTITY(1,1) PRIMARY KEY,
    employee_code       NVARCHAR(20) NOT NULL UNIQUE,
    -- Personal
    full_name_en        NVARCHAR(200) NOT NULL,
    full_name_ar        NVARCHAR(200),
    national_id         NVARCHAR(20),         -- Iqama / National ID
    nationality         NVARCHAR(50),
    is_saudi            BIT DEFAULT 0,         -- affects GOSI rate
    -- Job
    department_id       INT REFERENCES departments(department_id),
    job_title_en        NVARCHAR(100),
    job_title_ar        NVARCHAR(100),
    join_date           DATE,
    -- Salary structure (monthly, SAR)
    basic_salary        DECIMAL(18,2) DEFAULT 0,
    housing_allowance   DECIMAL(18,2) DEFAULT 0,
    transport_allowance DECIMAL(18,2) DEFAULT 0,
    other_allowance     DECIMAL(18,2) DEFAULT 0,
    -- Bank (for WPS)
    bank_name           NVARCHAR(100),
    iban                NVARCHAR(34),
    -- Status
    is_active           BIT DEFAULT 1,
    end_date            DATE,                  -- set when employee leaves
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- PART C — LOANS / ADVANCES
-- ============================================================

IF OBJECT_ID('employee_loans','U') IS NULL
CREATE TABLE employee_loans (
    loan_id             INT IDENTITY(1,1) PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id),
    loan_date           DATE NOT NULL,
    loan_amount         DECIMAL(18,2) NOT NULL,
    monthly_deduction   DECIMAL(18,2) NOT NULL,
    balance             DECIMAL(18,2) NOT NULL,   -- remaining
    notes               NVARCHAR(300),
    is_settled          BIT DEFAULT 0,
    created_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- PART D — PAYROLL RUNS
-- ============================================================

IF OBJECT_ID('payroll_runs','U') IS NULL
CREATE TABLE payroll_runs (
    run_id              INT IDENTITY(1,1) PRIMARY KEY,
    run_month           INT NOT NULL,          -- 1-12
    run_year            INT NOT NULL,
    run_label           NVARCHAR(30),          -- "June 2026"
    status              NVARCHAR(20) DEFAULT 'draft',  -- draft/approved/paid
    total_gross         DECIMAL(18,2) DEFAULT 0,
    total_deductions    DECIMAL(18,2) DEFAULT 0,
    total_net           DECIMAL(18,2) DEFAULT 0,
    total_gosi_employee DECIMAL(18,2) DEFAULT 0,
    total_gosi_employer DECIMAL(18,2) DEFAULT 0,
    created_by          INT,
    created_at          DATETIME DEFAULT GETDATE(),
    approved_at         DATETIME,
    CONSTRAINT UQ_payroll_period UNIQUE (run_month, run_year)
);
GO

-- Payslip = one line per employee per run
IF OBJECT_ID('payslips','U') IS NULL
CREATE TABLE payslips (
    payslip_id          INT IDENTITY(1,1) PRIMARY KEY,
    run_id              INT NOT NULL REFERENCES payroll_runs(run_id) ON DELETE CASCADE,
    employee_id         INT NOT NULL REFERENCES employees(employee_id),
    -- Snapshot of names
    employee_name_en    NVARCHAR(200),
    employee_name_ar    NVARCHAR(200),
    -- Earnings
    basic_salary        DECIMAL(18,2) DEFAULT 0,
    housing_allowance   DECIMAL(18,2) DEFAULT 0,
    transport_allowance DECIMAL(18,2) DEFAULT 0,
    other_allowance     DECIMAL(18,2) DEFAULT 0,
    overtime_hours      DECIMAL(9,2) DEFAULT 0,
    overtime_amount     DECIMAL(18,2) DEFAULT 0,
    gross_salary        DECIMAL(18,2) DEFAULT 0,
    -- Deductions
    gosi_employee       DECIMAL(18,2) DEFAULT 0,
    gosi_employer       DECIMAL(18,2) DEFAULT 0,
    loan_deduction      DECIMAL(18,2) DEFAULT 0,
    other_deduction     DECIMAL(18,2) DEFAULT 0,
    total_deductions    DECIMAL(18,2) DEFAULT 0,
    -- Net
    net_salary          DECIMAL(18,2) DEFAULT 0,
    -- For WPS
    iban                NVARCHAR(34),
    bank_name           NVARCHAR(100),
    notes               NVARCHAR(300)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_payslips_run' AND object_id=OBJECT_ID('payslips'))
CREATE INDEX IX_payslips_run ON payslips(run_id);
GO

-- ============================================================
-- PART E — END OF SERVICE (settlement records)
-- ============================================================

IF OBJECT_ID('eos_settlements','U') IS NULL
CREATE TABLE eos_settlements (
    eos_id              INT IDENTITY(1,1) PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id),
    employee_name_en    NVARCHAR(200),
    join_date           DATE,
    end_date            DATE,
    years_served        DECIMAL(9,2),
    last_salary         DECIMAL(18,2),         -- basic + housing (wage base)
    reason              NVARCHAR(30),          -- resignation / termination
    gratuity_amount     DECIMAL(18,2),
    notes               NVARCHAR(500),
    settled_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- DEFAULT PAYROLL ACCOUNTS (added to chart of accounts)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5200')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5200', 'Salaries Expense',        N'مصروف الرواتب',          'expense'),
('5210', 'GOSI Expense (Employer)', N'مصروف التأمينات',         'expense'),
('5220', 'End of Service Expense',  N'مصروف نهاية الخدمة',      'expense'),
('2300', 'Salaries Payable',        N'رواتب مستحقة',            'liability'),
('2310', 'GOSI Payable',            N'تأمينات مستحقة',          'liability'),
('2320', 'Employee Loans',          N'سلف الموظفين',            'asset');
GO

PRINT N'✅ Accounting & Payroll schema patch applied.';
GO
GO


-- ============================================================================
-- SECTION: 4. INVENTORY & MULTI-UNITS
-- ============================================================================

-- ============================================================
-- DayBill ERP - Inventory & Multi-Units Schema Patch
-- Run AFTER daybill_erp_schema.sql
-- Safe to re-run.
-- ============================================================

USE DayBillERP;
GO

-- ── Add purchase price + reorder level to products ───────────
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='purchase_price')
    ALTER TABLE products ADD purchase_price DECIMAL(18,2) DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='reorder_level')
    ALTER TABLE products ADD reorder_level DECIMAL(18,4) DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='stock_quantity')
    ALTER TABLE products ADD stock_quantity DECIMAL(18,4) DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='default_unit_id')
    ALTER TABLE products ADD default_unit_id INT NULL;
GO

-- ── Product Units ─────────────────────────────────────────────
-- Each product can have unlimited units (Piece, Box of 12, Carton of 144…)
-- conversion_factor = how many BASE units make 1 of THIS unit
-- e.g. base=Piece, Box=12 pieces → conversion_factor=12
IF OBJECT_ID('product_units','U') IS NULL
CREATE TABLE product_units (
    unit_id             INT IDENTITY(1,1) PRIMARY KEY,
    product_id          INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    unit_name_en        NVARCHAR(50) NOT NULL,
    unit_name_ar        NVARCHAR(50),
    conversion_factor   DECIMAL(18,6) NOT NULL DEFAULT 1,
    purchase_price      DECIMAL(18,2) DEFAULT 0,
    selling_price       DECIMAL(18,2) DEFAULT 0,
    barcode             NVARCHAR(20),
    is_default          BIT DEFAULT 0,
    is_purchase_unit    BIT DEFAULT 1,
    is_sales_unit       BIT DEFAULT 1,
    is_active           BIT DEFAULT 1,
    created_at          DATETIME DEFAULT GETDATE(),
    CONSTRAINT UQ_product_unit_barcode UNIQUE (barcode)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_product_units_product' AND object_id=OBJECT_ID('product_units'))
CREATE INDEX IX_product_units_product ON product_units(product_id);
GO

-- ── Inventory Transactions (full ledger) ──────────────────────
IF OBJECT_ID('inventory_transactions','U') IS NULL
CREATE TABLE inventory_transactions (
    txn_id              INT IDENTITY(1,1) PRIMARY KEY,
    product_id          INT NOT NULL REFERENCES products(product_id),
    txn_date            DATE NOT NULL DEFAULT GETDATE(),
    txn_type            NVARCHAR(30) NOT NULL,
    -- Types: opening / purchase / sale / adjustment_in / adjustment_out / return_in / return_out
    reference_type      NVARCHAR(30),          -- purchase_invoice / sales_invoice / manual
    reference_id        INT,
    unit_id             INT REFERENCES product_units(unit_id),
    unit_name           NVARCHAR(50),
    qty_in_units        DECIMAL(18,4) DEFAULT 0,   -- quantity in the referenced unit
    qty_in_base         DECIMAL(18,4) DEFAULT 0,   -- converted to base unit
    qty_out_units       DECIMAL(18,4) DEFAULT 0,
    qty_out_base        DECIMAL(18,4) DEFAULT 0,
    balance_base        DECIMAL(18,4) DEFAULT 0,   -- running balance in base units
    unit_cost           DECIMAL(18,2) DEFAULT 0,   -- cost per base unit at time of txn
    notes               NVARCHAR(300),
    created_at          DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inventory_product' AND object_id=OBJECT_ID('inventory_transactions'))
CREATE INDEX IX_inventory_product ON inventory_transactions(product_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inventory_date' AND object_id=OBJECT_ID('inventory_transactions'))
CREATE INDEX IX_inventory_date ON inventory_transactions(txn_date);
GO

PRINT N'✅ Inventory & Multi-Units patch applied.';
GO
GO


-- ============================================================================
-- SECTION: 5. SMART SEARCH & LISTING FLAGS
-- ============================================================================

-- ============================================================
-- DayBill ERP - Product Search & Listing Flags Patch
-- Adds alias name + per-channel active flags (sales / purchase)
-- Run AFTER daybill_erp_schema.sql. Safe to re-run.
-- ============================================================

USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='alias_name')
    ALTER TABLE products ADD alias_name NVARCHAR(100) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='list_in_sales')
    ALTER TABLE products ADD list_in_sales BIT DEFAULT 1;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='list_in_purchase')
    ALTER TABLE products ADD list_in_purchase BIT DEFAULT 1;
GO

-- Existing products: list in both channels by default
UPDATE products SET list_in_sales = 1 WHERE list_in_sales IS NULL;
UPDATE products SET list_in_purchase = 1 WHERE list_in_purchase IS NULL;
GO

PRINT N'✅ Product search & listing flags patch applied.';
GO
GO


-- ============================================================================
-- SECTION: 6. MULTIPLE BARCODES PER UNIT
-- ============================================================================

-- ============================================================
-- DayBill ERP - Multiple Barcodes per Unit
-- Lets one product-unit (e.g. "1 SR Sweet - PCS") have MANY
-- barcodes. Scanning any of them rings up that unit.
-- Run AFTER inventory_units_patch.sql
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'product_unit_barcodes')
BEGIN
    CREATE TABLE product_unit_barcodes (
        barcode_id      INT IDENTITY(1,1) PRIMARY KEY,
        unit_id         INT NOT NULL REFERENCES product_units(unit_id) ON DELETE CASCADE,
        product_id      INT NOT NULL REFERENCES products(product_id),
        barcode         NVARCHAR(50) NOT NULL UNIQUE,
        is_active       BIT DEFAULT 1,
        created_at      DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_unit_barcodes_unit    ON product_unit_barcodes(unit_id);
    CREATE INDEX IX_unit_barcodes_barcode ON product_unit_barcodes(barcode);
    PRINT 'product_unit_barcodes table created.';
END
ELSE
    PRINT 'product_unit_barcodes already exists.';
GO

-- Migrate any existing single barcodes into the multi-barcode table
INSERT INTO product_unit_barcodes (unit_id, product_id, barcode)
SELECT pu.unit_id, pu.product_id, pu.barcode
FROM product_units pu
WHERE pu.barcode IS NOT NULL
  AND pu.barcode <> ''
  AND NOT EXISTS (
      SELECT 1 FROM product_unit_barcodes b WHERE b.barcode = pu.barcode
  );
GO
PRINT 'Existing barcodes migrated.';
GO
GO


-- ============================================================================
-- SECTION: 7. WEIGHT SCALE ITEMS
-- ============================================================================

-- ============================================================
-- DayBill ERP - Weight Scale support for products
-- Adds fields for items sold by weight (e.g. vegetables, meat,
-- sweets sold per kg) and for scale-printed barcodes.
-- Run anytime after the core schema.
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='is_weighed')
    ALTER TABLE products ADD is_weighed BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='weight_unit')
    ALTER TABLE products ADD weight_unit NVARCHAR(10) DEFAULT 'kg';
GO
-- Scale barcodes embed a PLU code that the scale prints onto the label.
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('products') AND name='scale_plu')
    ALTER TABLE products ADD scale_plu NVARCHAR(20) NULL;
GO
PRINT 'Weight scale columns ready.';
GO
GO


-- ============================================================================
-- SECTION: 8. USER ROLES (Manager, Cashier)
-- ============================================================================

-- ============================================================
-- DayBill ERP - User Roles seed (Manager, Cashier)
-- Administrator already exists from the core schema.
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- Manager: most things except managing users/settings
IF NOT EXISTS (SELECT 1 FROM roles WHERE role_name_en='Manager')
INSERT INTO roles (role_name_en, role_name_ar, can_view_dashboard, can_manage_customers,
    can_manage_products, can_create_invoice, can_approve_invoice, can_view_reports,
    can_manage_users, can_manage_settings, can_zatca_submit)
VALUES ('Manager', N'مدير', 1, 1, 1, 1, 1, 1, 0, 0, 1);
GO

-- Cashier: sell only (create invoices, view dashboard)
IF NOT EXISTS (SELECT 1 FROM roles WHERE role_name_en='Cashier')
INSERT INTO roles (role_name_en, role_name_ar, can_view_dashboard, can_manage_customers,
    can_manage_products, can_create_invoice, can_approve_invoice, can_view_reports,
    can_manage_users, can_manage_settings, can_zatca_submit)
VALUES ('Cashier', N'كاشير', 1, 0, 0, 1, 0, 0, 0, 0, 0);
GO

PRINT 'Manager and Cashier roles ready.';
GO
GO


-- ============================================================================
-- SECTION: 9. PER-USER RIGHTS
-- ============================================================================

-- ============================================================
-- DayBill ERP - Per-user rights (Master / Reports / Edit / Delete)
-- Adds simple permission flags directly on the users table.
-- Admin (user_id with admin username) is always granted all.
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_master')
    ALTER TABLE users ADD can_master BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_reports')
    ALTER TABLE users ADD can_reports BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_edit')
    ALTER TABLE users ADD can_edit BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_delete')
    ALTER TABLE users ADD can_delete BIT DEFAULT 0;
GO

-- Grant everything to the admin account
UPDATE users SET can_master=1, can_reports=1, can_edit=1, can_delete=1
WHERE username='admin';
GO

PRINT 'User rights columns ready.';
GO
GO


-- ============================================================================
-- SECTION: 10. REPORT DESIGNER
-- ============================================================================

-- ============================================================
-- DayBill ERP - Report Designer module tables
-- Templates, sections, fields, printer settings, themes, versions.
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='report_templates')
CREATE TABLE report_templates (
    template_id     INT IDENTITY(1,1) PRIMARY KEY,
    template_name   NVARCHAR(120) NOT NULL,
    report_type     NVARCHAR(40) DEFAULT 'invoice',  -- invoice / credit_note / quote
    paper_size      NVARCHAR(20) DEFAULT 'A4',        -- A4 / A5 / 80mm / 58mm / Letter
    orientation     NVARCHAR(12) DEFAULT 'portrait',
    margin_top      INT DEFAULT 10,
    margin_bottom   INT DEFAULT 10,
    margin_left     INT DEFAULT 10,
    margin_right    INT DEFAULT 10,
    scaling         INT DEFAULT 100,
    print_copies    INT DEFAULT 1,
    theme_name      NVARCHAR(40) DEFAULT 'Modern',
    header_color    NVARCHAR(10) DEFAULT '#3A1FD6',
    footer_color    NVARCHAR(10) DEFAULT '#2A14A8',
    table_color     NVARCHAR(10) DEFAULT '#3A1FD6',
    font_color      NVARCHAR(10) DEFAULT '#1A1438',
    accent_color    NVARCHAR(10) DEFAULT '#7ED957',
    header_text     NVARCHAR(MAX) NULL,
    footer_text     NVARCHAR(MAX) NULL,
    header_height   INT DEFAULT 38,
    footer_height   INT DEFAULT 20,
    language        NVARCHAR(5) DEFAULT 'en',
    is_default      BIT DEFAULT 0,
    is_active       BIT DEFAULT 1,
    layout_json     NVARCHAR(MAX) NULL,   -- canvas elements (drag-drop) as JSON
    version         INT DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE(),
    updated_at      DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='report_sections')
CREATE TABLE report_sections (
    section_id      INT IDENTITY(1,1) PRIMARY KEY,
    template_id     INT NOT NULL REFERENCES report_templates(template_id) ON DELETE CASCADE,
    section_type    NVARCHAR(30) NOT NULL,  -- report_header/page_header/detail/group_header/group_footer/page_footer/report_footer
    height          INT DEFAULT 20,
    visible         BIT DEFAULT 1,
    sort_order      INT DEFAULT 0
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='report_fields')
CREATE TABLE report_fields (
    field_id        INT IDENTITY(1,1) PRIMARY KEY,
    template_id     INT NOT NULL REFERENCES report_templates(template_id) ON DELETE CASCADE,
    section_type    NVARCHAR(30) DEFAULT 'detail',
    field_key       NVARCHAR(60) NOT NULL,  -- invoice_number, customer_name, item_total ...
    field_label     NVARCHAR(120) NULL,
    field_type      NVARCHAR(30) DEFAULT 'text', -- text/label/image/logo/qr/barcode/signature/table/chart/line
    pos_x           INT DEFAULT 0,
    pos_y           INT DEFAULT 0,
    width           INT DEFAULT 100,
    height          INT DEFAULT 20,
    font_size       INT DEFAULT 9,
    bold            BIT DEFAULT 0,
    align           NVARCHAR(10) DEFAULT 'left',
    formula         NVARCHAR(MAX) NULL,
    is_custom       BIT DEFAULT 0
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='report_printer_settings')
CREATE TABLE report_printer_settings (
    printer_id      INT IDENTITY(1,1) PRIMARY KEY,
    template_id     INT NULL REFERENCES report_templates(template_id) ON DELETE CASCADE,
    printer_name    NVARCHAR(120) NULL,
    printer_type    NVARCHAR(20) DEFAULT 'A4',  -- A4 / thermal / dotmatrix / pdf
    is_default      BIT DEFAULT 0
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='report_themes')
CREATE TABLE report_themes (
    theme_id        INT IDENTITY(1,1) PRIMARY KEY,
    theme_name      NVARCHAR(40) NOT NULL UNIQUE,
    header_color    NVARCHAR(10),
    footer_color    NVARCHAR(10),
    table_color     NVARCHAR(10),
    font_color      NVARCHAR(10),
    accent_color    NVARCHAR(10)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='report_versions')
CREATE TABLE report_versions (
    version_id      INT IDENTITY(1,1) PRIMARY KEY,
    template_id     INT NOT NULL REFERENCES report_templates(template_id) ON DELETE CASCADE,
    version         INT NOT NULL,
    layout_json     NVARCHAR(MAX) NULL,
    saved_at        DATETIME DEFAULT GETDATE(),
    saved_by        NVARCHAR(50) NULL
);
GO

-- Seed the 5 built-in themes
IF NOT EXISTS (SELECT 1 FROM report_themes WHERE theme_name='Modern')
INSERT INTO report_themes (theme_name, header_color, footer_color, table_color, font_color, accent_color) VALUES
 ('Classic',     '#1A1A2E', '#1A1A2E', '#374151', '#111827', '#9CA3AF'),
 ('Modern',      '#3A1FD6', '#2A14A8', '#3A1FD6', '#1A1438', '#7ED957'),
 ('Professional','#0F4C81', '#0A3A63', '#0F4C81', '#1A1A2E', '#3B82F6'),
 ('Corporate',   '#006C35', '#004D26', '#006C35', '#1A1A2E', '#34D399'),
 ('Minimal',     '#FFFFFF', '#FFFFFF', '#E5E7EB', '#111827', '#6B7280');
GO

-- One default template if none exists
IF NOT EXISTS (SELECT 1 FROM report_templates)
INSERT INTO report_templates (template_name, is_default, header_text, footer_text)
VALUES ('Default Invoice (A4)', 1,
        'Tax Invoice', 'Thank you for your business. This is a ZATCA-compliant e-invoice.');
GO

PRINT 'Report Designer tables ready.';
GO
GO


-- ============================================================================
-- SECTION: 11. BARCODE DESIGNER
-- ============================================================================

-- ============================================================
-- DayBill ERP - Barcode Designer & Printing module tables
-- Templates, sequences, print history, settings, scans.
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='barcode_templates')
CREATE TABLE barcode_templates (
    template_id     INT IDENTITY(1,1) PRIMARY KEY,
    template_name   NVARCHAR(120) NOT NULL,
    barcode_type    NVARCHAR(20) DEFAULT 'code128',  -- code128 / ean13 / qr
    label_width_mm  DECIMAL(6,2) DEFAULT 50,
    label_height_mm DECIMAL(6,2) DEFAULT 25,
    is_sheet        BIT DEFAULT 0,        -- 0 = thermal single, 1 = A4 sheet grid
    sheet_cols      INT DEFAULT 3,
    sheet_rows      INT DEFAULT 8,
    gap_x_mm        DECIMAL(6,2) DEFAULT 2,
    gap_y_mm        DECIMAL(6,2) DEFAULT 2,
    layout_json     NVARCHAR(MAX) NULL,   -- canvas elements as JSON
    header_text     NVARCHAR(200) NULL,
    footer_text     NVARCHAR(200) NULL,
    is_default      BIT DEFAULT 0,
    is_active       BIT DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE(),
    updated_at      DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='barcode_sequences')
CREATE TABLE barcode_sequences (
    sequence_id     INT IDENTITY(1,1) PRIMARY KEY,
    prefix          NVARCHAR(10) NOT NULL,        -- PRD / INV / AST
    next_number     INT DEFAULT 1,
    number_length   INT DEFAULT 6,
    description     NVARCHAR(100) NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='barcode_print_history')
CREATE TABLE barcode_print_history (
    history_id      INT IDENTITY(1,1) PRIMARY KEY,
    template_id     INT NULL,
    product_id      INT NULL,
    barcode_value   NVARCHAR(60) NULL,
    copies          INT DEFAULT 1,
    printer_name    NVARCHAR(120) NULL,
    printed_by      NVARCHAR(50) NULL,
    printed_at      DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='barcode_settings')
CREATE TABLE barcode_settings (
    setting_id      INT IDENTITY(1,1) PRIMARY KEY,
    default_printer NVARCHAR(120) NULL,
    dpi             INT DEFAULT 203,
    print_density   INT DEFAULT 8,
    margin_mm       DECIMAL(6,2) DEFAULT 1,
    default_type    NVARCHAR(20) DEFAULT 'code128'
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='barcode_scans')
CREATE TABLE barcode_scans (
    scan_id         INT IDENTITY(1,1) PRIMARY KEY,
    barcode_value   NVARCHAR(60) NULL,
    product_id      INT NULL,
    scan_context    NVARCHAR(30) NULL,   -- pos / stock / verify
    scanned_by      NVARCHAR(50) NULL,
    scanned_at      DATETIME DEFAULT GETDATE()
);
GO

-- Seed sequences
IF NOT EXISTS (SELECT 1 FROM barcode_sequences WHERE prefix='PRD')
INSERT INTO barcode_sequences (prefix, next_number, number_length, description) VALUES
 ('PRD', 1, 6, 'Products'),
 ('INV', 1, 6, 'Invoices'),
 ('AST', 1, 6, 'Assets');
GO

-- Seed default thermal template
IF NOT EXISTS (SELECT 1 FROM barcode_templates)
INSERT INTO barcode_templates (template_name, barcode_type, label_width_mm,
    label_height_mm, is_sheet, is_default, header_text)
VALUES ('Thermal 50x25 (Code128)', 'code128', 50, 25, 0, 1, NULL);
GO

PRINT 'Barcode Designer tables ready.';
GO
GO


-- ============================================================================
-- SECTION: 12. PARTY LEDGERS + ACCOUNTING INTEGRATION
-- ============================================================================

-- ============================================================
-- DayBill ERP - Party Ledgers + Accounting Integration
-- 1. Each customer & supplier gets its own ledger account (with code)
-- 2. Adds a Bank account to the chart of accounts
-- 3. Links customers.account_id / suppliers.account_id
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- Add account_id link to customers & suppliers
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('customers') AND name='account_id')
    ALTER TABLE customers ADD account_id INT NULL REFERENCES accounts(account_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('suppliers') AND name='account_id')
    ALTER TABLE suppliers ADD account_id INT NULL REFERENCES accounts(account_id);
GO

-- Add a Bank account + Card clearing if missing
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1110')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type)
VALUES ('1110', 'Bank', N'البنك', 'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1120')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type)
VALUES ('1120', 'Card / POS Clearing', N'مقاصة البطاقات', 'asset');
GO

-- Parent group accounts so party ledgers nest under Receivable/Payable
-- (1200 = Accounts Receivable, 2100 = Accounts Payable already exist)

-- Create a ledger account for every customer that lacks one.
-- Customer ledger codes: 1200-0001, 1200-0002 ...
DECLARE @cid INT, @cname NVARCHAR(200), @ccode NVARCHAR(20), @n INT, @acc INT;
DECLARE cust_cur CURSOR FOR
    SELECT customer_id, customer_name_en FROM customers WHERE account_id IS NULL;
OPEN cust_cur;
FETCH NEXT FROM cust_cur INTO @cid, @cname;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @n = ISNULL((SELECT COUNT(*) FROM accounts WHERE account_code LIKE '1200-%'), 0) + 1;
    SET @ccode = '1200-' + RIGHT('0000' + CAST(@n AS NVARCHAR(10)), 4);
    INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type,
        parent_account_id)
    VALUES (@ccode, @cname, @cname, 'asset',
        (SELECT TOP 1 account_id FROM accounts WHERE account_code='1200'));
    SET @acc = SCOPE_IDENTITY();
    UPDATE customers SET account_id=@acc WHERE customer_id=@cid;
    FETCH NEXT FROM cust_cur INTO @cid, @cname;
END
CLOSE cust_cur; DEALLOCATE cust_cur;
GO

-- Create a ledger account for every supplier that lacks one.
-- Supplier ledger codes: 2100-0001, 2100-0002 ...
DECLARE @sid INT, @sname NVARCHAR(200), @scode NVARCHAR(20), @sn INT, @sacc INT;
DECLARE sup_cur CURSOR FOR
    SELECT supplier_id, supplier_name_en FROM suppliers WHERE account_id IS NULL;
OPEN sup_cur;
FETCH NEXT FROM sup_cur INTO @sid, @sname;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sn = ISNULL((SELECT COUNT(*) FROM accounts WHERE account_code LIKE '2100-%'), 0) + 1;
    SET @scode = '2100-' + RIGHT('0000' + CAST(@sn AS NVARCHAR(10)), 4);
    INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type,
        parent_account_id)
    VALUES (@scode, @sname, @sname, 'liability',
        (SELECT TOP 1 account_id FROM accounts WHERE account_code='2100'));
    SET @sacc = SCOPE_IDENTITY();
    UPDATE suppliers SET account_id=@sacc WHERE supplier_id=@sid;
    FETCH NEXT FROM sup_cur INTO @sid, @sname;
END
CLOSE sup_cur; DEALLOCATE sup_cur;
GO

PRINT 'Party ledgers + accounting integration ready.';
GO
GO


-- ============================================================================
-- END OF DAYBILL ERP SETUP
-- ============================================================================


-- ============================================================
-- SECTION 11: SALES & PURCHASE RETURNS
-- ============================================================
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


-- ============================================================
-- SECTION 12: PRODUCT MASTER EXTRA COLUMNS
-- ============================================================
-- ============================================================
-- DayBill ERP - Product Master extra columns
-- Adds pricing / inventory-level / notes fields. Safe to re-run.
-- ============================================================

IF COL_LENGTH('products','purchase_price') IS NULL
    ALTER TABLE products ADD purchase_price DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','wholesale_price') IS NULL
    ALTER TABLE products ADD wholesale_price DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','last_purchase_cost') IS NULL
    ALTER TABLE products ADD last_purchase_cost DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','average_cost') IS NULL
    ALTER TABLE products ADD average_cost DECIMAL(18,2) DEFAULT 0;
IF COL_LENGTH('products','min_stock') IS NULL
    ALTER TABLE products ADD min_stock DECIMAL(18,3) DEFAULT 0;
IF COL_LENGTH('products','max_stock') IS NULL
    ALTER TABLE products ADD max_stock DECIMAL(18,3) DEFAULT 0;
IF COL_LENGTH('products','reorder_quantity') IS NULL
    ALTER TABLE products ADD reorder_quantity DECIMAL(18,3) DEFAULT 0;
IF COL_LENGTH('products','storage_location') IS NULL
    ALTER TABLE products ADD storage_location NVARCHAR(100) NULL;
IF COL_LENGTH('products','internal_notes') IS NULL
    ALTER TABLE products ADD internal_notes NVARCHAR(500) NULL;
IF COL_LENGTH('products','sales_notes') IS NULL
    ALTER TABLE products ADD sales_notes NVARCHAR(500) NULL;
IF COL_LENGTH('products','purchase_notes') IS NULL
    ALTER TABLE products ADD purchase_notes NVARCHAR(500) NULL;
PRINT 'Product master extra columns ready.';
