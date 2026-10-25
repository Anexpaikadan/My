DayBill ERP - database folder
==============================

NEW INSTALLATION (new shop / new PC with SQL Server)
----------------------------------------------------
Run ONE file:   INSTALL_DayBillERP_AllInOne.sql

  A. Easiest: DayBill login  >  Database Settings  >  Create New Database...
     (type any name - DayBill runs this file for you)
  B. SQL Server Management Studio: open INSTALL_DayBillERP_AllInOne.sql  >  Execute (F5)
     It creates the database DayBillERP itself - no need to make it first.
  C. Command line:
     sqlcmd -S .\SQLEXPRESS -E -i database\INSTALL_DayBillERP_AllInOne.sql

It makes every table, view and procedure, the chart of accounts, VAT
categories, the admin user (you set the password at the first sign-in),
Cash Customer / Cash Supplier, Main Branch + Counter 1. No sample data.
Then sign in as admin  >  Settings  >  Company.

Safe to run again on an existing DayBill database: it only adds what is
missing and never deletes data.


UPDATING AN OLDER DATABASE
--------------------------
Nothing to do by hand. The *_patch.sql files in the patches\ folder are applied
automatically when DayBill starts (Settings > System > "Update the database
automatically"), or from Updates > Apply All Updates.


OTHER FILES in tools\ (only when your dealer asks)
--------------------------------------------------
REPAIR_product_keys.sql    repairs product keys on very old databases
units_reset_optional.sql   resets the unit list - deletes custom units!
RESET_user_password.sql    forgotten password: the user signs in with any
                           password and DayBill asks for a new one. Changes
                           nothing on a database that isn't DayBill's.
                           (Same query: login screen > Forgot password?)


For developers: INSTALL_DayBillERP_AllInOne.sql is built from
tools/sql_base/DayBillERP_Full_Setup.sql + all patches/*_patch.sql files with
    python tools/build_install_sql.py
