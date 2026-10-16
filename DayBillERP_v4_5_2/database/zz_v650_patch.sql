-- ============================================================
-- DayBill ERP - v6.5.0 database update
-- ------------------------------------------------------------
--  WhatsApp     every message sent with the Cloud API (Meta charges
--               each one since 1 Oct 2026) — the monthly count and
--               cost in Settings ▸ WhatsApp
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO

IF OBJECT_ID('whatsapp_messages','U') IS NULL
CREATE TABLE whatsapp_messages (
    msg_id      INT IDENTITY(1,1) PRIMARY KEY,
    sent_at     DATETIME DEFAULT GETDATE(),
    sent_date   DATE NULL,
    phone       NVARCHAR(30) NULL,
    kind        NVARCHAR(40) NULL,             -- sales | purchase_order | owner_report | …
    template    NVARCHAR(100) NULL,
    has_pdf     BIT DEFAULT 0,
    ok          BIT DEFAULT 1,
    info        NVARCHAR(300) NULL             -- WhatsApp message id or the error
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_whatsapp_messages_date')
    CREATE INDEX IX_whatsapp_messages_date ON whatsapp_messages(sent_date, ok);
GO

PRINT 'DayBill v6.5.0 database update applied (WhatsApp message count).';
GO
