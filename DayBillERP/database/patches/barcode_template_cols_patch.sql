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
