# ============================================================
# DayBill ERP - WPS (Wage Protection System) File Exporter
# Generates a salary file for upload to the bank / Mudad portal
# ============================================================
#
# The WPS file lists each employee's IBAN and net salary so the
# bank can verify wage payments with the Ministry of HRSD.
# Banks accept slightly different layouts; this produces a clean
# CSV with the standard columns most Saudi banks/Mudad accept.
# ============================================================

import csv


WPS_HEADERS = [
    "Record Type", "Employee ID", "Employee Name", "IBAN", "Bank Name",
    "Basic Salary", "Housing Allowance", "Other Allowances",
    "Deductions", "Net Salary", "Currency",
]


def export_wps_file(payslips: list, company: dict, output_path: str) -> str:
    """
    Write a WPS salary CSV.

    payslips : list of payslip rows (dicts) from the payslips table
    company  : company row (for the header record)
    output_path : .csv destination
    """
    total_net = sum(float(p.get("net_salary", 0) or 0) for p in payslips)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)

        # Employer header record
        w.writerow(["EMPLOYER", company.get("company_name_en", ""),
                    company.get("vat_registration_no", ""),
                    company.get("cr_number", ""),
                    f"Employees: {len(payslips)}",
                    f"Total Net: {total_net:.2f} SAR"])
        w.writerow([])
        w.writerow(WPS_HEADERS)

        for p in payslips:
            allowances = (float(p.get("transport_allowance", 0) or 0) +
                          float(p.get("other_allowance", 0) or 0) +
                          float(p.get("overtime_amount", 0) or 0))
            w.writerow([
                "SALARY",
                p.get("employee_id", ""),
                p.get("employee_name_en", ""),
                p.get("iban", "") or "",
                p.get("bank_name", "") or "",
                f"{float(p.get('basic_salary', 0) or 0):.2f}",
                f"{float(p.get('housing_allowance', 0) or 0):.2f}",
                f"{allowances:.2f}",
                f"{float(p.get('total_deductions', 0) or 0):.2f}",
                f"{float(p.get('net_salary', 0) or 0):.2f}",
                "SAR",
            ])

        # Trailer
        w.writerow([])
        w.writerow(["TOTAL", "", "", "", "", "", "", "", "", f"{total_net:.2f}", "SAR"])

    return output_path
