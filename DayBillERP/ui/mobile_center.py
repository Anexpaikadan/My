# ============================================================
# DayBill ERP - 📱 Mobile, PDT & Van Sales (Sidebar ▸ Inventory)
# ------------------------------------------------------------
#  Phones & PDT  — start the Wi-Fi server, the link + QR for the phones,
#                  signed-in devices, options
#  Users         — which modules each DayBill user may use on a phone /
#                  PDT (one app, only those modules show), van code + PIN
#  Inbox         — everything the devices sent: approve / reject / open
#  Van (internet)— the Hostinger relay: address, shop key, Sync now,
#                  auto sync, "Make upload folder"
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sys, os, json, threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg
from config.database import db
from modules import mobile_api as M
from modules import permissions as perm

_BG = {"runner": None, "timer": None, "busy": False, "last": ""}


# ── runs with DayBill (Main window calls start_background) ────
def start_background(root):
    """Auto-start the Wi-Fi server and the van auto-sync."""
    try:
        from modules.mobile_server import get_server, MainThreadRunner
        if cfg.flag("mobile_autostart", False) and M.tables_ready():
            get_server(root).start()
        _BG["runner"] = MainThreadRunner(root)
        _schedule(root)
    except Exception as e:
        print("[DayBill] mobile background:", e)


def _schedule(root):
    try:
        if _BG["timer"]:
            root.after_cancel(_BG["timer"])
    except Exception:
        pass
    mins = int(float(cfg.get("van_auto_sync_min", 0) or 0))
    if mins > 0 and cfg.get("van_relay_url"):
        _BG["timer"] = root.after(mins * 60000, lambda: (van_sync_bg(root), _schedule(root)))


def van_sync_bg(root, done=None):
    """Van sync in a background thread (network), database work on the
    main thread. done(msg) is called on the main thread."""
    if _BG["busy"]:
        return False
    from modules import van_sync as VS
    from modules.mobile_server import MainThreadRunner
    runner = _BG["runner"] or MainThreadRunner(root)
    _BG["runner"] = runner
    _BG["busy"] = True

    def work():
        try:
            msg = VS.sync(run=runner.call)
        except Exception as e:
            msg = "⚠ " + str(e)[:200]
        _BG["busy"] = False
        _BG["last"] = msg
        if done:          # back on DayBill's main thread (never touch Tk from here)
            runner.q.put((lambda: done(msg), {}, threading.Event()))
    threading.Thread(target=work, daemon=True, name="daybill-van-sync").start()
    return True


class MobileCenterView:
    def __init__(self, parent):
        self.C = C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.root = self.frame.winfo_toplevel()
        top = tk.Frame(self.frame, bg=C["card_bg"]); top.pack(fill="x")
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill="x")
        tk.Label(top, text="📱", font=("Segoe UI Emoji", 16), bg=C["card_bg"]).pack(side="left", padx=(14, 6), pady=8)
        tt = tk.Frame(top, bg=C["card_bg"]); tt.pack(side="left")
        tk.Label(tt, text="Mobile, PDT & Van Sales", font=("Segoe UI", 13, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(anchor="w")
        tk.Label(tt, text="one app on every phone / scanner — each user sees only his modules",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        if not M.tables_ready():
            tk.Label(self.frame, text="Mobile tables are missing.\n\nRestart DayBill (it adds them by itself) or run "
                     "database/patches/zz_mobile_patch.sql.", font=("Segoe UI", 11), bg=C["content_bg"],
                     fg=C["danger"], justify="center").pack(expand=True)
            return
        self.nb = ttk.Notebook(self.frame); self.nb.pack(fill="both", expand=True, padx=10, pady=8)
        self.t_wifi = tk.Frame(self.nb, bg=C["content_bg"])
        self.t_users = tk.Frame(self.nb, bg=C["content_bg"])
        self.t_inbox = tk.Frame(self.nb, bg=C["content_bg"])
        self.t_van = tk.Frame(self.nb, bg=C["content_bg"])
        self.nb.add(self.t_wifi, text="  📶 Phones & PDT (Wi-Fi)  ")
        self.nb.add(self.t_users, text="  👥 Users & modules  ")
        self.nb.add(self.t_inbox, text="  📥 Inbox  ")
        self.nb.add(self.t_van, text="  🚚 Van (internet)  ")
        self._build_wifi(); self._build_users(); self._build_inbox(); self._build_van()
        self._tick()

    # helpers ---------------------------------------------------
    def _card(self, parent, title, sub=""):
        C = self.C
        f = tk.Frame(parent, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        f.pack(fill="x", padx=6, pady=6)
        tk.Label(f, text=title, font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=12, pady=(10, 0))
        if sub:
            tk.Label(f, text=sub, font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                     justify="left", wraplength=900).pack(anchor="w", padx=12)
        inner = tk.Frame(f, bg=C["card_bg"]); inner.pack(fill="x", padx=12, pady=(6, 12))
        return inner

    def _btn(self, parent, text, cmd, primary=False, danger=False):
        C = self.C
        return tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 9, "bold" if primary else "normal"),
                         bg=C["primary"] if primary else ("#FEF2F2" if danger else C["card_bg"]),
                         fg="white" if primary else (C["danger"] if danger else C["text_primary"]),
                         relief="flat", padx=12, pady=6, cursor="hand2",
                         highlightthickness=0 if primary else 1, highlightbackground=C["border"])

    def _check(self, parent, text, key, default=False):
        v = tk.BooleanVar(value=cfg.flag(key, default))

        def flip():
            # these options are settings: no right = the tick goes back
            if not self._can_set():
                v.set(not v.get())
                return
            cfg.set(key, v.get()); cfg.save_settings()
        tk.Checkbutton(parent, text=text, variable=v, bg=self.C["card_bg"], activebackground=self.C["card_bg"],
                       font=("Segoe UI", 9), command=flip).pack(anchor="w")
        return v

    def _can_set(self):
        """Server, devices and phone options need the settings right."""
        return perm.allowed("company_settings", "settings", parent=self.frame)

    # ── Phones & PDT ───────────────────────────────────────────
    def _build_wifi(self):
        C = self.C
        from modules.mobile_server import get_server
        self.server = get_server(self.root)
        st = self._card(self.t_wifi, "DayBill Mobile server",
                        "Phones and PDT scanners on the SAME Wi-Fi as this PC open DayBill Mobile in Chrome. "
                        "Keep DayBill open on this PC while they work.")
        row = tk.Frame(st, bg=C["card_bg"]); row.pack(fill="x")
        self.srv_lbl = tk.Label(row, text="", font=("Segoe UI", 12, "bold"), bg=C["card_bg"])
        self.srv_lbl.pack(side="left")
        self.stop_btn = self._btn(row, "■ Stop", self._stop, danger=True); self.stop_btn.pack(side="right")
        self.start_btn = self._btn(row, "▶ Start", self._start, primary=True); self.start_btn.pack(side="right", padx=6)
        o = tk.Frame(st, bg=C["card_bg"]); o.pack(fill="x", pady=(8, 0))
        self._check(o, "Start automatically when DayBill opens", "mobile_autostart")
        self._check(o, "Goods Out / Stock Count / Stock Adjust wait for approval in the Inbox "
                       "(untick = stock changes at once)", "mobile_approve_stock")
        self._check(o, "Goods In: confirm the purchase at once (untick = draft, office checks prices)",
                    "mobile_goods_in_confirm")
        self._check(o, "Barcode Labels from the PDT: print at once on the label printer "
                       "(untick = wait in the Inbox ▸ 🖨 Print PDF)", "mobile_labels_autoprint", default=True)
        self._check(o, "Offer Poster: allowed to print at once when the PDT ticks 'Print now'",
                    "mobile_poster_autoprint", default=True)
        pr = tk.Frame(o, bg=C["card_bg"]); pr.pack(anchor="w", pady=(4, 0))
        tk.Label(pr, text="Port", bg=C["card_bg"], font=("Segoe UI", 9)).pack(side="left")
        self.port_v = tk.StringVar(value=str(cfg.get("mobile_port", 8090) or 8090))
        pe = tk.Entry(pr, textvariable=self.port_v, width=7, relief="solid", bd=1); pe.pack(side="left", padx=6)
        pe.bind("<FocusOut>", lambda e: self._save_port())
        lk = self._card(self.t_wifi, "Open it on the phone / PDT",
                        "1. Connect the phone or PDT to the shop Wi-Fi.  2. Open Chrome and type the address "
                        "(or scan the QR).  3. ⋮ menu ▸ Add to Home screen — it opens like an app.  "
                        "4. Sign in with the DayBill user name + password. PDT: the scan button types into the "
                        "app by itself (keyboard / wedge mode).")
        lr = tk.Frame(lk, bg=C["card_bg"]); lr.pack(fill="x")
        self.qr_lbl = tk.Label(lr, bg=C["card_bg"]); self.qr_lbl.pack(side="left")
        self.url_lbl = tk.Label(lr, text="", font=("Consolas", 16, "bold"), bg=C["card_bg"], fg=C["primary"],
                                justify="left")
        self.url_lbl.pack(side="left", padx=16, anchor="n")
        fw = tk.Frame(lk, bg=C["card_bg"]); fw.pack(fill="x", pady=(6, 0))
        tk.Label(fw, text="Phone can't open it?  Windows Firewall may block it →", bg=C["card_bg"],
                 fg=C["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self._btn(fw, "🛡 Allow in Windows Firewall", self._firewall).pack(side="left", padx=6)
        dv = self._card(self.t_wifi, "Signed-in devices")
        self.dev_tree = ttk.Treeview(dv, columns=("user", "device", "since", "seen"), show="headings", height=5)
        for k, t_, w in (("user", "User", 160), ("device", "Device", 180), ("since", "Signed in", 150),
                         ("seen", "Last seen", 150)):
            self.dev_tree.heading(k, text=t_); self.dev_tree.column(k, width=w)
        self.dev_tree.pack(fill="x")
        self._btn(dv, "Sign this device out", self._kick).pack(anchor="w", pady=(6, 0))
        self._paint_server()

    def _save_port(self):
        try:
            p = int(self.port_v.get())
            if 1024 <= p <= 65535 and p != int(cfg.get("mobile_port", 8090) or 8090):
                if not self._can_set():
                    self.port_v.set(str(cfg.get("mobile_port", 8090) or 8090))
                    return
                cfg.set("mobile_port", p); cfg.save_settings()
                if self.server.running:
                    self.server.stop()
                self.server.port = p
                self._paint_server()
        except ValueError:
            pass

    def _start(self):
        if not self._can_set():
            return
        self._save_port()
        if not self.server.start():
            messagebox.showerror("Mobile server", self.server.error or "Could not start.")
        self._paint_server()

    def _stop(self):
        if not self._can_set():
            return
        self.server.stop(); self._paint_server()

    def _paint_server(self):
        C = self.C
        on = self.server.running
        self.srv_lbl.configure(text=("● Running" if on else "○ Stopped"), fg=C["success"] if on else C["text_secondary"])
        self.start_btn.configure(state="disabled" if on else "normal")
        self.stop_btn.configure(state="normal" if on else "disabled")
        urls = self.server.urls()
        self.url_lbl.configure(text="\n".join(urls) if on else "Press ▶ Start",
                               fg=C["primary"] if on else C["text_secondary"])
        self._qr(urls[0] if on else "")
        self._load_devices()

    def _qr(self, text):
        if not text:
            self.qr_lbl.configure(image="", text=""); return
        try:
            import qrcode
            from PIL import ImageTk
            img = qrcode.make(text).resize((150, 150))
            self._qr_img = ImageTk.PhotoImage(img)
            self.qr_lbl.configure(image=self._qr_img)
        except Exception:
            self.qr_lbl.configure(text="")

    def _firewall(self):
        if not self._can_set():
            return
        port = int(cfg.get("mobile_port", 8090) or 8090)
        cmd = ('advfirewall firewall add rule name="DayBill Mobile" dir=in action=allow '
               'protocol=TCP localport=%d profile=private,domain' % port)
        if os.name == "nt":
            try:
                import ctypes
                r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", cmd, None, 0)
                if r > 32:
                    messagebox.showinfo("Firewall", "Done — phones on the Wi-Fi can open DayBill Mobile now.")
                    return
            except Exception:
                pass
        messagebox.showinfo("Firewall", "Run this once as Administrator (Command Prompt):\n\nnetsh " + cmd)

    def _load_devices(self):
        self.dev_tree.delete(*self.dev_tree.get_children())
        for r in M._all("SELECT TOP 50 t.token, u.username, t.device, t.created_at, t.last_seen FROM mobile_tokens t "
                        "LEFT JOIN users u ON u.user_id=t.user_id ORDER BY t.last_seen DESC"):
            self.dev_tree.insert("", "end", iid=r["token"], values=(
                r.get("username") or "", r.get("device") or "", str(r.get("created_at") or "")[:16],
                str(r.get("last_seen") or "")[:16]))

    def _kick(self):
        sel = self.dev_tree.selection()
        if not sel or not self._can_set():
            return
        for iid in sel:
            db.execute("DELETE FROM mobile_tokens WHERE token=?", (iid,))
        try:
            from modules.doc_actions import audit
            audit("sign_out", "mobile_device", None, "%d device(s) signed out" % len(sel))
        except Exception:
            pass
        self._load_devices()

    # ── Users & modules ────────────────────────────────────────
    def _build_users(self):
        C = self.C
        wrap = tk.Frame(self.t_users, bg=C["content_bg"]); wrap.pack(fill="both", expand=True, padx=6, pady=6)
        left = tk.Frame(wrap, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True)
        cols = ["user", "name"] + M.MODULE_KEYS + ["van"]
        self.u_tree = ttk.Treeview(left, columns=cols, show="headings", height=14)
        heads = {"user": ("User", 100), "name": ("Name", 140), "van": ("Van code", 80)}
        short = {"goods_in": "In", "goods_out": "Out", "count": "Count", "adjust": "Adjust",
                 "info": "Info", "price": "Price", "van": "Van", "po": "PO", "labels": "Labels",
                 "poster": "Poster"}
        for k in M.MODULE_KEYS:
            heads[k] = (short[k], 58)
        cols = ["user", "name"] + M.MODULE_KEYS + ["vancode"]
        heads["vancode"] = ("Van code", 80)
        self.u_tree.configure(columns=cols)
        for k in cols:
            self.u_tree.heading(k, text=heads[k][0]); self.u_tree.column(k, width=heads[k][1],
                                                                          anchor="w" if k in ("user", "name") else "center")
        self.u_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.u_tree.bind("<<TreeviewSelect>>", lambda e: self._pick_user())
        right = tk.Frame(wrap, bg=C["card_bg"], width=300, highlightbackground=C["border"], highlightthickness=1)
        right.pack(side="right", fill="y", padx=(8, 0)); right.pack_propagate(False)
        self.u_title = tk.Label(right, text="Pick a user", font=("Segoe UI", 11, "bold"), bg=C["card_bg"],
                                fg=C["text_primary"])
        self.u_title.pack(anchor="w", padx=12, pady=(10, 4))
        self.mod_vars = {}
        for k, en, ar, ic in M.MODULES:
            v = tk.BooleanVar(value=False); self.mod_vars[k] = v
            tk.Checkbutton(right, text="%s  %s  ·  %s" % (ic, en, ar), variable=v, bg=C["card_bg"],
                           activebackground=C["card_bg"], font=("Segoe UI", 10)).pack(anchor="w", padx=12)
        self.u_active = tk.BooleanVar(value=True)
        tk.Checkbutton(right, text="Mobile access ON", variable=self.u_active, bg=C["card_bg"],
                       activebackground=C["card_bg"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(right, text="Van code (van sales over the internet)", bg=C["card_bg"], font=("Segoe UI", 8),
                 fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(8, 0))
        self.u_van = tk.StringVar()
        tk.Entry(right, textvariable=self.u_van, relief="solid", bd=1).pack(fill="x", padx=12)
        tk.Label(right, text="New van PIN (4-8 digits, leave empty = keep)", bg=C["card_bg"], font=("Segoe UI", 8),
                 fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(6, 0))
        self.u_pin = tk.StringVar()
        tk.Entry(right, textvariable=self.u_pin, relief="solid", bd=1, show="●").pack(fill="x", padx=12)
        self.u_msg = tk.StringVar()
        tk.Label(right, textvariable=self.u_msg, bg=C["card_bg"], fg=C["primary"], font=("Segoe UI", 9),
                 wraplength=270, justify="left").pack(anchor="w", padx=12, pady=6)
        self._btn(right, "💾 Save", self._save_user, primary=True).pack(fill="x", padx=12)
        tk.Label(right, text="Phone / PDT sign-in = DayBill user name + password.\n"
                             "Van over the internet = van code + PIN.", bg=C["card_bg"],
                 fg=C["text_secondary"], font=("Segoe UI", 8), justify="left",
                 wraplength=270).pack(anchor="w", padx=12, pady=10)
        self._load_users()

    def _load_users(self):
        self.u_tree.delete(*self.u_tree.get_children())
        for u in M._all("SELECT user_id, username, full_name_en, is_active FROM users ORDER BY username"):
            a = M.access(u["user_id"])
            vals = [u["username"], u.get("full_name_en") or ""] + \
                   ["✓" if (a["active"] and k in a["modules"]) else "·" for k in M.MODULE_KEYS] + [a.get("van_code") or ""]
            self.u_tree.insert("", "end", iid=str(u["user_id"]), values=vals)

    def _pick_user(self):
        sel = self.u_tree.selection()
        if not sel:
            return
        uid = int(sel[0])
        keep = getattr(self, "_cur_uid", None) == uid
        self._cur_uid = uid
        a = M.access(uid)
        self.u_title.configure(text=self.u_tree.item(sel[0], "values")[0])
        for k, v in self.mod_vars.items():
            v.set(k in a["modules"])
        self.u_active.set(a["active"] or not M._one("SELECT 1 AS x FROM mobile_access WHERE user_id=?", (uid,)))
        self.u_van.set(a.get("van_code") or "")
        self.u_pin.set("")
        if not keep:
            self.u_msg.set("")

    def _save_user(self):
        from modules import permissions as _pm
        if not _pm.allowed("users", "edit"):
            return False
        sel = self.u_tree.selection()
        if not sel:
            self.u_msg.set("Pick a user on the left."); return
        uid = int(sel[0])
        mods = [k for k, v in self.mod_vars.items() if v.get()]
        van = self.u_van.get().strip().upper()
        pin = self.u_pin.get().strip()
        if pin and (not pin.isdigit() or not 4 <= len(pin) <= 8):
            self.u_msg.set("PIN: 4 to 8 digits."); return
        if "van" in mods and van:
            other = M._one("SELECT user_id FROM mobile_access WHERE van_code=? AND user_id<>?", (van, uid))
            if other:
                self.u_msg.set("Van code %s is used by another user." % van); return
            row = M._one("SELECT van_pin_hash FROM mobile_access WHERE user_id=?", (uid,))
            if not pin and not (row or {}).get("van_pin_hash"):
                self.u_msg.set("Give this van a PIN."); return
        M.set_access(uid, mods, active=self.u_active.get(), van_code=van or None, van_pin=pin or None)
        if not self.u_active.get() or not mods:
            db.execute("DELETE FROM mobile_tokens WHERE user_id=?", (uid,))
        self.u_pin.set("")
        self.u_msg.set("✔ Saved." + (" Press Van ▸ Sync now so the van can sign in." if van and pin else ""))
        self._load_users()
        self.u_tree.selection_set(str(uid))

    # ── Inbox ──────────────────────────────────────────────────
    def _build_inbox(self):
        C = self.C
        bar = tk.Frame(self.t_inbox, bg=C["content_bg"]); bar.pack(fill="x", padx=6, pady=6)
        self.in_filter = tk.StringVar(value="Waiting")
        for t_ in ("Waiting", "Problems", "All"):
            tk.Radiobutton(bar, text=t_, value=t_, variable=self.in_filter, command=self._load_inbox,
                           bg=C["content_bg"], activebackground=C["content_bg"],
                           font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
        self._btn(bar, "🔄 Refresh", self._load_inbox).pack(side="right")
        self._btn(bar, "✖ Reject", self._reject, danger=True).pack(side="right", padx=4)
        self._btn(bar, "📂 Open in DayBill", self._open_doc).pack(side="right", padx=4)
        self._btn(bar, "🖨 Print PDF", self._print_doc).pack(side="right", padx=4)
        self._btn(bar, "✔ Approve", self._approve, primary=True).pack(side="right", padx=4)
        pw = tk.PanedWindow(self.t_inbox, orient="vertical", bg=C["content_bg"], sashwidth=6)
        pw.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        tf = tk.Frame(pw, bg=C["card_bg"])
        cols = ("id", "time", "type", "title", "user", "device", "status", "result")
        self.in_tree = ttk.Treeview(tf, columns=cols, show="headings", height=12)
        for k, t_, w in (("id", "#", 50), ("time", "Time", 120), ("type", "Type", 100), ("title", "What", 240),
                         ("user", "User", 90), ("device", "Device", 100), ("status", "Status", 80),
                         ("result", "Result", 360)):
            self.in_tree.heading(k, text=t_); self.in_tree.column(k, width=w, anchor="w")
        self.in_tree.tag_configure("pending", background="#FFF7E6")
        self.in_tree.tag_configure("error", background="#FEF2F2")
        self.in_tree.pack(fill="both", expand=True)
        self.in_tree.bind("<<TreeviewSelect>>", lambda e: self._show_lines())
        self.in_tree.bind("<Double-1>", lambda e: self._open_doc())
        pw.add(tf, height=300)
        self.in_lines = tk.Text(pw, height=8, font=("Consolas", 9), relief="flat")
        pw.add(self.in_lines)
        self._load_inbox()

    def _load_inbox(self):
        f = self.in_filter.get()
        rows = [r for r in M.inbox("pending" if f == "Waiting" else ("error" if f == "Problems" else None))
                if r.get("doc_id") is not None]
        self._inbox = {str(r["doc_id"]): r for r in rows}
        self.in_tree.delete(*self.in_tree.get_children())
        for r in rows:
            self.in_tree.insert("", "end", iid=str(r["doc_id"]), tags=(r.get("status") or "",), values=(
                r["doc_id"], str(r.get("created_at") or "")[:16].replace("T", " "),
                M.DOC_TITLES.get(r.get("doc_type"), r.get("doc_type") or ""), r.get("title") or "",
                r.get("username") or "", r.get("device") or "", r.get("status") or "", r.get("result") or ""))
        n = M._one("SELECT COUNT(*) AS n FROM mobile_docs WHERE status='pending'") or {}
        try:
            self.nb.tab(self.t_inbox, text="  📥 Inbox%s  " % (" (%d)" % n["n"] if n.get("n") else ""))
        except Exception:
            pass

    def _sel_doc(self):
        sel = self.in_tree.selection()
        return self._inbox.get(sel[0]) if sel else None

    def _show_lines(self):
        d = self._sel_doc()
        self.in_lines.delete("1.0", "end")
        if not d:
            return
        names = {}
        try:
            lines = json.loads(d.get("lines_json") or "[]")
            head = json.loads(d.get("header_json") or "{}")
        except Exception:
            lines, head = [], {}
        txt = "  ".join("%s: %s" % (k, v) for k, v in head.items() if v not in (None, "")) + "\n"
        for ln in lines:
            pid = ln.get("product_id")
            if pid not in names:
                p = M._one("SELECT product_code, product_name_en FROM products WHERE product_id=?", (pid,)) or {}
                names[pid] = "%s  %s" % (p.get("product_code") or "", p.get("product_name_en") or pid)
            txt += "%-46s %s%8s %-8s%s\n" % (names[pid][:46], "−" if (ln.get("sign") or 1) < 0 else " ",
                                            ("%g" % float(ln.get("qty") or 0)), ln.get("unit") or "",
                                            ("  @ %.2f" % float(ln.get("price") or ln.get("cost") or 0))
                                            if (ln.get("price") or ln.get("cost")) else "")
        self.in_lines.insert("1.0", txt)

    # the right needed to approve / reject each kind of document
    _DOC_RIGHT = {"goods_in": ("purchase", "add"), "van_sale": ("sales", "add"),
                  "po": ("purchase", "add"), "labels": ("products", "print"),
                  "poster": ("products", "edit"),
                  "goods_out": ("stock_adjustment", "approve"),
                  "adjust": ("stock_adjustment", "approve"),
                  "count": ("stock_adjustment", "approve")}

    def _doc_allowed(self, d):
        mod, act = self._DOC_RIGHT.get(d.get("doc_type"), ("stock_adjustment", "approve"))
        return perm.allowed(mod, act, parent=self.frame)

    def _approve(self):
        from modules import permissions as _pm
        d = self._sel_doc()
        if not d or d["status"] not in ("pending", "error"):
            return
        if not self._doc_allowed(d):
            return False
        try:
            uid = (_pm.session_user() or {}).get("user_id")
            r = M.apply_doc(d["doc_id"], by_user=uid)
            messagebox.showinfo("Inbox", r.get("result") or "Done")
        except M.MobileError as e:
            messagebox.showerror("Inbox", str(e))
        self._load_inbox()

    def _reject(self):
        from modules import permissions as _pm
        d = self._sel_doc()
        if not d or d["status"] not in ("pending", "error"):
            return
        if not self._doc_allowed(d):        # same right as Approve
            return False
        why = simpledialog.askstring("Reject", "Why? (the device user sees this)", parent=self.frame) or ""
        M.reject_doc(d["doc_id"], why, (_pm.session_user() or {}).get("user_id"))
        try:
            from modules.doc_actions import audit
            audit("reject", "mobile", d["doc_id"], "%s — %s" % (d.get("title") or d.get("doc_type"), why))
        except Exception:
            pass
        self._load_inbox()

    def _open_doc(self):
        d = self._sel_doc()
        if not d:
            return
        try:
            if d.get("ref_table") == "purchase_invoices" and d.get("ref_id"):
                from ui.purchases import PurchaseForm
                PurchaseForm(self.frame, d["ref_id"], None)
            elif d.get("ref_table") == "sales_invoices" and d.get("ref_id"):
                from ui.invoices import InvoiceForm
                InvoiceForm(self.frame, invoice_id=d["ref_id"])
            elif d.get("doc_type") in M.FILE_DOCS and os.path.isfile(M.doc_file(d["doc_id"], d["doc_type"])):
                from modules import printer_service as ps
                ps.open_file(M.doc_file(d["doc_id"], d["doc_type"]))
            elif d.get("ref_table") == "purchase_orders" and d.get("ref_id"):
                from ui.quotes import DocForm
                DocForm(self.frame, kind="purchase_order", doc_id=d["ref_id"])
            else:
                self._show_lines()
        except Exception as e:
            messagebox.showerror("Open", str(e)[:200])

    def _print_doc(self):
        """v7.2: print the label / poster PDF a PDT sent."""
        d = self._sel_doc()
        if not d or d.get("doc_type") not in M.FILE_DOCS:
            messagebox.showinfo("Print", "Pick a Barcode Labels or Offer Poster line.", parent=self.frame)
            return
        path = M.doc_file(d["doc_id"], d["doc_type"])
        if not os.path.isfile(path):
            messagebox.showinfo("Print", "This job has no PDF yet (status: %s)." % d.get("status"),
                                parent=self.frame)
            return
        from ui import print_menu
        print_menu.send_pdf(self.frame, path, M.DOC_TITLES.get(d["doc_type"], "PDF"),
                            "labels" if d["doc_type"] == "labels" else "a4")

    # ── Van over the internet ──────────────────────────────────
    def _build_van(self):
        C = self.C
        a = self._card(self.t_van, "Van sales over the internet — through your Hostinger site",
                       "Van phone ⇄ your Hostinger site (DayBill Van Relay) ⇄ this PC. The van sells with no signal; "
                       "bills go up when it has internet, and come into DayBill when this PC syncs. "
                       "Nothing on this PC is opened to the internet.")
        top = tk.Frame(a, bg=C["card_bg"]); top.pack(fill="x")
        g = tk.Frame(top, bg=C["card_bg"]); g.pack(side="left", fill="x", expand=True, anchor="n")
        tk.Label(g, text="Relay address", bg=C["card_bg"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.v_url = tk.StringVar(value=cfg.get("van_relay_url", "") or "")
        tk.Entry(g, textvariable=self.v_url, width=48, relief="solid", bd=1).grid(row=0, column=1, sticky="w", padx=6, pady=3)
        tk.Label(g, text="e.g. https://van.yourshop.com/", bg=C["card_bg"], fg=C["text_secondary"],
                 font=("Segoe UI", 8)).grid(row=0, column=2, sticky="w")
        tk.Label(g, text="Shop key", bg=C["card_bg"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        self.v_key = tk.StringVar(value=cfg.get("van_relay_key", "") or "")
        self.key_e = tk.Entry(g, textvariable=self.v_key, width=48, relief="solid", bd=1, show="●")
        self.key_e.grid(row=1, column=1, sticky="w", padx=6, pady=3)
        tk.Checkbutton(g, text="show", bg=C["card_bg"], activebackground=C["card_bg"],
                       command=lambda: self.key_e.configure(show="" if self.key_e.cget("show") else "●")
                       ).grid(row=1, column=2, sticky="w")
        tk.Label(g, text="Auto sync every (minutes, 0 = off)", bg=C["card_bg"], font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w")
        self.v_auto = tk.StringVar(value=str(cfg.get("van_auto_sync_min", 0) or 0))
        tk.Entry(g, textvariable=self.v_auto, width=6, relief="solid", bd=1).grid(row=2, column=1, sticky="w", padx=6, pady=3)
        tk.Label(g, text="Van phones open", bg=C["card_bg"], font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w")
        self.v_phone = tk.StringVar()
        tk.Label(g, textvariable=self.v_phone, bg=C["card_bg"], fg=C["primary"], font=("Segoe UI", 10, "bold"),
                 cursor="hand2").grid(row=3, column=1, columnspan=2, sticky="w", padx=6, pady=3)
        self.v_qr = tk.Label(top, bg=C["card_bg"]); self.v_qr.pack(side="right", padx=(8, 0))
        b = tk.Frame(a, bg=C["card_bg"]); b.pack(fill="x", pady=(8, 0))
        self._btn(b, "💾 Save", self._van_save).pack(side="left")
        self._btn(b, "🔌 Test connection", self._van_test).pack(side="left", padx=6)
        self.sync_btn = self._btn(b, "⟳ Sync now", self._van_sync, primary=True)
        self.sync_btn.pack(side="left", padx=6)
        self._btn(b, "🌐 Check page", self._van_check).pack(side="left", padx=6)
        self.v_msg = tk.StringVar(value=("Last sync: %s" % cfg.get("van_last_sync")) if cfg.get("van_last_sync") else "")
        tk.Label(a, textvariable=self.v_msg, bg=C["card_bg"], fg=C["primary"], font=("Segoe UI", 10, "bold"),
                 wraplength=900, justify="left").pack(anchor="w", pady=(8, 0))
        s = self._card(self.t_van, "Set up once",
                       "1. Hostinger ▸ Databases ▸ MySQL: create a database + user (write down the names and the password).\n"
                       "2. Here: “📁 Make upload folder…” — type those details. DayBill makes daybill_van_upload.zip "
                       "(the relay, the van app and your secret shop key).\n"
                       "3. Hostinger ▸ File Manager ▸ open the folder of your sub-domain ▸ Upload the zip ▸ right-click it "
                       "▸ Extract (here) ▸ delete the zip.\n"
                       "4. Type the sub-domain above (https://…/) ▸ 🔌 Test connection ▸ ⟳ Sync now. "
                       "Something wrong? 🌐 Check page shows what and how to fix it.\n"
                       "5. Users & modules: tick 🚚 Van for the driver, give a van code + PIN ▸ Save ▸ Sync now.\n"
                       "6. Van phone: Chrome ▸ the “Van phones open” address (or scan the QR) ▸ ⋮ ▸ Add to Home screen "
                       "▸ sign in with van code + PIN.\n"
                       "New DayBill version? “📁 Make upload folder…” ▸ Update files only ▸ upload + extract the zip "
                       "(the site keeps its settings).")
        self._btn(s, "📁 Make upload folder…", self._van_folder, primary=True).pack(anchor="w")
        self._van_paint()

    def _van_paint(self):
        from modules import van_sync as VS
        u = VS.phone_url()
        self.v_phone.set(u or "—  (type the relay address and Save)")
        try:
            if not u:
                raise ValueError
            import qrcode
            from PIL import ImageTk
            self._v_qr_img = ImageTk.PhotoImage(qrcode.make(u).resize((110, 110)))
            self.v_qr.configure(image=self._v_qr_img)
        except Exception:
            self.v_qr.configure(image="")

    def _van_save(self):
        # nothing changed = nothing to save (Test / Sync call this first)
        try:
            auto_new = max(0, int(float(self.v_auto.get() or 0)))
        except ValueError:
            auto_new = 0
        try:
            auto_old = int(float(cfg.get("van_auto_sync_min", 0) or 0))
        except ValueError:
            auto_old = 0
        same = (self.v_url.get().strip() == (cfg.get("van_relay_url", "") or "")
                and self.v_key.get().strip() == (cfg.get("van_relay_key", "") or "")
                and auto_new == auto_old)
        if same:
            self.v_msg.set("✔ Saved.")
            return True
        if not self._can_set():
            # put the saved values back
            self.v_url.set(cfg.get("van_relay_url", "") or "")
            self.v_key.set(cfg.get("van_relay_key", "") or "")
            self.v_auto.set(str(auto_old))
            return False
        cfg.set("van_relay_url", self.v_url.get().strip())
        cfg.set("van_relay_key", self.v_key.get().strip())
        try:
            cfg.set("van_auto_sync_min", max(0, int(float(self.v_auto.get() or 0))))
        except ValueError:
            cfg.set("van_auto_sync_min", 0)
        cfg.save_settings()
        _schedule(self.root)
        self._van_paint()
        self.v_msg.set("✔ Saved.")
        return True

    def _van_check(self):
        self._van_save()
        from modules import van_sync as VS
        u = VS.check_page_url()
        if not u:
            self.v_msg.set("Type the relay address first."); return
        import webbrowser
        webbrowser.open(u)
        self.v_msg.set("Opened %s in your browser — it shows what is wrong and how to fix it. "
                       "(Also try it with http:// in front.)" % u)

    def _van_test(self):
        self._van_save()
        from modules import van_sync as VS
        self.v_msg.set("Testing…"); self.frame.update_idletasks()

        from modules.mobile_server import MainThreadRunner
        runner = _BG["runner"] or MainThreadRunner(self.root)
        _BG["runner"] = runner

        def work():
            err = None
            try:
                m = VS.test()
            except Exception as e:
                m, err = "⚠ " + str(e), e

            def show():
                self.v_msg.set(m)
                self.v_url.set(cfg.get("van_relay_url", "") or "")   # the address may have been corrected
                self._van_paint()
                alt = getattr(err, "http_ok", None)
                if alt and messagebox.askyesno(
                        "Van relay",
                        "https does not work on your site yet, but the http address works:\n%s\n\n"
                        "Use http for now? (Not encrypted. Van phones need https to open the app with no "
                        "signal — fix https with 🌐 Check page; DayBill goes back to https by itself when it "
                        "works.)" % alt, parent=self.frame):
                    self.v_url.set(alt)
                    self._van_test()
            runner.q.put((show, {}, threading.Event()))
        threading.Thread(target=work, daemon=True).start()

    def _van_sync(self):
        # Sync now books the van bills as sales
        if not perm.allowed("sales", "add", parent=self.frame):
            return
        self._van_save()
        self.v_msg.set("Syncing…")
        self.sync_btn.configure(state="disabled")

        def done(msg):
            try:
                self.v_msg.set(msg)
                self.sync_btn.configure(state="normal")
                self._load_inbox()
            except Exception:
                pass
        if not van_sync_bg(self.root, done):
            self.v_msg.set("A sync is already running…")
            self.sync_btn.configure(state="normal")

    def _van_folder(self):
        if not self._can_set():
            return
        C = self.C
        top = tk.Toplevel(self.frame); top.title("Make upload folder"); top.configure(bg=C["card_bg"])
        mode = tk.StringVar(value="update" if cfg.get("van_relay_key") else "new")
        tk.Label(top, text="What do you need?", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 2))
        for i, (v, t) in enumerate((("update", "Update files only — my site already has relay_config.php (keeps "
                                               "its database + shop key)"),
                                    ("new", "First time / new database — make relay_config.php too"))):
            tk.Radiobutton(top, text=t, variable=mode, value=v, bg=C["card_bg"], activebackground=C["card_bg"],
                           anchor="w", justify="left", wraplength=420,
                           command=lambda: paint()).grid(row=1 + i, column=0, columnspan=2, sticky="w", padx=12)
        tk.Label(top, text="Hostinger MySQL database (Databases ▸ MySQL Databases)", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"]).grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))
        vals, ents = {}, []
        for i, (k, lbl, d) in enumerate((("host", "Host", "localhost"), ("name", "Database name", ""),
                                         ("user", "User name", ""), ("password", "Password", ""))):
            tk.Label(top, text=lbl, bg=C["card_bg"]).grid(row=i + 4, column=0, sticky="w", padx=12, pady=3)
            v = tk.StringVar(value=d); vals[k] = v
            e = tk.Entry(top, textvariable=v, width=34, show="●" if k == "password" else "", relief="solid", bd=1)
            e.grid(row=i + 4, column=1, padx=12, pady=3); ents.append(e)

        def paint():
            for e in ents:
                e.configure(state="disabled" if mode.get() == "update" else "normal")
        paint()
        res = {}

        def ok():
            mysql = None
            if mode.get() == "new":
                if not vals["name"].get().strip() or not vals["user"].get().strip():
                    messagebox.showwarning("Upload folder", "Type the database name and user.", parent=top); return
                mysql = {k: v.get().strip() for k, v in vals.items()}
            folder = filedialog.askdirectory(title="Where to make the upload folder", parent=top)
            if not folder:
                return
            from modules import van_sync as VS
            dest = os.path.join(folder, "daybill_van_upload")
            try:
                _d, key = VS.build_upload_folder(dest, mysql)
            except Exception as e:
                messagebox.showerror("Upload folder", str(e)[:200], parent=top); return
            if key:
                self.v_key.set(key)
            res["dest"], res["mysql"] = dest, bool(mysql)
            top.destroy()
        self._btn(top, "📁 Choose folder and make it", ok, primary=True).grid(row=9, column=0, columnspan=2,
                                                                           sticky="ew", padx=12, pady=12)
        top.wait_window()
        if res.get("dest"):
            self.v_msg.set(
                "✔ Ready: %s.zip (and the same files in the folder %s)\n"
                "Hostinger ▸ File Manager ▸ the folder of your sub-domain ▸ Upload the zip ▸ right-click ▸ Extract "
                "▸ replace ▸ delete the zip. Then 🔌 Test connection.%s" % (
                    res["dest"], os.path.basename(res["dest"]),
                    " (relay_config.php inside is private — it holds the shop key and the DB password.)"
                    if res["mysql"] else " (Your site keeps its own relay_config.php.)"))
            try:
                from modules import printer_service as ps
                ps.open_file(os.path.dirname(res["dest"]))
            except Exception:
                pass

    def _tick(self):
        try:
            if not self.frame.winfo_exists():
                return
            self._paint_server() if self.nb.index("current") == 0 else None
            if self.nb.index("current") == 2:
                self._load_inbox()
            self.frame.after(8000, self._tick)
        except Exception:
            pass
