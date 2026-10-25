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
