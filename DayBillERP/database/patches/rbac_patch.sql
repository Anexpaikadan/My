-- ============================================================
-- DayBill ERP — User & Rights (RBAC) migration (auto-applied patch)
-- Safe to run multiple times. Adds tables/columns only if missing.
-- SQL Server (T-SQL).
-- ============================================================

-- ── Extra user columns (mobile, branch, warehouse, created_by) ──
IF COL_LENGTH('users','mobile') IS NULL
    ALTER TABLE users ADD mobile NVARCHAR(20) NULL;
IF COL_LENGTH('users','branch') IS NULL
    ALTER TABLE users ADD branch NVARCHAR(60) NULL;
IF COL_LENGTH('users','warehouse') IS NULL
    ALTER TABLE users ADD warehouse NVARCHAR(60) NULL;
IF COL_LENGTH('users','created_by') IS NULL
    ALTER TABLE users ADD created_by INT NULL;
GO

-- ── PERMISSIONS: one row per (module, action) ──────────────
IF OBJECT_ID('permissions','U') IS NULL
BEGIN
    CREATE TABLE permissions (
        permission_id   INT IDENTITY(1,1) PRIMARY KEY,
        module_key      NVARCHAR(40) NOT NULL,   -- products, sales, ...
        action_key      NVARCHAR(20) NOT NULL,   -- view, add, edit, ...
        CONSTRAINT UQ_perm UNIQUE (module_key, action_key)
    );
END
GO

-- ── ROLE ↔ PERMISSION grants ───────────────────────────────
IF OBJECT_ID('role_permissions','U') IS NULL
BEGIN
    CREATE TABLE role_permissions (
        role_id         INT NOT NULL REFERENCES roles(role_id),
        permission_id   INT NOT NULL REFERENCES permissions(permission_id),
        allowed         BIT NOT NULL DEFAULT 1,
        CONSTRAINT PK_role_perm PRIMARY KEY (role_id, permission_id)
    );
END
GO

-- ── LOGIN HISTORY ──────────────────────────────────────────
IF OBJECT_ID('login_history','U') IS NULL
BEGIN
    CREATE TABLE login_history (
        login_id        INT IDENTITY(1,1) PRIMARY KEY,
        user_id         INT NULL REFERENCES users(user_id),
        username        NVARCHAR(50) NULL,
        success         BIT NOT NULL DEFAULT 1,
        workstation     NVARCHAR(100) NULL,
        login_time      DATETIME NOT NULL DEFAULT GETDATE()
    );
END
GO

-- audit_logs table used by modules/audit.py (separate from schema's audit_log)
IF OBJECT_ID('audit_logs','U') IS NULL
BEGIN
    CREATE TABLE audit_logs (
        audit_id        INT IDENTITY(1,1) PRIMARY KEY,
        user_id         INT NULL,
        action          NVARCHAR(50) NOT NULL,
        module          NVARCHAR(50) NULL,
        ref_id          NVARCHAR(50) NULL,
        details         NVARCHAR(4000) NULL,
        workstation     NVARCHAR(100) NULL,
        created_at      DATETIME NOT NULL DEFAULT GETDATE()
    );
END
GO

-- ── Seed the 9 predefined roles (only if missing) ──────────
;WITH seed(en, ar) AS (
    SELECT 'Super Admin', N'مدير عام'      UNION ALL
    SELECT 'Admin',       N'مدير'          UNION ALL
    SELECT 'Manager',     N'مشرف'          UNION ALL
    SELECT 'Accountant',  N'محاسب'         UNION ALL
    SELECT 'Sales',       N'مبيعات'        UNION ALL
    SELECT 'Purchase',    N'مشتريات'       UNION ALL
    SELECT 'Inventory',   N'مخزون'         UNION ALL
    SELECT 'Cashier',     N'أمين صندوق'    UNION ALL
    SELECT 'Viewer',      N'مشاهد'
)
INSERT INTO roles (role_name_en, role_name_ar, is_active)
SELECT s.en, s.ar, 1 FROM seed s
WHERE NOT EXISTS (SELECT 1 FROM roles r WHERE r.role_name_en = s.en);
GO
