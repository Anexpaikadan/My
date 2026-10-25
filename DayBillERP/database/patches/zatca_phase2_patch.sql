-- ============================================================
-- SAUDI ERP - ZATCA Phase 2 Schema Patch (Step 6)
-- Adds columns needed for cryptographic stamping & hash chain.
-- Safe to run multiple times (checks existence first).
-- ============================================================

USE DayBillERP;
GO

-- ── company: store onboarding CSID credentials ──────────────
IF COL_LENGTH('company', 'zatca_csid_token') IS NULL
    ALTER TABLE company ADD zatca_csid_token NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_csid_secret') IS NULL
    ALTER TABLE company ADD zatca_csid_secret NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_compliance_token') IS NULL
    ALTER TABLE company ADD zatca_compliance_token NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_compliance_secret') IS NULL
    ALTER TABLE company ADD zatca_compliance_secret NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_compliance_request_id') IS NULL
    ALTER TABLE company ADD zatca_compliance_request_id NVARCHAR(100);
GO
IF COL_LENGTH('company', 'zatca_csr') IS NULL
    ALTER TABLE company ADD zatca_csr NVARCHAR(MAX);
GO
IF COL_LENGTH('company', 'zatca_onboarded') IS NULL
    ALTER TABLE company ADD zatca_onboarded BIT DEFAULT 0;
GO

-- ── sales_invoices: hash chain + signed XML ─────────────────
IF COL_LENGTH('sales_invoices', 'zatca_previous_hash') IS NULL
    ALTER TABLE sales_invoices ADD zatca_previous_hash NVARCHAR(256);
GO
IF COL_LENGTH('sales_invoices', 'zatca_signed_xml') IS NULL
    ALTER TABLE sales_invoices ADD zatca_signed_xml NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_signature') IS NULL
    ALTER TABLE sales_invoices ADD zatca_signature NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_qr_phase2') IS NULL
    ALTER TABLE sales_invoices ADD zatca_qr_phase2 NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_cleared_xml') IS NULL
    ALTER TABLE sales_invoices ADD zatca_cleared_xml NVARCHAR(MAX);
GO
IF COL_LENGTH('sales_invoices', 'zatca_warnings') IS NULL
    ALTER TABLE sales_invoices ADD zatca_warnings NVARCHAR(MAX);
GO

PRINT '✅ ZATCA Phase 2 schema patch applied.';
GO
