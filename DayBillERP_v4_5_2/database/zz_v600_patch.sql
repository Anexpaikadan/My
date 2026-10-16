-- ============================================================
-- DayBill ERP - v6.0.0 database update
-- ------------------------------------------------------------
--  ZATCA      one e-invoicing unit per till, debit notes, 700 number
--  POS        payment lines (cash / mada / STC Pay / Tabby …),
--             cashier shifts (opening float, counted cash)
--  Prices     price lists for customers (wholesale, VIP …)
--  Stock      stock per branch, transfers between branches,
--             batches with expiry dates (first-expiry-first-out)
--  Books      bank reconciliation, year-end closing entry
--  HR         leave, attendance, GOSI old / new system per employee
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

-- ── ZATCA ───────────────────────────────────────────────────
IF COL_LENGTH('zatca_egs','counter_id') IS NULL
    ALTER TABLE zatca_egs ADD counter_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','invoice_kind') IS NULL
    ALTER TABLE sales_invoices ADD invoice_kind NVARCHAR(12) NULL;
GO
IF COL_LENGTH('sales_invoices','original_invoice_no') IS NULL
    ALTER TABLE sales_invoices ADD original_invoice_no NVARCHAR(50) NULL;
GO
IF COL_LENGTH('sales_invoices','debit_reason') IS NULL
    ALTER TABLE sales_invoices ADD debit_reason NVARCHAR(200) NULL;
GO
IF COL_LENGTH('company','id_scheme') IS NULL
    ALTER TABLE company ADD id_scheme NVARCHAR(5) NULL;
GO

-- ── POS: payment lines ──────────────────────────────────────
IF OBJECT_ID('payment_tenders','U') IS NULL
CREATE TABLE payment_tenders (
    tender_id     INT IDENTITY(1,1) PRIMARY KEY,
    doc_type      NVARCHAR(20) NOT NULL,
    doc_id        INT NOT NULL,
    method        NVARCHAR(20) NOT NULL,
    amount        DECIMAL(18,2) NOT NULL DEFAULT 0,
    reference     NVARCHAR(100) NULL,
    account_id    INT NULL,
    created_at    DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_payment_tenders_doc')
    CREATE INDEX IX_payment_tenders_doc ON payment_tenders(doc_type, doc_id);
GO

-- ── POS: cashier shifts ─────────────────────────────────────
IF OBJECT_ID('cashier_shifts','U') IS NULL
CREATE TABLE cashier_shifts (
    shift_id       INT IDENTITY(1,1) PRIMARY KEY,
    counter_id     INT NULL,
    branch_id      INT NULL,
    user_id        INT NULL,
    username       NVARCHAR(50) NULL,
    opened_at      DATETIME DEFAULT GETDATE(),
    opening_float  DECIMAL(18,2) NOT NULL DEFAULT 0,
    closed_at      DATETIME NULL,
    expected_cash  DECIMAL(18,2) NULL,
    counted_cash   DECIMAL(18,2) NULL,
    difference     DECIMAL(18,2) NULL,
    status         NVARCHAR(10) NOT NULL DEFAULT 'open',
    notes          NVARCHAR(500) NULL
);
GO
IF COL_LENGTH('sales_invoices','shift_id') IS NULL
    ALTER TABLE sales_invoices ADD shift_id INT NULL;
GO
IF COL_LENGTH('sales_returns','shift_id') IS NULL
    ALTER TABLE sales_returns ADD shift_id INT NULL;
GO

-- ── price lists ─────────────────────────────────────────────
IF OBJECT_ID('price_lists','U') IS NULL
CREATE TABLE price_lists (
    price_list_id   INT IDENTITY(1,1) PRIMARY KEY,
    name_en         NVARCHAR(60) NOT NULL,
    name_ar         NVARCHAR(60) NULL,
    base_on         NVARCHAR(12) NOT NULL DEFAULT 'retail',
    adjust_percent  DECIMAL(9,3) NOT NULL DEFAULT 0,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('price_list_items','U') IS NULL
CREATE TABLE price_list_items (
    item_id         INT IDENTITY(1,1) PRIMARY KEY,
    price_list_id   INT NOT NULL,
    product_id      INT NOT NULL,
    unit_name       NVARCHAR(50) NULL,
    price           DECIMAL(18,4) NOT NULL DEFAULT 0
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_price_list_items')
    CREATE UNIQUE INDEX UX_price_list_items ON price_list_items(price_list_id, product_id, unit_name);
GO
IF COL_LENGTH('customers','price_list_id') IS NULL
    ALTER TABLE customers ADD price_list_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','price_list_id') IS NULL
    ALTER TABLE sales_invoices ADD price_list_id INT NULL;
GO

-- ── stock per branch ────────────────────────────────────────
-- A branch's stock = its rows on the stock card (inventory_transactions
-- .branch_id). Rows with no branch belong to the main branch, so a
-- one-branch shop sees no change at all.
IF COL_LENGTH('inventory_transactions','branch_id') IS NULL
    ALTER TABLE inventory_transactions ADD branch_id INT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_inv_txn_branch')
    CREATE INDEX IX_inv_txn_branch ON inventory_transactions(branch_id, product_id);
GO
IF OBJECT_ID('stock_transfers','U') IS NULL
CREATE TABLE stock_transfers (
    transfer_id      INT IDENTITY(1,1) PRIMARY KEY,
    transfer_number  NVARCHAR(30) NOT NULL,
    transfer_date    DATE NOT NULL,
    from_branch_id   INT NOT NULL,
    to_branch_id     INT NOT NULL,
    status           NVARCHAR(12) NOT NULL DEFAULT 'done',
    notes            NVARCHAR(300) NULL,
    created_by       INT NULL,
    created_at       DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('stock_transfer_lines','U') IS NULL
CREATE TABLE stock_transfer_lines (
    line_id       INT IDENTITY(1,1) PRIMARY KEY,
    transfer_id   INT NOT NULL,
    product_id    INT NOT NULL,
    unit_name     NVARCHAR(50) NULL,
    factor        DECIMAL(18,6) NOT NULL DEFAULT 1,
    quantity      DECIMAL(18,4) NOT NULL DEFAULT 0,
    qty_base      DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_cost     DECIMAL(18,4) NULL
);
GO

-- ── batches & expiry ────────────────────────────────────────
IF COL_LENGTH('products','track_expiry') IS NULL
    ALTER TABLE products ADD track_expiry BIT NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('purchase_invoice_lines','batch_no') IS NULL
    ALTER TABLE purchase_invoice_lines ADD batch_no NVARCHAR(50) NULL;
GO
IF COL_LENGTH('purchase_invoice_lines','expiry_date') IS NULL
    ALTER TABLE purchase_invoice_lines ADD expiry_date DATE NULL;
GO
IF OBJECT_ID('product_batches','U') IS NULL
CREATE TABLE product_batches (
    batch_id       INT IDENTITY(1,1) PRIMARY KEY,
    product_id     INT NOT NULL,
    branch_id      INT NULL,
    batch_no       NVARCHAR(50) NULL,
    expiry_date    DATE NULL,
    qty_base       DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_cost      DECIMAL(18,4) NULL,
    received_date  DATE NULL,
    created_at     DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('batch_movements','U') IS NULL
CREATE TABLE batch_movements (
    move_id       INT IDENTITY(1,1) PRIMARY KEY,
    batch_id      INT NOT NULL,
    source_type   NVARCHAR(30) NOT NULL,
    source_id     INT NOT NULL,
    qty_base      DECIMAL(18,4) NOT NULL,
    created_at    DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_batch_movements_src')
    CREATE INDEX IX_batch_movements_src ON batch_movements(source_type, source_id);
GO

-- ── bank reconciliation ─────────────────────────────────────
IF OBJECT_ID('bank_reconciliations','U') IS NULL
CREATE TABLE bank_reconciliations (
    rec_id             INT IDENTITY(1,1) PRIMARY KEY,
    account_id         INT NOT NULL,
    statement_date     DATE NOT NULL,
    statement_balance  DECIMAL(18,2) NOT NULL DEFAULT 0,
    cleared_balance    DECIMAL(18,2) NULL,
    difference         DECIMAL(18,2) NULL,
    status             NVARCHAR(10) NOT NULL DEFAULT 'draft',
    notes              NVARCHAR(300) NULL,
    created_by         INT NULL,
    created_at         DATETIME DEFAULT GETDATE(),
    finished_at        DATETIME NULL
);
GO
IF COL_LENGTH('journal_lines','rec_id') IS NULL
    ALTER TABLE journal_lines ADD rec_id INT NULL;
GO

-- ── year-end closing ────────────────────────────────────────
IF COL_LENGTH('financial_years','closing_journal_id') IS NULL
    ALTER TABLE financial_years ADD closing_journal_id INT NULL;
GO

-- ── HR: GOSI system, leave, attendance ──────────────────────
IF COL_LENGTH('employees','gosi_system') IS NULL
    ALTER TABLE employees ADD gosi_system NVARCHAR(4) NULL;
GO
IF OBJECT_ID('employee_leaves','U') IS NULL
CREATE TABLE employee_leaves (
    leave_id      INT IDENTITY(1,1) PRIMARY KEY,
    employee_id   INT NOT NULL,
    leave_type    NVARCHAR(20) NOT NULL DEFAULT 'annual',
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    days          DECIMAL(6,1) NOT NULL DEFAULT 0,
    paid          BIT NOT NULL DEFAULT 1,
    status        NVARCHAR(12) NOT NULL DEFAULT 'approved',
    notes         NVARCHAR(300) NULL,
    created_at    DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('attendance','U') IS NULL
CREATE TABLE attendance (
    att_id        INT IDENTITY(1,1) PRIMARY KEY,
    employee_id   INT NOT NULL,
    work_date     DATE NOT NULL,
    check_in      NVARCHAR(5) NULL,
    check_out     NVARCHAR(5) NULL,
    hours         DECIMAL(6,2) NULL,
    status        NVARCHAR(10) NOT NULL DEFAULT 'present',
    notes         NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_attendance_day')
    CREATE UNIQUE INDEX UX_attendance_day ON attendance(employee_id, work_date);
GO
PRINT '✅ DayBill v6.0.0 database update ready.';
GO
