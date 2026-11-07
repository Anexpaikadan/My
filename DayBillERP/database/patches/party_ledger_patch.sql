-- ============================================================
-- DayBill ERP - Party Ledgers + Accounting Integration
-- 1. Each customer & supplier gets its own ledger account (with code)
-- 2. Adds a Bank account to the chart of accounts
-- 3. Links customers.account_id / suppliers.account_id
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- Add account_id link to customers & suppliers
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('customers') AND name='account_id')
    ALTER TABLE customers ADD account_id INT NULL REFERENCES accounts(account_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('suppliers') AND name='account_id')
    ALTER TABLE suppliers ADD account_id INT NULL REFERENCES accounts(account_id);
GO

-- Add a Bank account + Card clearing if missing
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1110')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type)
VALUES ('1110', 'Bank', N'البنك', 'asset');
GO
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='1120')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type)
VALUES ('1120', 'Card / POS Clearing', N'مقاصة البطاقات', 'asset');
GO

-- Parent group accounts so party ledgers nest under Receivable/Payable
-- (1200 = Accounts Receivable, 2100 = Accounts Payable already exist)

-- Create a ledger account for every customer that lacks one.
-- Customer ledger codes: 1200-0001, 1200-0002 ...
DECLARE @cid INT, @cname NVARCHAR(200), @ccode NVARCHAR(20), @n INT, @acc INT;
DECLARE cust_cur CURSOR FOR
    SELECT customer_id, customer_name_en FROM customers WHERE account_id IS NULL;
OPEN cust_cur;
FETCH NEXT FROM cust_cur INTO @cid, @cname;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @n = ISNULL((SELECT COUNT(*) FROM accounts WHERE account_code LIKE '1200-%'), 0) + 1;
    SET @ccode = '1200-' + RIGHT('0000' + CAST(@n AS NVARCHAR(10)), 4);
    INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type,
        parent_account_id)
    VALUES (@ccode, @cname, @cname, 'asset',
        (SELECT TOP 1 account_id FROM accounts WHERE account_code='1200'));
    SET @acc = SCOPE_IDENTITY();
    UPDATE customers SET account_id=@acc WHERE customer_id=@cid;
    FETCH NEXT FROM cust_cur INTO @cid, @cname;
END
CLOSE cust_cur; DEALLOCATE cust_cur;
GO

-- Create a ledger account for every supplier that lacks one.
-- Supplier ledger codes: 2100-0001, 2100-0002 ...
DECLARE @sid INT, @sname NVARCHAR(200), @scode NVARCHAR(20), @sn INT, @sacc INT;
DECLARE sup_cur CURSOR FOR
    SELECT supplier_id, supplier_name_en FROM suppliers WHERE account_id IS NULL;
OPEN sup_cur;
FETCH NEXT FROM sup_cur INTO @sid, @sname;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sn = ISNULL((SELECT COUNT(*) FROM accounts WHERE account_code LIKE '2100-%'), 0) + 1;
    SET @scode = '2100-' + RIGHT('0000' + CAST(@sn AS NVARCHAR(10)), 4);
    INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type,
        parent_account_id)
    VALUES (@scode, @sname, @sname, 'liability',
        (SELECT TOP 1 account_id FROM accounts WHERE account_code='2100'));
    SET @sacc = SCOPE_IDENTITY();
    UPDATE suppliers SET account_id=@sacc WHERE supplier_id=@sid;
    FETCH NEXT FROM sup_cur INTO @sid, @sname;
END
CLOSE sup_cur; DEALLOCATE sup_cur;
GO

PRINT 'Party ledgers + accounting integration ready.';
GO
