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
