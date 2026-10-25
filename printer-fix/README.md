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

## How to use

**Main PC** (the printer cable is plugged into this PC – `MYPC` in the screenshot)

1. Double-click `FIX-PRINTER.bat` → **Yes**.
2. Press **1** (Main PC).
3. Press **Y** to share the printer and type its name. Write down the path it shows, e.g. `\\MYPC\EPSONTM-T20II`.
4. Restart the PC.

**Client PC** (prints to the Main PC's printer)

1. Double-click `FIX-PRINTER.bat` → **Yes**.
2. Press **2** (Client PC).
3. Restart the PC.
4. Open the file again → **Yes** → press **3** → type the path from the Main PC.
5. **Y** for default printer, **Y** for a test page.

Still `0x0000011b`? → **4 More tools → 1 Connect via LOCAL PORT**. This prints to `\\MYPC\Share` over normal file
sharing, without the RPC connection that causes the error (the printer driver must be installed on the Client PC –
for EPSON TM-T20II install the *Epson Advanced Printer Driver (APD)*). This works on every Windows version.

Asked for a password / *access denied*? → **4 More tools → 3 Save Main PC login** and enter the Main PC's Windows
user name and password (that user must have a password).

Windows blocks the file after download? Right-click → **Properties** → tick **Unblock** → **OK**.

## Menu

```
[1] MAIN PC     - the printer cable is in THIS PC
[2] CLIENT PC   - this PC prints to the Main PC's printer
[3] Connect printer on Client PC   after restart
[4] More tools
      [1] Connect via LOCAL PORT     Client PC - if [3] still fails
      [2] Share a printer            Main PC
      [3] Save Main PC login         Client PC - access denied / password
      [4] Set network to Private     both - sharing is blocked on Public
      [5] Diagnostics report         both
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
**Connect via LOCAL PORT** needs none of these changes and is the safest way if you prefer to keep them on.
