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
