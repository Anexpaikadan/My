# Network shared printer fix – one click

Fixes Windows error **`Operation failed with error 0x0000011b`** ("Windows cannot connect to the printer")
when adding a shared printer such as `\\MYPC\EPSON TM-T20II`. Also fixes `0x00000709`, `0x00000bcb`,
`0x0000007c`, *access denied* and *printer offline* on the network.

File: [`FIX-PRINTER.bat`](FIX-PRINTER.bat)

## Why it happens (deep check)

| Error | Cause | What the script changes |
|---|---|---|
| `0x0000011b` | Windows update for CVE-2021-1678 makes the **host** PC demand encrypted (RPC privacy) printer connections; older/other PCs fail. | Host + client: `HKLM\SYSTEM\CurrentControlSet\Control\Print` → `RpcAuthnLevelPrivacyEnabled = 0` |
| `0x0000011b` / `0x00000709` on Windows 11 22H2+ | Windows 11 22H2 uses RPC over TCP for printers by default; the other PC only accepts named pipes. | `HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\RPC` → `RpcUseNamedPipeProtocol = 1`, `RpcProtocols = 7`, `ForceKerberosForRpc = 0` |
| `0x00000bcb` | PrintNightmare update: only admins may install the driver from the host. | `...\Printers\PointAndPrint` → `RestrictDriverInstallationToAdministrators = 0` |
| Host not found / offline | Sharing services stopped, firewall blocks File and Printer Sharing, network set to **Public**. | Starts the services, enables firewall rules, option to set network to Private |
| Stuck queue | Old jobs in the spooler. | Restarts Print Spooler and clears `spool\PRINTERS` |

## How to use (2 minutes)

1. Copy `FIX-PRINTER.bat` to a USB stick or download it on each PC.
2. **On the HOST PC** (the one with the printer's USB cable – `MYPC` in the screenshot):
   double-click `FIX-PRINTER.bat` → **Yes** on the admin prompt → press **1** (Fix all).
   Not shared yet? Press **6** and type the printer name to share it.
3. **On every CLIENT PC**: double-click → **Yes** → press **1**.
4. **Restart both PCs** (the spooler and RPC settings are fully read at start-up).
5. On the client: run it again → press **4** → type `\\MYPC\PrinterShareName` → Y for default / test page.

Still `0x0000011b`? → press **5 – Connect via LOCAL PORT**. This prints to `\\MYPC\Share` over normal file sharing,
without the RPC connection that causes the error (the printer driver must be installed on the client –
for EPSON TM-T20II install the *Epson Advanced Printer Driver (APD)*). This works on every Windows version.

Asked for a password / *access denied*? → press **7** and enter the host PC's Windows user name and password
(the host user must have a password).

## Menu

```
[1] FIX ALL  - run on EVERY PC (host and clients)   <-- start here
[2] Fix HOST only   - the PC with the printer USB cable
[3] Fix CLIENT only - a PC that prints over the network
[4] Connect shared printer      \\PCNAME\PrinterShare
[5] Connect via LOCAL PORT      workaround if [4] still fails
[6] Share a printer on THIS PC  host side
[7] Save login for the host PC  fixes access denied / password
[8] Set network to Private      sharing is blocked on Public
[9] Diagnostics report
[0] Exit
```

## Command line (CMD) use

Open **CMD** in the folder with the file (it asks for admin rights by itself):

```bat
FIX-PRINTER.bat all                          :: fix host + client settings, restart spooler
FIX-PRINTER.bat host                         :: only the host part
FIX-PRINTER.bat client                       :: only the client part
FIX-PRINTER.bat diag MYPC                    :: diagnostics + test connection to MYPC
FIX-PRINTER.bat add \\MYPC\EPSONTM-T20II      :: connect the shared printer
```

For share names **with spaces** run CMD *as Administrator* first and quote the path:
`FIX-PRINTER.bat add "\\MYPC\EPSON TM-T20II"`.

Output files next to the `.bat`:

- `printer-fix-log.txt` – what was changed
- `printer-diagnostic-<PC>.txt` – diagnostics report (send this if you need help)

## Manual commands (same as the script)

Run in **CMD as Administrator**:

```bat
:: host and client
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Print" /v RpcAuthnLevelPrivacyEnabled /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\RPC" /v RpcUseNamedPipeProtocol /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\RPC" /v RpcProtocols /t REG_DWORD /d 7 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\RPC" /v ForceKerberosForRpc /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint" /v RestrictDriverInstallationToAdministrators /t REG_DWORD /d 0 /f
net stop spooler /y & net start spooler

:: client: connect
rundll32 printui.dll,PrintUIEntry /in /n "\\MYPC\EPSON TM-T20II"
```

## Undo

```bat
reg delete "HKLM\SYSTEM\CurrentControlSet\Control\Print" /v RpcAuthnLevelPrivacyEnabled /f
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\RPC" /f
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint" /v RestrictDriverInstallationToAdministrators /f
net stop spooler /y & net start spooler
```

## Security note

These settings turn off protections Microsoft added in 2021 (CVE-2021-1678, PrintNightmare). That is normal for a
small shop or home network where you trust all PCs, but don't use them on public or untrusted networks.
Option **5 (local port)** needs none of these changes and is the safest way if you prefer to keep them on.
