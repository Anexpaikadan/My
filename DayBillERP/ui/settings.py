# ============================================================
# DayBill ERP - Application Settings
# Tree menu (left) + details panel (right) + search + Save/Apply/
# Reset/Backup/Restore.  Company section reads/writes the company
# table; everything else persists to app_settings.json via cfg.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys, os, json, shutil
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db


# Field tuple: (key, label, type, options)
#   type: text | long | check | choice | number
def F(key, label, ftype="text", options=None):
    return {"key": key, "label": label, "type": ftype, "options": options or []}


def _printer_options():
    try:
        from modules import printer_service as ps
        names = ps.list_printers() or []
    except Exception:
        names = []
    return [("", "(Windows default printer)")] + [(n, n) for n in names]


def _plu_format_options():
    try:
        from ui.plu_manager import SCALE_FORMATS
        return [(k, v["label"]) for k, v in SCALE_FORMATS.items()]
    except Exception:
        return ["EAN13_WEIGHT_2", "EAN13_PRICE_2", "EAN13_WEIGHT_20",
                "EAN13_PRICE_21", "PLU_ONLY"]


SECTIONS = [
    {"key": "company", "title": "Company", "icon": "🏢", "store": "company", "fields": [
        F("company_name_en", "Company Name (EN)"),
        F("company_name_ar", "Company Name (AR)"),
        F("logo_path", "Company Logo (path)"),
        F("business_type", "Business Type", "choice",
          ["Retail", "Wholesale", "Manufacturing", "Trading", "Services",
           "Restaurant / F&B", "Other"]),
        F("vat_registration_no", "VAT/GST/TIN Number"),
        F("cr_number", "Registration Number (CR)"),
        F("address_en", "Address", "long"),
        F("country", "Country", "choice",
          ["Saudi Arabia", "UAE", "Bahrain", "Qatar", "Oman", "Kuwait", "India", "Other"]),
        F("state_en", "State / Province"),
        F("city_en", "City"),
        F("postal_code", "Postal Code"),
        F("phone", "Phone"),
        F("email", "Email"),
        F("website", "Website (printed on invoices)"),
        F("currency", "Currency", "choice", ["SAR", "AED", "BHD", "QAR", "OMR", "KWD", "USD", "INR"]),
        F("date_format", "Date Format (printed documents)", "choice",
          ["dd/MM/yyyy", "yyyy-MM-dd", "MM/dd/yyyy"]),
        F("time_format", "Time Format (printed documents)", "choice",
          ["24-hour", "12-hour (AM/PM)"]),
        F("language", "Language", "choice", ["en", "ar"]),
        F("fiscal_year_start", "Financial Year Start (MM-DD) — used by 'This year' in reports"),
    ]},
    {"key": "tax", "title": "Tax (VAT)", "icon": "🧮", "store": "app", "fields": [
        F("vat_enabled", "Enable VAT", "check"),
        F("sales_price_tax_mode", "Sales Price Mode — inclusive = price already has VAT (Invoice + POS)", "choice",
          ["inclusive", "exclusive"]),
        F("purchase_cost_tax_mode", "Purchase Cost Mode", "choice",
          ["inclusive", "exclusive"]),
        F("country_tax_profile", "Country Tax Profile (sets the default rate)", "choice",
          ["Saudi Arabia VAT 15%", "UAE VAT 5%", "Bahrain VAT 10%",
           "Oman VAT 5%", "Qatar / Kuwait (no VAT)", "Custom"]),
        F("tax_sales_rate", "Default VAT Rate % (new products)", "number"),
        F("apply_vat_sales", "Apply VAT On Sales Invoice", "check"),
        F("apply_vat_sales_return", "Apply VAT On Sales Return", "check"),
        F("apply_vat_pos", "Apply VAT On POS Invoice", "check"),
        F("apply_vat_purchase", "Apply VAT On Purchase Invoice", "check"),
        F("apply_vat_purchase_return", "Apply VAT On Purchase Return", "check"),
        F("pos_show_vat_column", "Show VAT Column In POS", "check"),
        F("receipt_vat_per_item", "Print VAT Of Each Item On The Receipt", "check"),
        F("pos_show_vat_receipt", "Show VAT Amount On Receipt", "check"),
        F("pos_print_vat_no", "Print VAT Number On Receipt", "check"),
        F("round_off_enabled", "Round-off Invoice Total", "check"),
        F("round_off_method", "Round-off Method", "choice",
          ["Nearest 0.05", "Nearest 0.10", "Nearest 1.00", "None"]),
    ]},
    {"key": "sales", "title": "Sales", "icon": "🧾", "store": "app", "fields": [
        F("sales_prefix", "Sales Invoice Prefix"),
        F("sales_start_no", "Starting Number", "number"),
        F("allow_negative_stock", "Allow Negative Stock", "check"),
        F("allow_price_edit", "Allow Price Edit", "check"),
        F("allow_discount_edit", "Allow Discount Edit", "check"),
        F("allow_sales_return", "Allow Sales Return", "check"),
        F("allow_edit_confirmed", "Allow edit / delete of confirmed documents (stock + accounts re-post automatically)", "check"),
        F("auto_print_invoice", "Auto Print Invoice", "check"),
        F("show_stock_during_sales", "Show Stock During Sales", "check"),
        F("barcode_mandatory_sales", "Barcode Mandatory", "check"),
        F("cart_dup_check", "Warn When Product Already In Cart", "check"),
        F("warn_sale_below_cost", "Warn When Selling Below Cost", "check"),
        F("auto_history_box", "Show last prices box when a product is picked", "check"),
        F("voice_search_enabled", "Voice product search in the invoice window", "check"),
    ]},
    {"key": "purchase", "title": "Purchase", "icon": "🛒", "store": "app", "fields": [
        F("purchase_prefix", "Purchase Invoice Prefix"),
        F("purchase_start_no", "Starting Number", "number"),
        F("allow_purchase_return", "Allow Purchase Return", "check"),
        F("auto_update_cost", "Auto Update Cost", "check"),
        F("cost_basis", "Cost Basis", "choice", ["Last Purchase", "Average Cost"]),
        F("barcode_mandatory_purchase", "Barcode Mandatory", "check"),
        # v6.4 📈 Price Updates
        F("price_alert_pct", "Price Updates: show items whose cost went up by at least (%)", "number"),
        F("price_rounding", "Price Updates: round new prices up to", "choice",
          ["0.05", "0.10", "0.25", "0.50", "1.00"]),
    ]},
    {"key": "pos", "title": "POS", "icon": "🖥", "store": "app", "fields": [
        F("pos_touchscreen", "Touchscreen Mode (big buttons and rows)", "check"),
        F("pos_fullscreen", "Full Screen POS", "check"),
        F("pos_show_favorites", "Show Favorite Products", "check"),
        F("pos_show_images", "Show Product Pictures On Favorite Buttons", "check"),
        F("pos_auto_focus_barcode", "Auto Focus Barcode", "check"),
        F("pos_auto_print", "Auto Print Receipt", "check"),
        F("pos_print_format", "Receipt Format", "choice",
          [("thermal", "Thermal receipt"), ("a4", "A4 invoice")]),
        F("pos_open_drawer", "Open Cash Drawer On Cash Sale", "check"),
        F("pos_voice_not_found", "Voice Alert When Product Not Found", "check"),
        F("pos_enable_hold", "Enable Hold Bills", "check"),
        F("pos_receipt_header", "Receipt Header Text"),
        F("pos_receipt_footer", "Receipt Footer Text"),
        F("pos_thankyou", "Thank You Message"),
        F("pos_qr_print", "Print QR Code", "check"),
        F("pos_show_cost_in_search", "Show purchase price in the product search list", "check"),
        # v6.0
        F("pos_extra_tenders", "More ways to pay beside Cash / Card (comma list: stc_pay, apple_pay, "
          "bank_transfer, tabby, tamara, voucher)"),
        F("pos_require_shift", "Cashier must open a shift (count the drawer) before the first sale", "check"),
        F("pos_blind_count", "Blind count when closing a shift (expected cash shown after the count)", "check"),
        F("pos_offline_queue", "Keep selling when the server can't be reached (bills kept on this PC, sent later)", "check"),
        F("cashier_watch_short", "Cashier Watch: warn when a cashier's cash is short by (SAR)", "number"),
    ]},
    {"key": "barcode", "title": "Barcode", "icon": "🏷", "store": "app", "fields": [
        F("barcode_prefix", "Product Prefix"),
        F("barcode_length", "Barcode Length (6 = short number 100001…, 13 = EAN-13)", "number"),
        F("barcode_check_digit", "Check Digit Enabled (8+ digits)", "check"),
        F("barcode_start", "First Auto Barcode (6 digits, e.g. 100001 or 543210)", "number"),
        F("barcode_system_locked", "System Barcodes Are Made By DayBill Only (no typing / changing; "
          "a maker's barcode goes in 🏷 Extra Barcodes)", "check"),
        F("barcode_label_size", "Default Label Size", "choice",
          ["20x10 mm", "30x20 mm", "40x25 mm", "50x25 mm", "60x40 mm",
           "2 × 7 (14/page)", "3 × 8 (24/page)", "4 × 10 (40/page)"]),
        F("barcode_sound", "Sound On Scan", "check"),
        F("auto_unit_barcode", "Create Barcodes Automatically (Product + Every Unit)", "check"),
    ]},
    {"key": "plu", "title": "PLU Scale", "icon": "⚖", "store": "app", "fields": [
        F("plu_enabled", "Enable PLU Scale (read weight / price barcodes)", "check"),
        F("plu_barcode_format", "Scale Barcode Format", "choice", _plu_format_options),
        F("plu_export_path", "PLU Export Folder (file for the scale)"),
        F("plu_export_on_save", "Export PLU file automatically when a scale item is saved", "check"),
    ]},
    {"key": "inventory", "title": "Inventory", "icon": "📦", "store": "app", "fields": [
        F("inv_negative_stock", "Negative Stock Control (Allow)", "check"),
        F("inv_low_stock_level", "Low Stock Alert Level (qty)", "number"),
        F("product_code_max_len", "Product Code Maximum Length (characters, 0 = no limit)", "number"),
        F("expiry_alert_days", "Warn about batches expiring within (days)", "number"),
        # v6.4 🧮 Stock Count (phone)
        F("count_needs_approval", "Stock counts from phones wait for the owner's OK (Stock Count ▸ To approve)", "check"),
        F("count_every_a_days", "Count A items (best sellers) every (days)", "number"),
        F("count_every_b_days", "Count B items every (days)", "number"),
        F("count_every_c_days", "Count C items every (days)", "number"),
        F("count_list_size", "Items on today's count list (at most)", "number"),
    ]},
    {"key": "hr", "title": "HR & Payroll", "icon": "👔", "store": "app", "fields": [
        F("hr_deduct_unpaid_days", "Payroll takes absent days and unpaid leave off the salary", "check"),
        # v6.6
        F("hr_sick_tiers", "Sick leave pay by the law (art. 117: 30 days full, 60 days ¾, 30 days unpaid)", "check"),
        F("hr_overtime_from_attendance", "Overtime hours from attendance (hours above the day + days off)", "check"),
        F("hr_leave_carry", "Unused annual leave carries on (earned from the join date; paid at the end of service)", "check"),
        F("hr_daily_hours", "Working hours a day (hourly wage = monthly ÷ 30 ÷ hours)", "number"),
        F("hr_wage_basis", "Wage for end of service, leave pay and overtime", "choice",
          [("actual", "Actual wage: basic + all allowances (law)"), ("basic_housing", "Basic + housing (contract)")]),
        F("hr_doc_alert_days", "Warn about Iqama / passport / insurance / contract expiring within (days)", "number"),
        F("hr_probation_days", "Probation for new staff (days, at most 180 — 2025 law)", "number"),
        F("hr_ramadan_hours", "Working hours a day in Ramadan (art. 98 — Muslim staff; 0 = off)", "number"),
        F("hr_ramadan_dates", "Ramadan dates if the moon changes them (YYYY-MM-DD:YYYY-MM-DD, empty = calendar)"),
        F("gosi_old_pension_pct", "GOSI pension % — old system (each side)", "number"),
        F("gosi_new_pension_steps", "GOSI pension % — new system steps (date:%, …)"),
        F("gosi_new_system_from", "New GOSI system starts (YYYY-MM-DD)"),
        F("gosi_saned_pct", "SANED (unemployment) % — each side", "number"),
        F("gosi_hazard_pct", "Occupational hazards % — employer", "number"),
        F("gosi_nonsaudi_employer_pct", "Non-Saudi: employer %", "number"),
        F("gosi_wage_cap", "GOSI wage cap (SAR, basic + housing)", "number"),
    ]},
    {"key": "accounting", "title": "Journal Posting", "icon": "📒", "store": "app", "fields": [
        F("acc_auto_posting", "Auto Ledger Posting", "check"),
        F("acc_manual_approval", "Manual Approval Required", "check"),
        F("acc_post_stock_adjust", "Post stock adjustments and counts to accounts", "check"),
    ]},
    {"key": "customer", "title": "Customer", "icon": "👥", "store": "app", "fields": [
        F("cust_prefix", "Customer Code Prefix"),
        F("cust_auto_code", "Auto Generate Code", "check"),
        F("cust_credit_limit", "Credit Limit Enabled", "check"),
        F("cust_over_credit_warn", "Over Credit Warning", "check"),
        F("cust_mandatory_mobile", "Mandatory Mobile", "check"),
        F("cust_mandatory_vat", "Mandatory VAT Number", "check"),
        F("loyalty_enabled", "⭐ Loyalty points (customers earn on every bill, spend as a discount)", "check"),
        F("loyalty_sar_per_point", "Loyalty · spend this many SAR to earn 1 point", "number"),
        F("loyalty_point_value", "Loyalty · 1 point is worth (SAR) when spent", "number"),
        F("loyalty_min_redeem", "Loyalty · fewest points spent at once", "number"),
    ]},
    {"key": "supplier", "title": "Supplier", "icon": "🏭", "store": "app", "fields": [
        F("sup_prefix", "Supplier Code Prefix"),
        F("sup_auto_code", "Auto Generate Code", "check"),
        F("sup_mandatory_vat", "Mandatory VAT", "check"),
    ]},
    {"key": "security", "title": "Users & Security", "icon": "🔐", "store": "app", "fields": [
        F("pwd_min_length", "Password Minimum Length", "number"),
        F("pwd_expiry_days", "Password Expiry (days, 0 = never)", "number"),
    ]},
    {"key": "print", "title": "Printing", "icon": "🖨", "store": "app", "fields": [
        F("print_direct", "Print on the default printer without asking (untick = choose the printer each time)", "check"),
        F("printer_invoice", "Invoice Printer (A4)", "choice", _printer_options),
        F("printer_pos", "POS Thermal Printer", "choice", _printer_options),
        F("printer_dotmatrix", "Dot-matrix Printer", "choice", _printer_options),
        F("printer_labels", "Label Printer", "choice", _printer_options),
        F("printer_a4", "A4 Reports Printer", "choice", _printer_options),
        F("pos_paper_size", "POS Paper Size", "choice", ["80mm", "58mm"]),
        F("print_copies", "Copies", "number"),
    ]},
    {"key": "online_forms", "title": "Online forms (Tally / Jotform)", "icon": "🌐", "store": "app", "fields": [
        F("forms_provider", "Forms from", "choice",
          [("tally", "Tally (tally.so)"), ("jotform", "Jotform (jotform.com)")]),
        F("tally_api_key", "Tally API key (tally.so ▸ Settings ▸ API keys)", "secret"),
        F("tally_form_customer", "Tally · customer registration form — ID or link (e.g. https://tally.so/r/4aXjl5)"),
        F("tally_form_supplier", "Tally · supplier registration form — ID or link"),
        F("tally_form_feedback", "Tally · customer feedback form — ID or link"),
        F("jotform_api_key", "Jotform API key (jotform.com ▸ Settings ▸ API ▸ Create New Key)", "secret"),
        F("jotform_region", "Jotform account", "choice",
          [("us", "jotform.com"), ("eu", "eu.jotform.com (EU)")]),
        F("jotform_form_customer", "Jotform · customer registration form — ID or link"),
        F("jotform_form_supplier", "Jotform · supplier registration form — ID or link"),
        F("jotform_form_feedback", "Jotform · customer feedback form — ID or link"),
        F("tally_auto_check", "Check for new answers when DayBill opens and every hour", "check"),
        F("receipt_feedback_qr", "Print a small 'Rate your visit' QR on POS receipts", "check"),
    ]},
    {"key": "whatsapp", "title": "WhatsApp", "icon": "🟢", "store": "app", "fields": [
        F("wa_enabled", "Enable WhatsApp (buttons on invoices, quotations, POs, receipts, statements)", "check"),
        F("wa_mode", "Send Using", "choice",
          ["WhatsApp app (free — you press Send)", "WhatsApp Cloud API (automatic)"]),
        F("wa_open_with", "Open Chats In", "choice",
          ["WhatsApp Desktop app", "WhatsApp Web (browser)"]),
        F("wa_country_code", "Default Country Code (e.g. 966)"),
        F("wa_owner_phone", "Owner WhatsApp No. (Day Close summary + evening report)"),
        F("owner_report_enabled", "Send the owner's evening report automatically", "check"),
        F("owner_report_time", "Evening report at time (HH:MM)"),
        F("owner_report_lang", "Evening report language", "choice", [("en", "English"), ("ar", "العربية (Arabic)")]),
        F("wa_owner_template", "Cloud API — Evening report template (approved; header document, {{1}} date, {{2}} sales, {{3}} summary)"),
        F("wa_price_per_msg", "Cloud API — price per message in SAR (for the monthly count)", "number"),
        F("wa_phone_id", "Cloud API — Phone Number ID"),
        F("wa_api_key", "Cloud API — Access Token"),
        F("wa_template_name", "Cloud API — Approved Template (optional)"),
        F("wa_template_lang", "Cloud API — Template Language", "choice", ["en", "ar", "en_US"]),
        F("wa_auto_invoice", "Send invoice automatically when a sales invoice is confirmed", "check"),
        F("wa_auto_statement", "Send receipt + balance automatically after a customer payment", "check"),
        F("wa_msg_invoice", "Invoice Message  ({name} {number} {date} {total} {due} {company})", "long"),
        F("wa_msg_quotation", "Quotation Message  ({name} {number} {total} {valid_until})", "long"),
        F("wa_msg_po", "Purchase Order Message  ({name} {number} {total} {expected})", "long"),
        F("wa_msg_receipt", "Receipt Message  ({name} {number} {amount} {balance})", "long"),
        F("wa_msg_statement", "Statement Message  ({name} {balance} {date})", "long"),
    ]},
    {"key": "ai", "title": "AI", "icon": "✨", "store": "app", "fields": [
        F("ai_enabled", "Use online AI (Claude) when a key is set", "check"),
        F("ai_api_key", "Claude API key (console.anthropic.com ▸ API Keys)", "secret"),
        F("ai_model_fast", "Model for names / spelling", "choice",
          ["claude-haiku-5-5", "claude-sonnet-5-5"]),
        F("ai_model_vision", "Model for reading supplier invoices", "choice",
          ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]),
        F("ai_markup_pct", "New products from invoices: selling price = cost + %", "number"),
        F("ai_auto_translate", "Fill the Arabic name automatically when it is empty", "check"),
        F("ai_dup_check", "Warn when a new product looks like an existing one", "check"),
        F("ai_autofill", "Suggest category / VAT / units from similar products", "check"),
    ]},
    {"key": "system", "title": "System", "icon": "⚙", "store": "app", "fields": [
        F("language", "Language", "choice", ["en", "ar"]),
        F("theme", "Theme (or 🎨 in the top bar)", "choice",
          ["daybill", "green", "blue", "teal", "graphite", "maroon", "sand", "purple", "custom"]),
        F("ui_text_size", "Text size (whole app — bigger letters)", "choice",
          ["100%", "112%", "125%", "140%", "160%"]),
        F("app_subtitle", "Sub name under “DayBill ERP” (sidebar) — empty = Billing & Inventory Management"),
        F("sidebar_collapsed", "Side menu folded to icons (☰ in the top bar opens / folds it)", "check"),
        F("win11_frame", "Windows 11 window frame (white title bar, round corners)", "check"),
        F("ui_compact", "Compact window headers + clear window edges and shadows (v6.7)", "check"),
        F("ui_form_style", "Tally-style entry boxes: example text, blue focus, red note under a wrong box (v6.8)", "check"),
        F("date_format", "Date Format (printed documents)", "choice",
          ["dd/MM/yyyy", "yyyy-MM-dd", "MM/dd/yyyy"]),
        F("currency", "Currency"),
        F("perf_search_limit", "Product Search Limit (rows shown while typing)", "number"),
        F("auto_migrate", "Update the database automatically when the app starts", "check"),
        F("update_url", "Update address (latest.json for 'Check online', optional)"),
    ]},
    {"key": "audit", "title": "Audit", "icon": "📝", "store": "app", "fields": [
        F("audit_user_activity", "Track User Activity", "check"),
        F("audit_price_changes", "Track Price Changes", "check"),
        F("audit_cost_changes", "Track Cost Changes", "check"),
        F("audit_deleted", "Track Deleted Records", "check"),
        F("audit_login", "Track Login History", "check"),
        F("audit_settings", "Track Settings Changes", "check"),
    ]},
    {"key": "notifications", "title": "Alerts", "icon": "🔔", "store": "app", "fields": [
        F("notify_low_stock", "Show low-stock items when the app opens", "check"),
        F("notify_payment_due", "Show customer invoices that are due when the app opens", "check"),
        F("notify_payment_due_days", "Include invoices due within (days)", "number"),
        F("notify_backup", "Show a message after each automatic backup", "check"),
    ]},
    {"key": "payment", "title": "Payment", "icon": "💳", "store": "app", "fields": [
        F("pay_method_cash", "Accept Cash", "check"),
        F("pay_method_bank", "Accept Bank Transfer", "check"),
        F("pay_method_credit_card", "Accept Credit Card", "check"),
        F("pay_method_debit_card", "Accept Debit Card", "check"),
        F("pay_method_cheque", "Accept Cheque", "check"),
        F("pay_default_terms", "Default Payment Terms", "choice",
          ["Due on Receipt", "Net 7", "Net 15", "Net 30", "Net 45", "Net 60"]),
        F("pay_default_credit_limit", "Default Customer Credit Limit", "number"),
        F("pay_auto_receipt", "Print a receipt automatically after saving a payment", "check"),
    ]},
    {"key": "backup", "title": "Backup", "icon": "💾", "store": "app", "fields": [
        F("backup_path", "Backup Folder (on the SQL Server machine)"),
        F("backup_on_exit", "Backup automatically when closing the app", "check"),
        F("backup_every_hours", "Automatic backup every (hours, 0 = off)", "choice",
          ["0", "2", "4", "8", "12", "24"]),
        F("backup_time", "Daily backup at time (HH:MM, empty = off)"),
        F("backup_keep", "Keep last N backup files", "choice",
          ["10", "30", "60", "120"]),
        # v6.4 ☁ cloud copy (Google Drive / OneDrive / Dropbox folder on this PC)
        F("cloud_backup_enabled", "☁ Copy a backup to the cloud folder every night (Google Drive / OneDrive / Dropbox)", "check"),
        F("cloud_backup_folder", "Cloud folder (empty = found by itself)"),
        F("cloud_backup_time", "Cloud backup at time (HH:MM)"),
        F("cloud_backup_keep", "Keep last N cloud copies", "choice", ["7", "14", "30", "60"]),
    ]},
    {"key": "financial_year", "title": "Financial Year", "icon": "📅", "store": "app", "fields": [
        F("fy_lock_previous", "Lock Previous Financial Years", "check"),
        F("fy_warn_before_close", "Ask Before Closing A Year", "check"),
    ]},
]


# Every option on these pages is used by the app. When you add a field,
# wire it into the module that should obey it (tests/settings_wiring
# checks that each key is read somewhere).
WIRED_KEYS = {f["key"] for _s in SECTIONS for f in _s["fields"]}


def _is_active(sec, f):
    return True


def _opt_pairs(f):
    """[(stored value, shown text)] for a choice field."""
    opts = f["options"]() if callable(f["options"]) else f["options"]
    out = []
    for o in opts or []:
        if isinstance(o, (tuple, list)):
            out.append((str(o[0]), str(o[1])))
        else:
            out.append((str(o), str(o)))
    return out


GROUPS = [          # the order a shop owner looks for things
    ("🏢 Company",               ["company", "system"]),
    ("🧾 Sales & POS",           ["sales", "pos", "payment"]),
    ("🛒 Purchase",              ["purchase"]),
    ("📦 Products & Barcodes",   ["inventory", "barcode", "plu"]),
    ("💰 Tax (VAT)",             ["tax"]),
    ("👥 Customers & Suppliers", ["customer", "supplier", "online_forms"]),
    ("🖨 Printing",              ["print"]),
    ("📒 Accounts & Year",       ["accounting", "financial_year"]),
    ("👔 HR & Payroll",          ["hr"]),
    ("🔔 Alerts & WhatsApp",     ["notifications", "whatsapp"]),
    ("🔐 Security & Backup",     ["security", "audit", "backup"]),
    ("✨ AI",                    ["ai"]),
]

DESCRIPTIONS = {
    "company": "Your business identity used on invoices, receipts and ZATCA QR.",
    "tax": "Control VAT mode (inclusive/exclusive) for sales and purchase.",
    "sales": "Invoice numbering and sales workflow options.",
    "purchase": "Purchase numbering, cost basis and return options.",
    "pos": "Touchscreen point-of-sale behaviour and receipt text.",
    "barcode": "Barcode structure, label size and scanner behaviour.",
    "plu": "Weighing-scale (PLU) barcodes and the PLU file for the scale.",
    "inventory": "Negative stock, the low-stock alert level and expiry warnings.",
    "hr": "GOSI rates (change them when GOSI announces new ones) and payroll deductions.",
    "accounting": "Journal posting behaviour. Default ledger accounts are set in Accounts ▸ Default Accounts.",
    "customer": "Customer code numbering, credit controls and loyalty points.",
    "supplier": "Supplier code numbering and controls.",
    "online_forms": "Customers and suppliers fill a Tally or Jotform web form on their phone; the answers wait "
                    "in Customers ▸ 🌐 Online forms until you review and add them.",
    "security": "Password policy. Users and rights are in Users & Rights.",
    "backup": "Automatic backup schedule and location.",
    "print": "Which printer each kind of document uses, and whether to ask first. "
             "Per-document printers: Printer Management.",
    "whatsapp": "Send invoices, quotations, purchase orders, receipts and statements on "
                "WhatsApp — free through the WhatsApp app, or automatic with the Cloud API.",
    "system": "Language, theme, currency, date format and start-up behaviour.",
    "notifications": "Messages shown when the app opens and after automatic backups.",
    "payment": "Which payment methods are offered, terms and receipts.",
    "financial_year": "Financial years, closing and locking.",
    "audit": "What user activity to track and log.",
    "ai": "Arabic names, supplier invoices, spelling. Sends only product names / the chosen invoice.",
}


class SettingsView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self.vars = {}            # section_key -> {field_key: tk var}
        self._company = {}
        self._current = None

        for w in parent.winfo_children():
            w.destroy()

        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)

        self._load_company()
        self._build(C)
        # open first section
        self._select_section(SECTIONS[0]["key"])

    # ── data ──────────────────────────────────────────────────
    def _load_company(self):
        try:
            self._company = db.fetchone(
                "SELECT * FROM company WHERE company_id=1") or {}
        except Exception:
            self._company = {}

    def _val(self, section, field):
        """Current stored value for a field."""
        if section["store"] == "company":
            if field["key"] in self.MIRROR_KEYS:
                return cfg.get(field["key"], self._company.get(field["key"], ""))
            return self._company.get(field["key"], "")
        if field["type"] == "check":
            return cfg.flag(field["key"], cfg.DEFAULT_SETTINGS.get(field["key"], False))
        return cfg.get(field["key"], cfg.DEFAULT_SETTINGS.get(field["key"], ""))

    # ── UI ────────────────────────────────────────────────────
    def _build(self, C):
        # header
        head = tk.Frame(self.frame, bg=C["content_bg"])
        head.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(head, text="⚙  Application Settings",
                 font=("Segoe UI", 18, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(side="left")

        # search
        self.search_var = tk.StringVar()
        sb = tk.Entry(head, textvariable=self.search_var, font=("Segoe UI", 10),
                      width=28, relief="solid", bd=1)
        sb.pack(side="right", ipady=4)
        tk.Label(head, text="🔍", bg=C["content_bg"]).pack(side="right", padx=4)
        self.search_var.trace("w", lambda *a: self._filter_tree())

        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=16, pady=6)

        # left tree
        leftwrap = tk.Frame(body, bg=C["card_bg"], width=240,
                            highlightbackground=C["border"], highlightthickness=1)
        leftwrap.pack(side="left", fill="y")
        leftwrap.pack_propagate(False)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Set.Treeview", rowheight=28, font=("Segoe UI", 10),
                        background=C["card_bg"], fieldbackground=C["card_bg"])
        self.tree = ttk.Treeview(leftwrap, show="tree", style="Set.Treeview",
                                 selectmode="browse")
        tsb = ttk.Scrollbar(leftwrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._fill_tree()

        # right details
        self.detail = tk.Frame(body, bg=C["card_bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        self.detail.pack(side="left", fill="both", expand=True, padx=(12, 0))

        # bottom buttons
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=16, pady=(4, 14))

        def mkbtn(txt, cmd, primary=False):
            tk.Button(bar, text=txt, font=("Segoe UI", 10,
                      "bold" if primary else "normal"),
                      bg=C["primary"] if primary else C["card_bg"],
                      fg="white" if primary else C["text_primary"],
                      relief="flat", padx=16, pady=8, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=cmd).pack(side="left", padx=(0, 8))

        mkbtn("💾  Save", self._save_current, primary=True)
        mkbtn("✔  Save & Apply", self._save_apply)
        mkbtn("↺  Reset Section", self._reset_section)
        mkbtn("✕  Cancel", self._cancel_edits)
        mkbtn("⬇  Backup Settings", self._backup)
        mkbtn("⬆  Restore Settings", self._restore)

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        flt = (self.search_var.get() if hasattr(self, "search_var") else "").lower()

        def matches(s):
            fields = s["fields"]
            if not fields and s["key"] != "financial_year":
                return False
            if not flt:
                return True
            return flt in s["title"].lower() or \
                any(flt in f["label"].lower() for f in fields)

        for gname, keys in GROUPS:
            secs = [self._section(k) for k in keys if self._section(k)]
            secs = [s for s in secs if matches(s)]
            if not secs:
                continue
            gid = "grp::" + gname
            # one group open at a time (the one being edited) — every page
            # fits on a small screen; a search opens all matches
            cur = getattr(self, "_current", None) or "company"
            self.tree.insert("", "end", iid=gid, text=gname,
                             open=bool(flt) or cur in keys, tags=("group",))
            for s in secs:
                self.tree.insert(gid, "end", iid=s["key"],
                                 text=f"   {s['icon']}  {s['title']}")
        self.tree.tag_configure("group", font=("Segoe UI", 9, "bold"))

    def _filter_tree(self):
        self._fill_tree()

    def _on_tree_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        if sel[0].startswith("grp::"):
            kids = self.tree.get_children(sel[0])     # a group → its first page
            if kids:
                self.tree.selection_set(kids[0]); self.tree.focus(kids[0])
            return
        self._render_section(sel[0])
        self._open_only(sel[0])

    def _open_only(self, key):
        """Accordion: only the group of the page on screen stays open."""
        if (self.search_var.get() if hasattr(self, "search_var") else ""):
            return
        for gname, keys in GROUPS:
            gid = "grp::" + gname
            try:
                if self.tree.exists(gid):
                    self.tree.item(gid, open=key in keys)
            except Exception:
                pass
        try:
            self.tree.see(key)
        except Exception:
            pass

    def _select_section(self, key):
        try:
            self.tree.selection_set(key)
            self.tree.focus(key)
        except Exception:
            pass
        self._render_section(key)
        self._open_only(key)

    def _section(self, key):
        return next((s for s in SECTIONS if s["key"] == key), None)

    def _render_section(self, key):
        C = cfg.theme()
        sec = self._section(key)
        if not sec:
            return
        self._current = key
        for w in self.detail.winfo_children():
            w.destroy()

        # header band
        head = tk.Frame(self.detail, bg=C["primary_light"])
        head.pack(fill="x")
        tk.Label(head, text=f"{sec['icon']}  {sec['title']}",
                 font=("Segoe UI", 15, "bold"), bg=C["primary_light"],
                 fg=C["primary"]).pack(anchor="w", padx=20, pady=(14, 2))
        desc = DESCRIPTIONS.get(key, "")
        if desc:
            tk.Label(head, text=desc, font=("Segoe UI", 9),
                     bg=C["primary_light"], fg=C["text_secondary"]).pack(
                         anchor="w", padx=20, pady=(0, 12))

        # scrollable field area
        canvas = tk.Canvas(self.detail, bg=C["card_bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self.detail, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=(20, 0), pady=10)
        holder = tk.Frame(canvas, bg=C["card_bg"])
        wid = canvas.create_window((0, 0), window=holder, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        holder.bind("<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        holder.columnconfigure(0, weight=1, uniform="col")
        holder.columnconfigure(1, weight=1, uniform="col")

        self.vars[key] = {}
        col = 0
        rowi = 0
        for f in sec["fields"]:
            if f["type"] in ("long", "check"):
                # full-width fields take their own row
                if col == 1:
                    rowi += 1
                    col = 0
                self._render_field(holder, C, sec, f, rowi, 0, span=2)
                rowi += 1
                col = 0
            else:
                self._render_field(holder, C, sec, f, rowi, col, span=1)
                col += 1
                if col == 2:
                    col = 0
                    rowi += 1

        if key == "financial_year":
            rowi += 1
            self._render_fy_panel(holder, C, rowi)
        if key == "tax":
            self._hook_tax_profile()
        if key == "plu":
            rowi += 1
            self._render_plu_tools(holder, C, rowi)
        if key == "barcode":
            rowi += 1
            self._render_barcode_tools(holder, C, rowi)
        if key == "ai":
            rowi += 1
            box = tk.Frame(holder, bg=C["card_bg"])
            box.grid(row=rowi, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 4))
            self._ai_test_var = tk.StringVar(value="")
            tk.Button(box, text="✨  Save & test the AI key", font=("Segoe UI", 9, "bold"),
                      bg=C["primary"], fg="white", relief="flat", padx=14, pady=6,
                      cursor="hand2", command=self._ai_test).pack(side="left")
            tk.Label(box, textvariable=self._ai_test_var, font=("Segoe UI", 9),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=10)
        if key == "notifications":
            rowi += 1
            tk.Button(holder, text="🔔  Show the alerts now", font=("Segoe UI", 9, "bold"),
                      bg=C["primary"], fg="white", relief="flat", padx=14, pady=6,
                      cursor="hand2", command=self._show_alerts_now).grid(
                          row=rowi, column=0, sticky="w", padx=8, pady=(10, 4))
        if key == "backup":
            rowi += 1
            self._render_cloud_tools(holder, C, rowi)
        if key == "whatsapp":
            rowi += 1
            box = tk.Frame(holder, bg=C["card_bg"])
            box.grid(row=rowi, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 4))
            self._owner_var = tk.StringVar(value="")
            tk.Button(box, text="📲  Save & send the evening report now", font=("Segoe UI", 9, "bold"),
                      bg=C["success"], fg="white", relief="flat", padx=14, pady=6,
                      cursor="hand2", command=self._owner_report_now).pack(side="left")
            tk.Label(box, textvariable=self._owner_var, font=("Segoe UI", 9), wraplength=520, justify="left",
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left", padx=10)
            # v6.5: Cloud API messages cost money since 1 Oct 2026 — show how many
            rowi += 1
            try:
                from modules import whatsapp as _wa
                self._wa_usage = _wa.usage_text()
            except Exception as e:
                self._wa_usage = "Cloud API message count: %s" % str(e)[:80]
            tk.Label(holder, text="📊  " + self._wa_usage, font=("Segoe UI", 9), bg="#F0FDF4", fg="#166534",
                     justify="left", anchor="w", wraplength=760, padx=10, pady=6).grid(
                         row=rowi, column=0, columnspan=2, sticky="we", padx=8, pady=(6, 4))

    def _store_section(self, key):
        """Save the fields of one section now (used by its 'test' buttons)."""
        try:
            for fkey, (var, _t) in self.vars.get(key, {}).items():
                cfg.set(fkey, var.get() if _t != "number" else (var.get() or 0))
            cfg.save_settings()
        except Exception:
            pass

    def _owner_report_now(self):
        self._store_section("whatsapp")
        try:
            from modules import owner_report as OR
            ok, msg = OR.send(interactive=True)
        except Exception as e:
            ok, msg = False, str(e)[:200]
        self._owner_var.set(("✅ " if ok else "⚠ ") + msg)
        return ok, msg

    def _render_cloud_tools(self, holder, C, rowi):
        from modules import cloud_backup as CB
        box = tk.Frame(holder, bg=C["card_bg"])
        box.grid(row=rowi, column=0, columnspan=2, sticky="we", padx=8, pady=(10, 4))
        found = CB.folders()
        st = CB.status()
        lines = ["Cloud folders on this PC: " + (", ".join("%s (%s)" % (n, p) for n, p in found)
                                                 if found else "none found — install Google Drive or "
                                                 "OneDrive and sign in, or type a folder above")]
        if st.get("last_ok"):
            lines.append("Last cloud copy: %s  ·  %s" % (st["last_ok"], st.get("last_file") or ""))
        if st.get("last_error"):
            lines.append("Last problem: %s" % st["last_error"])
        self._cloud_var = tk.StringVar(value="\n".join(lines))
        row = tk.Frame(box, bg=C["card_bg"])
        row.pack(anchor="w")

        def _browse():
            d = filedialog.askdirectory(title="Cloud folder (Google Drive / OneDrive / Dropbox)")
            if d:
                try:
                    self.vars["backup"]["cloud_backup_folder"][0].set(d)
                except Exception:
                    pass
        tk.Button(row, text="📁  Choose folder…", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                  relief="flat", padx=12, pady=6, highlightthickness=1, highlightbackground=C["border"],
                  cursor="hand2", command=_browse).pack(side="left")
        tk.Button(row, text="☁  Save & back up to the cloud now", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._cloud_now).pack(side="left", padx=8)
        tk.Label(box, textvariable=self._cloud_var, font=("Segoe UI", 9), wraplength=640, justify="left",
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(6, 0))

    def _cloud_now(self):
        self._store_section("backup")
        from modules import cloud_backup as CB
        self._cloud_var.set("Making the backup…")
        try:
            self.detail.update_idletasks()
        except Exception:
            pass

        box = {}

        def done(ok, msg):                  # runs in the copy thread: only store it
            box["res"] = (ok, msg)

        def poll():
            if "res" in box:
                ok_, msg_ = box["res"]
                try:
                    self._cloud_var.set(("✅ " if ok_ else "⚠ ") + msg_)
                except Exception:
                    pass
                return
            try:
                self.detail.after(300, poll)
            except Exception:
                pass
        ok, msg = CB.run(background=True, on_done=done)
        self._cloud_var.set(("" if ok else "⚠ ") + msg)
        if ok:
            poll()
        return ok, msg

    def _ai_test(self):
        try:
            for fkey, (var, _t) in self.vars.get("ai", {}).items():
                cfg.set(fkey, var.get() if _t != "number" else (var.get() or 0))
            cfg.save_settings()
        except Exception:
            pass
        self._ai_test_var.set("Testing…")
        from modules import ai_client
        from ui.product_ai_ui import run_bg
        run_bg(self.detail, ai_client.test_key,
               lambda r: self._ai_test_var.set(("✅ " if r[0] else "⚠ ") + r[1]),
               lambda e: self._ai_test_var.set("⚠ " + str(e)))

    def _hook_tax_profile(self):
        """Choosing a country profile fills in its VAT rate."""
        try:
            pvar = self.vars["tax"]["country_tax_profile"][0]
            rvar = self.vars["tax"]["tax_sales_rate"][0]
        except Exception:
            return

        def _on(*_):
            rate = cfg.TAX_PROFILES.get(pvar.get(), None)
            if rate is None and "no vat" in pvar.get().lower():
                rate = 0
            if rate is not None:
                rvar.set(str(rate))
        pvar.trace_add("write", _on)

    def _render_plu_tools(self, holder, C, rowi):
        row = tk.Frame(holder, bg=C["card_bg"])
        row.grid(row=rowi, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 4))

        def _browse():
            d = filedialog.askdirectory(title="Folder for the scale PLU file")
            if d:
                try:
                    self.vars["plu"]["plu_export_path"][0].set(d)
                except Exception:
                    pass

        def _export_now():
            try:
                from ui import plu_manager as PM
                ok, msg = PM.auto_export(force=True,
                                         folder=self.vars["plu"]["plu_export_path"][0].get(),
                                         fmt=self.vars["plu"]["plu_barcode_format"][0].get())
            except Exception as e:
                ok, msg = False, str(e)
            (messagebox.showinfo if ok else messagebox.showwarning)("PLU export", msg)
        for txt, cmd in (("📁  Choose folder…", _browse), ("⬆  Export PLU file now", _export_now)):
            tk.Button(row, text=txt, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                      fg=C["text_primary"], relief="flat", padx=12, pady=5, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=cmd).pack(side="left", padx=(0, 8))

    def _render_barcode_tools(self, holder, C, rowi):
        """Every product and every unit gets its own barcode — in one click,
        plus a shortcut to the label printer."""
        box = tk.Frame(holder, bg=C["card_bg"])
        box.grid(row=rowi, column=0, columnspan=2, sticky="ew", padx=8, pady=(12, 4))
        self._bc_msg = tk.StringVar()
        try:
            from modules import barcode_resolver as BR
            mp, mu = BR.missing_count()
            self._bc_msg.set("%d product(s) and %d unit(s) have no barcode yet." % (mp, mu)
                             if (mp or mu) else "✔ Every product and every unit has its own barcode.")
        except Exception:
            mp = mu = 0
        tk.Label(box, text="BARCODES FOR EVERY PRODUCT + UNIT", font=("Segoe UI", 8, "bold"),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        tk.Label(box, textvariable=self._bc_msg, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(anchor="w", pady=(2, 6))
        row = tk.Frame(box, bg=C["card_bg"]); row.pack(anchor="w")
        self._bc_make_btn = tk.Button(row, text="⚡  Make the missing barcodes now",
                                      font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                                      relief="flat", padx=14, pady=6, cursor="hand2",
                                      command=self._make_all_barcodes)
        self._bc_make_btn.pack(side="left")
        if not (mp or mu):
            self._bc_make_btn.configure(state="disabled", bg=C["border"])
        tk.Button(row, text="🖨  Print barcode labels", font=("Segoe UI", 9, "bold"),
                  bg=C["content_bg"], fg=C["text_primary"], relief="flat", padx=12, pady=5,
                  cursor="hand2", highlightbackground=C["border"], highlightthickness=1,
                  command=self._open_label_print).pack(side="left", padx=8)
        tk.Label(box, text="New codes are 6-digit numbers given in order (100001, 100002…) and never repeat "
                           "(change Barcode Length above for EAN-13). The product and "
                           "its piece (PCs) share one code; Box, Carton… each get their own. "
                           "Scanning any of them in POS, Sales, Purchase or Stock finds the "
                           "product WITH that unit.", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"], wraplength=640, justify="left").pack(anchor="w", pady=(6, 0))

    def _make_all_barcodes(self):
        from modules import barcode_resolver as BR
        mp, mu = BR.missing_count()
        if not (mp or mu):
            return 0
        # use the rules on screen (prefix / length / check digit), even unsaved
        try:
            for fkey, (var, _t) in self.vars.get("barcode", {}).items():
                if fkey in ("barcode_prefix", "barcode_length", "barcode_check_digit"):
                    cfg.set(fkey, var.get())
        except Exception:
            pass
        if not messagebox.askyesno("Barcodes", "Create barcodes for %d product(s) and %d unit(s) "
                                   "that have none?\n\nExisting barcodes are never changed."
                                   % (mp, mu)):
            return 0
        made = BR.ensure_barcodes()
        self._bc_msg.set("✔ %d barcode(s) created — every product and unit has its own now."
                         % len(made))
        try:
            self._bc_make_btn.configure(state="disabled", bg=cfg.theme()["border"])
            from modules import audit
            audit.log("edit", "products", None, "%d barcodes created (Settings)" % len(made))
        except Exception:
            pass
        return len(made)

    def _open_label_print(self):
        try:
            from ui.label_printer import open_window
            open_window(self.frame)
        except Exception as e:
            messagebox.showerror("Labels", str(e)[:200])

    def _show_alerts_now(self):
        try:
            from ui import alerts
            n = alerts.show_startup_alerts(self.frame.winfo_toplevel(), force=True)
            if not n:
                messagebox.showinfo("Alerts", "Nothing needs attention right now.")
        except Exception as e:
            messagebox.showerror("Alerts", str(e)[:200])

    def _render_fy_panel(self, holder, C, rowi):
        """List of financial years + Create/Close actions (real backend,
        not just settings toggles)."""
        wrap = tk.Frame(holder, bg=C["card_bg"])
        wrap.grid(row=rowi, column=0, columnspan=2, sticky="ew", padx=8, pady=(12, 4))
        tk.Label(wrap, text="FINANCIAL YEARS", font=("Segoe UI", 8, "bold"),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")

        try:
            from modules import financial_year as fy
            ready = fy.tables_ready()
        except Exception:
            ready = False
            fy = None

        if not ready:
            tk.Label(wrap, text="Run database/financial_year_patch.sql to enable "
                               "financial year management.",
                     font=("Segoe UI", 9), bg="#FFF7E6", fg="#9A6700",
                     wraplength=520, justify="left").pack(anchor="w", pady=6, ipady=6,
                                                          fill="x")
            return

        list_frame = tk.Frame(wrap, bg=C["card_bg"], highlightbackground=C["border"],
                              highlightthickness=1)
        list_frame.pack(fill="x", pady=(6, 8))

        years = fy.list_years()
        if not years:
            tk.Label(list_frame, text="No financial years yet.", font=("Segoe UI", 9),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(padx=10, pady=10)
        for y in years:
            row = tk.Frame(list_frame, bg=C["card_bg"])
            row.pack(fill="x", padx=10, pady=6)
            status = "🔒 Closed" if y.get("is_closed") else "🟢 Open"
            tk.Label(row, text=f"{y['label']}   ({y['start_date']} → {y['end_date']})",
                     font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                     fg=C["text_primary"]).pack(side="left")
            tk.Label(row, text=status, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=(C["text_secondary"] if y.get("is_closed") else C["accent"])
                     ).pack(side="left", padx=(10, 0))
            if not y.get("is_closed"):
                tk.Button(row, text="Close Year", font=("Segoe UI", 8, "bold"),
                          bg="#FEF2F2", fg=C["danger"], relief="flat", padx=10,
                          pady=4, cursor="hand2",
                          command=lambda fid=y["fy_id"], lbl=y["label"]:
                          self._close_fy(fid, lbl)).pack(side="right")
            else:
                tk.Button(row, text="Reopen", font=("Segoe UI", 8, "bold"),
                          bg=C["content_bg"], fg=C["text_primary"], relief="flat",
                          padx=10, pady=4, cursor="hand2",
                          command=lambda fid=y["fy_id"]: self._reopen_fy(fid)
                          ).pack(side="right")

        tk.Button(wrap, text="➕  Create New Financial Year", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._create_fy).pack(anchor="w")

    def _create_fy(self):
        from tkinter import simpledialog
        start = simpledialog.askstring("New Financial Year",
                                       "Start date (YYYY-MM-DD):",
                                       initialvalue=f"{datetime.now().year}-01-01")
        if not start:
            return
        end = simpledialog.askstring("New Financial Year",
                                     "End date (YYYY-MM-DD):",
                                     initialvalue=f"{datetime.now().year}-12-31")
        if not end:
            return
        from modules import financial_year as fy
        ok, msg = fy.create_year(start, end)
        (messagebox.showinfo if ok else messagebox.showerror)("Financial Year", msg)
        if ok:
            self._render_section("financial_year")

    def _close_fy(self, fy_id, label):
        # v6.0: closing posts the year-end closing entry (profit → Retained
        # Earnings) and then locks the year
        from modules import year_end as YE
        try:
            p = YE.preview(fy_id)
            probs = YE.checks(fy_id)
        except Exception:
            p, probs = {"profit": 0.0}, []
        txt = (f"Close and lock '{label}'?\n\n{'Profit' if p['profit'] >= 0 else 'Loss'} of the year: "
               f"{abs(p['profit']):,.2f} SAR — it moves to Retained Earnings, income and expense "
               f"accounts start the new year at zero.\n\nNo new transactions can be posted into "
               f"this year afterwards (it can be reopened).")
        if probs:
            txt += "\n\n⚠ Not finished yet:\n• " + "\n• ".join(probs) + "\n\nClose anyway?"
        if (cfg.flag("fy_warn_before_close", True) or probs) and not messagebox.askyesno(
                "Close Financial Year", txt):
            return
        try:
            ok, msg = YE.close(fy_id, force=True)
        except Exception as e:
            ok, msg = False, "Nothing was changed: %s" % str(e)[:200]
        (messagebox.showinfo if ok else messagebox.showerror)("Financial Year", msg)
        if ok:
            self._render_section("financial_year")

    def _reopen_fy(self, fy_id):
        from modules import year_end as YE
        try:
            ok, msg = YE.reopen(fy_id)
        except Exception as e:
            ok, msg = False, str(e)[:200]
        (messagebox.showinfo if ok else messagebox.showerror)("Financial Year", msg)
        if ok:
            self._render_section("financial_year")

    def _toggle(self, parent, C, var, label):
        """A modern on/off switch (replaces the plain checkbox)."""
        row = tk.Frame(parent, bg=C["content_bg"],
                       highlightbackground=C["border"], highlightthickness=1)
        row.pack(fill="x")
        tk.Label(row, text=label, bg=C["content_bg"], fg=C["text_primary"],
                 font=("Segoe UI", 10), anchor="w").pack(side="left", padx=10, pady=8)
        sw = tk.Canvas(row, width=48, height=24, bg=C["content_bg"],
                       highlightthickness=0, cursor="hand2")
        sw.pack(side="right", padx=10)

        def draw():
            sw.delete("all")
            on = bool(var.get())
            track = C["accent"] if on else "#C9C9D6"
            sw.create_oval(2, 2, 22, 22, fill=track, outline=track)
            sw.create_oval(26, 2, 46, 22, fill=track, outline=track)
            sw.create_rectangle(12, 2, 36, 22, fill=track, outline=track)
            kx = 36 if on else 12
            sw.create_oval(kx - 10, 2, kx + 10, 22, fill="white", outline=track)

        def toggle(e=None):
            var.set(not bool(var.get()))
            draw()
        sw.bind("<Button-1>", toggle)
        row.bind("<Button-1>", toggle)
        draw()
        return row

    def _render_field(self, parent, C, sec, f, rowi, coli, span=1):
        cell = tk.Frame(parent, bg=C["card_bg"])
        cell.grid(row=rowi, column=coli, columnspan=span, sticky="ew",
                  padx=8, pady=7)
        cur = self._val(sec, f)

        if f["type"] == "check":
            var = tk.BooleanVar(value=bool(cur))
            self._toggle(cell, C, var, f["label"])
        else:
            tk.Label(cell, text=f["label"].upper(), font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
            width = _field_width(f)
            if f["type"] == "choice":
                pairs = _opt_pairs(f)
                shown = [lbl for _, lbl in pairs]
                cur_s = "" if cur is None else str(cur)
                if pairs and cur_s not in [v for v, _ in pairs]:
                    if cur_s and cur_s not in shown:
                        pairs.append((cur_s, cur_s)); shown.append(cur_s)
                    elif not cur_s:
                        cur_s = pairs[0][0]
                lbl_of = dict(pairs)
                var = _ChoiceVar(tk.StringVar(value=lbl_of.get(cur_s, cur_s)), pairs)
                cbx = ttk.Combobox(cell, textvariable=var.shown, values=shown,
                                   state="readonly", font=("Segoe UI", 10),
                                   width=max(10, min(max((len(x) for x in shown), default=8) + 3, 60)))
                cbx.pack(anchor="w", ipady=3, pady=(2, 0))
            elif f["type"] == "long":
                txt = tk.Text(cell, height=3, font=("Segoe UI", 10), wrap="word",
                              relief="solid", bd=1, bg="white")
                txt.pack(fill="x", pady=(2, 0))
                val = "" if cur is None else str(cur)
                if not val and f["key"].startswith("wa_msg_"):
                    try:
                        from modules import whatsapp as _wa
                        kind = {"wa_msg_invoice": "sales", "wa_msg_quotation": "quotation",
                                "wa_msg_po": "purchase_order", "wa_msg_receipt": "receipt",
                                "wa_msg_statement": "statement"}[f["key"]]
                        val = _wa.DEFAULT_MESSAGES[kind]
                    except Exception:
                        pass
                txt.insert("1.0", val)
                var = _TextVar(txt)
            else:
                var = tk.StringVar(value="" if cur is None else str(cur))
                ent = tk.Entry(cell, textvariable=var, font=("Segoe UI", 10),
                               relief="solid", bd=1, bg="white",
                               show="•" if f["type"] == "secret" else "",
                               justify="right" if f["type"] == "number" else "left")
                if width:
                    ent.configure(width=width)
                    ent.pack(anchor="w", ipady=5, pady=(2, 0))
                else:
                    ent.pack(fill="x", ipady=5, pady=(2, 0))

        self.vars[key_of(sec)][f["key"]] = (var, f["type"])

    # ── save ──────────────────────────────────────────────────
    def _collect(self, key):
        out = {}
        for fkey, (var, ftype) in self.vars.get(key, {}).items():
            v = var.get()
            if ftype == "number":
                try:
                    v = float(v) if "." in str(v) else int(v)
                except Exception:
                    v = 0
            out[fkey] = v
        return out

    # Sections where a mistake is costly (accounting, tax, FY) — confirm first.
    CRITICAL_SECTIONS = {"accounting", "tax", "financial_year"}
    # fields that exist on both the Company page and the System page
    MIRROR_KEYS = ("language", "date_format", "currency", "time_format", "fiscal_year_start")

    def _save_current(self, apply_changes=False):
        if not self._current:
            return
        sec = self._section(self._current)

        if self._current in self.CRITICAL_SECTIONS:
            if not messagebox.askyesno(
                    "Confirm changes",
                    f"You're changing {sec['title']} settings. These affect how "
                    f"every future transaction is calculated and posted.\n\n"
                    f"Save these changes?"):
                return

        data = self._collect(self._current)
        vat_note = ""
        if sec["store"] == "company" and "vat_registration_no" in data:
            vat_note = self._clean_company_vat(data)

        if sec["store"] == "company":
            try:
                sets = ", ".join(f"{k}=?" for k in data.keys())
                vals = list(data.values())
                exists = db.fetchone("SELECT company_id FROM company WHERE company_id=1")
                if exists:
                    db.execute(f"UPDATE company SET {sets} WHERE company_id=1", vals)
                else:
                    # company_id is an IDENTITY column, but the rest of the
                    # app hardcodes company_id=1 everywhere — so the very
                    # first row must explicitly be 1, which requires
                    # toggling IDENTITY_INSERT for this one statement.
                    cols = ", ".join(data.keys())
                    qs = ", ".join("?" for _ in data)
                    try:
                        db.execute("SET IDENTITY_INSERT company ON")
                        db.execute(f"INSERT INTO company (company_id, {cols}) "
                                   f"VALUES (1, {qs})", vals)
                    finally:
                        db.execute("SET IDENTITY_INSERT company OFF")
                self._company.update(data)
                # These keys are also on the System page and are READ by the
                # app from app-settings — mirror them so a change here works.
                mirrored = False
                for k in self.MIRROR_KEYS:
                    if k in data:
                        cfg.set(k, data[k]); mirrored = True
                if mirrored:
                    try:
                        cfg.save_settings()
                    except Exception:
                        pass
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
                return
        else:
            for k, v in data.items():
                cfg.set(k, v)
            if "pos_paper_size" in data and str(cfg.get("paper_width", "80")) in ("58", "80"):
                # keep Print & Invoice ▸ Paper size in step with this one
                cfg.set("paper_width", "58" if str(data["pos_paper_size"]).startswith("58") else "80")
            if self._current == "system":
                cfg.set("theme_user_chosen", True)
                # keep the Company page (company table) in step
                both = {k: v for k, v in data.items() if k in self.MIRROR_KEYS}
                if both:
                    try:
                        db.execute("UPDATE company SET " + ", ".join(
                            f"{k}=?" for k in both) + " WHERE company_id=1",
                            list(both.values()))
                        self._company.update(both)
                    except Exception:
                        pass
            try:
                cfg.save_settings()
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
                return

        try:
            from modules import audit as _audit
            _audit.log("update", "settings", self._current,
                       ", ".join(f"{k}={v}" for k, v in list(data.items())[:25]))
        except Exception:
            pass

        if apply_changes and self._current == "system":
            # Theme / language now apply live across the whole app.
            try:
                from ui import main_window as mw
                if getattr(mw, "APP", None):
                    mw.APP.apply_live()
                    return
            except Exception:
                pass
            messagebox.showinfo("Saved", "Settings saved and applied.")
        elif vat_note:
            messagebox.showwarning(
                "Saved — but no QR code yet",
                f"{sec['title']} settings saved.\n\n{vat_note}\n\nUntil the VAT "
                "number is right, sales and POS invoices print WITHOUT the "
                "ZATCA QR code.")
        else:
            messagebox.showinfo("Saved", f"{sec['title']} settings saved.")

    def _clean_company_vat(self, data):
        """Saudi VAT number: save it as 15 plain digits (Arabic digits and
        spaces / dashes typed between groups are fixed). Returns a note
        when it still can't be used for the ZATCA QR code ('' = fine)."""
        try:
            from modules.zatca.qr_generator import (clean_vat_number,
                                                    valid_vat_number, vat_problem)
        except Exception:
            return ""
        raw = str(data.get("vat_registration_no") or "")
        if valid_vat_number(raw):
            fixed = clean_vat_number(raw)
            if fixed != raw:
                data["vat_registration_no"] = fixed
                try:
                    self.vars["company"]["vat_registration_no"][0].set(fixed)
                except Exception:
                    pass
            return ""
        country = str(data.get("country") or self._company.get("country") or "").strip()
        if country not in ("", "Saudi Arabia"):
            return ""                       # the ZATCA QR is for Saudi shops only
        return vat_problem(raw)

    def _save_apply(self):
        self._save_current(apply_changes=True)

    def _reset_section(self):
        if self._current and messagebox.askyesno(
                "Reset", "Reload this section from the last saved values?"):
            if self._section(self._current)["store"] == "company":
                self._load_company()
            self._render_section(self._current)

    def _cancel_edits(self):
        """Discard unsaved edits in the current section immediately (no
        confirmation) — a quick escape hatch, unlike Reset which asks."""
        if self._current:
            if self._section(self._current)["store"] == "company":
                self._load_company()
            self._render_section(self._current)

    # ── backup / restore of the settings file ─────────────────
    def _backup(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Settings", "*.json")],
            initialfile=f"daybill_settings_{datetime.now():%Y%m%d}.json")
        if not path:
            return
        try:
            shutil.copyfile(cfg.SETTINGS_FILE, path)
            messagebox.showinfo("Backup", f"Settings backed up to:\n{path}")
        except Exception as e:
            messagebox.showerror("Backup Error", str(e))

    def _restore(self):
        path = filedialog.askopenfilename(filetypes=[("Settings", "*.json")])
        if not path:
            return
        if not messagebox.askyesno("Restore",
                "Replace current settings with the selected file? "
                "Restart afterwards."):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg.save_settings(data)
            messagebox.showinfo("Restore", "Settings restored. Please restart the app.")
        except Exception as e:
            messagebox.showerror("Restore Error", str(e))


def key_of(sec):
    return sec["key"]


_SHORT_HINTS = ("prefix", "code", "length", "port", "days", "hours", "time", "limit",
                "level", "rate", "start", "keep", "decimal", "digits", "size",
                "min_", "_min", "_no", "number", "count", "lang", "phone", "_id")
_WIDE_HINTS = ("path", "folder", "address", "server", "token", "api_key", "header",
               "footer", "email", "website", "thankyou", "logo", "template_name",
               "company_name")


def _field_width(f):
    """Sensible box width for a setting (None = stretch to the column).
    Numbers and codes are short, choices fit their longest option,
    paths / e-mail / API keys use the full width."""
    k = f["key"].lower()
    if f["type"] == "number":
        return 12
    if f["type"] == "choice":
        try:
            longest = max((len(lbl) for _, lbl in _opt_pairs(f)), default=8)
        except Exception:
            longest = 20
        return max(10, min(longest + 3, 60))
    if any(h in k for h in _WIDE_HINTS):
        return None
    if any(h in k for h in _SHORT_HINTS):
        return 18
    return 34


class _ChoiceVar:
    """Combobox showing friendly text while storing a code value."""
    def __init__(self, shown, pairs):
        self.shown = shown
        self.pairs = pairs

    def get(self):
        txt = self.shown.get()
        for v, lbl in self.pairs:
            if lbl == txt:
                return v
        return txt

    def set(self, v):
        v = "" if v is None else str(v)
        for val, lbl in self.pairs:
            if val == v:
                self.shown.set(lbl)
                return
        self.shown.set(v)

    def trace_add(self, mode, cb):
        return self.shown.trace_add(mode, cb)


class _TextVar:
    """Makes a multi-line Text look like a StringVar (get/set)."""
    def __init__(self, widget):
        self.w = widget

    def get(self):
        try:
            return self.w.get("1.0", "end").rstrip("\n")
        except Exception:
            return ""

    def set(self, v):
        try:
            self.w.delete("1.0", "end")
            self.w.insert("1.0", v or "")
        except Exception:
            pass
