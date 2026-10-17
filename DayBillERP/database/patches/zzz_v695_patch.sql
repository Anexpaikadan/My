-- ============================================================
-- DayBill ERP v6.9.5
--   products.system_barcode   every product's own 5-digit number made by
--                             DayBill (10001 … 99999). The barcode typed /
--                             scanned from the packet stays in
--                             products.barcode. Both scan everywhere.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('products','U') IS NOT NULL AND COL_LENGTH('products','system_barcode') IS NULL
    EXEC(N'ALTER TABLE products ADD system_barcode NVARCHAR(20) NULL');
GO

IF COL_LENGTH('products','system_barcode') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_products_system_barcode')
    EXEC(N'CREATE UNIQUE INDEX UX_products_system_barcode ON products(system_barcode)
           WHERE system_barcode IS NOT NULL');
GO

-- every product gets its system barcode once: 10001, 10002 … in product
-- order, never a number already used as a barcode or a product code
IF COL_LENGTH('products','system_barcode') IS NOT NULL
BEGIN
    IF OBJECT_ID('tempdb..#sb_used') IS NOT NULL DROP TABLE #sb_used;
    CREATE TABLE #sb_used (code NVARCHAR(60) COLLATE DATABASE_DEFAULT PRIMARY KEY);
    EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(barcode)) FROM products
           WHERE LEN(LTRIM(RTRIM(ISNULL(barcode, N'''')))) = 5');
    EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(product_code)) FROM products
           WHERE LEN(LTRIM(RTRIM(ISNULL(product_code, N'''')))) = 5
             AND LTRIM(RTRIM(product_code)) NOT IN (SELECT code FROM #sb_used)');
    EXEC(N'INSERT INTO #sb_used SELECT DISTINCT system_barcode FROM products
           WHERE system_barcode IS NOT NULL AND system_barcode NOT IN (SELECT code FROM #sb_used)');
    IF OBJECT_ID('product_units','U') IS NOT NULL
        EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(barcode)) FROM product_units
               WHERE LEN(LTRIM(RTRIM(ISNULL(barcode, N'''')))) = 5
                 AND LTRIM(RTRIM(barcode)) NOT IN (SELECT code FROM #sb_used)');
    IF OBJECT_ID('product_unit_barcodes','U') IS NOT NULL
        EXEC(N'INSERT INTO #sb_used SELECT DISTINCT LTRIM(RTRIM(barcode)) FROM product_unit_barcodes
               WHERE LEN(LTRIM(RTRIM(ISNULL(barcode, N'''')))) = 5
                 AND LTRIM(RTRIM(barcode)) NOT IN (SELECT code FROM #sb_used)');
    EXEC(N'
    DECLARE @pid INT, @n INT, @s NVARCHAR(20);
    SELECT @n = ISNULL(MAX(TRY_CAST(system_barcode AS INT)), 10000) FROM products
     WHERE system_barcode LIKE N''[1-9][0-9][0-9][0-9][0-9]'';
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR
        SELECT product_id FROM products WHERE system_barcode IS NULL ORDER BY product_id;
    OPEN c;
    FETCH NEXT FROM c INTO @pid;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @n = @n + 1;
        WHILE @n <= 99999 AND EXISTS (SELECT 1 FROM #sb_used WHERE code = CAST(@n AS NVARCHAR(20)))
            SET @n = @n + 1;
        IF @n > 99999 BREAK;
        SET @s = CAST(@n AS NVARCHAR(20));
        UPDATE products SET system_barcode = @s WHERE product_id = @pid;
        INSERT INTO #sb_used (code) VALUES (@s);
        FETCH NEXT FROM c INTO @pid;
    END
    CLOSE c;
    DEALLOCATE c;');
    DROP TABLE #sb_used;
END
GO
