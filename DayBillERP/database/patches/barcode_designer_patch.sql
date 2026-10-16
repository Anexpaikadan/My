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
