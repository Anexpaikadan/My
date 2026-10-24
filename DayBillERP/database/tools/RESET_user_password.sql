-- ============================================================
-- DayBill ERP — forgotten password (run BY HAND, never automatic)
-- ------------------------------------------------------------
-- Nobody can sign in? On the server PC:
--   1. Open SQL Server Management Studio and connect.
--   2. File ▸ Open this file (or New Query and paste it).
--   3. Change the two lines marked  <<<  if needed, then Execute (F5).
--   4. In DayBill, sign in as that user with ANY password — DayBill
--      asks for a new password first (like a new installation).
-- It changes NOTHING on a database that is not DayBill's.
-- The same query is shown in DayBill: login screen ▸ 🔑 Forgot password?
-- ============================================================
USE [DayBillERP];                                   -- <<< your DayBill database name
GO
DECLARE @user NVARCHAR(50) = N'admin';              -- <<< the user to reset

IF COL_LENGTH('users','user_id') IS NULL OR OBJECT_ID('sales_invoices') IS NULL
    RAISERROR('This is not a DayBill database - nothing was changed.', 16, 1);
ELSE
BEGIN
    UPDATE users SET password_hash = N'RESET', is_active = 1 WHERE username = @user;
    IF OBJECT_ID('login_history') IS NOT NULL
        DELETE FROM login_history WHERE username = @user AND success = 0;
    SELECT username, is_active,
           N'Now sign in with any password - DayBill asks for a new one' AS next_step
    FROM users WHERE username = @user;
END
GO
