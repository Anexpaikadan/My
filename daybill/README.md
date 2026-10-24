# Daybill Print – QR file upload & print app (PHP + MySQL)

A simple print-shop / book-stall app:

1. **Customer** scans the QR code at the counter → the upload page opens on their phone
   (**English or العربية**, switch at the top) → they pick files and set **copies, paper size,
   colour / black & white, one side / both sides, layout and pages** → they see the **estimated price**
   → tap **Upload** → they get a 4-letter code (e.g. `K7QM`) to show at the counter.
2. **Employee** logs in → sees new orders appear automatically (with a beep) → taps an order →
   previews the file, changes copies/size/**price** if needed → presses **OK – Print**.
   Then enters/changes the **bill amount** and presses **Complete order**.
3. **Admin** creates employees with passwords, chooses which paper sizes / colour / sides customers
   can pick, sets the **price rules**, the printer, and prints the **QR code poster**.

Works on **XAMPP on the shop PC** (localhost / shop Wi‑Fi) or on **cloud hosting such as Hostinger**
(customers can upload from anywhere; a small print agent on the shop PC prints the jobs).

Supported files: PDF, JPG, PNG, TXT, and Word/Excel/PowerPoint (Office files need LibreOffice
installed for one-tap printing; otherwise employees open/download them and print manually, then
press **Mark printed**).

## Admin: options and prices

**Customer options** (Admin → Customer options): tick the paper sizes (A4, A3, A5, A6, A2, Letter,
Legal, Tabloid, Statement, plus your own e.g. `Photo 4x6`), colour (B/W, colour) and sides
(one side, both sides) you offer. Only ticked options appear for customers — if only **A4** is
ticked, customers just see "A4" with nothing to choose.

**Prices** (Admin → Prices): every paper + colour + sides combination has its own rule:

| First N pages | Fixed price | Each extra page | Result |
|---|---|---|---|
| 2 | 2 SR | 1 SR | 1–2 pages = 2 SR, 3 pages = 3 SR, 10 pages = 10 SR |
| 1 | 2 SR | 1 SR | 1 page = 2 SR, 2 pages = 3 SR, 10 pages = 11 SR |
| 0 | 0 | 0.5 SR | 0.5 SR per page |

Pages are counted as *selected pages × copies*. A3 can have a different rate than A4, colour
than B/W, both sides than one side. The currency (default `SR`) is set in Shop settings.

**Staff can change the price**: each file has a Price field (Save to keep it; "Changed by staff"
is shown next to the calculated price), and the order's Bill amount can be edited with **Save amount**
or when completing the order. Page counts are read from PDFs automatically; for Word/Excel files
the page count is unknown, so staff should check the price.

**Language**: customers switch English / العربية at the top of the upload page; the default
language is set in Admin → Shop settings.

---

## 1. Install on XAMPP (Windows)

1. Install [XAMPP](https://www.apachefriends.org/) and start **Apache** and **MySQL** from the XAMPP Control Panel.
2. Copy the `daybill` folder to `C:\xampp\htdocs\daybill`.
3. Open `config.php` and check the MySQL user/password (XAMPP default is `root` with empty password).
4. Enable HTTPS (section 2), then open **https://localhost/daybill/install.php**,
   choose the admin username and password, and click **Install**.
5. **Delete `install.php`** after installing.
6. Log in at **https://localhost/daybill/login.php**.

## 2. HTTPS

XAMPP already ships Apache with SSL on port 443 and a self-signed test certificate.

1. In `C:\xampp\apache\conf\httpd.conf` make sure these lines are **not** commented out (no `#`):
   ```
   LoadModule ssl_module modules/mod_ssl.so
   LoadModule rewrite_module modules/mod_rewrite.so
   LoadModule headers_module modules/mod_headers.so
   Include conf/extra/httpd-ssl.conf
   ```
   and that the `<Directory "C:/xampp/htdocs">` block has `AllowOverride All` (so `.htaccess` works).
2. **Better certificate (recommended):** create a certificate for your PC's LAN IP so phones show
   fewer warnings. Easiest is [mkcert](https://github.com/FiloSottile/mkcert):
   ```
   mkcert -install
   mkcert 192.168.1.10 localhost
   ```
   Copy the two generated files to `C:\xampp\apache\conf\ssl.crt\server.crt` and
   `C:\xampp\apache\conf\ssl.key\server.key` (or change `SSLCertificateFile` /
   `SSLCertificateKeyFile` in `conf\extra\httpd-ssl.conf`) and restart Apache.
   With a self-signed certificate customers will see a "Not secure / Advanced → Proceed" warning
   the first time — mkcert's root CA can be installed on the shop's own devices to avoid it.
   If you have a real domain name pointing to the shop, a free Let's Encrypt certificate removes the warning for everyone.
3. Restart Apache. **HTTPS is always required** and cannot be switched off: `http://` pages
   redirect to `https://`, forms/uploads over `http://` are refused, login cookies are HTTPS-only,
   browsers are told to always use HTTPS (HSTS), the QR code always uses `https://`, and the print
   agent only connects to an `https://` address. So HTTPS must be set up before `install.php`.

## 3. Let customers' phones reach the PC

- Give the shop PC a **fixed IP** on the Wi‑Fi router (e.g. `192.168.1.10`).
- Allow Apache through **Windows Firewall** (ports 80 and 443, Private network).
- Customers connect to the shop Wi‑Fi and scan the QR code.
- In the app go to **QR code**, enter `https://192.168.1.10/daybill/index.php`, click **Update**, then **Print poster**.

## 4. Printing setup (one-tap print, print mode "Local")

The app prints from the PC that runs XAMPP, to any printer installed in Windows.

1. Get **[SumatraPDF](https://www.sumatrapdfreader.org/download-free-pdf-viewer)** (free) — either:
   - **easiest:** download the *portable* version and copy the `.exe` into the app's `tools` folder
     (`C:\xampp\htdocs\daybill\tools\`), or
   - install it normally. The app finds it automatically in `Program Files`, `Program Files (x86)`
     and `C:\Users\<you>\AppData\Local\SumatraPDF\`.

   **Admin → Printing** shows ✅ *SumatraPDF found* or ❌ *not found* (you can also type the path there).
   If an order shows *"SumatraPDF is not installed"*, do this step and press **OK – Print** again.
2. *(Optional)* Install **[LibreOffice](https://www.libreoffice.org/)** so Word/Excel/PowerPoint
   files can be printed with one tap (`soffice_path` in `config.php`).
3. **Admin → Printing**: set the default B/W printer and (optionally) colour printer, and under
   **Printer for each paper size** pick a printer per paper size and colour — e.g. A4 B/W → your A4
   laser printer, A3 → your A3 printer, colour → your colour printer. Empty = default printer.
   On each order, staff can choose another printer in the **Printer** menu before pressing **OK – Print**.
   Use the exact printer names from Windows Settings → Printers (the list is suggested automatically).
4. **Important:** start Apache from the XAMPP Control Panel as your normal Windows user
   (not as a Windows *service*). A service runs as the SYSTEM account, which usually cannot
   see your printers. If you must run it as a service: `services.msc` → Apache → Properties →
   Log On → "This account" → your Windows user.

Print options sent to the printer: copies, paper size (A4/A3/A5/Letter/Legal), colour or
black & white, one/both sides, portrait/landscape, page range (e.g. `1-3,5`), fit to page.
Whether duplex/colour/A3 actually work depends on your printer.

On Linux/macOS the app uses the CUPS `lp` command instead.

Test without a printer: set `'print_dry_run' => true` in `config.php` (commands are written to the PHP error log).

### Print modes (Admin → Printing)

| Mode | Use when | How it prints |
|---|---|---|
| **Local** | App runs in XAMPP on the shop PC | Server prints directly with SumatraPDF |
| **Cloud + print agent** | App hosted online (Hostinger etc.) | `agent/print-agent.php` on the shop PC fetches jobs and prints them |
| **Browser** | No agent possible | Staff tap *Open & print*, the file opens in a new tab, they print with the browser and choose the shown options |

## 5. Cloud hosting (Hostinger or any PHP + MySQL host)

1. **Hosting panel (hPanel) → Databases → MySQL**: create a database and user. Note the
   database name, user and password (e.g. `u123456789_daybill`). Host is normally `localhost`.
2. **File Manager**: upload the `daybill` folder into `public_html/` (you can leave out the `agent` folder there,
   it is only needed on the shop PC).
3. Edit `public_html/daybill/config.php`: set `db_host` (`localhost`), `db_name`, `db_user`, `db_pass`.
4. **SSL**: hPanel → Security → SSL → install the free SSL for your domain (HTTPS works without warnings).
5. Open `https://yourdomain.com/daybill/install.php`, create the admin, then **delete `install.php`**.
6. Log in → **Admin → Printing** → choose **Cloud + print agent** → Save. An **agent key** appears.
7. **QR code** page: the address is `https://yourdomain.com/daybill/index.php` — print the poster.
   Customers can now upload over mobile data too, no shop Wi‑Fi needed.
8. PHP upload limits come from `.user.ini` (25 MB per file); you can also change them in hPanel → PHP Configuration.

### Print agent on the shop PC

The website cannot reach your shop printer, so a small program on the shop PC asks the website
for print jobs every 3 seconds and prints them.

1. Install PHP on the shop PC — easiest is XAMPP (only `C:\xampp\php\php.exe` is used; Apache/MySQL
   don't need to run). Install **SumatraPDF** (or put the portable `.exe` in the agent's `tools` folder)
   and optionally LibreOffice, as in section 4. The agent sends the shop PC's printer list to the
   website, so you can pick printers per paper size in Admin → Printing.
2. Copy the `agent` folder to the shop PC, e.g. `C:\daybill-agent\`.
3. Edit `agent-config.php`: `server_url` = `https://yourdomain.com/daybill/`, `agent_key` = the key from Admin.
4. Double-click **`start-agent.bat`**. You should see `Connected to "<shop name>". Waiting for print jobs…`
   (it restarts itself if it stops). To start it automatically: press Win+R → `shell:startup` →
   put a shortcut to `start-agent.bat` there.
5. If it says *certificate verify failed*: download `https://curl.se/ca/cacert.pem` and set `ca_file` in `agent-config.php`.

In Admin → Printing you can see whether the agent is connected; the order page warns staff when it is not.
When staff press **OK – Print** the file is *queued*, the agent prints it within seconds and it shows as *printed*
(or *failed* with the reason).

## 6. Daily use

| Who | Page |
|---|---|
| Customer | `https://<pc-ip>/daybill/` (via QR code) |
| Employee / Admin | `https://<pc-ip>/daybill/login.php` |
| Admin | **Admin** (employees, printers, prices) and **QR code** |

- **Waiting** tab: new orders, oldest first. The page checks for new orders every 8 seconds and beeps.
- **Done today**: completed orders; the top shows today's count and total bill.
- Search by code, customer name or phone.
- Uploaded files are deleted automatically after the number of days set in Admin (default 2) to protect customer privacy.

## Files

| File | Purpose |
|---|---|
| `index.php` | Customer upload page (QR target) |
| `login.php`, `logout.php` | Staff login |
| `staff.php` | Order list for employees |
| `job.php` | Order details: preview, change options, print, complete |
| `file.php` | Secure file preview/download (staff only) |
| `admin.php` | Employees and settings (admin only) |
| `qr.php` | QR code poster (admin only, works offline) |
| `printer.php` | Local printing (print mode "Local") |
| `api.php` | API for the shop-PC print agent (cloud mode) |
| `agent/` | Print agent for the shop PC: `print-agent.php`, `agent-config.php`, `start-agent.bat`, `print-core.php` |
| `tools/` | Optional place for the portable `SumatraPDF.exe` |
| `lang.php` | English / Arabic texts for the customer page |
| `lib.php`, `config.php` | Shared code and configuration |
| `schema.sql`, `install.php` | Database setup |
| `uploads/` | Stored customer files (blocked from direct web access) |

## Security notes

- The print agent authenticates with a secret key; create a new key in Admin if it leaks.
- Passwords are stored with `password_hash` (bcrypt); all queries use prepared statements; forms use CSRF tokens.
- Uploaded files get random names, are type-checked, and are only reachable through `file.php` after login.
- Login is rate-limited per session; session cookies are `Secure` + `HttpOnly`.
- Change the MySQL `root` password in production and update `config.php`.
- If PHP shows "file too large", raise `upload_max_filesize` and `post_max_size` in `C:\xampp\php\php.ini`.
