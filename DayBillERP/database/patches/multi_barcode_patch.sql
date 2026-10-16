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
