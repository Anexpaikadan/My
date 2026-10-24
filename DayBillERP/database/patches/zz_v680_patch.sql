-- ============================================================
-- DayBill ERP - v6.8.0 database update
-- ------------------------------------------------------------
--  Online forms   answers from Tally web forms (customer and
--                 supplier registration, receipt feedback) wait
--                 here until someone reviews them
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('online_form_entries','U') IS NULL
CREATE TABLE online_form_entries (
    entry_id      INT IDENTITY(1,1) PRIMARY KEY,
    form_kind     NVARCHAR(20) NOT NULL,          -- customer | supplier | feedback
    submission_id NVARCHAR(60) NOT NULL,          -- Tally submission id (never twice)
    submitted_at  DATETIME NULL,
    received_at   DATETIME DEFAULT GETDATE(),
    title         NVARCHAR(200) NULL,             -- name, or the start of the comment
    phone         NVARCHAR(30) NULL,
    rating        INT NULL,                       -- feedback: 1–5 stars
    bill_no       NVARCHAR(40) NULL,              -- feedback: bill on the receipt QR
    payload_json  NVARCHAR(MAX) NULL,             -- all answers as sent
    status        NVARCHAR(20) DEFAULT 'new',     -- new | added | ignored | done
    record_id     INT NULL,                       -- the customer / supplier made from it
    handled_by    NVARCHAR(50) NULL,
    handled_at    DATETIME NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_online_form_entries_sub')
    CREATE UNIQUE INDEX UX_online_form_entries_sub ON online_form_entries(submission_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_online_form_entries_kind')
    CREATE INDEX IX_online_form_entries_kind ON online_form_entries(form_kind, status);
GO

PRINT 'DayBill v6.8.0 database update applied (online forms).';
GO
