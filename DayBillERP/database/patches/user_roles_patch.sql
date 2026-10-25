-- ============================================================
-- DayBill ERP - User Roles seed (Manager, Cashier)
-- Administrator already exists from the core schema.
-- Safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- Manager: most things except managing users/settings
IF NOT EXISTS (SELECT 1 FROM roles WHERE role_name_en='Manager')
INSERT INTO roles (role_name_en, role_name_ar, can_view_dashboard, can_manage_customers,
    can_manage_products, can_create_invoice, can_approve_invoice, can_view_reports,
    can_manage_users, can_manage_settings, can_zatca_submit)
VALUES ('Manager', N'مدير', 1, 1, 1, 1, 1, 1, 0, 0, 1);
GO

-- Cashier: sell only (create invoices, view dashboard)
IF NOT EXISTS (SELECT 1 FROM roles WHERE role_name_en='Cashier')
INSERT INTO roles (role_name_en, role_name_ar, can_view_dashboard, can_manage_customers,
    can_manage_products, can_create_invoice, can_approve_invoice, can_view_reports,
    can_manage_users, can_manage_settings, can_zatca_submit)
VALUES ('Cashier', N'كاشير', 1, 0, 0, 1, 0, 0, 0, 0, 0);
GO

PRINT 'Manager and Cashier roles ready.';
GO
