-- ============================================================
-- DayBill ERP - Invoice Designer: one design per document type
-- The first template shipped with type 'invoice', which no screen
-- uses. It belongs to Sales Invoice.
-- ============================================================
IF EXISTS (SELECT 1 FROM sys.tables WHERE name='report_templates')
    UPDATE report_templates SET report_type='sales_invoice'
     WHERE report_type IS NULL OR report_type IN ('invoice', 'tax_invoice');
GO
