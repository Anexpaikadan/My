-- ============================================================
-- DayBill ERP - Accounting & Payroll Schema Patch
-- Double-entry journals + Saudi payroll system
-- Safe to run multiple times.
-- ============================================================

USE DayBillERP;
GO

-- ============================================================
-- PART A — DOUBLE-ENTRY ACCOUNTING
-- ============================================================

-- Journal entries (header)
IF OBJECT_ID('journal_entries','U') IS NULL
CREATE TABLE journal_entries (
    journal_id          INT IDENTITY(1,1) PRIMARY KEY,
    journal_number      NVARCHAR(30) NOT NULL UNIQUE,
    entry_date          DATE NOT NULL,
    reference           NVARCHAR(100),
    description_en      NVARCHAR(500),
    description_ar      NVARCHAR(500),
    source_type         NVARCHAR(30),         -- manual/sales/purchase/payment/payroll
    source_id           INT,                  -- link to originating record
    total_debit         DECIMAL(18,2) DEFAULT 0,
    total_credit        DECIMAL(18,2) DEFAULT 0,
    is_posted           BIT DEFAULT 0,        -- draft vs posted
    created_by          INT,
    created_at          DATETIME DEFAULT GETDATE(),
    posted_at           DATETIME
);
GO

-- Journal lines (debit/credit per account)
IF OBJECT_ID('journal_lines','U') IS NULL
CREATE TABLE journal_lines (
    line_id             INT IDENTITY(1,1) PRIMARY KEY,
    journal_id          INT NOT NULL REFERENCES journal_entries(journal_id) ON DELETE CASCADE,
    line_number         INT NOT NULL,
    account_id          INT NOT NULL REFERENCES accounts(account_id),
    debit               DECIMAL(18,2) DEFAULT 0,
    credit              DECIMAL(18,2) DEFAULT 0,
    description         NVARCHAR(300)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_lines_account')
    CREATE INDEX IX_journal_lines_account ON journal_lines(account_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_journal_entries_date')
    CREATE INDEX IX_journal_entries_date ON journal_entries(entry_date);
GO

-- ============================================================
-- PART B — EMPLOYEES
-- ============================================================

IF OBJECT_ID('departments','U') IS NULL
CREATE TABLE departments (
    department_id       INT IDENTITY(1,1) PRIMARY KEY,
    name_en             NVARCHAR(100) NOT NULL,
    name_ar             NVARCHAR(100),
    is_active           BIT DEFAULT 1
);
GO

IF OBJECT_ID('employees','U') IS NULL
CREATE TABLE employees (
    employee_id         INT IDENTITY(1,1) PRIMARY KEY,
    employee_code       NVARCHAR(20) NOT NULL UNIQUE,
    -- Personal
    full_name_en        NVARCHAR(200) NOT NULL,
    full_name_ar        NVARCHAR(200),
    national_id         NVARCHAR(20),         -- Iqama / National ID
    nationality         NVARCHAR(50),
    is_saudi            BIT DEFAULT 0,         -- affects GOSI rate
    -- Job
    department_id       INT REFERENCES departments(department_id),
    job_title_en        NVARCHAR(100),
    job_title_ar        NVARCHAR(100),
    join_date           DATE,
    -- Salary structure (monthly, SAR)
    basic_salary        DECIMAL(18,2) DEFAULT 0,
    housing_allowance   DECIMAL(18,2) DEFAULT 0,
    transport_allowance DECIMAL(18,2) DEFAULT 0,
    other_allowance     DECIMAL(18,2) DEFAULT 0,
    -- Bank (for WPS)
    bank_name           NVARCHAR(100),
    iban                NVARCHAR(34),
    -- Status
    is_active           BIT DEFAULT 1,
    end_date            DATE,                  -- set when employee leaves
    created_at          DATETIME DEFAULT GETDATE(),
    updated_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- PART C — LOANS / ADVANCES
-- ============================================================

IF OBJECT_ID('employee_loans','U') IS NULL
CREATE TABLE employee_loans (
    loan_id             INT IDENTITY(1,1) PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id),
    loan_date           DATE NOT NULL,
    loan_amount         DECIMAL(18,2) NOT NULL,
    monthly_deduction   DECIMAL(18,2) NOT NULL,
    balance             DECIMAL(18,2) NOT NULL,   -- remaining
    notes               NVARCHAR(300),
    is_settled          BIT DEFAULT 0,
    created_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- PART D — PAYROLL RUNS
-- ============================================================

IF OBJECT_ID('payroll_runs','U') IS NULL
CREATE TABLE payroll_runs (
    run_id              INT IDENTITY(1,1) PRIMARY KEY,
    run_month           INT NOT NULL,          -- 1-12
    run_year            INT NOT NULL,
    run_label           NVARCHAR(30),          -- "June 2026"
    status              NVARCHAR(20) DEFAULT 'draft',  -- draft/approved/paid
    total_gross         DECIMAL(18,2) DEFAULT 0,
    total_deductions    DECIMAL(18,2) DEFAULT 0,
    total_net           DECIMAL(18,2) DEFAULT 0,
    total_gosi_employee DECIMAL(18,2) DEFAULT 0,
    total_gosi_employer DECIMAL(18,2) DEFAULT 0,
    created_by          INT,
    created_at          DATETIME DEFAULT GETDATE(),
    approved_at         DATETIME,
    CONSTRAINT UQ_payroll_period UNIQUE (run_month, run_year)
);
GO

-- Payslip = one line per employee per run
IF OBJECT_ID('payslips','U') IS NULL
CREATE TABLE payslips (
    payslip_id          INT IDENTITY(1,1) PRIMARY KEY,
    run_id              INT NOT NULL REFERENCES payroll_runs(run_id) ON DELETE CASCADE,
    employee_id         INT NOT NULL REFERENCES employees(employee_id),
    -- Snapshot of names
    employee_name_en    NVARCHAR(200),
    employee_name_ar    NVARCHAR(200),
    -- Earnings
    basic_salary        DECIMAL(18,2) DEFAULT 0,
    housing_allowance   DECIMAL(18,2) DEFAULT 0,
    transport_allowance DECIMAL(18,2) DEFAULT 0,
    other_allowance     DECIMAL(18,2) DEFAULT 0,
    overtime_hours      DECIMAL(9,2) DEFAULT 0,
    overtime_amount     DECIMAL(18,2) DEFAULT 0,
    gross_salary        DECIMAL(18,2) DEFAULT 0,
    -- Deductions
    gosi_employee       DECIMAL(18,2) DEFAULT 0,
    gosi_employer       DECIMAL(18,2) DEFAULT 0,
    loan_deduction      DECIMAL(18,2) DEFAULT 0,
    other_deduction     DECIMAL(18,2) DEFAULT 0,
    total_deductions    DECIMAL(18,2) DEFAULT 0,
    -- Net
    net_salary          DECIMAL(18,2) DEFAULT 0,
    -- For WPS
    iban                NVARCHAR(34),
    bank_name           NVARCHAR(100),
    notes               NVARCHAR(300)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_payslips_run')
    CREATE INDEX IX_payslips_run ON payslips(run_id);
GO

-- ============================================================
-- PART E — END OF SERVICE (settlement records)
-- ============================================================

IF OBJECT_ID('eos_settlements','U') IS NULL
CREATE TABLE eos_settlements (
    eos_id              INT IDENTITY(1,1) PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES employees(employee_id),
    employee_name_en    NVARCHAR(200),
    join_date           DATE,
    end_date            DATE,
    years_served        DECIMAL(9,2),
    last_salary         DECIMAL(18,2),         -- basic + housing (wage base)
    reason              NVARCHAR(30),          -- resignation / termination
    gratuity_amount     DECIMAL(18,2),
    notes               NVARCHAR(500),
    settled_at          DATETIME DEFAULT GETDATE()
);
GO

-- ============================================================
-- DEFAULT PAYROLL ACCOUNTS (added to chart of accounts)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_code='5200')
INSERT INTO accounts (account_code, account_name_en, account_name_ar, account_type) VALUES
('5200', 'Salaries Expense',        N'مصروف الرواتب',          'expense'),
('5210', 'GOSI Expense (Employer)', N'مصروف التأمينات',         'expense'),
('5220', 'End of Service Expense',  N'مصروف نهاية الخدمة',      'expense'),
('2300', 'Salaries Payable',        N'رواتب مستحقة',            'liability'),
('2310', 'GOSI Payable',            N'تأمينات مستحقة',          'liability'),
('2320', 'Employee Loans',          N'سلف الموظفين',            'asset');
GO

PRINT '✅ Accounting & Payroll schema patch applied.';
GO
