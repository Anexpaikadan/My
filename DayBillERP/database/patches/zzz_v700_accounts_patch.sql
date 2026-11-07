-- ============================================================
-- DayBill ERP v7.0 — account groups (masters)
--   accounts.is_group   1 = a group that holds ledgers (Assets, Current
--                       Assets, Expenses …). Every ledger sits under a
--                       group (parent_account_id). An account that has
--                       accounts under it is shown as a group too.
-- Idempotent: safe on every database.
-- ============================================================

IF OBJECT_ID('accounts','U') IS NOT NULL AND COL_LENGTH('accounts','is_group') IS NULL
    EXEC(N'ALTER TABLE accounts ADD is_group BIT NOT NULL CONSTRAINT DF_accounts_is_group DEFAULT 0');
GO

-- the main heads and every account that already has accounts under it
IF COL_LENGTH('accounts','is_group') IS NOT NULL
    EXEC(N'UPDATE a SET is_group = 1 FROM accounts a
           WHERE a.is_group = 0
             AND (a.parent_account_id IS NULL AND a.account_code IN (N''1000'', N''2000'', N''3000'', N''4000'', N''5000'')
                  OR EXISTS (SELECT 1 FROM accounts c WHERE c.parent_account_id = a.account_id))');
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_accounts_parent')
   AND OBJECT_ID('accounts','U') IS NOT NULL
    CREATE INDEX IX_accounts_parent ON accounts(parent_account_id);
GO
