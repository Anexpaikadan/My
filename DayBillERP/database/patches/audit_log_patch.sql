-- ============================================================
-- DayBill ERP - Audit Log Patch
-- (Converted from BillPOS MySQL audit_logs)
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('audit_logs','U') IS NULL
CREATE TABLE audit_logs (
    id          BIGINT IDENTITY(1,1) PRIMARY KEY,
    user_id     INT NULL,
    action      NVARCHAR(50) NOT NULL,      -- create / update / delete / login / post ...
    module      NVARCHAR(50) NOT NULL,      -- sales / purchase / vouchers / users ...
    ref_id      NVARCHAR(50) NULL,          -- document id / number
    details     NVARCHAR(MAX) NULL,
    workstation NVARCHAR(100) NULL,         -- replaces PHP ip_address on desktop
    created_at  DATETIME DEFAULT GETDATE()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_audit_user')
    CREATE INDEX idx_audit_user ON audit_logs(user_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_audit_module')
    CREATE INDEX idx_audit_module ON audit_logs(module);
GO

PRINT '✅ Audit log patch applied.';
GO
