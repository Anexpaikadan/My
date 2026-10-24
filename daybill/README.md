# Daybill Print – QR file upload & print app (PHP + MySQL)

A simple print-shop / book-stall app:

1. **Customer** scans the QR code at the counter → the upload page opens on their phone →
   they pick files and set **copies, paper size, colour, sides, layout and pages** → tap **Upload**
   → they get a 4-letter code (e.g. `K7QM`) to show at the counter.
2. **Employee** logs in → sees new orders appear automatically (with a beep) → taps an order →
   previews the file, changes copies/size if needed → presses **OK – Print** → it prints on the shop printer.
   Then **Complete order** with the bill amount.
3. **Admin** creates employees with passwords, sets the printer and price per page,
   and prints the **QR code poster** for the upload page.

Supported files: PDF, JPG, PNG, TXT, and Word/Excel/PowerPoint (Office files need LibreOffice
installed for one-tap printing; otherwise employees open/download them and print manually, then
press **Mark printed**).

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
3. Restart Apache. `http://` requests are automatically redirected to `https://`
   (`.htaccess` + `force_https` in `config.php`).

## 3. Let customers' phones reach the PC

- Give the shop PC a **fixed IP** on the Wi‑Fi router (e.g. `192.168.1.10`).
- Allow Apache through **Windows Firewall** (ports 80 and 443, Private network).
- Customers connect to the shop Wi‑Fi and scan the QR code.
- In the app go to **QR code**, enter `https://192.168.1.10/daybill/index.php`, click **Update**, then **Print poster**.

## 4. Printing setup (one-tap print)

The app prints from the PC that runs XAMPP, to any printer installed in Windows.

1. Install **[SumatraPDF](https://www.sumatrapdfreader.org/download-free-pdf-viewer)**
   (free). Default path `C:\Program Files\SumatraPDF\SumatraPDF.exe` — change `sumatra_path` in
   `config.php` if you installed it elsewhere (portable/per-user installs often go to
   `C:\Users\<you>\AppData\Local\SumatraPDF\SumatraPDF.exe`).
2. *(Optional)* Install **[LibreOffice](https://www.libreoffice.org/)** so Word/Excel/PowerPoint
   files can be printed with one tap (`soffice_path` in `config.php`).
3. In **Admin → Shop & printer settings**, choose the B/W printer and (optionally) a colour
   printer. Leave empty to use the Windows default printer.
4. **Important:** start Apache from the XAMPP Control Panel as your normal Windows user
   (not as a Windows *service*). A service runs as the SYSTEM account, which usually cannot
   see your printers. If you must run it as a service: `services.msc` → Apache → Properties →
   Log On → "This account" → your Windows user.

Print options sent to the printer: copies, paper size (A4/A3/A5/Letter/Legal), colour or
black & white, one/both sides, portrait/landscape, page range (e.g. `1-3,5`), fit to page.
Whether duplex/colour/A3 actually work depends on your printer.

On Linux/macOS the app uses the CUPS `lp` command instead.

Test without a printer: set `'print_dry_run' => true` in `config.php` (commands are written to the PHP error log).

## 5. Daily use

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
| `printer.php` | Sends files to the printer (SumatraPDF / lp) |
| `lib.php`, `config.php` | Shared code and configuration |
| `schema.sql`, `install.php` | Database setup |
| `uploads/` | Stored customer files (blocked from direct web access) |

## Security notes

- Passwords are stored with `password_hash` (bcrypt); all queries use prepared statements; forms use CSRF tokens.
- Uploaded files get random names, are type-checked, and are only reachable through `file.php` after login.
- Login is rate-limited per session; session cookies are `Secure` + `HttpOnly`.
- Change the MySQL `root` password in production and update `config.php`.
- If PHP shows "file too large", raise `upload_max_filesize` and `post_max_size` in `C:\xampp\php\php.ini`.
