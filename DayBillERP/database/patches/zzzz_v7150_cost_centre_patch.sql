-- ============================================================
-- DayBill ERP - v7.15.0: cost centre on vouchers
-- Idempotent. Nothing existing is changed.
-- ============================================================
USE DayBillERP;
GO
IF COL_LENGTH('journal_entries','cost_center_id') IS NULL
    ALTER TABLE journal_entries ADD cost_center_id INT NULL;
GO
IF COL_LENGTH('journal_lines','cost_center_id') IS NULL
    ALTER TABLE journal_lines ADD cost_center_id INT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_lines_cost_center')
    CREATE INDEX IX_journal_lines_cost_center ON journal_lines(cost_center_id);
GO
PRINT 'DayBill v7.15.0 patch applied.';
GO
