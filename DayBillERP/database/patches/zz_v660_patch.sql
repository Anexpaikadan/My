-- ============================================================
-- DayBill ERP - v6.6.0 database update  (HR & Payroll)
-- ------------------------------------------------------------
--  employees     documents with expiry dates (Iqama / ID, passport,
--                medical insurance, contract), birth date, phone, email
--  payslips      overtime / bonus / absence + sick-leave deduction kept
--                apart, the loan the instalment came from
--  payroll_runs  approved / paid (salaries, GOSI) with the dates
--  eos_settlements  final settlement: award before the resignation
--                share, leave days paid, loan taken back, net
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF COL_LENGTH('employees','iqama_expiry') IS NULL      ALTER TABLE employees ADD iqama_expiry DATE NULL;
GO
IF COL_LENGTH('employees','passport_no') IS NULL       ALTER TABLE employees ADD passport_no NVARCHAR(30) NULL;
GO
IF COL_LENGTH('employees','passport_expiry') IS NULL   ALTER TABLE employees ADD passport_expiry DATE NULL;
GO
IF COL_LENGTH('employees','insurance_expiry') IS NULL  ALTER TABLE employees ADD insurance_expiry DATE NULL;
GO
IF COL_LENGTH('employees','contract_end') IS NULL      ALTER TABLE employees ADD contract_end DATE NULL;
GO
IF COL_LENGTH('employees','birth_date') IS NULL        ALTER TABLE employees ADD birth_date DATE NULL;
GO
IF COL_LENGTH('employees','phone') IS NULL             ALTER TABLE employees ADD phone NVARCHAR(30) NULL;
GO
IF COL_LENGTH('employees','email') IS NULL             ALTER TABLE employees ADD email NVARCHAR(120) NULL;
GO
IF COL_LENGTH('employees','gender') IS NULL            ALTER TABLE employees ADD gender NVARCHAR(1) NULL;   -- M / F
GO
-- annual leave balance carried in from before DayBill (days left on that date)
IF COL_LENGTH('employees','leave_open_days') IS NULL   ALTER TABLE employees ADD leave_open_days DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('employees','leave_open_date') IS NULL   ALTER TABLE employees ADD leave_open_date DATE NULL;
GO

IF COL_LENGTH('payslips','loan_id') IS NULL            ALTER TABLE payslips ADD loan_id INT NULL;
GO
IF COL_LENGTH('payslips','bonus_amount') IS NULL       ALTER TABLE payslips ADD bonus_amount DECIMAL(18,2) NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('payslips','absence_days') IS NULL       ALTER TABLE payslips ADD absence_days DECIMAL(9,2) NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('payslips','absence_deduction') IS NULL  ALTER TABLE payslips ADD absence_deduction DECIMAL(18,2) NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('payslips','sick_deduction') IS NULL     ALTER TABLE payslips ADD sick_deduction DECIMAL(18,2) NOT NULL DEFAULT 0;
GO

IF COL_LENGTH('payroll_runs','paid_at') IS NULL        ALTER TABLE payroll_runs ADD paid_at DATETIME NULL;
GO
IF COL_LENGTH('payroll_runs','paid_method') IS NULL    ALTER TABLE payroll_runs ADD paid_method NVARCHAR(30) NULL;
GO
IF COL_LENGTH('payroll_runs','gosi_paid_at') IS NULL   ALTER TABLE payroll_runs ADD gosi_paid_at DATETIME NULL;
GO

IF COL_LENGTH('eos_settlements','award_full') IS NULL      ALTER TABLE eos_settlements ADD award_full DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','award_share') IS NULL     ALTER TABLE eos_settlements ADD award_share DECIMAL(9,4) NULL;
GO
IF COL_LENGTH('eos_settlements','leave_days') IS NULL      ALTER TABLE eos_settlements ADD leave_days DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('eos_settlements','leave_pay') IS NULL       ALTER TABLE eos_settlements ADD leave_pay DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','loan_recovered') IS NULL  ALTER TABLE eos_settlements ADD loan_recovered DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','net_settlement') IS NULL  ALTER TABLE eos_settlements ADD net_settlement DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','wage_basis') IS NULL      ALTER TABLE eos_settlements ADD wage_basis NVARCHAR(20) NULL;
GO

-- v6.6: probation (up to 180 days, 2025 law), resignation dates (art. 79 / 2025),
--       Ramadan hours (art. 98), notice pay and art. 77 compensation in the settlement
IF COL_LENGTH('employees','probation_days') IS NULL    ALTER TABLE employees ADD probation_days INT NULL;
GO
IF COL_LENGTH('employees','resign_date') IS NULL       ALTER TABLE employees ADD resign_date DATE NULL;
GO
IF COL_LENGTH('employees','resign_status') IS NULL     ALTER TABLE employees ADD resign_status NVARCHAR(20) NULL;
GO
IF COL_LENGTH('employees','ramadan_hours') IS NULL     ALTER TABLE employees ADD ramadan_hours BIT NULL;  -- NULL = yes
GO
IF COL_LENGTH('eos_settlements','days_not_counted') IS NULL ALTER TABLE eos_settlements ADD days_not_counted DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('eos_settlements','notice_days') IS NULL     ALTER TABLE eos_settlements ADD notice_days DECIMAL(9,2) NULL;
GO
IF COL_LENGTH('eos_settlements','notice_amount') IS NULL   ALTER TABLE eos_settlements ADD notice_amount DECIMAL(18,2) NULL;
GO
IF COL_LENGTH('eos_settlements','compensation_77') IS NULL ALTER TABLE eos_settlements ADD compensation_77 DECIMAL(18,2) NULL;
GO

PRINT 'DayBill v6.6.0 database update applied (HR documents, payslip parts, payroll paid, final settlement).';
GO
