-- ============================================================
-- DayBill ERP - ZATCA Phase 2 connection + send queue (v5.21)
-- ------------------------------------------------------------
-- zatca_egs : this shop's e-invoicing unit (EGS): private key,
--             ZATCA certificates (CSIDs), invoice counter (ICV)
--             and the last invoice hash (PIH chain)
-- sales_invoices / sales_returns : the signed XML, hash, Phase 2 QR
--             and the ZATCA answer of every document sent
-- Idempotent: safe to run multiple times.
-- ============================================================
USE DayBillERP;
GO
IF OBJECT_ID('zatca_egs','U') IS NULL
CREATE TABLE zatca_egs (
    egs_id            INT IDENTITY(1,1) PRIMARY KEY,
    env               NVARCHAR(20)  NOT NULL DEFAULT 'sandbox',
    egs_name          NVARCHAR(100) NULL,
    egs_serial        NVARCHAR(200) NULL,
    private_key       NVARCHAR(MAX) NULL,
    csr               NVARCHAR(MAX) NULL,
    ccsid_token       NVARCHAR(MAX) NULL,
    ccsid_secret      NVARCHAR(200) NULL,
    ccsid_request_id  NVARCHAR(100) NULL,
    pcsid_token       NVARCHAR(MAX) NULL,
    pcsid_secret      NVARCHAR(200) NULL,
    pcsid_request_id  NVARCHAR(100) NULL,
    cert_expires      DATETIME NULL,
    icv               INT NOT NULL DEFAULT 0,
    last_hash         NVARCHAR(200) NULL,
    status            NVARCHAR(20) NOT NULL DEFAULT 'new',
    is_active         BIT NOT NULL DEFAULT 1,
    auto_send         BIT NOT NULL DEFAULT 1,
    onboarded_at      DATETIME NULL,
    created_at        DATETIME NOT NULL DEFAULT GETDATE(),
    last_error        NVARCHAR(1000) NULL
);
GO
-- ── sales_invoices ──────────────────────────────────────────
IF COL_LENGTH('sales_invoices','zatca_uuid') IS NULL ALTER TABLE sales_invoices ADD zatca_uuid NVARCHAR(36) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_icv') IS NULL ALTER TABLE sales_invoices ADD zatca_icv INT NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_kind') IS NULL ALTER TABLE sales_invoices ADD zatca_kind NVARCHAR(12) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_egs_id') IS NULL ALTER TABLE sales_invoices ADD zatca_egs_id INT NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_attempts') IS NULL ALTER TABLE sales_invoices ADD zatca_attempts INT NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_last_error') IS NULL ALTER TABLE sales_invoices ADD zatca_last_error NVARCHAR(2000) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_status') IS NULL ALTER TABLE sales_invoices ADD zatca_status NVARCHAR(20) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_invoice_hash') IS NULL ALTER TABLE sales_invoices ADD zatca_invoice_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_previous_hash') IS NULL ALTER TABLE sales_invoices ADD zatca_previous_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_signed_xml') IS NULL ALTER TABLE sales_invoices ADD zatca_signed_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_qr_phase2') IS NULL ALTER TABLE sales_invoices ADD zatca_qr_phase2 NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_cleared_xml') IS NULL ALTER TABLE sales_invoices ADD zatca_cleared_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_warnings') IS NULL ALTER TABLE sales_invoices ADD zatca_warnings NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_response') IS NULL ALTER TABLE sales_invoices ADD zatca_response NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_invoices','zatca_submitted_at') IS NULL ALTER TABLE sales_invoices ADD zatca_submitted_at DATETIME NULL;
GO
-- ── sales_returns (credit notes) ────────────────────────────
IF COL_LENGTH('sales_returns','zatca_uuid') IS NULL ALTER TABLE sales_returns ADD zatca_uuid NVARCHAR(36) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_icv') IS NULL ALTER TABLE sales_returns ADD zatca_icv INT NULL;
GO
IF COL_LENGTH('sales_returns','zatca_kind') IS NULL ALTER TABLE sales_returns ADD zatca_kind NVARCHAR(12) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_egs_id') IS NULL ALTER TABLE sales_returns ADD zatca_egs_id INT NULL;
GO
IF COL_LENGTH('sales_returns','zatca_attempts') IS NULL ALTER TABLE sales_returns ADD zatca_attempts INT NULL;
GO
IF COL_LENGTH('sales_returns','zatca_last_error') IS NULL ALTER TABLE sales_returns ADD zatca_last_error NVARCHAR(2000) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_status') IS NULL ALTER TABLE sales_returns ADD zatca_status NVARCHAR(20) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_invoice_hash') IS NULL ALTER TABLE sales_returns ADD zatca_invoice_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_previous_hash') IS NULL ALTER TABLE sales_returns ADD zatca_previous_hash NVARCHAR(256) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_signed_xml') IS NULL ALTER TABLE sales_returns ADD zatca_signed_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_qr_phase2') IS NULL ALTER TABLE sales_returns ADD zatca_qr_phase2 NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_cleared_xml') IS NULL ALTER TABLE sales_returns ADD zatca_cleared_xml NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_warnings') IS NULL ALTER TABLE sales_returns ADD zatca_warnings NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_response') IS NULL ALTER TABLE sales_returns ADD zatca_response NVARCHAR(MAX) NULL;
GO
IF COL_LENGTH('sales_returns','zatca_submitted_at') IS NULL ALTER TABLE sales_returns ADD zatca_submitted_at DATETIME NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sales_invoices_zatca_q' AND object_id=OBJECT_ID('sales_invoices'))
    CREATE INDEX IX_sales_invoices_zatca_q ON sales_invoices(zatca_status, zatca_icv);
GO
PRINT N'✅ ZATCA Phase 2 connection + send queue ready.';
GO
