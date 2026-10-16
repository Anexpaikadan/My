-- ============================================================
-- DayBill ERP v5.23.0 - Mobile / PDT / Van sales
-- ------------------------------------------------------------
--   mobile_access : which DayBill user may use which mobile modules
--                   (Goods In, Goods Out, Stock Count, Stock Adjust,
--                   Product Info, Price Check, Van Sales) + van code / PIN
--   mobile_tokens : signed-in devices
--   mobile_docs   : every document sent from a phone / PDT / van
--                   (inbox: pending → applied / rejected), never twice
-- Safe to run again.
-- ============================================================
IF OBJECT_ID('mobile_access','U') IS NULL
CREATE TABLE mobile_access (
    user_id       INT NOT NULL PRIMARY KEY REFERENCES users(user_id),
    modules       NVARCHAR(300) NULL,
    van_code      NVARCHAR(20) NULL,
    van_pin_hash  NVARCHAR(200) NULL,
    is_active     BIT NOT NULL DEFAULT 1,
    updated_at    DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('mobile_tokens','U') IS NULL
CREATE TABLE mobile_tokens (
    token       NVARCHAR(64) NOT NULL PRIMARY KEY,
    user_id     INT NOT NULL,
    device      NVARCHAR(120) NULL,
    created_at  DATETIME DEFAULT GETDATE(),
    last_seen   DATETIME DEFAULT GETDATE()
);
GO
IF OBJECT_ID('mobile_docs','U') IS NULL
CREATE TABLE mobile_docs (
    doc_id       INT IDENTITY(1,1) PRIMARY KEY,
    doc_uid      NVARCHAR(64) NOT NULL UNIQUE,
    doc_type     NVARCHAR(20) NOT NULL,
    source       NVARCHAR(20) NOT NULL DEFAULT 'wifi',
    user_id      INT NULL,
    device       NVARCHAR(120) NULL,
    status       NVARCHAR(20) NOT NULL DEFAULT 'pending',
    title        NVARCHAR(200) NULL,
    header_json  NVARCHAR(MAX) NULL,
    lines_json   NVARCHAR(MAX) NULL,
    result       NVARCHAR(400) NULL,
    ref_table    NVARCHAR(40) NULL,
    ref_id       INT NULL,
    created_at   DATETIME DEFAULT GETDATE(),
    applied_at   DATETIME NULL,
    applied_by   INT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_mobile_docs_status'
               AND object_id=OBJECT_ID('mobile_docs'))
    CREATE INDEX IX_mobile_docs_status ON mobile_docs(status, created_at);
GO
IF COL_LENGTH('mobile_access','device_seq') IS NULL
    ALTER TABLE mobile_access ADD device_seq INT NOT NULL DEFAULT 0;
GO
IF COL_LENGTH('sales_invoices','van_ref') IS NULL
    ALTER TABLE sales_invoices ADD van_ref NVARCHAR(40) NULL;
GO
