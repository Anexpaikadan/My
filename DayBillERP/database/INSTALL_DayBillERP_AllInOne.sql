-- ============================================================
-- DayBill ERP — FULL DATABASE INSTALLER  (clean new installation)
-- generated 2026-10-23 20:36  ·  ONE file = the whole database
-- ------------------------------------------------------------
-- WHAT IT MAKES
--   • the DayBillERP database (Arabic collation) and EVERY table,
--     view, procedure and index the app uses
--   • only the starting data a new shop needs:
--       admin user (you set the password at the first sign-in),
--       roles Administrator / Manager / Cashier, chart of accounts,
--       default account mapping, VAT categories (S/Z/E/O 15%),
--       Cash Customer + Cash Supplier, Main Branch + Counter 1,
--       this year's financial year, invoice / barcode numbering,
--       default print templates and themes
--   • NO sample products, customers, invoices or test data
--   • the company is EMPTY ('Your Company Name', no VAT number):
--     fill it in DayBill ▸ Settings ▸ Company — the first-run
--     wizard opens for that on the first sign-in.
--
-- HOW TO RUN (pick one)
--   A. DayBill login ▸ ⚙ Database Settings ▸ Create New Database…
--      (any database name — runs this file for you)
--   B. SSMS: open this file ▸ Execute (F5). It creates the database
--      DayBillERP itself — no need to create it first.
--   C. sqlcmd -S .\SQLEXPRESS -E -i database\INSTALL_DayBillERP_AllInOne.sql
--
-- Safe to run again on an existing DayBill database: tables, indexes
-- and starting data are only added when missing, nothing is deleted.
-- Regenerate after adding patches:  python tools/build_install_sql.py
-- ============================================================

SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET NUMERIC_ROUNDABORT OFF;
GO

-- ▼▼▼  BASE: DayBillERP_Full_Setup.sql  ▼▼▼
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
    company_name_en, company_name_ar, vat_registration_no
) VALUES (
    N'Your Company Name', N'اسم شركتك', N''
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

GO

-- ▼▼▼  PATCH: accounting_payroll_patch.sql  ▼▼▼
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

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_lines_account')
    CREATE INDEX IX_journal_lines_account ON journal_lines(account_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_entries_date')
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

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_payslips_run')
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

PRINT '✅ Accounting & Payroll schema patch applied.';
GO

GO

-- ▼▼▼  PATCH: audit_log_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Audit Log Patch
-- (Converted from BillPOS MySQL audit_logs)
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('audit_logs','U') IS NULL
CREATE TABLE audit_logs (
    id          BIGINT IDENTITY(1,1) PRIMARY KEY,
    user_id     INT NULL,
    action      NVARCHAR(50) NOT NULL,      -- create / update / delete / login / post ...
    module      NVARCHAR(50) NOT NULL,      -- sales / purchase / vouchers / users ...
    ref_id      NVARCHAR(50) NULL,          -- document id / number
    details     NVARCHAR(MAX) NULL,
    workstation NVARCHAR(100) NULL,         -- replaces PHP ip_address on desktop
    created_at  DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_audit_user')
    CREATE INDEX idx_audit_user ON audit_logs(user_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_audit_module')
    CREATE INDEX idx_audit_module ON audit_logs(module);
GO

PRINT '✅ Audit log patch applied.';
GO

GO

-- ▼▼▼  PATCH: barcode_designer_patch.sql  ▼▼▼
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

-- ▼▼▼  PATCH: barcode_template_cols_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v5.8 — Label Designer columns
-- The designer saves paper mode / sheet grid / margin / dpi, but the
-- original barcode_templates table only had is_sheet/sheet_cols/
-- sheet_rows, so creating or saving a template failed on SQL Server.
-- ============================================================
IF COL_LENGTH('barcode_templates','paper_mode') IS NULL
    ALTER TABLE barcode_templates ADD paper_mode NVARCHAR(20) DEFAULT 'thermal';
GO
IF COL_LENGTH('barcode_templates','cols_per_sheet') IS NULL
    ALTER TABLE barcode_templates ADD cols_per_sheet INT DEFAULT 3;
GO
IF COL_LENGTH('barcode_templates','rows_per_sheet') IS NULL
    ALTER TABLE barcode_templates ADD rows_per_sheet INT DEFAULT 8;
GO
IF COL_LENGTH('barcode_templates','margin_mm') IS NULL
    ALTER TABLE barcode_templates ADD margin_mm DECIMAL(6,2) DEFAULT 5;
GO
IF COL_LENGTH('barcode_templates','dpi') IS NULL
    ALTER TABLE barcode_templates ADD dpi INT DEFAULT 203;
GO
IF COL_LENGTH('barcode_templates','show_border') IS NULL
    ALTER TABLE barcode_templates ADD show_border BIT DEFAULT 1;
GO
-- carry the old sheet settings over
UPDATE barcode_templates
   SET paper_mode = CASE WHEN ISNULL(is_sheet,0)=1 THEN 'a4sheet' ELSE 'thermal' END,
       cols_per_sheet = ISNULL(sheet_cols, 3),
       rows_per_sheet = ISNULL(sheet_rows, 8)
 WHERE paper_mode IS NULL;
GO
PRINT 'Label Designer columns ready.';
GO

GO

-- ▼▼▼  PATCH: cash_supplier_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Default "CASH" Walk-in Supplier
-- ------------------------------------------------------------
-- Mirrors the existing Cash Customer (default_accounts_patch.sql
-- Part G): the new-purchase screen auto-selects this supplier for
-- spot/cash purchases so a supplier doesn't have to be picked first.
-- Its ledger points at the master Cash account. Idempotent.
-- ============================================================
USE DayBillERP;
GO

IF EXISTS (SELECT 1 FROM sys.columns
           WHERE object_id=OBJECT_ID('suppliers') AND name='account_id')
BEGIN
    IF NOT EXISTS (SELECT 1 FROM suppliers WHERE supplier_code='CASH')
        INSERT INTO suppliers (supplier_code, supplier_name_en, supplier_name_ar,
            country_code, account_id)
        VALUES ('CASH', 'Cash Supplier', N'مورد نقدي', 'SA',
                (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100'));

    UPDATE suppliers
       SET account_id = (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100')
     WHERE supplier_code='CASH' AND account_id IS NULL;
END
ELSE
BEGIN
    IF NOT EXISTS (SELECT 1 FROM suppliers WHERE supplier_code='CASH')
        INSERT INTO suppliers (supplier_code, supplier_name_en, supplier_name_ar,
            country_code)
        VALUES ('CASH', 'Cash Supplier', N'مورد نقدي', 'SA');
END
GO

PRINT '✅ Cash walk-in supplier ready.';
GO

GO

-- ▼▼▼  PATCH: coa_defaults_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Standard chart of accounts (Saudi retail)
-- Adds the accounts a shop needs that were still missing and puts
-- every standard account under its group so the chart shows as a
-- tree. Only adds / fills blanks — never renames or moves an
-- account the user already set up. Safe to run many times.
-- ============================================================
DECLARE @acc TABLE (code NVARCHAR(20), en NVARCHAR(200), ar NVARCHAR(200),
                    typ NVARCHAR(30), parent NVARCHAR(20));
INSERT INTO @acc VALUES
 ('1000', N'Assets',                        N'الأصول',                     'asset',     NULL),
 ('1010', N'Current Assets',                N'الأصول المتداولة',            'asset',     '1000'),
 ('1100', N'Cash',                          N'النقد',                       'asset',     '1010'),
 ('1110', N'Bank',                          N'البنك',                       'asset',     '1010'),
 ('1120', N'Card / POS Clearing',           N'مقاصة البطاقات',              'asset',     '1010'),
 ('1130', N'Savings Account',               N'حساب التوفير',                'asset',     '1010'),
 ('1140', N'Online Payment Gateway',        N'بوابة الدفع الإلكتروني',      'asset',     '1010'),
 ('1150', N'Petty Cash',                    N'العهدة النقدية',              'asset',     '1010'),
 ('1200', N'Accounts Receivable',           N'حسابات القبض',                'asset',     '1010'),
 ('1300', N'Inventory',                     N'المخزون',                     'asset',     '1010'),
 ('1400', N'Advances & Prepaid Expenses',   N'دفعات مقدمة ومصروفات مدفوعة مقدماً', 'asset', '1010'),
 ('1500', N'Fixed Assets',                  N'الأصول الثابتة',              'asset',     '1000'),
 ('1510', N'Furniture & Fixtures',          N'الأثاث والتجهيزات',            'asset',     '1500'),
 ('1520', N'Equipment & Computers',         N'المعدات والحاسبات',            'asset',     '1500'),
 ('1530', N'Vehicles',                      N'السيارات',                     'asset',     '1500'),
 ('1590', N'Accumulated Depreciation',      N'مجمع الإهلاك',                'asset',     '1500'),
 ('2000', N'Liabilities',                   N'الخصوم',                      'liability', NULL),
 ('2100', N'Accounts Payable',              N'حسابات الدفع',                'liability', '2000'),
 ('2200', N'VAT Payable',                   N'ضريبة القيمة المضافة المستحقة', 'liability', '2000'),
 ('2210', N'VAT Collected (Output)',        N'ضريبة المخرجات',              'liability', '2200'),
 ('2220', N'VAT Paid (Input)',              N'ضريبة المدخلات',              'liability', '2200'),
 ('2300', N'Salaries Payable',              N'رواتب مستحقة',                'liability', '2000'),
 ('2310', N'GOSI Payable',                  N'تأمينات مستحقة',              'liability', '2000'),
 ('2330', N'End of Service Provision',      N'مخصص نهاية الخدمة',           'liability', '2000'),
 ('2400', N'Accrued Expenses',              N'مصروفات مستحقة',              'liability', '2000'),
 ('2500', N'Loans Payable',                 N'قروض',                        'liability', '2000'),
 ('3000', N'Equity',                        N'حقوق الملكية',                'equity',    NULL),
 ('3100', N'Owner''s Capital',              N'رأس المال',                   'equity',    '3000'),
 ('3200', N'Owner''s Drawings',             N'المسحوبات الشخصية',           'equity',    '3000'),
 ('3300', N'Retained Earnings',             N'الأرباح المبقاة',             'equity',    '3000'),
 ('3400', N'Opening Balance Equity',        N'أرصدة افتتاحية',              'equity',    '3000'),
 ('4000', N'Revenue',                       N'الإيرادات',                   'revenue',   NULL),
 ('4100', N'Sales Revenue',                 N'إيرادات المبيعات',            'revenue',   '4000'),
 ('4200', N'Sales Returns',                 N'مردودات المبيعات',            'revenue',   '4000'),
 ('4300', N'Other Income',                  N'إيرادات أخرى',               'revenue',   '4000'),
 ('4310', N'Discount Received',             N'خصم مكتسب',                   'revenue',   '4000'),
 ('5000', N'Expenses',                      N'المصروفات',                   'expense',   NULL),
 ('5100', N'Cost of Goods Sold',            N'تكلفة البضاعة المباعة',       'expense',   '5000'),
 ('5150', N'Purchase Returns',              N'مردودات المشتريات',           'expense',   '5000'),
 ('5160', N'Stock Adjustment',              N'تسوية المخزون',               'expense',   '5000'),
 ('5200', N'Salaries Expense',              N'مصروف الرواتب',               'expense',   '5000'),
 ('5210', N'GOSI Expense (Employer)',       N'مصروف التأمينات',             'expense',   '5000'),
 ('5220', N'End of Service Expense',        N'مصروف نهاية الخدمة',          'expense',   '5000'),
 ('5300', N'Rent Expense',                  N'مصروف الإيجار',               'expense',   '5000'),
 ('5310', N'Electricity Expense',           N'مصروف الكهرباء',              'expense',   '5000'),
 ('5320', N'Fuel Expense',                  N'مصروف الوقود',                'expense',   '5000'),
 ('5330', N'Office Expense',                N'مصروفات مكتبية',              'expense',   '5000'),
 ('5340', N'Water Expense',                 N'مصروف المياه',                'expense',   '5000'),
 ('5350', N'Telephone & Internet',          N'الهاتف والإنترنت',            'expense',   '5000'),
 ('5360', N'Maintenance & Repairs',         N'الصيانة والإصلاح',            'expense',   '5000'),
 ('5370', N'Transport & Delivery',          N'النقل والتوصيل',              'expense',   '5000'),
 ('5380', N'Advertising',                   N'الدعاية والإعلان',            'expense',   '5000'),
 ('5390', N'General Expense',               N'مصروفات عامة',                'expense',   '5000'),
 ('5400', N'Discount Allowed',              N'خصم مسموح به',                'expense',   '5000'),
 ('5410', N'Bank Charges',                  N'عمولات بنكية',                'expense',   '5000'),
 ('5420', N'Government Fees & Licences',    N'رسوم حكومية وتراخيص',         'expense',   '5000'),
 ('5430', N'Insurance Expense',             N'مصروف التأمين',               'expense',   '5000'),
 ('5440', N'Depreciation Expense',          N'مصروف الإهلاك',               'expense',   '5000'),
 ('5450', N'Cash Shortage / Excess',        N'عجز / زيادة الصندوق',          'expense',   '5000'),
 ('5900', N'Rounding Difference',           N'فروقات التقريب',              'expense',   '5000');

INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type)
SELECT a.code, a.en, a.ar, a.typ FROM @acc a
 WHERE NOT EXISTS (SELECT 1 FROM accounts x WHERE x.account_code = a.code);

UPDATE x SET parent_account_id = p.account_id
  FROM accounts x
  JOIN @acc a ON a.code = x.account_code
  JOIN accounts p ON p.account_code = a.parent
 WHERE x.parent_account_id IS NULL AND a.parent IS NOT NULL;
GO

-- v6.9: account_settings may not exist yet (default_accounts_patch runs
-- after this one) — dynamic SQL so a new database never errors here
IF OBJECT_ID('account_settings','U') IS NOT NULL
    EXEC(N'IF NOT EXISTS (SELECT 1 FROM account_settings WHERE setting_key=''default_opening_equity'')
             INSERT INTO account_settings (setting_key, account_code)
             VALUES (''default_opening_equity'', ''3400'');');
GO

GO

-- ▼▼▼  PATCH: company_settings_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Fix: Company settings missing columns
-- ------------------------------------------------------------
-- Settings -> Company writes business_type, country, state_en,
-- timezone, date_format, time_format, and language, but these
-- columns were never added to the company table — every save from
-- that page failed with "Invalid column name" errors. Idempotent.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('company','business_type') IS NULL
    ALTER TABLE company ADD business_type NVARCHAR(30);
GO
IF COL_LENGTH('company','country') IS NULL
    ALTER TABLE company ADD country NVARCHAR(50) DEFAULT 'Saudi Arabia';
GO
IF COL_LENGTH('company','state_en') IS NULL
    ALTER TABLE company ADD state_en NVARCHAR(100);
GO
IF COL_LENGTH('company','timezone') IS NULL
    ALTER TABLE company ADD timezone NVARCHAR(40) DEFAULT 'Asia/Riyadh';
GO
IF COL_LENGTH('company','date_format') IS NULL
    ALTER TABLE company ADD date_format NVARCHAR(20) DEFAULT 'dd/MM/yyyy';
GO
IF COL_LENGTH('company','time_format') IS NULL
    ALTER TABLE company ADD time_format NVARCHAR(20) DEFAULT '24-hour';
GO
IF COL_LENGTH('company','language') IS NULL
    ALTER TABLE company ADD language NVARCHAR(5) DEFAULT 'en';
GO

PRINT '✅ Company settings columns added.';
GO

GO

-- ▼▼▼  PATCH: default_accounts_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Default Cash Account & Auto-Posting Patch
-- ------------------------------------------------------------
-- Adds the master Cash Account, the missing ledger accounts the
-- posting engine already references, a configurable default-account
-- map, per-payment-method ledger mapping, branch-wise cash mapping,
-- a fund-transfer (banking) table and a simple expenses table.
--
-- Idempotent: safe to run multiple times.
-- ============================================================

USE DayBillERP;
GO

-- ============================================================
-- PART A — CHART OF ACCOUNTS ADDITIONS
-- ------------------------------------------------------------
-- The posting engine references 1110 (Bank) and 1120 (Card) but the
-- base schema never created them, so card/bank legs were being
-- dropped and journals stored UNBALANCED. These inserts fix that and
-- add the remaining accounts the spec calls for.
-- ============================================================

-- Current Assets group (under 1000 Assets)
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1010')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
SELECT '1010', 'Current Assets', N'الأصول المتداولة', 'asset', a.account_id
FROM accounts a WHERE a.account_code='1000';
GO

-- Make the existing Cash account the MASTER "Cash Account" under Current Assets.
-- (Code stays 1100 so existing postings/history keep resolving. To use the
--  spec code 100001 instead, uncomment the optional block at the bottom.)
UPDATE accounts
   SET account_name_en = 'Cash Account',
       account_name_ar = N'حساب النقد',
       parent_account_id = (SELECT account_id FROM accounts WHERE account_code='1010')
 WHERE account_code='1100';
GO

-- Banking / tender accounts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1110')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1110', 'Main Bank Account',          N'الحساب البنكي الرئيسي', 'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1120')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1120', 'Card / Credit Card Clearing', N'حساب تسوية البطاقات',   'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1130')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1130', 'Savings Account',            N'حساب التوفير',          'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1140')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1140', 'Online Payment Gateway',     N'بوابة الدفع الإلكتروني', 'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1150')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('1150', 'Petty Cash',                 N'النثرية',               'asset');
GO

-- Returns (contra) accounts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='4200')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('4200', 'Sales Returns',              N'مردودات المبيعات',      'revenue');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5150')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5150', 'Purchase Returns',           N'مردودات المشتريات',     'expense');
GO

-- Expense accounts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5300')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5300', 'Rent Expense',               N'مصروف الإيجار',         'expense'),
('5310', 'Electricity Expense',        N'مصروف الكهرباء',        'expense'),
('5320', 'Fuel Expense',               N'مصروف الوقود',          'expense'),
('5330', 'Office Expense',             N'مصروفات مكتبية',        'expense'),
('5390', 'General Expense',            N'مصروفات عامة',          'expense'),
('5400', 'Discount Allowed',           N'الخصم المسموح به',      'expense'),
('5900', 'Rounding Difference',        N'فروقات التقريب',        'expense');
GO

-- ============================================================
-- PART B — DEFAULT ACCOUNT MAP (key -> account)
-- ------------------------------------------------------------
-- A DB-resident copy of the default-account selections. The app
-- reads/writes these through config/account_defaults.py; this table
-- keeps the mapping available to SQL/reporting too.
-- ============================================================
IF OBJECT_ID('account_settings','U') IS NULL
CREATE TABLE account_settings (
    setting_key   NVARCHAR(50) NOT NULL PRIMARY KEY,
    account_id    INT NULL REFERENCES accounts(account_id),
    account_code  NVARCHAR(20) NULL,
    updated_at    DATETIME DEFAULT GETDATE()
);
GO

-- Seed the map from the codes above (only rows that are missing).
MERGE account_settings AS tgt
USING (VALUES
    ('default_cash',            '1100'),
    ('default_bank',            '1110'),
    ('default_card',            '1120'),
    ('default_savings',         '1130'),
    ('default_gateway',         '1140'),
    ('default_petty_cash',      '1150'),
    ('default_sales',           '4100'),
    ('default_purchase',        '1300'),
    ('default_inventory',       '1300'),
    ('default_receivable',      '1200'),
    ('default_payable',         '2100'),
    ('default_tax_payable',     '2210'),
    ('default_tax_receivable',  '2220'),
    ('default_cogs',            '5100'),
    ('default_salary_expense',  '5200'),
    ('default_discount',        '5400'),
    ('default_round_off',       '5900'),
    ('default_sales_return',    '4200'),
    ('default_purchase_return', '5150')
) AS src(setting_key, account_code)
ON tgt.setting_key = src.setting_key
WHEN NOT MATCHED THEN
    INSERT (setting_key, account_code, account_id)
    VALUES (src.setting_key, src.account_code,
            (SELECT account_id FROM accounts WHERE account_code = src.account_code));
GO

-- ============================================================
-- PART C — PAYMENT METHOD -> LEDGER MAPPING
-- ============================================================
IF OBJECT_ID('payment_method_accounts','U') IS NULL
CREATE TABLE payment_method_accounts (
    method_code   NVARCHAR(20) NOT NULL PRIMARY KEY,
    label_en      NVARCHAR(50),
    account_id    INT NULL REFERENCES accounts(account_id),
    is_active     BIT DEFAULT 1
);
GO

MERGE payment_method_accounts AS tgt
USING (VALUES
    ('cash',          'Cash',          '1100'),
    ('card',          'Card',          '1120'),
    ('bank_transfer', 'Bank Transfer', '1110'),
    ('gateway',       'Online Gateway','1140')
) AS src(method_code, label_en, code)
ON tgt.method_code = src.method_code
WHEN NOT MATCHED THEN
    INSERT (method_code, label_en, account_id)
    VALUES (src.method_code, src.label_en,
            (SELECT account_id FROM accounts WHERE account_code = src.code));
GO

-- ============================================================
-- PART D — BRANCHES + BRANCH-WISE CASH MAPPING
-- ============================================================
IF OBJECT_ID('branches','U') IS NULL
CREATE TABLE branches (
    branch_id     INT IDENTITY(1,1) PRIMARY KEY,
    name_en       NVARCHAR(100) NOT NULL,
    name_ar       NVARCHAR(100),
    is_active     BIT DEFAULT 1
);
GO

IF OBJECT_ID('branch_cash_accounts','U') IS NULL
CREATE TABLE branch_cash_accounts (
    branch_id            INT NOT NULL PRIMARY KEY REFERENCES branches(branch_id),
    cash_account_id      INT NULL REFERENCES accounts(account_id),
    petty_cash_account_id INT NULL REFERENCES accounts(account_id),
    bank_account_id      INT NULL REFERENCES accounts(account_id)
);
GO

-- ============================================================
-- PART E — BANKING: FUND TRANSFERS
-- ============================================================
IF OBJECT_ID('bank_transfers','U') IS NULL
CREATE TABLE bank_transfers (
    transfer_id     INT IDENTITY(1,1) PRIMARY KEY,
    transfer_date   DATE NOT NULL,
    from_account_id INT NOT NULL REFERENCES accounts(account_id),
    to_account_id   INT NOT NULL REFERENCES accounts(account_id),
    amount          DECIMAL(18,2) NOT NULL,
    reference       NVARCHAR(100),
    notes           NVARCHAR(300),
    journal_id      INT NULL REFERENCES journal_entries(journal_id),
    created_at      DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- PART F — EXPENSES (immediate-pay expense vouchers)
-- ============================================================
IF OBJECT_ID('expenses','U') IS NULL
CREATE TABLE expenses (
    expense_id      INT IDENTITY(1,1) PRIMARY KEY,
    expense_date    DATE NOT NULL,
    expense_account_id INT NOT NULL REFERENCES accounts(account_id),
    amount          DECIMAL(18,2) NOT NULL,
    vat_amount      DECIMAL(18,2) DEFAULT 0,
    payment_method  NVARCHAR(20) DEFAULT 'cash',  -- cash/bank/card/gateway
    paid_from_account_id INT NULL REFERENCES accounts(account_id),
    reference       NVARCHAR(100),
    description     NVARCHAR(300),
    journal_id      INT NULL REFERENCES journal_entries(journal_id),
    created_by      INT,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

PRINT '✅ Default accounts & auto-posting patch applied.';
GO

-- ============================================================
-- PART G — DEFAULT "CASH" WALK-IN CUSTOMER
-- ------------------------------------------------------------
-- The new-invoice screen auto-selects this customer. Its ledger
-- points at the master Cash account, so an unpaid "cash sale"
-- never lands in receivables. (Fully-paid cash sales debit Cash
-- regardless.) Guarded for whether party_ledger_patch has added
-- the account_id column yet.
-- ============================================================
IF EXISTS (SELECT 1 FROM sys.columns
           WHERE object_id=OBJECT_ID('customers') AND name='account_id')
BEGIN
    IF NOT EXISTS (SELECT 1 FROM customers WHERE customer_code='CASH')
        INSERT INTO customers (customer_code, customer_name_en, customer_name_ar,
            customer_type, country_code, account_id)
        VALUES ('CASH', 'Cash Customer', N'عميل نقدي', 'B2C', 'SA',
                (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100'));

    UPDATE customers
       SET account_id = (SELECT TOP 1 account_id FROM accounts WHERE account_code='1100')
     WHERE customer_code='CASH';
END
ELSE
BEGIN
    IF NOT EXISTS (SELECT 1 FROM customers WHERE customer_code='CASH')
        INSERT INTO customers (customer_code, customer_name_en, customer_name_ar,
            customer_type, country_code)
        VALUES ('CASH', 'Cash Customer', N'عميل نقدي', 'B2C', 'SA');
END
GO

PRINT '✅ Cash walk-in customer ready.';
GO

-- ============================================================
-- OPTIONAL: switch the master cash code 1100 -> 100001
-- (spec asked for an editable 100001). Uncomment to apply.
-- The app resolves cash by the configured code, so postings follow.
-- ------------------------------------------------------------
-- UPDATE accounts        SET account_code='100001' WHERE account_code='1100';
-- UPDATE account_settings SET account_code='100001' WHERE setting_key='default_cash';
-- UPDATE payment_method_accounts
--    SET account_id=(SELECT account_id FROM accounts WHERE account_code='100001')
--  WHERE method_code='cash';
-- GO

GO

-- ▼▼▼  PATCH: default_purchase_unit_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP — Default Purchase Unit (additive, idempotent)
-- ------------------------------------------------------------
-- Product Units already track a "default SALES unit" (is_default).
-- This adds a separate "default PURCHASE unit" flag so purchase
-- invoices can auto-select a different pack size (e.g. sell by
-- Piece, but purchase by Carton) instead of reusing the sales
-- default. Safe to re-run; backward compatible with older DBs.
-- ============================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('product_units')
      AND name = 'is_default_purchase'
)
BEGIN
    ALTER TABLE product_units
        ADD is_default_purchase BIT NOT NULL DEFAULT 0;
END
GO

-- Backfill: for products with no purchase-default yet, use the same
-- unit as their sales default so nothing behaves differently until
-- someone explicitly picks a different purchase unit.
UPDATE pu
SET is_default_purchase = 1
FROM product_units pu
WHERE pu.is_default = 1
  AND NOT EXISTS (
      SELECT 1 FROM product_units pu2
      WHERE pu2.product_id = pu.product_id
        AND pu2.is_default_purchase = 1
  );
GO

GO

-- ▼▼▼  PATCH: expense_vat_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Expenses with VAT + asset purchases (v5.11)
-- ------------------------------------------------------------
-- The Expenses screen can now also record ASSET purchases (shop
-- furniture, equipment, computers, vehicles) with their input VAT,
-- and remembers the supplier, VAT rate and price-includes-VAT choice
-- so an entry can be opened and edited later.
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('expenses','expense_kind') IS NULL
    ALTER TABLE expenses ADD expense_kind NVARCHAR(10) DEFAULT 'expense';
GO
IF COL_LENGTH('expenses','supplier_id') IS NULL
    ALTER TABLE expenses ADD supplier_id INT NULL;
GO
IF COL_LENGTH('expenses','vat_rate') IS NULL
    ALTER TABLE expenses ADD vat_rate DECIMAL(5,2) NULL;
GO
IF COL_LENGTH('expenses','price_incl_vat') IS NULL
    ALTER TABLE expenses ADD price_incl_vat BIT DEFAULT 0;
GO
IF COL_LENGTH('expenses','supplier_vat_no') IS NULL
    ALTER TABLE expenses ADD supplier_vat_no NVARCHAR(20) NULL;
GO

PRINT '✅ expenses: asset purchases + VAT details added.';
GO

GO

-- ▼▼▼  PATCH: financial_year_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: inventory_units_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Inventory & Multi-Units Schema Patch
-- Runs after the base schema (INSTALL_DayBillERP_AllInOne.sql)
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

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_product_units_product')
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

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inventory_product')
    CREATE INDEX IX_inventory_product ON inventory_transactions(product_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inventory_date')
    CREATE INDEX IX_inventory_date ON inventory_transactions(txn_date);
GO

PRINT '✅ Inventory & Multi-Units patch applied.';
GO

GO

-- ▼▼▼  PATCH: multi_barcode_patch.sql  ▼▼▼
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

-- ▼▼▼  PATCH: party_ledger_patch.sql  ▼▼▼
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

-- ▼▼▼  PATCH: password_expiry_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Password expiry (Settings ▸ Users & Security ▸
-- Password Expiry). Remembers when each password was last set;
-- sign-in asks for a new password once it is older than the
-- configured number of days.
-- ============================================================
IF COL_LENGTH('users','password_changed_at') IS NULL
    ALTER TABLE users ADD password_changed_at DATETIME NULL
        CONSTRAINT DF_users_password_changed_at DEFAULT GETDATE();
GO

GO

-- ▼▼▼  PATCH: pos_favorites_patch.sql  ▼▼▼
-- ============================================================
-- POS favourites: products marked with ⭐ in the Product form (or
-- the Product list right-click menu) appear as one-touch buttons on
-- the POS ★ Favourites tab. fav_order lets you sort them.
-- Safe to run more than once.
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('products') AND name = 'is_favorite')
    ALTER TABLE products ADD is_favorite BIT NOT NULL DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('products') AND name = 'fav_order')
    ALTER TABLE products ADD fav_order INT NOT NULL DEFAULT 0;
GO
PRINT 'POS favourites patch applied.';
GO

GO

-- ▼▼▼  PATCH: price_change_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: print_designer_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Invoice Designer: one design per document type
-- The first template shipped with type 'invoice', which no screen
-- uses. It belongs to Sales Invoice.
-- ============================================================
IF EXISTS (SELECT 1 FROM sys.tables WHERE name='report_templates')
    UPDATE report_templates SET report_type='sales_invoice'
     WHERE report_type IS NULL OR report_type IN ('invoice', 'tax_invoice');
GO

GO

-- ▼▼▼  PATCH: product_extras_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Product Brands, Barcode Type/Default, Images
-- ------------------------------------------------------------
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- ── Brands ──────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='product_brands')
CREATE TABLE product_brands (
    brand_id       INT IDENTITY(1,1) PRIMARY KEY,
    brand_name_en  NVARCHAR(80) NOT NULL,
    brand_name_ar  NVARCHAR(80) NULL,
    is_active      BIT DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);
GO

IF COL_LENGTH('products','brand_id') IS NULL
    ALTER TABLE products ADD brand_id INT NULL;
GO

-- ── Barcode type + default flag (per-unit multi-barcode) ─────
IF COL_LENGTH('product_unit_barcodes','barcode_type') IS NULL
    ALTER TABLE product_unit_barcodes ADD barcode_type NVARCHAR(15) DEFAULT 'EAN-13';
GO
IF COL_LENGTH('product_unit_barcodes','is_default') IS NULL
    ALTER TABLE product_unit_barcodes ADD is_default BIT DEFAULT 0;
GO
-- make the first barcode of each unit the default, if none is set yet
IF EXISTS (SELECT 1 FROM product_unit_barcodes WHERE is_default=1)
    PRINT 'Default barcodes already set.';
ELSE
BEGIN
    ;WITH first_bc AS (
        SELECT barcode_id, ROW_NUMBER() OVER (PARTITION BY unit_id ORDER BY barcode_id) AS rn
        FROM product_unit_barcodes
    )
    UPDATE b SET b.is_default = 1
    FROM product_unit_barcodes b
    JOIN first_bc f ON f.barcode_id = b.barcode_id AND f.rn = 1;
END
GO

-- ── Per-product accounting overrides (optional; blank = use Default Accounts) ──
IF COL_LENGTH('products','sales_account_id') IS NULL
    ALTER TABLE products ADD sales_account_id INT NULL;
GO
IF COL_LENGTH('products','purchase_account_id') IS NULL
    ALTER TABLE products ADD purchase_account_id INT NULL;
GO
IF COL_LENGTH('products','inventory_account_id') IS NULL
    ALTER TABLE products ADD inventory_account_id INT NULL;
GO
IF COL_LENGTH('products','tax_account_id') IS NULL
    ALTER TABLE products ADD tax_account_id INT NULL;
GO

-- ── Multiple product images ───────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='product_images')
CREATE TABLE product_images (
    image_id     INT IDENTITY(1,1) PRIMARY KEY,
    product_id   INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    image_path   NVARCHAR(400) NOT NULL,
    is_default   BIT DEFAULT 0,
    sort_order   INT DEFAULT 0,
    created_at   DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_product_images_product')
    CREATE INDEX IX_product_images_product ON product_images(product_id);
GO

PRINT '✅ Product brand/barcode/accounting/image patch applied.';
GO

GO

-- ▼▼▼  PATCH: product_master_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: purchase_payment_method_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Fix: purchase_invoices missing payment_method
-- ------------------------------------------------------------
-- The Purchase Invoice screen writes a payment_method value, but the
-- column was never added to the table -> every save failed with a
-- "column missing" SQL error. Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('purchase_invoices','payment_method') IS NULL
    ALTER TABLE purchase_invoices ADD payment_method NVARCHAR(20) DEFAULT 'cash';
GO

PRINT '✅ purchase_invoices.payment_method added.';
GO

GO

-- ▼▼▼  PATCH: quotation_po_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: rbac_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP — User & Rights (RBAC) migration (auto-applied patch)
-- Safe to run multiple times. Adds tables/columns only if missing.
-- SQL Server (T-SQL).
-- ============================================================

-- ── Extra user columns (mobile, branch, warehouse, created_by) ──
IF COL_LENGTH('users','mobile') IS NULL
    ALTER TABLE users ADD mobile NVARCHAR(20) NULL;
IF COL_LENGTH('users','branch') IS NULL
    ALTER TABLE users ADD branch NVARCHAR(60) NULL;
IF COL_LENGTH('users','warehouse') IS NULL
    ALTER TABLE users ADD warehouse NVARCHAR(60) NULL;
IF COL_LENGTH('users','created_by') IS NULL
    ALTER TABLE users ADD created_by INT NULL;
GO

-- ── PERMISSIONS: one row per (module, action) ──────────────
IF OBJECT_ID('permissions','U') IS NULL
BEGIN
    CREATE TABLE permissions (
        permission_id   INT IDENTITY(1,1) PRIMARY KEY,
        module_key      NVARCHAR(40) NOT NULL,   -- products, sales, ...
        action_key      NVARCHAR(20) NOT NULL,   -- view, add, edit, ...
        CONSTRAINT UQ_perm UNIQUE (module_key, action_key)
    );
END
GO

-- ── ROLE ↔ PERMISSION grants ───────────────────────────────
IF OBJECT_ID('role_permissions','U') IS NULL
BEGIN
    CREATE TABLE role_permissions (
        role_id         INT NOT NULL REFERENCES roles(role_id),
        permission_id   INT NOT NULL REFERENCES permissions(permission_id),
        allowed         BIT NOT NULL DEFAULT 1,
        CONSTRAINT PK_role_perm PRIMARY KEY (role_id, permission_id)
    );
END
GO

-- ── LOGIN HISTORY ──────────────────────────────────────────
IF OBJECT_ID('login_history','U') IS NULL
BEGIN
    CREATE TABLE login_history (
        login_id        INT IDENTITY(1,1) PRIMARY KEY,
        user_id         INT NULL REFERENCES users(user_id),
        username        NVARCHAR(50) NULL,
        success         BIT NOT NULL DEFAULT 1,
        workstation     NVARCHAR(100) NULL,
        login_time      DATETIME NOT NULL DEFAULT GETDATE()
    );
END
GO

-- audit_logs table used by modules/audit.py (separate from schema's audit_log)
IF OBJECT_ID('audit_logs','U') IS NULL
BEGIN
    CREATE TABLE audit_logs (
        audit_id        INT IDENTITY(1,1) PRIMARY KEY,
        user_id         INT NULL,
        action          NVARCHAR(50) NOT NULL,
        module          NVARCHAR(50) NULL,
        ref_id          NVARCHAR(50) NULL,
        details         NVARCHAR(4000) NULL,
        workstation     NVARCHAR(100) NULL,
        created_at      DATETIME NOT NULL DEFAULT GETDATE()
    );
END
GO

-- ── Seed the 9 predefined roles (only if missing) ──────────
;WITH seed(en, ar) AS (
    SELECT 'Super Admin', N'مدير عام'      UNION ALL
    SELECT 'Admin',       N'مدير'          UNION ALL
    SELECT 'Manager',     N'مشرف'          UNION ALL
    SELECT 'Accountant',  N'محاسب'         UNION ALL
    SELECT 'Sales',       N'مبيعات'        UNION ALL
    SELECT 'Purchase',    N'مشتريات'       UNION ALL
    SELECT 'Inventory',   N'مخزون'         UNION ALL
    SELECT 'Cashier',     N'أمين صندوق'    UNION ALL
    SELECT 'Viewer',      N'مشاهد'
)
INSERT INTO roles (role_name_en, role_name_ar, is_active)
SELECT s.en, s.ar, 1 FROM seed s
WHERE NOT EXISTS (SELECT 1 FROM roles r WHERE r.role_name_en = s.en);
GO

GO

-- ▼▼▼  PATCH: report_designer_patch.sql  ▼▼▼
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

-- ▼▼▼  PATCH: returns_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: search_listing_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Product Search & Listing Flags Patch
-- Adds alias name + per-channel active flags (sales / purchase)
-- Runs after the base schema (INSTALL_DayBillERP_AllInOne.sql). Safe to re-run.
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

PRINT '✅ Product search & listing flags patch applied.';
GO

GO

-- ▼▼▼  PATCH: stock_posting_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v5.7 — stock & accounts posting engine
-- ------------------------------------------------------------
-- * sales_invoices.sale_channel ('POS' / 'INV') for the POS report
-- * index for stock-movement lookups by document
-- * records the stock that OLDER versions already moved for existing
--   purchases and returns (they moved stock on save, even drafts), so
--   editing / confirming / deleting those documents now reverses the
--   old movement exactly once — no double stock.
-- Safe to run more than once.
-- ============================================================

IF COL_LENGTH('sales_invoices','sale_channel') IS NULL
    ALTER TABLE sales_invoices ADD sale_channel NVARCHAR(10) NULL;
GO

IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_invtxn_reference')
    CREATE INDEX IX_invtxn_reference ON inventory_transactions(reference_type, reference_id);
GO

-- Purchases saved by older versions (stock was added at save time)
IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND OBJECT_ID('purchase_invoice_lines','U') IS NOT NULL
   AND OBJECT_ID('product_units','U') IS NOT NULL
BEGIN
    INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type,
        reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base,
        balance_base, unit_cost, notes)
    SELECT l.product_id, ISNULL(pi.invoice_date, CAST(GETDATE() AS date)),
        'purchase', 'purchase_invoice', pi.purchase_id,
        ISNULL(l.unit_of_measure_en, 'Unit'), l.quantity,
        l.quantity * ISNULL((SELECT TOP 1 NULLIF(pu.conversion_factor, 0)
                             FROM product_units pu
                             WHERE pu.product_id = l.product_id
                               AND pu.unit_name_en = l.unit_of_measure_en), 1),
        0, 0, 0, 0, N'moved before v5.7'
    FROM purchase_invoice_lines l
    JOIN purchase_invoices pi ON pi.purchase_id = l.purchase_id
    JOIN products p ON p.product_id = l.product_id
    WHERE ISNULL(pi.invoice_status, '') <> 'cancelled'
      AND ISNULL(l.quantity, 0) <> 0
      AND NOT EXISTS (SELECT 1 FROM inventory_transactions t
                      WHERE t.reference_type = 'purchase_invoice'
                        AND t.reference_id = pi.purchase_id);
END
GO

-- Sales returns saved by older versions (stock added back, base qty)
IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND OBJECT_ID('sales_return_lines','U') IS NOT NULL
BEGIN
    INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type,
        reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base,
        balance_base, unit_cost, notes)
    SELECT l.product_id,
        ISNULL(TRY_CONVERT(date, r.return_date), CAST(ISNULL(r.created_at, GETDATE()) AS date)),
        'return_in', 'sales_return', r.return_id, ISNULL(l.unit_of_measure_en, 'Unit'),
        l.quantity, l.quantity, 0, 0, 0, 0, N'moved before v5.7'
    FROM sales_return_lines l
    JOIN sales_returns r ON r.return_id = l.return_id
    JOIN products p ON p.product_id = l.product_id
    WHERE ISNULL(l.quantity, 0) <> 0
      AND NOT EXISTS (SELECT 1 FROM inventory_transactions t
                      WHERE t.reference_type = 'sales_return'
                        AND t.reference_id = r.return_id);
END
GO

-- Purchase returns saved by older versions (stock taken out, base qty)
IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND OBJECT_ID('purchase_return_lines','U') IS NOT NULL
BEGIN
    INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type,
        reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base,
        balance_base, unit_cost, notes)
    SELECT l.product_id,
        ISNULL(TRY_CONVERT(date, r.return_date), CAST(ISNULL(r.created_at, GETDATE()) AS date)),
        'return_out', 'purchase_return', r.return_id, ISNULL(l.unit_of_measure_en, 'Unit'),
        0, 0, l.quantity, l.quantity, 0, 0, N'moved before v5.7'
    FROM purchase_return_lines l
    JOIN purchase_returns r ON r.return_id = l.return_id
    JOIN products p ON p.product_id = l.product_id
    WHERE ISNULL(l.quantity, 0) <> 0
      AND NOT EXISTS (SELECT 1 FROM inventory_transactions t
                      WHERE t.reference_type = 'purchase_return'
                        AND t.reference_id = r.return_id);
END
GO


-- Offset account for manual stock adjustments / physical counts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5160')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5160', 'Stock Adjustment', N'تسوية المخزون', 'expense');
GO

PRINT 'Stock & accounts posting engine patch applied.';
GO

GO

-- ▼▼▼  PATCH: user_rights_patch.sql  ▼▼▼
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

-- ▼▼▼  PATCH: user_roles_patch.sql  ▼▼▼
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

-- ▼▼▼  PATCH: weight_scale_patch.sql  ▼▼▼
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

-- ▼▼▼  PATCH: zatca_phase2_patch.sql  ▼▼▼
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

PRINT '✅ ZATCA Phase 2 schema patch applied.';
GO

GO

-- ▼▼▼  PATCH: zz_barcode_unique_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v5.22.0 - unit barcodes: unique, but blanks allowed
-- ------------------------------------------------------------
-- product_units had  CONSTRAINT UQ_product_unit_barcode UNIQUE (barcode).
-- On SQL Server a UNIQUE constraint lets only ONE row have NULL, so the
-- second unit saved without a barcode (or the second unit removed from a
-- product, which clears its barcode) failed with
--   "Violation of UNIQUE KEY constraint 'UQ_product_unit_barcode'".
-- Now: a filtered unique index - every real barcode is still unique,
-- any number of units may have no barcode. Safe to run again.
-- ============================================================
SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
IF OBJECT_ID('product_units','U') IS NOT NULL
BEGIN
    DECLARE @n sysname;
    SELECT TOP 1 @n = kc.name
      FROM sys.key_constraints kc
      JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id
                               AND ic.index_id  = kc.unique_index_id
      JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
     WHERE kc.parent_object_id = OBJECT_ID('product_units')
       AND kc.type = 'UQ' AND c.name = 'barcode';
    IF @n IS NOT NULL
        EXEC(N'ALTER TABLE product_units DROP CONSTRAINT [' + @n + N']');
END
GO
IF OBJECT_ID('product_units','U') IS NOT NULL
    UPDATE product_units SET barcode = NULL WHERE LTRIM(RTRIM(barcode)) = '';
GO
IF OBJECT_ID('product_units','U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes
                    WHERE name = 'UX_product_units_barcode'
                      AND object_id = OBJECT_ID('product_units'))
    CREATE UNIQUE INDEX UX_product_units_barcode
        ON product_units(barcode) WHERE barcode IS NOT NULL AND barcode <> '';
GO

GO

-- ▼▼▼  PATCH: zz_branch_counter_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - Branches, counters (tills) and product key (v5.12)
-- ------------------------------------------------------------
-- * branches      : shops / locations (one shared stock)
-- * counters      : cash counters (POS / billing PCs) of a branch
-- * branch_id + counter_id stamped on sales, POS bills, returns,
--   purchases, receipts / payments and expenses → counter-wise and
--   branch-wise sales + day close.
-- * app_license   : trial start + product key, shared by every PC
--   that uses this database.
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('branches','U') IS NULL
CREATE TABLE branches (
    branch_id     INT IDENTITY(1,1) PRIMARY KEY,
    name_en       NVARCHAR(100) NOT NULL,
    name_ar       NVARCHAR(100),
    is_active     BIT DEFAULT 1
);
GO
IF COL_LENGTH('branches','code') IS NULL
    ALTER TABLE branches ADD code NVARCHAR(10) NULL;
GO
IF COL_LENGTH('branches','address') IS NULL
    ALTER TABLE branches ADD address NVARCHAR(200) NULL;
GO
IF COL_LENGTH('branches','phone') IS NULL
    ALTER TABLE branches ADD phone NVARCHAR(30) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM branches)
    INSERT INTO branches (name_en, name_ar, code, is_active) VALUES (N'Main Branch', N'الفرع الرئيسي', 'B1', 1);
GO

IF OBJECT_ID('counters','U') IS NULL
CREATE TABLE counters (
    counter_id     INT IDENTITY(1,1) PRIMARY KEY,
    branch_id      INT NOT NULL REFERENCES branches(branch_id),
    code           NVARCHAR(10) NOT NULL,
    name_en        NVARCHAR(60) NOT NULL,
    workstation    NVARCHAR(100) NULL,      -- PC name last used for it
    is_active      BIT DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM counters)
    INSERT INTO counters (branch_id, code, name_en, is_active)
    SELECT TOP 1 branch_id, 'C1', N'Counter 1', 1 FROM branches ORDER BY branch_id;
GO

IF COL_LENGTH('sales_invoices','branch_id') IS NULL
    ALTER TABLE sales_invoices ADD branch_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','counter_id') IS NULL
    ALTER TABLE sales_invoices ADD counter_id INT NULL;
GO
IF COL_LENGTH('sales_returns','branch_id') IS NULL
    ALTER TABLE sales_returns ADD branch_id INT NULL;
GO
IF COL_LENGTH('sales_returns','counter_id') IS NULL
    ALTER TABLE sales_returns ADD counter_id INT NULL;
GO
IF COL_LENGTH('purchase_invoices','branch_id') IS NULL
    ALTER TABLE purchase_invoices ADD branch_id INT NULL;
GO
IF COL_LENGTH('purchase_invoices','counter_id') IS NULL
    ALTER TABLE purchase_invoices ADD counter_id INT NULL;
GO
IF COL_LENGTH('purchase_returns','branch_id') IS NULL
    ALTER TABLE purchase_returns ADD branch_id INT NULL;
GO
IF COL_LENGTH('purchase_returns','counter_id') IS NULL
    ALTER TABLE purchase_returns ADD counter_id INT NULL;
GO
IF COL_LENGTH('payments','branch_id') IS NULL
    ALTER TABLE payments ADD branch_id INT NULL;
GO
IF COL_LENGTH('payments','counter_id') IS NULL
    ALTER TABLE payments ADD counter_id INT NULL;
GO
IF COL_LENGTH('expenses','branch_id') IS NULL
    ALTER TABLE expenses ADD branch_id INT NULL;
GO
IF COL_LENGTH('expenses','counter_id') IS NULL
    ALTER TABLE expenses ADD counter_id INT NULL;
GO

-- older data belongs to the first branch / counter
UPDATE sales_invoices SET branch_id = (SELECT TOP 1 branch_id FROM branches ORDER BY branch_id)
    WHERE branch_id IS NULL;
GO
UPDATE sales_invoices SET counter_id = (SELECT TOP 1 counter_id FROM counters ORDER BY counter_id)
    WHERE counter_id IS NULL;
GO

IF OBJECT_ID('app_license','U') IS NULL
CREATE TABLE app_license (
    id              INT NOT NULL PRIMARY KEY,
    install_id      NVARCHAR(40) NOT NULL,
    installed_at    DATE NOT NULL,
    product_key     NVARCHAR(1000) NULL,
    activated_at    DATETIME NULL,
    last_online     DATETIME NULL,
    online_status   NVARCHAR(20) NULL,       -- active / blocked / unknown
    online_message  NVARCHAR(300) NULL
);
GO

PRINT '✅ Branches, counters and product key tables ready.';
GO

GO

-- ▼▼▼  PATCH: zz_mobile_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v5.23.0 - Mobile / PDT / Van sales
-- ------------------------------------------------------------
--   mobile_access : which DayBill user may use which mobile modules
--                   (Goods In, Goods Out, Stock Count, Stock Adjust,
--                   Product Info, Price Check, Van Sales) + van code / PIN
--   mobile_tokens : signed-in devices
--   mobile_docs   : every document sent from a phone / PDT / van
--                   (inbox: pending → applied / rejected), never twice
-- Safe to run again.
-- ============================================================
IF OBJECT_ID('mobile_access','U') IS NULL
CREATE TABLE mobile_access (
    user_id       INT NOT NULL PRIMARY KEY REFERENCES users(user_id),
    modules       NVARCHAR(300) NULL,
    van_code      NVARCHAR(20) NULL,
    van_pin_hash  NVARCHAR(200) NULL,
    is_active     BIT NOT NULL DEFAULT 1,
    updated_at    DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('mobile_tokens','U') IS NULL
CREATE TABLE mobile_tokens (
    token       NVARCHAR(64) NOT NULL PRIMARY KEY,
    user_id     INT NOT NULL,
    device      NVARCHAR(120) NULL,
    created_at  DATETIME DEFAULT GETDATE(),
    last_seen   DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('mobile_docs','U') IS NULL
CREATE TABLE mobile_docs (
    doc_id       INT IDENTITY(1,1) PRIMARY KEY,
    doc_uid      NVARCHAR(64) NOT NULL UNIQUE,
    doc_type     NVARCHAR(20) NOT NULL,
    source       NVARCHAR(20) NOT NULL DEFAULT 'wifi',
    user_id      INT NULL,
    device       NVARCHAR(120) NULL,
    status       NVARCHAR(20) NOT NULL DEFAULT 'pending',
    title        NVARCHAR(200) NULL,
    header_json  NVARCHAR(MAX) NULL,
    lines_json   NVARCHAR(MAX) NULL,
    result       NVARCHAR(400) NULL,
    ref_table    NVARCHAR(40) NULL,
    ref_id       INT NULL,
    created_at   DATETIME DEFAULT GETDATE(),
    applied_at   DATETIME NULL,
    applied_by   INT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_mobile_docs_status'
               AND object_id=OBJECT_ID('mobile_docs'))
    CREATE INDEX IX_mobile_docs_status ON mobile_docs(status, created_at);
GO
IF COL_LENGTH('mobile_access','device_seq') IS NULL
    ALTER TABLE mobile_access ADD device_seq INT NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('sales_invoices','van_ref') IS NULL
    ALTER TABLE sales_invoices ADD van_ref NVARCHAR(40) NULL;
GO

GO

-- ▼▼▼  PATCH: zz_offers_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: zz_pos_split_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - POS part-cash / part-card payment (v5.15)
-- ------------------------------------------------------------
-- A POS bill can be paid partly in cash and partly by card.
-- cash_paid / card_paid keep that split so reports can show it
-- (the accounts are posted from the same amounts).
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO
IF COL_LENGTH('sales_invoices','cash_paid') IS NULL
    ALTER TABLE sales_invoices ADD cash_paid DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('sales_invoices','card_paid') IS NULL
    ALTER TABLE sales_invoices ADD card_paid DECIMAL(18,2) NULL;
GO
PRINT '✅ POS cash + card split columns ready.';
GO

GO

-- ▼▼▼  PATCH: zz_v600_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - v6.0.0 database update
-- ------------------------------------------------------------
--  ZATCA      one e-invoicing unit per till, debit notes, 700 number
--  POS        payment lines (cash / mada / STC Pay / Tabby …),
--             cashier shifts (opening float, counted cash)
--  Prices     price lists for customers (wholesale, VIP …)
--  Stock      stock per branch, transfers between branches,
--             batches with expiry dates (first-expiry-first-out)
--  Books      bank reconciliation, year-end closing entry
--  HR         leave, attendance, GOSI old / new system per employee
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- ── ZATCA ───────────────────────────────────────────────────
IF OBJECT_ID('zatca_egs','U') IS NOT NULL AND COL_LENGTH('zatca_egs','counter_id') IS NULL
    EXEC(N'ALTER TABLE zatca_egs ADD counter_id INT NULL');   -- table made by zz_zatca2 (v6.9)
GO
IF COL_LENGTH('sales_invoices','invoice_kind') IS NULL
    ALTER TABLE sales_invoices ADD invoice_kind NVARCHAR(12) NULL;
GO
IF COL_LENGTH('sales_invoices','original_invoice_no') IS NULL
    ALTER TABLE sales_invoices ADD original_invoice_no NVARCHAR(50) NULL;
GO
IF COL_LENGTH('sales_invoices','debit_reason') IS NULL
    ALTER TABLE sales_invoices ADD debit_reason NVARCHAR(200) NULL;
GO
IF COL_LENGTH('company','id_scheme') IS NULL
    ALTER TABLE company ADD id_scheme NVARCHAR(5) NULL;
GO

-- ── POS: payment lines ──────────────────────────────────────
IF OBJECT_ID('payment_tenders','U') IS NULL
CREATE TABLE payment_tenders (
    tender_id     INT IDENTITY(1,1) PRIMARY KEY,
    doc_type      NVARCHAR(20) NOT NULL,
    doc_id        INT NOT NULL,
    method        NVARCHAR(20) NOT NULL,
    amount        DECIMAL(18,2) NOT NULL DEFAULT 0,
    reference     NVARCHAR(100) NULL,
    account_id    INT NULL,
    created_at    DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_payment_tenders_doc')
    CREATE INDEX IX_payment_tenders_doc ON payment_tenders(doc_type, doc_id);
GO

-- ── POS: cashier shifts ─────────────────────────────────────
IF OBJECT_ID('cashier_shifts','U') IS NULL
CREATE TABLE cashier_shifts (
    shift_id       INT IDENTITY(1,1) PRIMARY KEY,
    counter_id     INT NULL,
    branch_id      INT NULL,
    user_id        INT NULL,
    username       NVARCHAR(50) NULL,
    opened_at      DATETIME DEFAULT GETDATE(),
    opening_float  DECIMAL(18,2) NOT NULL DEFAULT 0,
    closed_at      DATETIME NULL,
    expected_cash  DECIMAL(18,2) NULL,
    counted_cash   DECIMAL(18,2) NULL,
    difference     DECIMAL(18,2) NULL,
    status         NVARCHAR(10) NOT NULL DEFAULT 'open',
    notes          NVARCHAR(500) NULL
);
GO
IF COL_LENGTH('sales_invoices','shift_id') IS NULL
    ALTER TABLE sales_invoices ADD shift_id INT NULL;
GO
IF COL_LENGTH('sales_returns','shift_id') IS NULL
    ALTER TABLE sales_returns ADD shift_id INT NULL;
GO

-- ── price lists ─────────────────────────────────────────────
IF OBJECT_ID('price_lists','U') IS NULL
CREATE TABLE price_lists (
    price_list_id   INT IDENTITY(1,1) PRIMARY KEY,
    name_en         NVARCHAR(60) NOT NULL,
    name_ar         NVARCHAR(60) NULL,
    base_on         NVARCHAR(12) NOT NULL DEFAULT 'retail',
    adjust_percent  DECIMAL(9,3) NOT NULL DEFAULT 0,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('price_list_items','U') IS NULL
CREATE TABLE price_list_items (
    item_id         INT IDENTITY(1,1) PRIMARY KEY,
    price_list_id   INT NOT NULL,
    product_id      INT NOT NULL,
    unit_name       NVARCHAR(50) NULL,
    price           DECIMAL(18,4) NOT NULL DEFAULT 0
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_price_list_items')
    CREATE UNIQUE INDEX UX_price_list_items ON price_list_items(price_list_id, product_id, unit_name);
GO
IF COL_LENGTH('customers','price_list_id') IS NULL
    ALTER TABLE customers ADD price_list_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','price_list_id') IS NULL
    ALTER TABLE sales_invoices ADD price_list_id INT NULL;
GO

-- ── stock per branch ────────────────────────────────────────
-- A branch's stock = its rows on the stock card (inventory_transactions
-- .branch_id). Rows with no branch belong to the main branch, so a
-- one-branch shop sees no change at all.
IF COL_LENGTH('inventory_transactions','branch_id') IS NULL
    ALTER TABLE inventory_transactions ADD branch_id INT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inv_txn_branch')
    CREATE INDEX IX_inv_txn_branch ON inventory_transactions(branch_id, product_id);
GO
IF OBJECT_ID('stock_transfers','U') IS NULL
CREATE TABLE stock_transfers (
    transfer_id      INT IDENTITY(1,1) PRIMARY KEY,
    transfer_number  NVARCHAR(30) NOT NULL,
    transfer_date    DATE NOT NULL,
    from_branch_id   INT NOT NULL,
    to_branch_id     INT NOT NULL,
    status           NVARCHAR(12) NOT NULL DEFAULT 'done',
    notes            NVARCHAR(300) NULL,
    created_by       INT NULL,
    created_at       DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('stock_transfer_lines','U') IS NULL
CREATE TABLE stock_transfer_lines (
    line_id       INT IDENTITY(1,1) PRIMARY KEY,
    transfer_id   INT NOT NULL,
    product_id    INT NOT NULL,
    unit_name     NVARCHAR(50) NULL,
    factor        DECIMAL(18,6) NOT NULL DEFAULT 1,
    quantity      DECIMAL(18,4) NOT NULL DEFAULT 0,
    qty_base      DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_cost     DECIMAL(18,4) NULL
);
GO

-- ── batches & expiry ────────────────────────────────────────
IF COL_LENGTH('products','track_expiry') IS NULL
    ALTER TABLE products ADD track_expiry BIT NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('purchase_invoice_lines','batch_no') IS NULL
    ALTER TABLE purchase_invoice_lines ADD batch_no NVARCHAR(50) NULL;
GO
IF COL_LENGTH('purchase_invoice_lines','expiry_date') IS NULL
    ALTER TABLE purchase_invoice_lines ADD expiry_date DATE NULL;
GO
IF OBJECT_ID('product_batches','U') IS NULL
CREATE TABLE product_batches (
    batch_id       INT IDENTITY(1,1) PRIMARY KEY,
    product_id     INT NOT NULL,
    branch_id      INT NULL,
    batch_no       NVARCHAR(50) NULL,
    expiry_date    DATE NULL,
    qty_base       DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_cost      DECIMAL(18,4) NULL,
    received_date  DATE NULL,
    created_at     DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('batch_movements','U') IS NULL
CREATE TABLE batch_movements (
    move_id       INT IDENTITY(1,1) PRIMARY KEY,
    batch_id      INT NOT NULL,
    source_type   NVARCHAR(30) NOT NULL,
    source_id     INT NOT NULL,
    qty_base      DECIMAL(18,4) NOT NULL,
    created_at    DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_batch_movements_src')
    CREATE INDEX IX_batch_movements_src ON batch_movements(source_type, source_id);
GO

-- ── bank reconciliation ─────────────────────────────────────
IF OBJECT_ID('bank_reconciliations','U') IS NULL
CREATE TABLE bank_reconciliations (
    rec_id             INT IDENTITY(1,1) PRIMARY KEY,
    account_id         INT NOT NULL,
    statement_date     DATE NOT NULL,
    statement_balance  DECIMAL(18,2) NOT NULL DEFAULT 0,
    cleared_balance    DECIMAL(18,2) NULL,
    difference         DECIMAL(18,2) NULL,
    status             NVARCHAR(10) NOT NULL DEFAULT 'draft',
    notes              NVARCHAR(300) NULL,
    created_by         INT NULL,
    created_at         DATETIME DEFAULT GETDATE(),
    finished_at        DATETIME NULL
);
GO
IF COL_LENGTH('journal_lines','rec_id') IS NULL
    ALTER TABLE journal_lines ADD rec_id INT NULL;
GO

-- ── year-end closing ────────────────────────────────────────
IF COL_LENGTH('financial_years','closing_journal_id') IS NULL
    ALTER TABLE financial_years ADD closing_journal_id INT NULL;
GO

-- ── HR: GOSI system, leave, attendance ──────────────────────
IF COL_LENGTH('employees','gosi_system') IS NULL
    ALTER TABLE employees ADD gosi_system NVARCHAR(4) NULL;
GO
IF OBJECT_ID('employee_leaves','U') IS NULL
CREATE TABLE employee_leaves (
    leave_id      INT IDENTITY(1,1) PRIMARY KEY,
    employee_id   INT NOT NULL,
    leave_type    NVARCHAR(20) NOT NULL DEFAULT 'annual',
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    days          DECIMAL(6,1) NOT NULL DEFAULT 0,
    paid          BIT NOT NULL DEFAULT 1,
    status        NVARCHAR(12) NOT NULL DEFAULT 'approved',
    notes         NVARCHAR(300) NULL,
    created_at    DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('attendance','U') IS NULL
CREATE TABLE attendance (
    att_id        INT IDENTITY(1,1) PRIMARY KEY,
    employee_id   INT NOT NULL,
    work_date     DATE NOT NULL,
    check_in      NVARCHAR(5) NULL,
    check_out     NVARCHAR(5) NULL,
    hours         DECIMAL(6,2) NULL,
    status        NVARCHAR(10) NOT NULL DEFAULT 'present',
    notes         NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_attendance_day')
    CREATE UNIQUE INDEX UX_attendance_day ON attendance(employee_id, work_date);
GO
PRINT '✅ DayBill v6.0.0 database update ready.';
GO

GO

-- ▼▼▼  PATCH: zz_v640_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: zz_v650_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - v6.5.0 database update
-- ------------------------------------------------------------
--  WhatsApp     every message sent with the Cloud API (Meta charges
--               each one since 1 Oct 2026) — the monthly count and
--               cost in Settings ▸ WhatsApp
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('whatsapp_messages','U') IS NULL
CREATE TABLE whatsapp_messages (
    msg_id      INT IDENTITY(1,1) PRIMARY KEY,
    sent_at     DATETIME DEFAULT GETDATE(),
    sent_date   DATE NULL,
    phone       NVARCHAR(30) NULL,
    kind        NVARCHAR(40) NULL,             -- sales | purchase_order | owner_report | …
    template    NVARCHAR(100) NULL,
    has_pdf     BIT DEFAULT 0,
    ok          BIT DEFAULT 1,
    info        NVARCHAR(300) NULL             -- WhatsApp message id or the error
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_whatsapp_messages_date')
    CREATE INDEX IX_whatsapp_messages_date ON whatsapp_messages(sent_date, ok);
GO

PRINT 'DayBill v6.5.0 database update applied (WhatsApp message count).';
GO

GO

-- ▼▼▼  PATCH: zz_v660_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - v6.6.0 database update  (HR & Payroll)
-- ------------------------------------------------------------
--  employees     documents with expiry dates (Iqama / ID, passport,
--                medical insurance, contract), birth date, phone, email
--  payslips      overtime / bonus / absence + sick-leave deduction kept
--                apart, the loan the instalment came from
--  payroll_runs  approved / paid (salaries, GOSI) with the dates
--  eos_settlements  final settlement: award before the resignation
--                share, leave days paid, loan taken back, net
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('employees','iqama_expiry') IS NULL      ALTER TABLE employees ADD iqama_expiry DATE NULL;
GO
IF COL_LENGTH('employees','passport_no') IS NULL       ALTER TABLE employees ADD passport_no NVARCHAR(30) NULL;
GO
IF COL_LENGTH('employees','passport_expiry') IS NULL   ALTER TABLE employees ADD passport_expiry DATE NULL;
GO
IF COL_LENGTH('employees','insurance_expiry') IS NULL  ALTER TABLE employees ADD insurance_expiry DATE NULL;
GO
IF COL_LENGTH('employees','contract_end') IS NULL      ALTER TABLE employees ADD contract_end DATE NULL;
GO
IF COL_LENGTH('employees','birth_date') IS NULL        ALTER TABLE employees ADD birth_date DATE NULL;
GO
IF COL_LENGTH('employees','phone') IS NULL             ALTER TABLE employees ADD phone NVARCHAR(30) NULL;
GO
IF COL_LENGTH('employees','email') IS NULL             ALTER TABLE employees ADD email NVARCHAR(120) NULL;
GO
IF COL_LENGTH('employees','gender') IS NULL            ALTER TABLE employees ADD gender NVARCHAR(1) NULL;   -- M / F
GO
-- annual leave balance carried in from before DayBill (days left on that date)
IF COL_LENGTH('employees','leave_open_days') IS NULL   ALTER TABLE employees ADD leave_open_days DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('employees','leave_open_date') IS NULL   ALTER TABLE employees ADD leave_open_date DATE NULL;
GO

IF COL_LENGTH('payslips','loan_id') IS NULL            ALTER TABLE payslips ADD loan_id INT NULL;
GO
IF COL_LENGTH('payslips','bonus_amount') IS NULL       ALTER TABLE payslips ADD bonus_amount DECIMAL(18,2) NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('payslips','absence_days') IS NULL       ALTER TABLE payslips ADD absence_days DECIMAL(9,2) NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('payslips','absence_deduction') IS NULL  ALTER TABLE payslips ADD absence_deduction DECIMAL(18,2) NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('payslips','sick_deduction') IS NULL     ALTER TABLE payslips ADD sick_deduction DECIMAL(18,2) NOT NULL DEFAULT 0;
GO

IF COL_LENGTH('payroll_runs','paid_at') IS NULL        ALTER TABLE payroll_runs ADD paid_at DATETIME NULL;
GO
IF COL_LENGTH('payroll_runs','paid_method') IS NULL    ALTER TABLE payroll_runs ADD paid_method NVARCHAR(30) NULL;
GO
IF COL_LENGTH('payroll_runs','gosi_paid_at') IS NULL   ALTER TABLE payroll_runs ADD gosi_paid_at DATETIME NULL;
GO

IF COL_LENGTH('eos_settlements','award_full') IS NULL      ALTER TABLE eos_settlements ADD award_full DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','award_share') IS NULL     ALTER TABLE eos_settlements ADD award_share DECIMAL(9,4) NULL;
GO
IF COL_LENGTH('eos_settlements','leave_days') IS NULL      ALTER TABLE eos_settlements ADD leave_days DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('eos_settlements','leave_pay') IS NULL       ALTER TABLE eos_settlements ADD leave_pay DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','loan_recovered') IS NULL  ALTER TABLE eos_settlements ADD loan_recovered DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','net_settlement') IS NULL  ALTER TABLE eos_settlements ADD net_settlement DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','wage_basis') IS NULL      ALTER TABLE eos_settlements ADD wage_basis NVARCHAR(20) NULL;
GO

-- v6.6: probation (up to 180 days, 2025 law), resignation dates (art. 79 / 2025),
--       Ramadan hours (art. 98), notice pay and art. 77 compensation in the settlement
IF COL_LENGTH('employees','probation_days') IS NULL    ALTER TABLE employees ADD probation_days INT NULL;
GO
IF COL_LENGTH('employees','resign_date') IS NULL       ALTER TABLE employees ADD resign_date DATE NULL;
GO
IF COL_LENGTH('employees','resign_status') IS NULL     ALTER TABLE employees ADD resign_status NVARCHAR(20) NULL;
GO
IF COL_LENGTH('employees','ramadan_hours') IS NULL     ALTER TABLE employees ADD ramadan_hours BIT NULL;  -- NULL = yes
GO
IF COL_LENGTH('eos_settlements','days_not_counted') IS NULL ALTER TABLE eos_settlements ADD days_not_counted DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('eos_settlements','notice_days') IS NULL     ALTER TABLE eos_settlements ADD notice_days DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('eos_settlements','notice_amount') IS NULL   ALTER TABLE eos_settlements ADD notice_amount DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','compensation_77') IS NULL ALTER TABLE eos_settlements ADD compensation_77 DECIMAL(18,2) NULL;
GO

PRINT 'DayBill v6.6.0 database update applied (HR documents, payslip parts, payroll paid, final settlement).';
GO

GO

-- ▼▼▼  PATCH: zz_v680_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - v6.8.0 database update
-- ------------------------------------------------------------
--  Online forms   answers from Tally web forms (customer and
--                 supplier registration, receipt feedback) wait
--                 here until someone reviews them
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('online_form_entries','U') IS NULL
CREATE TABLE online_form_entries (
    entry_id      INT IDENTITY(1,1) PRIMARY KEY,
    form_kind     NVARCHAR(20) NOT NULL,          -- customer | supplier | feedback
    submission_id NVARCHAR(60) NOT NULL,          -- Tally submission id (never twice)
    submitted_at  DATETIME NULL,
    received_at   DATETIME DEFAULT GETDATE(),
    title         NVARCHAR(200) NULL,             -- name, or the start of the comment
    phone         NVARCHAR(30) NULL,
    rating        INT NULL,                       -- feedback: 1–5 stars
    bill_no       NVARCHAR(40) NULL,              -- feedback: bill on the receipt QR
    payload_json  NVARCHAR(MAX) NULL,             -- all answers as sent
    status        NVARCHAR(20) DEFAULT 'new',     -- new | added | ignored | done
    record_id     INT NULL,                       -- the customer / supplier made from it
    handled_by    NVARCHAR(50) NULL,
    handled_at    DATETIME NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_online_form_entries_sub')
    CREATE UNIQUE INDEX UX_online_form_entries_sub ON online_form_entries(submission_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_online_form_entries_kind')
    CREATE INDEX IX_online_form_entries_kind ON online_form_entries(form_kind, status);
GO

PRINT 'DayBill v6.8.0 database update applied (online forms).';
GO

GO

-- ▼▼▼  PATCH: zz_zatca2_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP - ZATCA Phase 2 connection + send queue (v5.21)
-- ------------------------------------------------------------
-- zatca_egs : this shop's e-invoicing unit (EGS): private key,
--             ZATCA certificates (CSIDs), invoice counter (ICV)
--             and the last invoice hash (PIH chain)
-- sales_invoices / sales_returns : the signed XML, hash, Phase 2 QR
--             and the ZATCA answer of every document sent
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO
IF OBJECT_ID('zatca_egs','U') IS NULL
CREATE TABLE zatca_egs (
    egs_id            INT IDENTITY(1,1) PRIMARY KEY,
    env               NVARCHAR(20)  NOT NULL DEFAULT 'sandbox',
    egs_name          NVARCHAR(100) NULL,
    egs_serial        NVARCHAR(200) NULL,
    private_key       NVARCHAR(MAX) NULL,
    csr               NVARCHAR(MAX) NULL,
    ccsid_token       NVARCHAR(MAX) NULL,
    ccsid_secret      NVARCHAR(MAX) NULL,
    ccsid_request_id  NVARCHAR(100) NULL,
    pcsid_token       NVARCHAR(MAX) NULL,
    pcsid_secret      NVARCHAR(MAX) NULL,
    pcsid_request_id  NVARCHAR(100) NULL,
    cert_expires      DATETIME NULL,
    icv               INT NOT NULL DEFAULT 0,
    last_hash         NVARCHAR(200) NULL,
    status            NVARCHAR(20) NOT NULL DEFAULT 'new',
    is_active         BIT NOT NULL DEFAULT 1,
    auto_send         BIT NOT NULL DEFAULT 1,
    onboarded_at      DATETIME NULL,
    created_at        DATETIME NOT NULL DEFAULT GETDATE(),
    last_error        NVARCHAR(1000) NULL
);
GO
-- ── sales_invoices ──────────────────────────────────────────
IF COL_LENGTH('sales_invoices','zatca_uuid') IS NULL ALTER TABLE sales_invoices ADD zatca_uuid NVARCHAR(36) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_icv') IS NULL ALTER TABLE sales_invoices ADD zatca_icv INT NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_kind') IS NULL ALTER TABLE sales_invoices ADD zatca_kind NVARCHAR(12) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_egs_id') IS NULL ALTER TABLE sales_invoices ADD zatca_egs_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_attempts') IS NULL ALTER TABLE sales_invoices ADD zatca_attempts INT NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_last_error') IS NULL ALTER TABLE sales_invoices ADD zatca_last_error NVARCHAR(2000) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_status') IS NULL ALTER TABLE sales_invoices ADD zatca_status NVARCHAR(20) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_invoice_hash') IS NULL ALTER TABLE sales_invoices ADD zatca_invoice_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_previous_hash') IS NULL ALTER TABLE sales_invoices ADD zatca_previous_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_signed_xml') IS NULL ALTER TABLE sales_invoices ADD zatca_signed_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_qr_phase2') IS NULL ALTER TABLE sales_invoices ADD zatca_qr_phase2 NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_cleared_xml') IS NULL ALTER TABLE sales_invoices ADD zatca_cleared_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_warnings') IS NULL ALTER TABLE sales_invoices ADD zatca_warnings NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_response') IS NULL ALTER TABLE sales_invoices ADD zatca_response NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_submitted_at') IS NULL ALTER TABLE sales_invoices ADD zatca_submitted_at DATETIME NULL;
GO
-- ── sales_returns (credit notes) ────────────────────────────
IF COL_LENGTH('sales_returns','zatca_uuid') IS NULL ALTER TABLE sales_returns ADD zatca_uuid NVARCHAR(36) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_icv') IS NULL ALTER TABLE sales_returns ADD zatca_icv INT NULL;
GO
IF COL_LENGTH('sales_returns','zatca_kind') IS NULL ALTER TABLE sales_returns ADD zatca_kind NVARCHAR(12) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_egs_id') IS NULL ALTER TABLE sales_returns ADD zatca_egs_id INT NULL;
GO
IF COL_LENGTH('sales_returns','zatca_attempts') IS NULL ALTER TABLE sales_returns ADD zatca_attempts INT NULL;
GO
IF COL_LENGTH('sales_returns','zatca_last_error') IS NULL ALTER TABLE sales_returns ADD zatca_last_error NVARCHAR(2000) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_status') IS NULL ALTER TABLE sales_returns ADD zatca_status NVARCHAR(20) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_invoice_hash') IS NULL ALTER TABLE sales_returns ADD zatca_invoice_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_previous_hash') IS NULL ALTER TABLE sales_returns ADD zatca_previous_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_signed_xml') IS NULL ALTER TABLE sales_returns ADD zatca_signed_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_qr_phase2') IS NULL ALTER TABLE sales_returns ADD zatca_qr_phase2 NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_cleared_xml') IS NULL ALTER TABLE sales_returns ADD zatca_cleared_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_warnings') IS NULL ALTER TABLE sales_returns ADD zatca_warnings NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_response') IS NULL ALTER TABLE sales_returns ADD zatca_response NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_submitted_at') IS NULL ALTER TABLE sales_returns ADD zatca_submitted_at DATETIME NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sales_invoices_zatca_q' AND object_id=OBJECT_ID('sales_invoices'))
    CREATE INDEX IX_sales_invoices_zatca_q ON sales_invoices(zatca_status, zatca_icv);
GO
PRINT N'✅ ZATCA Phase 2 connection + send queue ready.';
GO

GO

-- ▼▼▼  PATCH: zzz_v690_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v6.9.0 — repairs (runs LAST: zzz_ sorts after zz_zatca2)
-- Databases made by the older one-file installer missed three things
-- because some patches ran before the table they change existed.
-- Idempotent: safe on every database, changes nothing that is right.
-- ============================================================

-- ZATCA Phase 2: an e-invoicing unit per counter (till)
IF OBJECT_ID('zatca_egs','U') IS NOT NULL AND COL_LENGTH('zatca_egs','counter_id') IS NULL
    EXEC(N'ALTER TABLE zatca_egs ADD counter_id INT NULL');
GO

-- Opening Balance Equity account used by Opening Balances
IF OBJECT_ID('account_settings','U') IS NOT NULL
    EXEC(N'IF NOT EXISTS (SELECT 1 FROM account_settings WHERE setting_key=''default_opening_equity'')
             INSERT INTO account_settings (setting_key, account_code)
             VALUES (''default_opening_equity'', ''3400'');');
GO

-- the company row (empty — the first-run wizard asks for the details)
IF OBJECT_ID('company','U') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM company)
    INSERT INTO company (company_name_en, company_name_ar, vat_registration_no)
    VALUES (N'Your Company Name', N'اسم شركتك', N'');
GO

GO

-- ▼▼▼  PATCH: zzz_v691_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v6.9.1 — a return put on the party's account settles
-- the bill it was made from (runs LAST: zzz_ sorts after zz_*).
--   applied_bill_id  the sales / purchase invoice the return settled
--   applied_amount   how much of that bill it settled
-- Older returns are linked once here, oldest first, never more than
-- the bill still had open. Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('sales_returns','U') IS NOT NULL AND COL_LENGTH('sales_returns','applied_bill_id') IS NULL
    EXEC(N'ALTER TABLE sales_returns ADD applied_bill_id INT NULL, applied_amount DECIMAL(18,2) NULL');
GO
IF OBJECT_ID('purchase_returns','U') IS NOT NULL AND COL_LENGTH('purchase_returns','applied_bill_id') IS NULL
    EXEC(N'ALTER TABLE purchase_returns ADD applied_bill_id INT NULL, applied_amount DECIMAL(18,2) NULL');
GO

-- sales returns on the customer's account (a refund in cash / card / bank is not)
IF OBJECT_ID('sales_returns','U') IS NOT NULL AND OBJECT_ID('sales_invoices','U') IS NOT NULL
   AND COL_LENGTH('sales_returns','applied_bill_id') IS NOT NULL
EXEC(N'
DECLARE @rid INT, @bill INT, @amt DECIMAL(18,2);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
    SELECT return_id FROM sales_returns
    WHERE applied_bill_id IS NULL AND ISNULL(return_status,''confirmed'')=''confirmed''
      AND LTRIM(RTRIM(ISNULL(original_invoice_no,''''))) <> ''''
      AND LOWER(ISNULL(NULLIF(LTRIM(RTRIM(payment_method)),''''),''cash''))
          NOT IN (''cash'',''card'',''mada'',''cheque'',''bank'',''bank_transfer'',''gateway'')
    ORDER BY return_id;
OPEN c; FETCH NEXT FROM c INTO @rid;
WHILE @@FETCH_STATUS = 0
BEGIN
    SELECT @bill = NULL, @amt = NULL;
    SELECT TOP 1 @bill = si.invoice_id,
           @amt = CASE WHEN ISNULL(r.total_amount,0) < ISNULL(si.total_amount,0) - ISNULL(si.paid_amount,0)
                       THEN ISNULL(r.total_amount,0)
                       ELSE ISNULL(si.total_amount,0) - ISNULL(si.paid_amount,0) END
    FROM sales_returns r
    JOIN sales_invoices si ON si.invoice_number = LTRIM(RTRIM(r.original_invoice_no))
                          AND si.invoice_status = ''confirmed''
                          AND (r.customer_id IS NULL OR si.customer_id = r.customer_id)
    WHERE r.return_id = @rid
    ORDER BY si.invoice_id DESC;
    IF @bill IS NOT NULL AND @amt > 0.005
    BEGIN
        UPDATE sales_invoices
           SET paid_amount = ISNULL(paid_amount,0) + @amt,
               payment_status = CASE WHEN ISNULL(paid_amount,0) + @amt >= ISNULL(total_amount,0) - 0.005
                                     THEN ''paid'' ELSE ''partial'' END
         WHERE invoice_id = @bill;
        UPDATE sales_returns SET applied_bill_id = @bill, applied_amount = @amt WHERE return_id = @rid;
    END
    FETCH NEXT FROM c INTO @rid;
END
CLOSE c; DEALLOCATE c;');
GO

-- purchase returns that reduce what is owed to the supplier
IF OBJECT_ID('purchase_returns','U') IS NOT NULL AND OBJECT_ID('purchase_invoices','U') IS NOT NULL
   AND COL_LENGTH('purchase_returns','applied_bill_id') IS NOT NULL
EXEC(N'
DECLARE @rid INT, @bill INT, @amt DECIMAL(18,2);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
    SELECT return_id FROM purchase_returns
    WHERE applied_bill_id IS NULL AND ISNULL(return_status,''confirmed'')=''confirmed''
      AND LTRIM(RTRIM(ISNULL(original_purchase_no,''''))) <> ''''
      AND LOWER(ISNULL(NULLIF(LTRIM(RTRIM(payment_method)),''''),''credit''))
          NOT IN (''cash'',''card'',''mada'',''cheque'',''bank'',''bank_transfer'',''gateway'')
    ORDER BY return_id;
OPEN c; FETCH NEXT FROM c INTO @rid;
WHILE @@FETCH_STATUS = 0
BEGIN
    SELECT @bill = NULL, @amt = NULL;
    SELECT TOP 1 @bill = pu.purchase_id,
           @amt = CASE WHEN ISNULL(r.total_amount,0) < ISNULL(pu.total_amount,0) - ISNULL(pu.paid_amount,0)
                       THEN ISNULL(r.total_amount,0)
                       ELSE ISNULL(pu.total_amount,0) - ISNULL(pu.paid_amount,0) END
    FROM purchase_returns r
    JOIN purchase_invoices pu ON pu.invoice_number = LTRIM(RTRIM(r.original_purchase_no))
                             AND pu.invoice_status = ''confirmed''
                             AND (r.supplier_id IS NULL OR pu.supplier_id = r.supplier_id)
    WHERE r.return_id = @rid
    ORDER BY pu.purchase_id DESC;
    IF @bill IS NOT NULL AND @amt > 0.005
    BEGIN
        UPDATE purchase_invoices
           SET paid_amount = ISNULL(paid_amount,0) + @amt,
               payment_status = CASE WHEN ISNULL(paid_amount,0) + @amt >= ISNULL(total_amount,0) - 0.005
                                     THEN ''paid'' ELSE ''partial'' END
         WHERE purchase_id = @bill;
        UPDATE purchase_returns SET applied_bill_id = @bill, applied_amount = @amt WHERE return_id = @rid;
    END
    FETCH NEXT FROM c INTO @rid;
END
CLOSE c; DEALLOCATE c;');
GO

GO

-- ▼▼▼  PATCH: zzz_v692_patch.sql  ▼▼▼
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

-- a phone's sign-in ends when the user's password is changed
IF OBJECT_ID('mobile_tokens','U') IS NOT NULL AND COL_LENGTH('mobile_tokens','pw_sig') IS NULL
    EXEC(N'ALTER TABLE mobile_tokens ADD pw_sig NVARCHAR(16) NULL');
GO

-- ZATCA: "Protect keys" stores each secret locked (~206 characters) — the
-- secret columns were NVARCHAR(200), so protecting always failed
IF COL_LENGTH('zatca_egs','ccsid_secret') IS NOT NULL AND COL_LENGTH('zatca_egs','ccsid_secret') <> -1
    EXEC(N'ALTER TABLE zatca_egs ALTER COLUMN ccsid_secret NVARCHAR(MAX) NULL');
GO
IF COL_LENGTH('zatca_egs','pcsid_secret') IS NOT NULL AND COL_LENGTH('zatca_egs','pcsid_secret') <> -1
    EXEC(N'ALTER TABLE zatca_egs ALTER COLUMN pcsid_secret NVARCHAR(MAX) NULL');
GO

GO

-- ▼▼▼  PATCH: zzz_v693_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v6.9.3
--   journal_entries.voucher_type   SI / POS / SR / PI / PR / CR / BR /
--                                   CP / BP / EX / CT / JV / OB / ADJ / CE …
--   consumption_entries / _lines    Consumable entry: stock used by the shop
--                                   itself (staff food, bakery production …)
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('journal_entries','U') IS NOT NULL AND COL_LENGTH('journal_entries','voucher_type') IS NULL
    EXEC(N'ALTER TABLE journal_entries ADD voucher_type NVARCHAR(10) NULL');
GO

-- older journals get their type once (receipts / payments: cash first)
IF COL_LENGTH('journal_entries','voucher_type') IS NOT NULL
EXEC(N'
UPDATE journal_entries SET voucher_type = CASE LOWER(ISNULL(source_type, ''''))
    WHEN ''sales'' THEN ''SI''            WHEN ''pos'' THEN ''POS''
    WHEN ''sales_return'' THEN ''SR''     WHEN ''debit_note'' THEN ''DN''
    WHEN ''cogs'' THEN ''COS''            WHEN ''cogs_return'' THEN ''COS''
    WHEN ''purchase'' THEN ''PI''         WHEN ''purchase_return'' THEN ''PR''
    WHEN ''purchase_return_cost'' THEN ''PR''
    WHEN ''receipt'' THEN ''CR''          WHEN ''payment'' THEN ''CP''
    WHEN ''expense'' THEN CASE WHEN source_id IS NULL THEN ''CP'' ELSE ''EX'' END
    WHEN ''transfer'' THEN ''CT''
    WHEN ''opening'' THEN ''OB''          WHEN ''opening_accounts'' THEN ''OB''
    WHEN ''opening_stock'' THEN ''OB''
    WHEN ''adjustment'' THEN CASE WHEN UPPER(ISNULL(reference,'''')) LIKE ''OPEN%'' THEN ''OB'' ELSE ''JV'' END
    WHEN ''stock_adjust'' THEN ''ADJ''    WHEN ''cycle_count'' THEN ''ADJ''
    WHEN ''consumption'' THEN ''CE''
    WHEN ''payroll'' THEN ''PY''          WHEN ''salary_payment'' THEN ''SAL''
    WHEN ''gosi_payment'' THEN ''GOSI''   WHEN ''eos'' THEN ''EOS''
    WHEN ''employee_loan'' THEN ''LN''    WHEN ''day_close'' THEN ''DC''
    WHEN ''shift'' THEN ''SH''
    ELSE ''JV'' END
WHERE voucher_type IS NULL;');
GO

-- receipts / payments that never touched a cash account → bank
IF COL_LENGTH('journal_entries','voucher_type') IS NOT NULL AND OBJECT_ID('account_settings','U') IS NOT NULL
EXEC(N'
DECLARE @cash TABLE (account_id INT PRIMARY KEY);
INSERT INTO @cash (account_id)
SELECT DISTINCT a.account_id FROM accounts a
WHERE a.account_code IN (SELECT account_code FROM account_settings
                         WHERE setting_key IN (''default_cash'', ''default_petty_cash''))
   OR a.account_code IN (''1100'', ''1150'');
IF OBJECT_ID(''payment_method_accounts'', ''U'') IS NOT NULL
    INSERT INTO @cash (account_id)
    SELECT DISTINCT p.account_id FROM payment_method_accounts p
    WHERE p.method_code = ''cash'' AND p.account_id IS NOT NULL
      AND p.account_id NOT IN (SELECT account_id FROM @cash);
UPDATE j SET voucher_type = CASE j.voucher_type WHEN ''CR'' THEN ''BR'' ELSE ''BP'' END
FROM journal_entries j
WHERE j.voucher_type IN (''CR'', ''CP'')
  AND NOT EXISTS (SELECT 1 FROM journal_lines l JOIN @cash c ON c.account_id = l.account_id
                  WHERE l.journal_id = j.journal_id);');
GO

IF OBJECT_ID('journal_entries','U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_voucher_type'
                   AND object_id=OBJECT_ID('journal_entries'))
   AND COL_LENGTH('journal_entries','voucher_type') IS NOT NULL
    EXEC(N'CREATE INDEX IX_journal_voucher_type ON journal_entries(voucher_type)');
GO

-- ── Consumable entry ─────────────────────────────────────────
IF OBJECT_ID('consumption_entries','U') IS NULL
CREATE TABLE consumption_entries (
    entry_id          INT IDENTITY(1,1) PRIMARY KEY,
    entry_number      NVARCHAR(30) NOT NULL UNIQUE,
    entry_date        DATE NOT NULL,
    purpose           NVARCHAR(30) NOT NULL DEFAULT 'staff_food',
    expense_account_id INT NULL,
    unit_name         NVARCHAR(100) NULL,          -- room / production unit (e.g. Bakery)
    warehouse_id      INT NULL,
    branch_id         INT NULL,
    counter_id        INT NULL,
    total_cost        DECIMAL(18,2) NOT NULL DEFAULT 0,
    notes             NVARCHAR(500) NULL,
    entry_status      NVARCHAR(20) NOT NULL DEFAULT 'confirmed',
    created_by        INT NULL,
    created_at        DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at        DATETIME NULL
);
GO
IF OBJECT_ID('consumption_lines','U') IS NULL
CREATE TABLE consumption_lines (
    line_id           INT IDENTITY(1,1) PRIMARY KEY,
    entry_id          INT NOT NULL REFERENCES consumption_entries(entry_id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    product_id        INT NOT NULL,
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    product_name_ar   NVARCHAR(300) NULL,
    quantity          DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_of_measure_en NVARCHAR(50) NULL,
    unit_cost         DECIMAL(18,4) NOT NULL DEFAULT 0,
    line_total        DECIMAL(18,2) NOT NULL DEFAULT 0
);
GO

-- expense accounts a consumable entry posts to (only added when missing)
IF OBJECT_ID('accounts','U') IS NOT NULL
BEGIN
    DECLARE @p INT = (SELECT account_id FROM accounts WHERE account_code='5000');
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5460')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5460', N'Staff Food & Welfare', N'طعام ورعاية الموظفين', 'expense', @p);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5470')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5470', N'Production Materials Used', N'مواد مستهلكة في الإنتاج', 'expense', @p);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5480')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5480', N'Shop Supplies Used', N'مستلزمات المحل المستهلكة', 'expense', @p);
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5490')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5490', N'Samples & Tasting', N'عينات وتذوق', 'expense', @p);
END
GO

-- user rights for the new Consumable entry: the same as each role has for
-- Stock Adjustment (the administrator can change them in Users & Rights)
IF OBJECT_ID('permissions','U') IS NOT NULL AND OBJECT_ID('role_permissions','U') IS NOT NULL
BEGIN
    INSERT INTO permissions (module_key, action_key)
    SELECT 'consumption', a.action_key FROM (SELECT DISTINCT action_key FROM permissions) a
    WHERE NOT EXISTS (SELECT 1 FROM permissions p WHERE p.module_key='consumption'
                      AND p.action_key=a.action_key);
    INSERT INTO role_permissions (role_id, permission_id, allowed)
    SELECT rp.role_id, pc.permission_id, rp.allowed
    FROM role_permissions rp
    JOIN permissions ps ON ps.permission_id=rp.permission_id AND ps.module_key='stock_adjustment'
    JOIN permissions pc ON pc.module_key='consumption' AND pc.action_key=ps.action_key
    WHERE NOT EXISTS (SELECT 1 FROM role_permissions x WHERE x.role_id=rp.role_id
                      AND x.permission_id=pc.permission_id);
END
GO

IF OBJECT_ID('consumption_entries','U') IS NOT NULL AND COL_LENGTH('consumption_entries','branch_id') IS NULL
    EXEC(N'ALTER TABLE consumption_entries ADD branch_id INT NULL, counter_id INT NULL');
GO

GO

-- ▼▼▼  PATCH: zzz_v695_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v6.9.5
--   products.system_barcode   every product's own 5-digit number made by
--                             DayBill (10001 … 99999). The barcode typed /
--                             scanned from the packet stays in
--                             products.barcode. Both scan everywhere.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','system_barcode') IS NULL
    EXEC(N'ALTER TABLE products ADD system_barcode NVARCHAR(20) NULL');
GO

IF COL_LENGTH('products','system_barcode') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_products_system_barcode')
    EXEC(N'CREATE UNIQUE INDEX UX_products_system_barcode ON products(system_barcode)
           WHERE system_barcode IS NOT NULL');
GO

-- every product gets its system barcode once: 10001, 10002 … in product
-- order, never a number already used as a barcode or a product code
IF COL_LENGTH('products','system_barcode') IS NOT NULL
BEGIN
    IF OBJECT_ID('tempdb..#sb_used') IS NOT NULL DROP TABLE #sb_used;
    CREATE TABLE #sb_used (code NVARCHAR(60) COLLATE DATABASE_DEFAULT PRIMARY KEY);
    EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(barcode)) FROM products
           WHERE LEN(LTRIM(RTRIM(ISNULL(barcode, N'''')))) = 5');
    EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(product_code)) FROM products
           WHERE LEN(LTRIM(RTRIM(ISNULL(product_code, N'''')))) = 5
             AND LTRIM(RTRIM(product_code)) NOT IN (SELECT code FROM #sb_used)');
    EXEC(N'INSERT INTO #sb_used SELECT DISTINCT system_barcode FROM products
           WHERE system_barcode IS NOT NULL AND system_barcode NOT IN (SELECT code FROM #sb_used)');
    IF OBJECT_ID('product_units','U') IS NOT NULL
        EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(barcode)) FROM product_units
               WHERE LEN(LTRIM(RTRIM(ISNULL(barcode, N'''')))) = 5
                 AND LTRIM(RTRIM(barcode)) NOT IN (SELECT code FROM #sb_used)');
    IF OBJECT_ID('product_unit_barcodes','U') IS NOT NULL
        EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(barcode)) FROM product_unit_barcodes
               WHERE LEN(LTRIM(RTRIM(ISNULL(barcode, N'''')))) = 5
                 AND LTRIM(RTRIM(barcode)) NOT IN (SELECT code FROM #sb_used)');
    EXEC(N'
    DECLARE @pid INT, @n INT, @s NVARCHAR(20);
    SELECT @n = ISNULL(MAX(TRY_CAST(system_barcode AS INT)), 10000) FROM products
     WHERE system_barcode LIKE N''[1-9][0-9][0-9][0-9][0-9]'';
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR
        SELECT product_id FROM products WHERE system_barcode IS NULL ORDER BY product_id;
    OPEN c;
    FETCH NEXT FROM c INTO @pid;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @n = @n + 1;
        WHILE @n <= 99999 AND EXISTS (SELECT 1 FROM #sb_used WHERE code = CAST(@n AS NVARCHAR(20)))
            SET @n = @n + 1;
        IF @n > 99999 BREAK;
        SET @s = CAST(@n AS NVARCHAR(20));
        UPDATE products SET system_barcode = @s WHERE product_id = @pid;
        INSERT INTO #sb_used (code) VALUES (@s);
        FETCH NEXT FROM c INTO @pid;
    END
    CLOSE c;
    DEALLOCATE c;');
    DROP TABLE #sb_used;
END
GO

-- customer / supplier opening balances are OB vouchers (they were JV)
IF COL_LENGTH('journal_entries','voucher_type') IS NOT NULL
    EXEC(N'UPDATE journal_entries SET voucher_type = N''OB''
           WHERE LOWER(ISNULL(source_type, N'''')) IN (N''opening_customer'', N''opening_supplier'')
             AND ISNULL(voucher_type, N''JV'') = N''JV''');
GO

GO

-- ▼▼▼  PATCH: zzz_v700_accounts_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.0 — account groups (masters)
--   accounts.is_group   1 = a group that holds ledgers (Assets, Current
--                       Assets, Expenses …). Every ledger sits under a
--                       group (parent_account_id). An account that has
--                       accounts under it is shown as a group too.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('accounts','U') IS NOT NULL AND COL_LENGTH('accounts','is_group') IS NULL
    EXEC(N'ALTER TABLE accounts ADD is_group BIT NOT NULL CONSTRAINT DF_accounts_is_group DEFAULT 0');
GO

-- the main heads and every account that already has accounts under it
IF COL_LENGTH('accounts','is_group') IS NOT NULL
    EXEC(N'UPDATE a SET is_group = 1 FROM accounts a
           WHERE a.is_group = 0
             AND (a.parent_account_id IS NULL AND a.account_code IN (N''1000'', N''2000'', N''3000'', N''4000'', N''5000'')
                  OR EXISTS (SELECT 1 FROM accounts c WHERE c.parent_account_id = a.account_id))');
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_accounts_parent')
   AND OBJECT_ID('accounts','U') IS NOT NULL
    CREATE INDEX IX_accounts_parent ON accounts(parent_account_id);
GO

GO

-- ▼▼▼  PATCH: zzz_v700_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.0 — countries and business modules
--   company.country_code      SA Saudi Arabia · AE UAE · IN India
--   company.state_code        region / emirate / GST state of the company
--   company.currency_symbol   what prints next to amounts (SAR, AED, ₹ …)
--   company.business_modules  retail,supermarket,restaurant,textiles,production
--   company_options           company settings kept in the company database
--   customers / suppliers .state_code   (GST place of supply, emirate)
--   products.hsn_code         India HSN / SAC code
--   *.place_of_supply         India: the state a bill belongs to
--   vat_categories.tax_kind   std / zero / exempt / nil / oos
--   bom_headers / bom_lines   recipes and bills of materials
-- A database made before v7.0 is a Saudi retail + supermarket company.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','country_code') IS NULL
    EXEC(N'ALTER TABLE company ADD country_code NVARCHAR(2) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','state_code') IS NULL
    EXEC(N'ALTER TABLE company ADD state_code NVARCHAR(10) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','currency_symbol') IS NULL
    EXEC(N'ALTER TABLE company ADD currency_symbol NVARCHAR(10) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL AND COL_LENGTH('company','business_modules') IS NULL
    EXEC(N'ALTER TABLE company ADD business_modules NVARCHAR(200) NULL');
GO
IF OBJECT_ID('company','U') IS NOT NULL
    EXEC(N'UPDATE company SET country_code = N''SA'' WHERE country_code IS NULL OR country_code = N''''');
GO
IF OBJECT_ID('company','U') IS NOT NULL
    EXEC(N'UPDATE company SET business_modules = N''retail,supermarket''
           WHERE business_modules IS NULL OR business_modules = N''''');
GO

IF OBJECT_ID('company_options','U') IS NULL
CREATE TABLE company_options (
    opt_key     NVARCHAR(100) NOT NULL PRIMARY KEY,
    opt_value   NVARCHAR(MAX) NULL,
    updated_at  DATETIME DEFAULT GETDATE()
);
GO

IF OBJECT_ID('customers','U') IS NOT NULL AND COL_LENGTH('customers','state_code') IS NULL
    EXEC(N'ALTER TABLE customers ADD state_code NVARCHAR(10) NULL');
GO
IF OBJECT_ID('suppliers','U') IS NOT NULL AND COL_LENGTH('suppliers','state_code') IS NULL
    EXEC(N'ALTER TABLE suppliers ADD state_code NVARCHAR(10) NULL');
GO
IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','hsn_code') IS NULL
    EXEC(N'ALTER TABLE products ADD hsn_code NVARCHAR(20) NULL');
GO
IF OBJECT_ID('branches','U') IS NOT NULL AND COL_LENGTH('branches','state_code') IS NULL
    EXEC(N'ALTER TABLE branches ADD state_code NVARCHAR(10) NULL');
GO

IF OBJECT_ID('sales_invoices','U') IS NOT NULL AND COL_LENGTH('sales_invoices','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE sales_invoices ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('purchase_invoices','U') IS NOT NULL AND COL_LENGTH('purchase_invoices','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE purchase_invoices ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('sales_returns','U') IS NOT NULL AND COL_LENGTH('sales_returns','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE sales_returns ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('purchase_returns','U') IS NOT NULL AND COL_LENGTH('purchase_returns','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE purchase_returns ADD place_of_supply NVARCHAR(10) NULL');
GO
IF OBJECT_ID('quotations','U') IS NOT NULL AND COL_LENGTH('quotations','place_of_supply') IS NULL
    EXEC(N'ALTER TABLE quotations ADD place_of_supply NVARCHAR(10) NULL');
GO

IF OBJECT_ID('vat_categories','U') IS NOT NULL AND COL_LENGTH('vat_categories','tax_kind') IS NULL
    EXEC(N'ALTER TABLE vat_categories ADD tax_kind NVARCHAR(10) NULL');
GO
IF COL_LENGTH('vat_categories','tax_kind') IS NOT NULL
    EXEC(N'UPDATE vat_categories SET tax_kind =
              CASE WHEN UPPER(LEFT(category_code,1)) = N''Z'' THEN N''zero''
                   WHEN UPPER(LEFT(category_code,1)) = N''E'' THEN N''exempt''
                   WHEN UPPER(LEFT(category_code,1)) = N''O'' THEN N''oos''
                   WHEN ISNULL(vat_rate,0) > 0 THEN N''std'' ELSE N''nil'' END
           WHERE tax_kind IS NULL');
GO

-- ── recipes / bills of materials ────────────────────────────
IF OBJECT_ID('bom_headers','U') IS NULL
CREATE TABLE bom_headers (
    bom_id          INT IDENTITY(1,1) PRIMARY KEY,
    product_id      INT NOT NULL,
    bom_name        NVARCHAR(200) NULL,
    output_qty      DECIMAL(18,4) NOT NULL DEFAULT 1,
    output_unit     NVARCHAR(50) NULL,
    labour_cost     DECIMAL(18,4) NOT NULL DEFAULT 0,
    overhead_cost   DECIMAL(18,4) NOT NULL DEFAULT 0,
    deduct_on_sale  BIT NOT NULL DEFAULT 0,      -- restaurant: selling the dish uses up the recipe
    is_default      BIT NOT NULL DEFAULT 1,
    is_active       BIT NOT NULL DEFAULT 1,
    notes           NVARCHAR(500) NULL,
    created_at      DATETIME DEFAULT GETDATE(),
    updated_at      DATETIME NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bom_headers_product')
    CREATE INDEX IX_bom_headers_product ON bom_headers(product_id);
GO

IF OBJECT_ID('bom_lines','U') IS NULL
CREATE TABLE bom_lines (
    line_id         INT IDENTITY(1,1) PRIMARY KEY,
    bom_id          INT NOT NULL,
    component_id    INT NOT NULL,
    quantity        DECIMAL(18,4) NOT NULL,
    unit_name       NVARCHAR(50) NULL,
    waste_pct       DECIMAL(9,3) NOT NULL DEFAULT 0,
    notes           NVARCHAR(200) NULL,
    sort_order      INT NOT NULL DEFAULT 0
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bom_lines_bom')
    CREATE INDEX IX_bom_lines_bom ON bom_lines(bom_id);
GO

GO

-- ▼▼▼  PATCH: zzz_v700_production_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.0 — Production (manufacturing)
--   production_entries   one production run: the product made, how
--                        many, status (draft / confirmed / cancelled)
--                        and what it cost (materials + labour +
--                        overhead = total, cost of one unit)
--   production_lines     the materials of a run: planned (from the
--                        bill of materials) and really used, unit,
--                        cost each, line cost
--   account 5250         Production Labour & Overheads Applied — the
--                        credit side of labour and overhead put into
--                        the finished goods' cost
--   journal voucher type PRD (Production)
-- Confirming an entry moves the stock and posts the journal
-- (modules/production.py); a draft moves nothing.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('production_entries','U') IS NULL
CREATE TABLE production_entries (
    entry_id          INT IDENTITY(1,1) PRIMARY KEY,
    entry_number      NVARCHAR(30) NOT NULL UNIQUE,
    entry_date        DATE NOT NULL,
    product_id        INT NOT NULL,                 -- the finished product made
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    bom_id            INT NULL,                     -- the bill of materials used
    quantity          DECIMAL(18,4) NOT NULL DEFAULT 0,   -- made, in unit_name
    unit_name         NVARCHAR(50) NULL,
    unit_factor       DECIMAL(18,6) NOT NULL DEFAULT 1,   -- base units in one unit_name
    qty_base          DECIMAL(18,4) NOT NULL DEFAULT 0,   -- made, in base units
    entry_status      NVARCHAR(20) NOT NULL DEFAULT 'draft',
    material_cost     DECIMAL(18,2) NOT NULL DEFAULT 0,
    labour_cost       DECIMAL(18,2) NOT NULL DEFAULT 0,
    overhead_cost     DECIMAL(18,2) NOT NULL DEFAULT 0,
    total_cost        DECIMAL(18,2) NOT NULL DEFAULT 0,
    unit_cost         DECIMAL(18,6) NOT NULL DEFAULT 0,   -- cost of one unit_name
    branch_id         INT NULL,
    counter_id        INT NULL,
    notes             NVARCHAR(500) NULL,
    -- what confirming did to the finished product's average cost, so
    -- cancel / edit can put it back exactly
    fg_avg_before     DECIMAL(18,4) NULL,
    fg_avg_after      DECIMAL(18,4) NULL,
    fg_stock_after    DECIMAL(18,4) NULL,
    created_by        INT NULL,
    created_at        DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at        DATETIME NULL,
    confirmed_at      DATETIME NULL,
    cancelled_at      DATETIME NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_entries_date')
    CREATE INDEX IX_production_entries_date ON production_entries(entry_date, entry_status);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_entries_product')
    CREATE INDEX IX_production_entries_product ON production_entries(product_id);
GO

IF OBJECT_ID('production_lines','U') IS NULL
CREATE TABLE production_lines (
    line_id           INT IDENTITY(1,1) PRIMARY KEY,
    entry_id          INT NOT NULL REFERENCES production_entries(entry_id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    component_id      INT NOT NULL,                 -- the material
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    qty_planned       DECIMAL(18,4) NOT NULL DEFAULT 0,   -- from the bill of materials
    qty_used          DECIMAL(18,4) NOT NULL DEFAULT 0,   -- really used (can differ)
    unit_name         NVARCHAR(50) NULL,
    unit_factor       DECIMAL(18,6) NOT NULL DEFAULT 1,
    is_stock          BIT NOT NULL DEFAULT 1,       -- 0 = a service: cost only, no stock
    cost_each         DECIMAL(18,6) NOT NULL DEFAULT 0,   -- one unit_name, at its average cost
    line_cost         DECIMAL(18,2) NOT NULL DEFAULT 0,
    notes             NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_lines_entry')
    CREATE INDEX IX_production_lines_entry ON production_lines(entry_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_production_lines_component')
    CREATE INDEX IX_production_lines_component ON production_lines(component_id);
GO

-- the account labour + overhead are applied to (only added when missing)
IF OBJECT_ID('accounts','U') IS NOT NULL
BEGIN
    DECLARE @p INT = (SELECT account_id FROM accounts WHERE account_code='5000');
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5250')
        INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type, parent_account_id)
        VALUES ('5250', N'Production Labour & Overheads Applied',
                N'تكاليف العمالة والمصاريف المحملة على الإنتاج', 'expense', @p);
END
GO

GO

-- ▼▼▼  PATCH: zzz_v700_restaurant_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: zzz_v700_textiles_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.0 — Textiles & Garments: size / colour variants
--   products.variant_parent_id   the style (main product) a size /
--                                colour belongs to (NULL = not a variant)
--   products.variant_size        its size   ('' when the style has no sizes)
--   products.variant_colour      its colour ('' when the style has no colours)
-- Every variant is a normal product (own code, own 5-digit system
-- barcode, own stock), so sales, purchases, POS, stock and reports work
-- as before; these columns only link it to its style.
-- No foreign key on purpose: deleting a style never fails because of
-- its variants (they stay as normal products).
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','variant_parent_id') IS NULL
    EXEC(N'ALTER TABLE products ADD variant_parent_id INT NULL');
GO
IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','variant_size') IS NULL
    EXEC(N'ALTER TABLE products ADD variant_size NVARCHAR(40) NULL');
GO
IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','variant_colour') IS NULL
    EXEC(N'ALTER TABLE products ADD variant_colour NVARCHAR(40) NULL');
GO

-- the variants of a style, fast
IF COL_LENGTH('products','variant_parent_id') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_products_variant_parent'
                   AND object_id = OBJECT_ID('products'))
    EXEC(N'CREATE INDEX IX_products_variant_parent ON products(variant_parent_id)
           INCLUDE (variant_size, variant_colour)');
GO

-- one product per style + size + colour (adding sizes later never
-- makes a second "Shirt - M - Red")
IF COL_LENGTH('products','variant_parent_id') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_products_variant'
                   AND object_id = OBJECT_ID('products'))
    EXEC(N'CREATE UNIQUE INDEX UX_products_variant
           ON products(variant_parent_id, variant_size, variant_colour)
           WHERE variant_parent_id IS NOT NULL');
GO

GO

-- ▼▼▼  PATCH: zzz_v740_qr_login_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.4 — QR sign-in for every user / employee
--   user_qr_keys     one personal QR key per user (only its hash is
--                    kept), valid until it expires or is turned off
--   employees.user_id   the DayBill user an employee signs in with
-- ============================================================
IF OBJECT_ID('user_qr_keys','U') IS NULL
CREATE TABLE user_qr_keys (
    user_id         INT NOT NULL PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    key_hash        NVARCHAR(64) NOT NULL,
    key_hint        NVARCHAR(8) NULL,
    allow_mobile    BIT NOT NULL DEFAULT 1,
    allow_desktop   BIT NOT NULL DEFAULT 1,
    expires_at      DATETIME NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE(),
    created_by      INT NULL,
    last_used       DATETIME NULL,
    use_count       INT NOT NULL DEFAULT 0,
    sent_to         NVARCHAR(30) NULL,
    sent_at         DATETIME NULL
);
GO

IF OBJECT_ID('user_qr_keys','U') IS NOT NULL AND
   NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_user_qr_keys_hash')
CREATE UNIQUE INDEX UX_user_qr_keys_hash ON user_qr_keys(key_hash);
GO

IF OBJECT_ID('employees','U') IS NOT NULL AND COL_LENGTH('employees','user_id') IS NULL
    ALTER TABLE employees ADD user_id INT NULL;
GO

GO

-- ▼▼▼  PATCH: zzz_v750_orders_patch.sql  ▼▼▼
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

GO

-- ▼▼▼  PATCH: zzz_v770_account_groups_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.7 — the full set of default account GROUPS
--   Assets      › Current Assets › Cash-in-Hand · Bank Accounts ·
--                 Sundry Debtors · Stock-in-Hand · Loans & Advances ·
--                 Deposits;  Fixed Assets;  Investments
--   Liabilities › Current Liabilities › Sundry Creditors · Duties &
--                 Taxes · Provisions & Payroll;  Loans (Liability)
--   Equity      › Capital Account · Reserves & Surplus
--   Revenue     › Sales Accounts · Direct Income · Indirect Income
--   Expenses    › Direct Expenses (Cost of Sales) · Employee Costs ·
--                 Administrative Expenses · Selling & Distribution ·
--                 Financial Charges
-- Account codes never change (postings use them). A default ledger is
-- moved into its new group ONLY while it still sits where DayBill put
-- it — a ledger you moved yourself stays where you put it. Safe to run
-- again (Chart of Accounts ▸ Add default groups).
-- ============================================================
IF OBJECT_ID('accounts','U') IS NOT NULL AND COL_LENGTH('accounts','is_group') IS NOT NULL
BEGIN
    DECLARE @g TABLE (ord INT, code NVARCHAR(20), en NVARCHAR(100), ar NVARCHAR(100),
                      typ NVARCHAR(20), parent NVARCHAR(20));
    INSERT INTO @g VALUES
    ( 1, N'1000', N'Assets',                      N'الأصول',                     N'asset',     NULL),
    ( 2, N'1010', N'Current Assets',              N'الأصول المتداولة',           N'asset',     N'1000'),
    ( 3, N'1011', N'Cash-in-Hand',                N'النقدية في الصندوق',         N'asset',     N'1010'),
    ( 4, N'1012', N'Bank Accounts',               N'الحسابات البنكية',           N'asset',     N'1010'),
    ( 5, N'1013', N'Sundry Debtors',              N'المدينون',                   N'asset',     N'1010'),
    ( 6, N'1014', N'Stock-in-Hand',               N'المخزون',                    N'asset',     N'1010'),
    ( 7, N'1015', N'Loans & Advances (Asset)',    N'القروض والسلف',              N'asset',     N'1010'),
    ( 8, N'1016', N'Deposits (Asset)',            N'التأمينات والودائع',         N'asset',     N'1010'),
    ( 9, N'1500', N'Fixed Assets',                N'الأصول الثابتة',             N'asset',     N'1000'),
    (10, N'1600', N'Investments',                 N'الاستثمارات',                N'asset',     N'1000'),
    (11, N'2000', N'Liabilities',                 N'الخصوم',                     N'liability', NULL),
    (12, N'2001', N'Current Liabilities',         N'الخصوم المتداولة',           N'liability', N'2000'),
    (13, N'2002', N'Sundry Creditors',            N'الدائنون',                   N'liability', N'2001'),
    (14, N'2003', N'Duties & Taxes',              N'الرسوم والضرائب',            N'liability', N'2001'),
    (15, N'2004', N'Provisions & Payroll',        N'المخصصات والرواتب المستحقة', N'liability', N'2001'),
    (16, N'2005', N'Loans (Liability)',           N'القروض',                     N'liability', N'2000'),
    (17, N'3000', N'Equity',                      N'حقوق الملكية',               N'equity',    NULL),
    (18, N'3001', N'Capital Account',             N'حساب رأس المال',             N'equity',    N'3000'),
    (19, N'3002', N'Reserves & Surplus',          N'الاحتياطيات والأرباح المبقاة', N'equity',  N'3000'),
    (20, N'4000', N'Revenue',                     N'الإيرادات',                  N'revenue',   NULL),
    (21, N'4001', N'Sales Accounts',              N'حسابات المبيعات',            N'revenue',   N'4000'),
    (22, N'4002', N'Direct Income',               N'الإيرادات المباشرة',         N'revenue',   N'4000'),
    (23, N'4003', N'Indirect Income',             N'الإيرادات الأخرى',           N'revenue',   N'4000'),
    (24, N'5000', N'Expenses',                    N'المصروفات',                  N'expense',   NULL),
    (25, N'5001', N'Direct Expenses (Cost of Sales)', N'المصروفات المباشرة (تكلفة المبيعات)', N'expense', N'5000'),
    (26, N'5002', N'Employee Costs',              N'تكاليف الموظفين',            N'expense',   N'5000'),
    (27, N'5003', N'Administrative Expenses',     N'المصروفات الإدارية',         N'expense',   N'5000'),
    (28, N'5004', N'Selling & Distribution',      N'مصروفات البيع والتوزيع',     N'expense',   N'5000'),
    (29, N'5005', N'Financial Charges',           N'المصروفات المالية',          N'expense',   N'5000');

    -- 1) the groups (parents first); a code already used by something else is left alone
    DECLARE @ord INT = 1, @n INT = (SELECT MAX(ord) FROM @g);
    WHILE @ord <= @n
    BEGIN
        DECLARE @code NVARCHAR(20), @en NVARCHAR(100), @ar NVARCHAR(100), @typ NVARCHAR(20), @par NVARCHAR(20);
        SELECT @code = code, @en = en, @ar = ar, @typ = typ, @par = parent FROM @g WHERE ord = @ord;
        IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code = @code)
            INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type,
                                  parent_account_id, is_active, is_group)
            VALUES (@code, @en, @ar, @typ,
                    (SELECT account_id FROM accounts WHERE account_code = @par), 1, 1);
        ELSE IF EXISTS (SELECT 1 FROM accounts WHERE account_code = @code AND account_name_en = @en)
            UPDATE accounts SET is_group = 1, is_active = 1 WHERE account_code = @code;
        SET @ord = @ord + 1;
    END;

    -- 2) default ledgers into their group — only while still in DayBill's place
    --    (old parent code, or no parent at all)
    DECLARE @m TABLE (ledger NVARCHAR(20), grp NVARCHAR(20), oldp NVARCHAR(20));
    INSERT INTO @m VALUES
    (N'1100', N'1011', N'1010'), (N'1150', N'1011', N'1010'),
    (N'1110', N'1012', N'1010'), (N'1120', N'1012', N'1010'), (N'1130', N'1012', N'1010'),
    (N'1140', N'1012', N'1010'),
    (N'1200', N'1013', N'1010'), (N'1300', N'1014', N'1010'),
    (N'1400', N'1015', N'1010'), (N'2320', N'1015', N'2000'),
    (N'2100', N'2002', N'2000'), (N'2200', N'2003', N'2000'),
    (N'2300', N'2004', N'2000'), (N'2310', N'2004', N'2000'), (N'2330', N'2004', N'2000'),
    (N'2400', N'2004', N'2000'), (N'2500', N'2005', N'2000'),
    (N'3100', N'3001', N'3000'), (N'3200', N'3001', N'3000'), (N'3400', N'3001', N'3000'),
    (N'3300', N'3002', N'3000'),
    (N'4100', N'4001', N'4000'), (N'4200', N'4001', N'4000'),
    (N'4300', N'4003', N'4000'), (N'4310', N'4003', N'4000'),
    (N'5100', N'5001', N'5000'), (N'5150', N'5001', N'5000'), (N'5160', N'5001', N'5000'),
    (N'5250', N'5001', N'5000'), (N'5470', N'5001', N'5000'),
    (N'5200', N'5002', N'5000'), (N'5210', N'5002', N'5000'), (N'5220', N'5002', N'5000'),
    (N'5460', N'5002', N'5000'),
    (N'5300', N'5003', N'5000'), (N'5310', N'5003', N'5000'), (N'5320', N'5003', N'5000'),
    (N'5330', N'5003', N'5000'), (N'5340', N'5003', N'5000'), (N'5350', N'5003', N'5000'),
    (N'5360', N'5003', N'5000'), (N'5390', N'5003', N'5000'), (N'5420', N'5003', N'5000'),
    (N'5430', N'5003', N'5000'), (N'5440', N'5003', N'5000'), (N'5480', N'5003', N'5000'),
    (N'5370', N'5004', N'5000'), (N'5380', N'5004', N'5000'), (N'5400', N'5004', N'5000'),
    (N'5490', N'5004', N'5000'),
    (N'5410', N'5005', N'5000'), (N'5450', N'5005', N'5000'), (N'5900', N'5005', N'5000');

    UPDATE a SET parent_account_id = grp.account_id
    FROM accounts a
    JOIN @m m ON m.ledger = a.account_code
    JOIN @g g ON g.code = m.grp
    JOIN accounts grp ON grp.account_code = m.grp AND grp.account_name_en = g.en
    LEFT JOIN accounts p ON p.account_id = a.parent_account_id
    WHERE grp.account_id <> a.account_id
      AND (a.parent_account_id IS NULL OR p.account_code = m.oldp);

    -- Employee Loans is money staff owe the shop: an asset (it was filed as one, outside any group)
    UPDATE accounts SET account_type = N'asset' WHERE account_code = N'2320' AND account_type <> N'asset';
END;
GO

GO

-- ▼▼▼  PATCH: zzz_v780_party_snapshot_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.8 — the customer typed on the bill
--   A sale to someone who is not in Customers: the Name, VAT / GST No.,
--   Mobile and Address typed in the Sales window / POS are kept ON THE
--   BILL (the snapshot columns) and printed. The mobile number gets its
--   own column.
-- ============================================================
IF OBJECT_ID('sales_invoices','U') IS NOT NULL AND COL_LENGTH('sales_invoices','customer_phone') IS NULL
    ALTER TABLE sales_invoices ADD customer_phone NVARCHAR(30) NULL;
GO

GO

-- ▼▼▼  PATCH: zzz_v790_designer_patch.sql  ▼▼▼
-- ============================================================
-- DayBill ERP v7.9 — Invoice Designer options
--   design_slot : 2 / 3 = "Design 2" / "Design 3" of the document
--                 (the ★ default stays in is_default) — the Print menu
--                 offers them next to the default layout
--   page_json   : page settings (lines per page, minimum lines, row
--                 gap, custom paper size, pre-printed paper, ask the
--                 printer, graphics / text printing)
-- ============================================================
IF OBJECT_ID('report_templates','U') IS NOT NULL AND COL_LENGTH('report_templates','design_slot') IS NULL
    ALTER TABLE report_templates ADD design_slot TINYINT NULL;
GO
IF OBJECT_ID('report_templates','U') IS NOT NULL AND COL_LENGTH('report_templates','page_json') IS NULL
    ALTER TABLE report_templates ADD page_json NVARCHAR(MAX) NULL;
GO

GO

-- ============================================================
-- FINAL CHECK — what the database has now
-- ============================================================
SET NOCOUNT ON;
DECLARE @t INT = (SELECT COUNT(*) FROM sys.tables);
DECLARE @a INT = (SELECT COUNT(*) FROM accounts);
DECLARE @u INT = (SELECT COUNT(*) FROM users);
DECLARE @p INT = (SELECT COUNT(*) FROM products);
PRINT N'------------------------------------------------------------';
PRINT N'DayBill ERP database ready:  ' + DB_NAME();
PRINT N'  tables            : ' + CAST(@t AS NVARCHAR(10));
PRINT N'  chart of accounts : ' + CAST(@a AS NVARCHAR(10)) + N' accounts';
PRINT N'  users             : ' + CAST(@u AS NVARCHAR(10)) + N'  (admin — set the password at first sign-in)';
PRINT N'  products          : ' + CAST(@p AS NVARCHAR(10));
PRINT N'Next: open DayBill ▸ sign in as admin ▸ Settings ▸ Company.';
PRINT N'------------------------------------------------------------';
SET NOCOUNT OFF;        -- the connection that ran this keeps counting rows (rowcount checks need it)
GO
