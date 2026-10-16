# ============================================================
# DayBill ERP - Database Tool (v6.1)
# Pick a database · reset a password · convert another program's
# database into DayBill. Start:  python dbtool.py
#   (the built program: DayBillERP.exe --dbtool, or the
#    "DayBill Database Tool" shortcut / DayBill_Database_Tool.bat)
# ============================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from ui.dbtool_window import main
    main()
