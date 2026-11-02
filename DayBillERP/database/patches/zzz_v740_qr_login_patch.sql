-- ============================================================
-- DayBill ERP v7.4 — QR sign-in for every user / employee
--   user_qr_keys     one personal QR key per user (only its hash is
--                    kept), valid until it expires or is turned off
--   employees.user_id   the DayBill user an employee signs in with
-- ============================================================
IF OBJECT_ID('user_qr_keys','U') IS NULL
CREATE TABLE user_qr_keys (
    user_id         INT NOT NULL PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    key_hash        NVARCHAR(64) NOT NULL,
    key_hint        NVARCHAR(8) NULL,
    allow_mobile    BIT NOT NULL DEFAULT 1,
    allow_desktop   BIT NOT NULL DEFAULT 1,
    expires_at      DATETIME NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE(),
    created_by      INT NULL,
    last_used       DATETIME NULL,
    use_count       INT NOT NULL DEFAULT 0,
    sent_to         NVARCHAR(30) NULL,
    sent_at         DATETIME NULL
);
GO

IF OBJECT_ID('user_qr_keys','U') IS NOT NULL AND
   NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_user_qr_keys_hash')
CREATE UNIQUE INDEX UX_user_qr_keys_hash ON user_qr_keys(key_hash);
GO

IF OBJECT_ID('employees','U') IS NOT NULL AND COL_LENGTH('employees','user_id') IS NULL
    ALTER TABLE employees ADD user_id INT NULL;
GO
