# ============================================================
# DayBill ERP - Database Tool (v6.1)
# Pick a database · reset a password · convert another program's
# database into DayBill. Start:  python dbtool.py
#   (the built program: DayBillERP.exe --dbtool, or the
#    "DayBill Database Tool" shortcut / DayBill_Database_Tool.bat)
# v6.9.3: a password reset or a convert into a DayBill database needs
# the user name + password of an administrator of that database.
# ============================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from ui.dbtool_window import main
    main()
