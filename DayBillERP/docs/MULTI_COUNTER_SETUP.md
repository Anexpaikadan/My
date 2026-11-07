# 🖥 DayBill ERP — several counters on one server

One PC is the **server**: it has SQL Server and the DayBill database.
Every **counter** PC connects to it over the shop network, so products,
stock, prices, customers, accounts and bill numbers are shared live.

```
           ┌──────────────── SERVER PC ────────────────┐
           │ SQL Server Express + DayBill database      │
           │ fixed IP, e.g. 192.168.1.10, never sleeps  │
           └───────────────┬────────────────────────────┘
                           │  shop network (cable / Wi-Fi)
        ┌──────────────────┼──────────────────┐
   Counter 1           Counter 2           Office PC
   DayBillERP.exe      DayBillERP.exe      DayBillERP.exe
```

## A. Server PC (once)

1. **SQL Server Express** with the DayBill database is installed here (if
   DayBill already works on this PC, it is).
2. **Network access for SQL Server**
   - *SQL Server Configuration Manager* ▸ SQL Server Network Configuration
     ▸ Protocols for SQLEXPRESS ▸ **TCP/IP ▸ Enable**.
   - TCP/IP ▸ IP Addresses ▸ **IPAll**: *TCP Dynamic Ports* empty,
     *TCP Port* = **1433**.
   - Windows ▸ Services ▸ restart **SQL Server (SQLEXPRESS)**.
   - Optional: start **SQL Server Browser** (Automatic) — then the
     counters can also type `SERVER-PC\SQLEXPRESS`.
3. **Windows Firewall** — in DayBill: login screen ▸ **⚙ Database
   Settings ▸ 🛡 Allow SQL Server in Firewall** (press **Yes** when
   Windows asks). It allows TCP 1433 and UDP 1434 on private networks and
   shows the address the counters must type.
   Or once in Command Prompt (Run as administrator):
   ```
   netsh advfirewall firewall add rule name="DayBill SQL Server" dir=in action=allow protocol=TCP localport=1433 profile=private,domain
   netsh advfirewall firewall add rule name="DayBill SQL Browser" dir=in action=allow protocol=UDP localport=1434 profile=private,domain
   ```
   The shop network must be a **Private** network (Windows ▸ Settings ▸
   Network ▸ the network ▸ *Private*).
4. **One SQL login for the counters** (SSMS):
   - right-click the server ▸ Properties ▸ Security ▸ **SQL Server and
     Windows Authentication mode** ▸ restart the SQL Server service;
   - Security ▸ Logins ▸ **New Login…** e.g. `daybill` + a strong
     password, untick *User must change password*;
   - User Mapping ▸ tick **DayBillERP** ▸ role **db_owner** (DayBill
     updates its own tables when a new version starts).
5. **Fixed IP** for the server (a reservation in the router), e.g.
   `192.168.1.10`. `ipconfig` shows it.
6. Power options: the server **never sleeps** and is switched on before
   the counters.

## B. Each counter PC

1. Install **ODBC Driver 18 for SQL Server** (SQL Server itself is NOT
   needed on a counter).
2. Copy **DayBillERP.exe** — the **same version** as on the server.
3. Login screen ▸ **⚙ Database Settings**
   - **Server:** `192.168.1.10,1433` (or `SERVER-PC\SQLEXPRESS`);
     **🔍 Find** also looks on the network.
   - **Authentication:** SQL Server Authentication — `daybill` + password.
   - **🗂 List** ▸ pick **DayBillERP** ▸ **Test Connection** ▸
     **Save & Connect**.
4. Sign in with the cashier's DayBill user.

## C. Counters in DayBill (once, as admin)

1. **Administration ▸ 🏬 Branches & Counters**.
2. Branch: e.g. *Main Branch* ▸ **💾 Save branch**.
3. Counters: **＋ New** ▸ *Counter 1*, its branch ▸ **💾 Save counter** —
   again for Counter 2, 3 …
4. On **each PC**: select its counter ▸ **🖥 Use on THIS PC**.
   A new PC asks *"Which counter is this PC?"* by itself when DayBill
   starts and there is more than one counter.

Bills, returns, receipts, payments and expenses made on a PC carry its
counter; the counter's name is shown at the top of DayBill.

## What is shared and what belongs to one PC

| Shared (the database) | This PC only |
|---|---|
| Products, stock, prices, customers, suppliers, accounts, users, bill numbers (one series, never twice) | Which counter it is, its printers (receipt / A4 / kitchen), screen and grid settings |

## Every day

- Each cashier opens a **shift** on their own counter; **Day Close** and
  the reports can be filtered per counter or per branch.
- **Server switched off / network down:** the POS keeps the bill on the
  counter (`OFF-…`) and sends it when the server is back.
- **ZATCA (Saudi Arabia):** each counter can be connected as its own
  device (ZATCA ▸ Connect ▸ tick "Connect THIS till only").
- **Phones / PDT:** run DayBill Mobile on one PC, normally the server.
- **Updates:** update **all PCs to the same version** at the same time.
- **Backups:** on the server (⚙ Database Settings ▸ 💾 Backup Now).

## A counter can't connect?

| Message / problem | Check |
|---|---|
| Time-out, "server was not found" | `ping 192.168.1.10` from the counter · TCP/IP enabled, port 1433 · firewall button pressed on the server · the network is *Private* · SQL Server service running |
| `SERVER-PC\SQLEXPRESS` not found but `IP,1433` works | start the **SQL Server Browser** service, or keep using `IP,1433` |
| "Login failed for user 'daybill'" | password · Mixed Mode switched on and the service restarted |
| "Cannot open database" | User Mapping ▸ DayBillERP ▸ db_owner |
| Works, then stops after a restart of the server | give the server a fixed IP |

**First press ⚙ Database Settings ▸ 🩺 Check connection** on the counter.
It tests every step — the server's name, the SQL Server Browser, the TCP
port, the sign-in, the speed — and says exactly what to fix for the step
that fails.

## The server does not show on the other PCs

**🔍 Find** looks for servers three ways: the SQL Server Browser
(broadcast, UDP 1434, to the whole network and to your own subnet), every
PC of your network with port 1433 open, and the names you used before.
When nothing shows:

1. **Type the server as `IP,1433`** (e.g. `192.168.1.10,1433`). This needs
   no Browser and no PC-name lookup — the most reliable way, and the
   fastest.
2. On the **server PC**: TCP/IP enabled and IPAll TCP Port 1433 (step A.2),
   the SQL Server service restarted, **🛡 Allow SQL Server in Firewall**
   pressed, and the network set to **Private** (Windows ▸ Settings ▸
   Network ▸ the network ▸ Private) — on a *Public* network Windows blocks
   it.
3. To see `SERVER-PC\SQLEXPRESS` in the list: Windows ▸ Services ▸
   **SQL Server Browser** ▸ Startup type *Automatic* ▸ Start.
4. Both PCs on the **same network** (same router / Wi-Fi; a guest Wi-Fi
   usually keeps PCs apart), and `ping 192.168.1.10` answers from the
   counter.

## Fast database

- **Cable, not Wi-Fi**, between the counters and the server PC; Wi-Fi adds
  delay on every request. 🩺 Check connection shows the speed (under
  ~3 ms per request is fast).
- Counters connect with **`IP,1433`** — no name lookup, no Browser step.
- **⚡ Speed up database** (Database Settings) once a week or after big
  imports: refreshes SQL Server's statistics and tidies fragmented
  indexes. Safe while people work.
- The **server PC**: SSD disk, never sleeps, not used for heavy other work.
  SQL Server keeps the busy parts of the database in memory by itself —
  give the server PC enough RAM (8 GB or more). SQL Server Express uses up
  to about 1.4 GB for that cache; a very big shop can move to the
  Standard edition.
- **💾 Backup Now** regularly (Database Settings) — a safe copy, not a
  speed setting, but a slow PC is no reason to skip it.
