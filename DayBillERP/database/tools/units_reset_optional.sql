-- ============================================================
-- OPTIONAL: wipe all existing product units
-- ------------------------------------------------------------
-- Run ONLY if you want to clear every product_units record and
-- re-add units through the new Quick Product Form / Units Manager.
-- ⚠ This cannot be undone. Take a backup first.
-- Products themselves are NOT touched; each keeps its base
-- unit_of_measure_en on the products row.
-- ============================================================
USE DayBillERP;
GO
-- DELETE FROM product_units;
-- PRINT '⚠ All product units removed. Re-add via Quick Product Form.';
GO
