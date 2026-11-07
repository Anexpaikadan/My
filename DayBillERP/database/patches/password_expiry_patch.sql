-- ============================================================
-- DayBill ERP - Password expiry (Settings ▸ Users & Security ▸
-- Password Expiry). Remembers when each password was last set;
-- sign-in asks for a new password once it is older than the
-- configured number of days.
-- ============================================================
IF COL_LENGTH('users','password_changed_at') IS NULL
    ALTER TABLE users ADD password_changed_at DATETIME NULL
        CONSTRAINT DF_users_password_changed_at DEFAULT GETDATE();
GO
