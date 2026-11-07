-- ============================================================
-- DayBill ERP - v7.12.0: Packing Slip / Delivery Note, Item Load Request,
-- Sales Export, Bank Cards, Card Machines, Reminders, Message Templates
-- ------------------------------------------------------------
-- Idempotent: every table / column is guarded, safe to run again.
-- Nothing is deleted or changed in existing data.
-- ============================================================
USE DayBillERP;
GO

-- ── Packing slips + item load requests (no stock, no accounts) ─
IF OBJECT_ID('simple_docs','U') IS NULL
CREATE TABLE simple_docs (
    doc_id          INT IDENTITY(1,1) PRIMARY KEY,
    doc_kind        NVARCHAR(20) NOT NULL,           -- packing_slip | load_request
    doc_number      NVARCHAR(30) NOT NULL UNIQUE,
    doc_date        DATE NOT NULL,
    customer_id     INT NULL,
    party_name      NVARCHAR(200) NULL,
    salesman_id     INT NULL,
    vehicle_id      INT NULL,
    route_id        INT NULL,
    driver_name     NVARCHAR(100) NULL,
    source_kind     NVARCHAR(20) NULL,               -- sales | sales_order
    source_id       INT NULL,
    source_number   NVARCHAR(50) NULL,
    packages        INT NULL,
    needed_date     DATE NULL,
    doc_status      NVARCHAR(20) NOT NULL DEFAULT 'open',   -- open | done | cancelled
    notes           NVARCHAR(500) NULL,
    branch_id       INT NULL,
    counter_id      INT NULL,
    created_by      INT NULL,
    created_at      DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at      DATETIME NULL
);
GO
IF OBJECT_ID('simple_doc_lines','U') IS NULL
CREATE TABLE simple_doc_lines (
    line_id           INT IDENTITY(1,1) PRIMARY KEY,
    doc_id            INT NOT NULL REFERENCES simple_docs(doc_id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    product_id        INT NOT NULL,
    product_code      NVARCHAR(50) NULL,
    product_name_en   NVARCHAR(300) NULL,
    product_name_ar   NVARCHAR(300) NULL,
    quantity          DECIMAL(18,4) NOT NULL DEFAULT 0,
    unit_of_measure_en NVARCHAR(50) NULL,
    done_qty          DECIMAL(18,4) NOT NULL DEFAULT 0,  -- packed / loaded
    remarks           NVARCHAR(200) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_simple_docs_kind_date')
    CREATE INDEX IX_simple_docs_kind_date ON simple_docs(doc_kind, doc_date);
GO

-- ── Sales Export (zero-rated export invoice) ─────────────────
IF COL_LENGTH('sales_invoices','is_export') IS NULL
    ALTER TABLE sales_invoices ADD is_export BIT NOT NULL DEFAULT 0;
GO

-- ── Bank cards (Mada, Visa …) + card machines (bank POS terminals) ─
IF OBJECT_ID('bank_cards','U') IS NULL
CREATE TABLE bank_cards (
    card_id         INT IDENTITY(1,1) PRIMARY KEY,
    card_name       NVARCHAR(60) NOT NULL,
    card_name_ar    NVARCHAR(60) NULL,
    account_id      INT NULL,                         -- where the money lands
    commission_pct  DECIMAL(9,3) NOT NULL DEFAULT 0,
    notes           NVARCHAR(300) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM bank_cards)
INSERT INTO bank_cards (card_name, card_name_ar) VALUES
    (N'Mada', N'مدى'), (N'Visa', N'فيزا'), (N'MasterCard', N'ماستركارد'),
    (N'American Express', N'أمريكان إكسبريس'), (N'STC Pay', N'STC Pay'), (N'Apple Pay', N'Apple Pay');
GO
IF OBJECT_ID('card_machines','U') IS NULL
CREATE TABLE card_machines (
    machine_id      INT IDENTITY(1,1) PRIMARY KEY,
    machine_name    NVARCHAR(80) NOT NULL,
    bank_name       NVARCHAR(80) NULL,
    terminal_id     NVARCHAR(40) NULL,
    account_id      INT NULL,
    counter_name    NVARCHAR(80) NULL,
    notes           NVARCHAR(300) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

-- ── Reminders ────────────────────────────────────────────────
IF OBJECT_ID('reminders','U') IS NULL
CREATE TABLE reminders (
    reminder_id     INT IDENTITY(1,1) PRIMARY KEY,
    title           NVARCHAR(150) NOT NULL,
    details         NVARCHAR(500) NULL,
    due_date        DATE NOT NULL,
    repeat_every    NVARCHAR(10) NOT NULL DEFAULT 'none',   -- none | week | month | year
    for_user_id     INT NULL,                               -- NULL = everyone
    is_done         BIT NOT NULL DEFAULT 0,
    done_at         DATETIME NULL,
    created_by      INT NULL,
    created_at      DATETIME DEFAULT GETDATE()
);
GO

-- ── Message templates (WhatsApp / SMS / e-mail) ──────────────
IF OBJECT_ID('message_templates','U') IS NULL
CREATE TABLE message_templates (
    template_id     INT IDENTITY(1,1) PRIMARY KEY,
    template_name   NVARCHAR(80) NOT NULL,
    channel         NVARCHAR(10) NOT NULL DEFAULT 'whatsapp',  -- whatsapp | sms | email
    purpose         NVARCHAR(30) NULL,                         -- invoice | statement | reminder | other
    subject         NVARCHAR(150) NULL,
    body            NVARCHAR(2000) NOT NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);
GO
IF NOT EXISTS (SELECT 1 FROM message_templates)
INSERT INTO message_templates (template_name, channel, purpose, subject, body) VALUES
    (N'Invoice', N'whatsapp', N'invoice', NULL,
     N'Dear {customer}, thank you for shopping at {shop}. Your bill {number} is {total}.'),
    (N'Payment reminder', N'whatsapp', N'reminder', NULL,
     N'Dear {customer}, your balance with {shop} is {balance}. Please pay at your earliest convenience.'),
    (N'Statement', N'email', N'statement', N'Your statement from {shop}',
     N'Dear {customer},\nplease find your account statement attached. Balance: {balance}.\n\n{shop}');
GO

PRINT 'DayBill v7.12.0 patch applied.';
GO
