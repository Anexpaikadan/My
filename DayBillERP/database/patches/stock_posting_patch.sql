-- ============================================================
-- DayBill ERP v5.7 — stock & accounts posting engine
-- ------------------------------------------------------------
-- * sales_invoices.sale_channel ('POS' / 'INV') for the POS report
-- * index for stock-movement lookups by document
-- * records the stock that OLDER versions already moved for existing
--   purchases and returns (they moved stock on save, even drafts), so
--   editing / confirming / deleting those documents now reverses the
--   old movement exactly once — no double stock.
-- Safe to run more than once.
-- ============================================================

IF COL_LENGTH('sales_invoices','sale_channel') IS NULL
    ALTER TABLE sales_invoices ADD sale_channel NVARCHAR(10) NULL;
GO

IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_invtxn_reference')
    CREATE INDEX IX_invtxn_reference ON inventory_transactions(reference_type, reference_id);
GO

-- Purchases saved by older versions (stock was added at save time)
IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND OBJECT_ID('purchase_invoice_lines','U') IS NOT NULL
   AND OBJECT_ID('product_units','U') IS NOT NULL
BEGIN
    INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type,
        reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base,
        balance_base, unit_cost, notes)
    SELECT l.product_id, ISNULL(pi.invoice_date, CAST(GETDATE() AS date)),
        'purchase', 'purchase_invoice', pi.purchase_id,
        ISNULL(l.unit_of_measure_en, 'Unit'), l.quantity,
        l.quantity * ISNULL((SELECT TOP 1 NULLIF(pu.conversion_factor, 0)
                             FROM product_units pu
                             WHERE pu.product_id = l.product_id
                               AND pu.unit_name_en = l.unit_of_measure_en), 1),
        0, 0, 0, 0, N'moved before v5.7'
    FROM purchase_invoice_lines l
    JOIN purchase_invoices pi ON pi.purchase_id = l.purchase_id
    JOIN products p ON p.product_id = l.product_id
    WHERE ISNULL(pi.invoice_status, '') <> 'cancelled'
      AND ISNULL(l.quantity, 0) <> 0
      AND NOT EXISTS (SELECT 1 FROM inventory_transactions t
                      WHERE t.reference_type = 'purchase_invoice'
                        AND t.reference_id = pi.purchase_id);
END
GO

-- Sales returns saved by older versions (stock added back, base qty)
IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND OBJECT_ID('sales_return_lines','U') IS NOT NULL
BEGIN
    INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type,
        reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base,
        balance_base, unit_cost, notes)
    SELECT l.product_id,
        ISNULL(TRY_CONVERT(date, r.return_date), CAST(ISNULL(r.created_at, GETDATE()) AS date)),
        'return_in', 'sales_return', r.return_id, ISNULL(l.unit_of_measure_en, 'Unit'),
        l.quantity, l.quantity, 0, 0, 0, 0, N'moved before v5.7'
    FROM sales_return_lines l
    JOIN sales_returns r ON r.return_id = l.return_id
    JOIN products p ON p.product_id = l.product_id
    WHERE ISNULL(l.quantity, 0) <> 0
      AND NOT EXISTS (SELECT 1 FROM inventory_transactions t
                      WHERE t.reference_type = 'sales_return'
                        AND t.reference_id = r.return_id);
END
GO

-- Purchase returns saved by older versions (stock taken out, base qty)
IF OBJECT_ID('inventory_transactions','U') IS NOT NULL
   AND OBJECT_ID('purchase_return_lines','U') IS NOT NULL
BEGIN
    INSERT INTO inventory_transactions (product_id, txn_date, txn_type, reference_type,
        reference_id, unit_name, qty_in_units, qty_in_base, qty_out_units, qty_out_base,
        balance_base, unit_cost, notes)
    SELECT l.product_id,
        ISNULL(TRY_CONVERT(date, r.return_date), CAST(ISNULL(r.created_at, GETDATE()) AS date)),
        'return_out', 'purchase_return', r.return_id, ISNULL(l.unit_of_measure_en, 'Unit'),
        0, 0, l.quantity, l.quantity, 0, 0, N'moved before v5.7'
    FROM purchase_return_lines l
    JOIN purchase_returns r ON r.return_id = l.return_id
    JOIN products p ON p.product_id = l.product_id
    WHERE ISNULL(l.quantity, 0) <> 0
      AND NOT EXISTS (SELECT 1 FROM inventory_transactions t
                      WHERE t.reference_type = 'purchase_return'
                        AND t.reference_id = r.return_id);
END
GO


-- Offset account for manual stock adjustments / physical counts
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5160')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5160', 'Stock Adjustment', N'تسوية المخزون', 'expense');
GO

PRINT 'Stock & accounts posting engine patch applied.';
GO
