# 🛠️ DayBill ERP — Setup & Run Guide (Windows)

Follow these in order. Total time ~20 minutes.

---

## 1. Install Python 3.10+

1. Download from https://www.python.org/downloads/
2. Run the installer — **tick "Add Python to PATH"** at the bottom.
3. Verify in Command Prompt:
   ```
   python --version
   ```
   You should see `Python 3.10` or higher.

---

## 2. Install SQL Server (free Express edition)

1. Download **SQL Server Express**: https://www.microsoft.com/sql-server/sql-server-downloads
2. Choose **Basic** installation.
3. Install **SSMS** (SQL Server Management Studio): https://aka.ms/ssms
4. Note your server name (usually `localhost\SQLEXPRESS` or `.\SQLEXPRESS`).

---

## 3. Install the ODBC Driver

Download and install **ODBC Driver 19 for SQL Server** (recommended) or 18/17:
https://aka.ms/downloadmsodbcsql

The app auto-detects whichever version you have (19, 18, or 17).
Driver 18/19 encrypt connections by default; the app sets
`TrustServerCertificate=yes` automatically so local SQL Server works.

(Without this driver, the app cannot connect to the database.)

---

## 4. Create the Database

1. Open **SSMS**, connect to your server.
2. Open `database\INSTALL_DayBillERP_AllInOne.sql` → press **F5** to run it.
   → Creates the `DayBillERP` database with every table, the chart of
     accounts and all updates (including ZATCA Phase 2).
   (Or in the app: login ▸ DB Settings ▸ **Create New Database…**.)
   The database is **clean**: no sample products / customers / bills and
   an empty company. Only the starting data is added (admin user, roles,
   chart of accounts, VAT categories, Cash Customer / Supplier, Main Branch).
   Running the file again on an existing database is safe — it only adds
   what is missing.
3. First sign-in: `admin` → set your password. The *Welcome to DayBill
   ERP* setup window opens this one time — fill Settings ▸ Company there.
4. Later updates install themselves when the app starts.

### ZATCA Phase 2 (e-invoicing)

Sidebar ▸ Reports & Compliance ▸ **ZATCA**: fill the shop details (✓ / ✗
shows what is missing), choose **Sandbox** first (test, OTP filled in for
you) and press **Connect to ZATCA**. Test a few bills. Then *Disconnect*,
connect to **Simulation**, and finally **Production** with an OTP from
fatoora.zatca.gov.sa (Onboard new solution unit ▸ Generate OTP, valid 1 hour).
After that every bill is signed, prints the Phase 2 QR and is sent to ZATCA
by itself. B2B customers need VAT no. + full national address.
Tip: a signed bill can't be edited any more (also in Sandbox), so try Sandbox
on a test database first (login ▸ Database Settings ▸ Create New Database…).

---

## 5. Install Python Libraries

Open Command Prompt **inside the `daybill_erp` folder**:

```
cd path\to\daybill_erp
pip install -r requirements.txt
```

If that fails, install the core ones individually:
```
pip install pyodbc reportlab arabic-reshaper python-bidi qrcode pillow cryptography lxml bcrypt openpyxl requests
```

---

## 6. Arabic PDF Font (for Arabic invoices)

Create a folder `modules/fonts/` and drop an Arabic TTF inside, e.g.:
- **Amiri** (free): https://fonts.google.com/specimen/Amiri → `Amiri-Regular.ttf`
- or **Cairo**: https://fonts.google.com/specimen/Cairo → `Cairo-Regular.ttf`

Without this, English prints fine but Arabic shows as boxes.

---

## 7. Run the App

```
python main.py
```

1. On the login screen, click **⚙ Database Settings**.
2. Enter your server (e.g. `localhost\SQLEXPRESS`), database `DayBillERP`.
3. Choose **Windows Authentication** (simplest) → **Test Connection** → **Save & Connect**.
4. Log in as `admin`. On a new installation DayBill asks you to **set the
   admin password** the first time (type it twice), then signs you in.
   Use that password from then on.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `pyodbc` connection error | Check ODBC Driver 17 is installed; verify server name |
| "Login failed for user" | Use Windows Authentication, or enable SQL auth in SSMS |
| Arabic shows as boxes | Add an Arabic TTF to `modules/fonts/` |
| QR code blank | `pip install qrcode pillow` |
| App won't start | Run `python main.py` from inside the `daybill_erp` folder |

---

## Default Login
**Username:** `admin` — on first sign-in DayBill asks you to set its password.
