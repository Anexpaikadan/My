-- ============================================================
-- DayBill ERP v6.9.1 — a return put on the party's account settles
-- the bill it was made from (runs LAST: zzz_ sorts after zz_*).
--   applied_bill_id  the sales / purchase invoice the return settled
--   applied_amount   how much of that bill it settled
-- Older returns are linked once here, oldest first, never more than
-- the bill still had open. Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('sales_returns','U') IS NOT NULL AND COL_LENGTH('sales_returns','applied_bill_id') IS NULL
    EXEC(N'ALTER TABLE sales_returns ADD applied_bill_id INT NULL, applied_amount DECIMAL(18,2) NULL');
GO
IF OBJECT_ID('purchase_returns','U') IS NOT NULL AND COL_LENGTH('purchase_returns','applied_bill_id') IS NULL
    EXEC(N'ALTER TABLE purchase_returns ADD applied_bill_id INT NULL, applied_amount DECIMAL(18,2) NULL');
GO

-- sales returns on the customer's account (a refund in cash / card / bank is not)
IF OBJECT_ID('sales_returns','U') IS NOT NULL AND OBJECT_ID('sales_invoices','U') IS NOT NULL
   AND COL_LENGTH('sales_returns','applied_bill_id') IS NOT NULL
EXEC(N'
DECLARE @rid INT, @bill INT, @amt DECIMAL(18,2);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
    SELECT return_id FROM sales_returns
    WHERE applied_bill_id IS NULL AND ISNULL(return_status,''confirmed'')=''confirmed''
      AND LTRIM(RTRIM(ISNULL(original_invoice_no,''''))) <> ''''
      AND LOWER(ISNULL(NULLIF(LTRIM(RTRIM(payment_method)),''''),''cash''))
          NOT IN (''cash'',''card'',''mada'',''cheque'',''bank'',''bank_transfer'',''gateway'')
    ORDER BY return_id;
OPEN c; FETCH NEXT FROM c INTO @rid;
WHILE @@FETCH_STATUS = 0
BEGIN
    SELECT @bill = NULL, @amt = NULL;
    SELECT TOP 1 @bill = si.invoice_id,
           @amt = CASE WHEN ISNULL(r.total_amount,0) < ISNULL(si.total_amount,0) - ISNULL(si.paid_amount,0)
                       THEN ISNULL(r.total_amount,0)
                       ELSE ISNULL(si.total_amount,0) - ISNULL(si.paid_amount,0) END
    FROM sales_returns r
    JOIN sales_invoices si ON si.invoice_number = LTRIM(RTRIM(r.original_invoice_no))
                          AND si.invoice_status = ''confirmed''
                          AND (r.customer_id IS NULL OR si.customer_id = r.customer_id)
    WHERE r.return_id = @rid
    ORDER BY si.invoice_id DESC;
    IF @bill IS NOT NULL AND @amt > 0.005
    BEGIN
        UPDATE sales_invoices
           SET paid_amount = ISNULL(paid_amount,0) + @amt,
               payment_status = CASE WHEN ISNULL(paid_amount,0) + @amt >= ISNULL(total_amount,0) - 0.005
                                     THEN ''paid'' ELSE ''partial'' END
         WHERE invoice_id = @bill;
        UPDATE sales_returns SET applied_bill_id = @bill, applied_amount = @amt WHERE return_id = @rid;
    END
    FETCH NEXT FROM c INTO @rid;
END
CLOSE c; DEALLOCATE c;');
GO

-- purchase returns that reduce what is owed to the supplier
IF OBJECT_ID('purchase_returns','U') IS NOT NULL AND OBJECT_ID('purchase_invoices','U') IS NOT NULL
   AND COL_LENGTH('purchase_returns','applied_bill_id') IS NOT NULL
EXEC(N'
DECLARE @rid INT, @bill INT, @amt DECIMAL(18,2);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
    SELECT return_id FROM purchase_returns
    WHERE applied_bill_id IS NULL AND ISNULL(return_status,''confirmed'')=''confirmed''
      AND LTRIM(RTRIM(ISNULL(original_purchase_no,''''))) <> ''''
      AND LOWER(ISNULL(NULLIF(LTRIM(RTRIM(payment_method)),''''),''credit''))
          NOT IN (''cash'',''card'',''mada'',''cheque'',''bank'',''bank_transfer'',''gateway'')
    ORDER BY return_id;
OPEN c; FETCH NEXT FROM c INTO @rid;
WHILE @@FETCH_STATUS = 0
BEGIN
    SELECT @bill = NULL, @amt = NULL;
    SELECT TOP 1 @bill = pu.purchase_id,
           @amt = CASE WHEN ISNULL(r.total_amount,0) < ISNULL(pu.total_amount,0) - ISNULL(pu.paid_amount,0)
                       THEN ISNULL(r.total_amount,0)
                       ELSE ISNULL(pu.total_amount,0) - ISNULL(pu.paid_amount,0) END
    FROM purchase_returns r
    JOIN purchase_invoices pu ON pu.invoice_number = LTRIM(RTRIM(r.original_purchase_no))
                             AND pu.invoice_status = ''confirmed''
                             AND (r.supplier_id IS NULL OR pu.supplier_id = r.supplier_id)
    WHERE r.return_id = @rid
    ORDER BY pu.purchase_id DESC;
    IF @bill IS NOT NULL AND @amt > 0.005
    BEGIN
        UPDATE purchase_invoices
           SET paid_amount = ISNULL(paid_amount,0) + @amt,
               payment_status = CASE WHEN ISNULL(paid_amount,0) + @amt >= ISNULL(total_amount,0) - 0.005
                                     THEN ''paid'' ELSE ''partial'' END
         WHERE purchase_id = @bill;
        UPDATE purchase_returns SET applied_bill_id = @bill, applied_amount = @amt WHERE return_id = @rid;
    END
    FETCH NEXT FROM c INTO @rid;
END
CLOSE c; DEALLOCATE c;');
GO
