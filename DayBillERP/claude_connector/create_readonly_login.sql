-- ============================================================
-- OPTIONAL (recommended): a SQL login that can only READ.
-- The connector never writes anyway, but with this login SQL
-- Server itself refuses any change — a second lock on the door.
--
-- 1) Run this in SQL Server Management Studio (as admin).
--    Change the password and the database name if yours differs.
-- 2) Rename connector_config.example.json to connector_config.json
--    and put the same username/password there.
-- ============================================================
USE master;
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'daybill_claude')
    CREATE LOGIN daybill_claude WITH PASSWORD = 'Change_This_Password_123!',
        CHECK_POLICY = ON;
GO
USE DayBillERP;          -- << your DayBill database name
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'daybill_claude')
    CREATE USER daybill_claude FOR LOGIN daybill_claude;
GO
ALTER ROLE db_datareader ADD MEMBER daybill_claude;   -- read every table
DENY INSERT, UPDATE, DELETE, EXECUTE, ALTER TO daybill_claude;
GO
-- SQL Server must allow SQL logins: Server Properties > Security >
-- "SQL Server and Windows Authentication mode" (restart the service).
