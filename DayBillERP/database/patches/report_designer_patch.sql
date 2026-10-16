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
