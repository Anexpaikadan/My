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
