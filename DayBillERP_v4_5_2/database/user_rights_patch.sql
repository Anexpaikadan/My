-- ============================================================
-- DayBill ERP - Per-user rights (Master / Reports / Edit / Delete)
-- Adds simple permission flags directly on the users table.
-- Admin (user_id with admin username) is always granted all.
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_master')
    ALTER TABLE users ADD can_master BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_reports')
    ALTER TABLE users ADD can_reports BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_edit')
    ALTER TABLE users ADD can_edit BIT DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('users') AND name='can_delete')
    ALTER TABLE users ADD can_delete BIT DEFAULT 0;
GO

-- Grant everything to the admin account
UPDATE users SET can_master=1, can_reports=1, can_edit=1, can_delete=1
WHERE username='admin';
GO

PRINT 'User rights columns ready.';
GO
