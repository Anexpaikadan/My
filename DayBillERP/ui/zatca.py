# ============================================================
# DayBill ERP - ZATCA e-Invoicing (Phase 2) screen
# ------------------------------------------------------------
# Not connected → 3 easy steps on one page:
#   1. shop details (as on the VAT certificate) — checked live
#   2. where: Sandbox (test) / Simulation / Production
#   3. OTP from the Fatoora portal → 🔐 Connect
#      (DayBill makes its key + request, gets the compliance certificate,
#       passes the 6 ZATCA test documents and gets the production
#       certificate — all by itself, with a live step list)
# Connected → status, counts, every document sent / waiting / rejected,
# Send now, Send again after a fix, view / save the XML.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys, os, threading, queue, webbrowser
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules.zatca import egs as E, phase2 as P

FATOORA_PORTAL = "https://fatoora.zatca.gov.sa/"
ENV_INFO = [
    ("sandbox", "🧪  Sandbox", "Test only — nothing reaches ZATCA's real system. "
                              "The OTP is filled in for you."),
    ("simulation", "🧰  Simulation", "Practice with your real VAT number: Fatoora portal ▸ "
                                    "Simulation ▸ OTP."),
    ("production", "✅  Production", "Real e-invoicing. OTP from the Fatoora portal "
                                     "(fatoora.zatca.gov.sa)."),
]
STATUS_TXT = {"waiting": "⏳ Waiting", "reported": "✅ Reported", "cleared": "✅ Cleared",
              "rejected": "❌ Rejected", "fix": "✋ Fix needed"}


class ZatcaView:
    def __init__(self, parent):
        self.parent = parent
        C = self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._q = queue.Queue()
        self._busy = False
        self._ctx = None
        self.render()
        try:
            from ui import zatca_sender
            zatca_sender.on_change(self._on_sent)
            self.frame.bind("<Destroy>", lambda e: e.widget is self.frame
                            and zatca_sender.off_change(self._on_sent))
        except Exception:
            pass

    # ── page switch ──────────────────────────────────────────
    def render(self):
        for w in self.frame.winfo_children():
            w.destroy()
        C = self.C
        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(top, text="🔐  ZATCA e-Invoicing (Phase 2)", font=("Segoe UI", 17, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        if not E.tables_ready():
            tk.Label(self.frame, text="⚠ The ZATCA tables are missing — open Updates ▸ Apply "
                                      "All Updates once, then come back.",
                     font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                     fg=C["danger"]).pack(anchor="w", padx=22, pady=20)
            return
        e = E.active()
        on = bool(e and e.get("status") == "connected")
        pill = ("✅ Connected · %s" % P.ENV_NAMES.get(e["env"], e["env"])) if on else "⏳ Not connected"
        tk.Label(top, text=pill, font=("Segoe UI", 9, "bold"),
                 bg="#ECFDF3" if on else "#FFFBEB", fg="#047857" if on else "#B45309",
                 padx=12, pady=5).pack(side="right")
        if on:
            self._dashboard(e)
        else:
            self._connect_page()

    # ============================================================
    # CONNECT
    # ============================================================
    def _card(self, title, side=None):
        C = self.C
        box = tk.Frame(self.body, bg=C["card_bg"], highlightbackground=C["border"],
                       highlightthickness=1)
        box.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(box, text=title, font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", padx=12, pady=(8, 0))
        inner = tk.Frame(box, bg=C["card_bg"]); inner.pack(fill="x", padx=12, pady=(4, 10))
        return inner

    def _connect_page(self):
        C = self.C
        tk.Label(self.frame, text="Connect DayBill to ZATCA once — after that every bill is "
                                  "signed, gets the new QR and is sent to ZATCA by itself.",
                 font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=22)
        # scrollable body (small screens)
        wrap = tk.Frame(self.frame, bg=C["content_bg"]); wrap.pack(fill="both", expand=True)
        cv = tk.Canvas(wrap, bg=C["content_bg"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        self.body = tk.Frame(cv, bg=C["content_bg"])
        win = cv.create_window((0, 0), window=self.body, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.bind("<Configure>", lambda ev: cv.itemconfig(win, width=ev.width))
        self.body.bind("<Configure>", lambda ev: cv.configure(scrollregion=cv.bbox("all")))
        sb.pack(side="right", fill="y"); cv.pack(side="left", fill="both", expand=True)
        self._canvas = cv

        # v6.5: do I have to connect (25th wave) + what ZATCA would reject
        self._ready_box = self._card("🩺  BEFORE YOU CONNECT  —  do you need Phase 2, and is your data ready?")
        self._render_ready(self._ready_box)

        # 1. details
        d = self._card("1.  YOUR SHOP DETAILS  (exactly as on your VAT certificate / national address)")
        comp = E.company()
        self.vars, self.marks = {}, {}
        for i, (key, label, rule) in enumerate(E.DETAIL_FIELDS):
            r, col = divmod(i, 3)
            cell = tk.Frame(d, bg=C["card_bg"]); cell.grid(row=r, column=col, sticky="w", padx=(0, 18), pady=3)
            tk.Label(cell, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w")
            line = tk.Frame(cell, bg=C["card_bg"]); line.pack(anchor="w")
            v = tk.StringVar(value=str(comp.get(key) or ""))
            ent = tk.Entry(line, textvariable=v, width=26, font=("Segoe UI", 10), relief="solid",
                           bd=1, justify="right" if key.endswith("_ar") else "left")
            ent.pack(side="left", ipady=2)
            m = tk.Label(line, text="", font=("Segoe UI", 9, "bold"), bg=C["card_bg"], width=2)
            m.pack(side="left", padx=4)
            v.trace_add("write", lambda *a, k=key: self._check_field(k))
            self.vars[key], self.marks[key] = v, m
        self.detail_msg = tk.Label(d, text="", font=("Segoe UI", 9), bg=C["card_bg"],
                                   fg=C["danger"], justify="left", anchor="w")
        self.detail_msg.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        for k in self.vars:
            self._check_field(k)

        # 2. where
        w = self._card("2.  WHERE TO CONNECT")
        last = str(cfg.get("zatca_env_last", "sandbox") or "sandbox")
        self.env_v = tk.StringVar(value=last if last in P.ENV_URLS else "sandbox")
        self.env_btns = {}
        row = tk.Frame(w, bg=C["card_bg"]); row.pack(fill="x")
        for key, title, desc in ENV_INFO:
            f = tk.Frame(row, bg="#F8FAFC", highlightthickness=2, highlightbackground=C["border"],
                         cursor="hand2")
            f.pack(side="left", padx=(0, 10), fill="y")
            t = tk.Label(f, text=title, font=("Segoe UI", 11, "bold"), bg="#F8FAFC", cursor="hand2")
            t.pack(anchor="w", padx=10, pady=(6, 0))
            ds = tk.Label(f, text=desc, font=("Segoe UI", 8), bg="#F8FAFC", fg=C["text_secondary"],
                          wraplength=230, justify="left", cursor="hand2")
            ds.pack(anchor="w", padx=10, pady=(0, 6))
            for x in (f, t, ds):
                x.bind("<Button-1>", lambda e, k=key: self._set_env(k))
            self.env_btns[key] = (f, t, ds)
        r2 = tk.Frame(w, bg=C["card_bg"]); r2.pack(fill="x", pady=(8, 0))
        tk.Label(r2, text="Branch name", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.branch_v = tk.StringVar(value=str(cfg.get("zatca_branch", "") or "Main Branch"))
        tk.Entry(r2, textvariable=self.branch_v, width=22, font=("Segoe UI", 10), relief="solid",
                 bd=1).pack(side="left", padx=(4, 16), ipady=2)
        tk.Label(r2, text="Business type", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.industry_v = tk.StringVar(value=str(comp.get("business_type") or "Retail"))
        ttk.Combobox(r2, textvariable=self.industry_v, width=18,
                     values=["Retail", "Supermarket", "Wholesale", "Restaurant", "Pharmacy",
                             "Services", "Trading", "Other"]).pack(side="left", padx=4)
        # v6.0: one ZATCA unit per till (own counter + hash chain)
        self.till_v = tk.BooleanVar(value=False)
        self._till_id = None
        try:
            _cid = E.this_counter()
            if _cid:
                from modules import branches as _br
                _bn, _cn = _br.labels()
                self._till_id = _cid
                self.till_v.set(bool(E.units()))      # a 2nd unit is normally for one till
                r2b = tk.Frame(w, bg=C["card_bg"]); r2b.pack(fill="x", pady=(8, 0))
                tk.Checkbutton(r2b, text="Connect THIS till only (%s) as its own ZATCA unit — "
                                         "recommended when the shop has more than one till" % (_cn or _cid),
                               variable=self.till_v, bg=C["card_bg"], activebackground=C["card_bg"],
                               font=("Segoe UI", 9)).pack(side="left")
        except Exception:
            pass

        # 3. OTP + connect
        o = self._card("3.  OTP  +  CONNECT")
        help_ = ("Get the OTP:  fatoora.zatca.gov.sa ▸ log in ▸ Onboard new solution unit / device ▸ "
                 "number of OTP codes 1 ▸ Generate.  The OTP works for 1 hour.")
        self.otp_help = tk.Label(o, text=help_, font=("Segoe UI", 9), bg=C["card_bg"],
                                 fg=C["text_secondary"], wraplength=900, justify="left")
        self.otp_help.pack(anchor="w")
        r3 = tk.Frame(o, bg=C["card_bg"]); r3.pack(fill="x", pady=(8, 0))
        tk.Label(r3, text="OTP", font=("Segoe UI", 11, "bold"), bg=C["card_bg"]).pack(side="left")
        self.otp_v = tk.StringVar()
        self.otp_e = tk.Entry(r3, textvariable=self.otp_v, width=10, font=("Consolas", 18, "bold"),
                              relief="solid", bd=1, justify="center")
        self.otp_e.pack(side="left", padx=8, ipady=2)
        tk.Button(r3, text="🌐  Open Fatoora portal", font=("Segoe UI", 9), bg=C["card_bg"],
                  relief="flat", padx=10, pady=5, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1,
                  command=lambda: webbrowser.open(FATOORA_PORTAL)).pack(side="left", padx=6)
        self.connect_btn = tk.Button(r3, text="🔐  Connect to ZATCA", font=("Segoe UI", 12, "bold"),
                                     bg=C.get("tile_green", "#16A34A"), fg="white", relief="flat",
                                     padx=22, pady=8, cursor="hand2", command=self._connect)
        self.connect_btn.pack(side="left", padx=14)
        # steps
        self.step_lbls = {}
        sf = tk.Frame(o, bg=C["card_bg"]); sf.pack(fill="x", pady=(10, 0))
        for key, text in E.STEPS:
            l = tk.Label(sf, text="○  " + text, font=("Segoe UI", 10), bg=C["card_bg"],
                         fg=C["text_secondary"], anchor="w")
            l.pack(anchor="w")
            self.step_lbls[key] = (l, text)
        self.connect_msg = tk.Label(o, text="", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                                    fg=C["danger"], wraplength=900, justify="left", anchor="w")
        self.connect_msg.pack(anchor="w", pady=(6, 0))
        self._set_env(self.env_v.get())

    def _check_field(self, key):
        rule = next(r for k, _l, r in E.DETAIL_FIELDS if k == key)
        v = self.vars[key].get()
        prob = E.check_value(rule, v)
        if key in ("company_name_en", "company_name_ar") and prob == "missing":
            other = "company_name_ar" if key == "company_name_en" else "company_name_en"
            if other in self.vars and self.vars[other].get().strip():
                prob = ""
        ok = not prob
        self.marks[key].config(text="✓" if ok else "✗", fg="#16A34A" if ok else "#DC2626")
        return prob

    def _detail_problems(self):
        out = []
        for key, label, _r in E.DETAIL_FIELDS:
            p = self._check_field(key)
            if p:
                out.append("%s — %s" % (label, p))
        return out

    def _set_env(self, key):
        self.env_v.set(key)
        C = self.C
        for k, (f, t, ds) in self.env_btns.items():
            on = k == key
            bg = "#EEF2FF" if on else "#F8FAFC"
            f.config(highlightbackground=C["primary"] if on else C["border"], bg=bg)
            t.config(bg=bg, fg=C["primary"] if on else C["text_primary"])
            ds.config(bg=bg)
        if key == "sandbox":
            self.otp_v.set(P.SANDBOX_OTP)
            self.otp_help.config(text="Sandbox: the test OTP %s is filled in for you — just press "
                                      "Connect." % P.SANDBOX_OTP)
        else:
            if self.otp_v.get() == P.SANDBOX_OTP:
                self.otp_v.set("")
            self.otp_help.config(text="Get the OTP:  fatoora.zatca.gov.sa ▸ log in ▸ "
                                 + ("Simulation ▸ " if key == "simulation" else "")
                                 + "Onboard new solution unit / device ▸ number of OTP codes 1 ▸ "
                                   "Generate.  The OTP works for 1 hour.")

    def _step(self, key, state, text=""):
        if key not in self.step_lbls:
            return
        lbl, base = self.step_lbls[key]
        icon, col = {"run": ("⏳", "#2563EB"), "ok": ("✅", "#16A34A"),
                     "fail": ("❌", "#DC2626")}.get(state, ("○", self.C["text_secondary"]))
        lbl.config(text="%s  %s%s" % (icon, base, ("   — " + text) if text else ""), fg=col)

    def _connect(self):
        if self._busy:
            return
        probs = self._detail_problems()
        if probs:
            self.detail_msg.config(text="Fill these first:  " + "   ·   ".join(probs))
            self.connect_msg.config(text="⚠ Some shop details are missing — see step 1.")
            return
        self.detail_msg.config(text="")
        env = self.env_v.get()
        if env == "production" and not messagebox.askyesno(
                "ZATCA", "Connect to PRODUCTION?\n\nFrom now on every bill is signed and sent to "
                "ZATCA for real.", parent=self.frame):
            return
        try:
            E.save_details({k: v.get() for k, v in self.vars.items()})
            cfg.set("zatca_env_last", env)
            cfg.set("zatca_branch", self.branch_v.get().strip())
            cfg.save_settings()
        except Exception:
            pass
        for k in self.step_lbls:
            self._step(k, "")
        self.connect_msg.config(text="", fg=self.C["danger"])
        try:
            self._ctx = E.start_connect(env, self.otp_v.get(), self.branch_v.get().strip(),
                                        self.industry_v.get().strip(),
                                        counter_id=self._till_id if self.till_v.get() else None)
        except ValueError as e:
            self.connect_msg.config(text="⚠ " + str(e))
            return
        except Exception as e:
            self.connect_msg.config(text="⚠ Could not make the key: %s" % str(e)[:200])
            return
        self._busy = True
        self.connect_btn.config(state="disabled", text="⏳  Connecting…")
        ctx = self._ctx

        def work():
            try:
                res = E.run_connect(ctx, lambda s, st, t: self._q.put(("step", s, st, t)))
                self._q.put(("done", res))
            except Exception as e:
                self._q.put(("error", str(e)))
        threading.Thread(target=work, daemon=True).start()
        self.frame.after(150, self._pump)

    def _pump(self):
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "step":
                    self._step(msg[1], msg[2], msg[3])
                elif msg[0] == "done":
                    self._busy = False
                    try:
                        E.finish_connect(self._ctx, msg[1])
                    except Exception as e:
                        self.connect_msg.config(text="⚠ Connected, but saving failed: %s" % e)
                        return
                    self._step("done", "ok")
                    try:
                        from ui.ui_polish import toast
                        toast(self.frame.winfo_toplevel(), "Connected to ZATCA ✓", kind="success")
                    except Exception:
                        pass
                    try:
                        from ui import zatca_sender
                        zatca_sender.kick()
                    except Exception:
                        pass
                    self.frame.after(900, self.render)
                    return
                elif msg[0] == "error":
                    self._busy = False
                    self.connect_btn.config(state="normal", text="🔐  Connect to ZATCA")
                    self.connect_msg.config(text="❌ " + msg[1] + "\n" + self._hint(msg[1]))
                    return
        except queue.Empty:
            pass
        if self._busy:
            self.frame.after(150, self._pump)

    @staticmethod
    def _hint(err):
        e = err.lower()
        if "otp" in e:
            return "→ Make a new OTP in the Fatoora portal (it works 1 hour) and press Connect again."
        if "internet" in e or "connection" in e or "server name" in e or "time" in e:
            return "→ Check the internet, the PC date & time, then press Connect again."
        if "not accepted" in e:
            return "→ Check the shop details in step 1 (VAT, CR, address) and try again."
        return "→ Press Connect again. If it keeps failing, send this message to your DayBill dealer."

    # ============================================================
    # 🩺 READINESS (v6.5)
    # ============================================================
    ICONS = {"ok": ("✔", "#16A34A"), "warn": ("⚠", "#B45309"), "fail": ("✖", "#DC2626"),
             "info": ("ℹ", "#2563EB")}

    def _render_ready(self, box):
        from modules.zatca import readiness as R
        C = self.C
        for w in box.winfo_children():
            w.destroy()
        try:
            wv = R.wave_check()
            checks = R.data_check()
        except Exception as e:
            tk.Label(box, text="Check failed: %s" % str(e)[:200], bg=C["card_bg"], fg=C["danger"]).pack(anchor="w")
            return None
        self.ready_wave, self.ready_checks = wv, checks
        col = {"ok": "#047857", "warn": "#B45309", "fail": "#B91C1C", "info": "#1D4ED8"}[wv["level"]]
        tk.Label(box, text=wv["text"], font=("Segoe UI", 10, "bold"), bg=C["card_bg"], fg=col,
                 wraplength=900, justify="left", anchor="w").pack(anchor="w", fill="x")
        yrs = "   ".join("%s: %s" % (y, "{:,.0f}".format(v)) for y, v in wv["years"].items())
        tk.Label(box, text="Taxable sales by year (SAR, before VAT):  %s   ·   %s" % (yrs, wv["note"]),
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"], wraplength=900,
                 justify="left", anchor="w").pack(anchor="w", fill="x", pady=(2, 6))
        grid = tk.Frame(box, bg=C["card_bg"]); grid.pack(fill="x")
        for i, c in enumerate(checks):
            ic, fg = self.ICONS[c["level"]]
            tk.Label(grid, text=ic, font=("Segoe UI", 11, "bold"), bg=C["card_bg"], fg=fg).grid(
                row=i, column=0, sticky="nw", padx=(0, 6))
            txt = c["title"] + (("  —  " + c["detail"]) if c["detail"] else "")
            tk.Label(grid, text=txt, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_primary"],
                     wraplength=640, justify="left", anchor="w").grid(row=i, column=1, sticky="w")
            if c["fix"]:
                tk.Label(grid, text="→ " + c["fix"], font=("Segoe UI", 8), bg=C["card_bg"], fg=fg,
                         wraplength=330, justify="left", anchor="w").grid(row=i, column=2, sticky="w", padx=(10, 0))
        n = R.summary(checks)
        bar = tk.Frame(box, bg=C["card_bg"]); bar.pack(fill="x", pady=(6, 0))
        tk.Label(bar, text=("✔ Ready" if n["ready"] else "✖ Fix the red items first") +
                 "   (%d OK · %d to look at · %d to fix)" % (n["ok"], n["warn"], n["fail"]),
                 font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg="#047857" if n["ready"] else "#B91C1C").pack(side="left")
        tk.Button(bar, text="🩺  Check again", font=("Segoe UI", 9), bg=C["card_bg"], relief="flat", padx=10,
                  pady=3, cursor="hand2", highlightthickness=1, highlightbackground=C["border"],
                  command=lambda: self._render_ready(box)).pack(side="right")
        return n

    def _check_window(self):
        C = self.C
        win = tk.Toplevel(self.frame)
        win.title("ZATCA check")
        win.configure(bg=C["content_bg"])
        win.geometry("1060x520")
        try:
            win.transient(self.frame.winfo_toplevel())
        except Exception:
            pass
        win.bind("<Escape>", lambda e: win.destroy())
        tk.Label(win, text="🩺  ZATCA check", font=("Segoe UI", 14, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=16, pady=(12, 4))
        box = tk.Frame(win, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        inner = tk.Frame(box, bg=C["card_bg"]); inner.pack(fill="both", expand=True, padx=12, pady=10)
        self._render_ready(inner)
        self.check_win = win
        return win

    def _show_fix(self):
        from modules.zatca import readiness as R
        sel = self.tree.selection()
        if not sel:
            return ""
        vals = self.tree.item(sel[0], "values")
        status, msg = vals[0], vals[-1]
        if not any(k in status for k in ("Rejected", "Fix", "Waiting")) or not msg:
            self.fix_v.set("✔ Nothing to fix for this bill." if "✅" in status else
                           "Click a rejected / waiting bill to see how to fix it.")
            return ""
        code, hint = R.fix_hint(msg)
        self.fix_v.set("How to fix%s:  %s" % ((" (%s)" % code) if code else "", hint))
        return hint

    # ============================================================
    # DASHBOARD
    # ============================================================
    def _dashboard(self, e):
        C = self.C
        info = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        info.pack(fill="x", padx=20, pady=(8, 6))
        a = tk.Frame(info, bg=C["card_bg"]); a.pack(fill="x", padx=14, pady=8)
        exp = e.get("cert_expires")
        try:
            from modules.offers import to_dt
            exp_d = to_dt(exp)
        except Exception:
            exp_d = None
        since = e.get("onboarded_at")
        try:
            from modules.offers import to_dt as _td
            since = _td(since)
        except Exception:
            pass
        self._info_base = ("Unit  %s   ·   connected %s   ·   certificate valid until %s"
                           % (e.get("egs_name") or "",
                              since.strftime("%d/%m/%Y") if hasattr(since, "strftime") else "",
                              exp_d.strftime("%d/%m/%Y") if exp_d else "—"))
        self.info_v = tk.StringVar(value=self._info_base)
        tk.Label(a, textvariable=self.info_v, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        if exp_d and (exp_d - datetime.now()).days < 30:
            tk.Label(a, text="⚠ certificate ends soon — Reconnect", font=("Segoe UI", 9, "bold"),
                     bg=C["card_bg"], fg=C["danger"]).pack(side="left", padx=10)
        # v6.0: every till's unit + key protection + 24-hour warning
        u = tk.Frame(info, bg=C["card_bg"]); u.pack(fill="x", padx=14, pady=(0, 4))
        units = E.units()
        till_txt = []
        try:
            from modules import branches as _br
            cn = {c["counter_id"]: (c.get("code") or c.get("name_en")) for c in _br.list_counters()}
        except Exception:
            cn = {}
        for x in units:
            till_txt.append("%s%s (ICV %s)" % (x.get("egs_name") or x["egs_id"],
                                               (" · till " + str(cn.get(x.get("counter_id"), x.get("counter_id"))))
                                               if x.get("counter_id") else " · whole shop",
                                               x.get("icv") or 0))
        tk.Label(u, text="Units:  " + ("   |   ".join(till_txt) or "—"), font=("Segoe UI", 8),
                 bg=C["card_bg"], fg=C["text_secondary"], wraplength=1000, justify="left").pack(side="left")
        try:
            from modules.zatca import vault as _V
            vst, vtxt = _V.status()
        except Exception:
            vst, vtxt = "none", ""
        kb = tk.Frame(info, bg=C["card_bg"]); kb.pack(fill="x", padx=14, pady=(0, 4))
        self.key_lbl = tk.Label(kb, text=vtxt, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                                fg="#047857" if vst == "protected" else "#B45309")
        self.key_lbl.pack(side="left")
        if vst == "plain":
            tk.Button(kb, text="🔒  Protect keys", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                      relief="flat", padx=10, pady=3, cursor="hand2", highlightthickness=1,
                      highlightbackground=C["border"], command=self._protect_keys).pack(side="left", padx=8)
        elif vst == "protected":
            tk.Button(kb, text="🔑  Recovery code", font=("Segoe UI", 9), bg=C["card_bg"],
                      relief="flat", padx=10, pady=3, cursor="hand2", highlightthickness=1,
                      highlightbackground=C["border"], command=self._recovery).pack(side="left", padx=8)
        if E.this_counter() and not any(x.get("counter_id") == E.this_counter() for x in units):
            tk.Button(kb, text="➕  Connect this till as its own unit", font=("Segoe UI", 9),
                      bg=C["card_bg"], relief="flat", padx=10, pady=3, cursor="hand2",
                      highlightthickness=1, highlightbackground=C["border"],
                      command=self._force_connect_page).pack(side="left", padx=8)
        od = E.overdue_text()
        if od:
            tk.Label(info, text=od, font=("Segoe UI", 10, "bold"), bg="#FEF2F2", fg="#B91C1C",
                     anchor="w", padx=10, pady=5, wraplength=1100,
                     justify="left").pack(fill="x", padx=14, pady=(0, 6))
        b = tk.Frame(info, bg=C["card_bg"]); b.pack(fill="x", padx=14, pady=(0, 8))
        tk.Button(b, text="📤  Send now", font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._send_now).pack(side="left")
        self.auto_v = tk.BooleanVar(value=bool(e.get("auto_send", 1)))
        tk.Checkbutton(b, text="Send automatically in the background", variable=self.auto_v,
                       bg=C["card_bg"], font=("Segoe UI", 9),
                       command=lambda: E.set_auto_send(self.auto_v.get())).pack(side="left", padx=12)
        tk.Button(b, text="⏻  Disconnect", font=("Segoe UI", 9), bg=C["card_bg"], fg=C["danger"],
                  relief="flat", padx=10, pady=4, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._disconnect).pack(side="right")
        tk.Button(b, text="🔄  Reconnect / renew", font=("Segoe UI", 9), bg=C["card_bg"],
                  relief="flat", padx=10, pady=4, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._reconnect).pack(side="right", padx=6)
        names = ["%s  %s" % c for c in P.VATEX_CHOICES]
        cur = str(cfg.get("zatca_vatex_z", "VATEX-SA-35") or "VATEX-SA-35")
        if cur == "VATEX-SA-36" and not cfg.flag("zatca_vatex_v692", False):
            cur = "VATEX-SA-35"            # SA-36 was wrongly labelled "medicines" before v6.9.2
        self.vatex_v = tk.StringVar(value=next((n for n in names if n.startswith(cur)), names[3]))
        cb = ttk.Combobox(b, textvariable=self.vatex_v, values=names, state="readonly", width=34)
        cb.pack(side="right")
        tk.Label(b, text="Zero-rated reason", font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="right", padx=(12, 4))
        cb.bind("<<ComboboxSelected>>", lambda ev: (cfg.set("zatca_vatex_z", self.vatex_v.get().split()[0]),
                                                    cfg.set("zatca_vatex_v692", True),
                                                     cfg.save_settings()))

        tiles = tk.Frame(self.frame, bg=C["content_bg"]); tiles.pack(fill="x", padx=20)
        self.tile_vars = {}
        for key, title, col in (("waiting", "⏳ Waiting to send", "#2563EB"),
                                ("reported", "✅ Reported (B2C)", "#16A34A"),
                                ("cleared", "✅ Cleared (B2B)", "#0F766E"),
                                ("fix", "✋ Need a fix", "#B45309"),
                                ("rejected", "❌ Rejected", "#DC2626")):
            f = tk.Frame(tiles, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1,
                         cursor="hand2")
            f.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=4)
            v = tk.StringVar(value="0")
            n = tk.Label(f, textvariable=v, font=("Segoe UI", 20, "bold"), bg=C["card_bg"], fg=col)
            n.pack(anchor="w", padx=12, pady=(4, 0))
            t = tk.Label(f, text=title, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"])
            t.pack(anchor="w", padx=12, pady=(0, 6))
            for x in (f, n, t):
                x.bind("<Button-1>", lambda ev, k=key: (self.show_v.set(STATUS_TXT.get(k, "All")),
                                                         self._fill()))
            self.tile_vars[key] = v

        bar = tk.Frame(self.frame, bg=C["content_bg"]); bar.pack(fill="x", padx=20, pady=(6, 2))
        tk.Label(bar, text="Show", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.show_v = tk.StringVar(value="All")
        sc = ttk.Combobox(bar, textvariable=self.show_v, state="readonly", width=14,
                          values=["All"] + list(STATUS_TXT.values()))
        sc.pack(side="left", padx=6)
        sc.bind("<<ComboboxSelected>>", lambda ev: self._fill())
        for txt, cmd in (("🩺  Check", self._check_window),
                         ("🔁  Send again (after a fix)", self._resend),
                         ("📄  View XML", self._view_xml), ("💾  Save XML", self._save_xml)):
            tk.Button(bar, text=txt, font=("Segoe UI", 9), bg=C["card_bg"], relief="flat",
                      padx=10, pady=3, cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1, command=cmd).pack(side="right", padx=(6, 0))

        wrap = tk.Frame(self.frame, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=20, pady=(2, 4))
        cols = [("status", "Status", 120, "w"), ("number", "No.", 110, "w"), ("date", "Date", 90, "center"),
                ("party", "Customer", 170, "w"), ("type", "Type", 130, "w"),
                ("total", "Total", 90, "e"), ("icv", "Counter", 84, "center"),
                ("msg", "ZATCA message", 380, "w")]
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for k, h, wd, an in cols:
            self.tree.heading(k, text=h, anchor="e" if an == "e" else ("w" if an == "w" else "center"))
            self.tree.column(k, width=wd, anchor=an, stretch=k in ("party", "msg"))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        for tag, bg in (("rejected", "#FEF2F2"), ("fix", "#FFFBEB"), ("waiting", "#EFF6FF")):
            self.tree.tag_configure(tag, background=bg)
        self.tree.bind("<Double-1>", lambda ev: self._view_xml())
        self.tree.bind("<<TreeviewSelect>>", lambda ev: self._show_fix())
        self.fix_v = tk.StringVar(value="Click a rejected / waiting bill to see how to fix it.")
        self.fix_lbl = tk.Label(self.frame, textvariable=self.fix_v, font=("Segoe UI", 9, "bold"), bg="#FFFBEB",
                                fg="#92400E", anchor="w", justify="left", wraplength=1100, padx=10, pady=5)
        self.log_v = tk.StringVar()
        # packed at the bottom FIRST, so a small screen squeezes the table, not these lines
        tk.Label(self.frame, textvariable=self.log_v, font=("Consolas", 8), bg=C["content_bg"],
                 fg=C["text_secondary"], anchor="w", justify="left").pack(side="bottom", fill="x", padx=22,
                                                                          pady=(0, 8), before=wrap)
        self.fix_lbl.pack(side="bottom", fill="x", padx=20, pady=(2, 2), before=wrap)
        self.fix_lbl.bind("<Configure>", lambda ev: self.fix_lbl.config(wraplength=max(300, ev.width - 30)))
        self._fill()

    def _fill(self):
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return
        st = E.stats()
        for k, v in self.tile_vars.items():
            v.set(str(st.get(k, 0)))
        try:
            e = E.active() or {}
            self.info_v.set("%s   ·   documents signed: %s" % (self._info_base, e.get("icv") or 0))
        except Exception:
            pass
        want = next((k for k, t in STATUS_TXT.items() if t == self.show_v.get()), None)
        self.tree.delete(*self.tree.get_children())
        for r in E.documents(300, only=(want,) if want else None):
            s = r.get("zatca_status") or ""
            typ = ("B2B tax invoice" if r.get("zatca_kind") == "standard" else "B2C simplified")
            if r["kind"] == "sales_return":
                typ = ("B2B" if r.get("zatca_kind") == "standard" else "B2C") + " credit note"
            msg = r.get("zatca_last_error") or r.get("zatca_warnings") or ""
            if s in ("reported", "cleared") and not msg:
                sub = r.get("zatca_submitted_at")
                msg = "sent %s" % (str(sub)[:16] if sub else "")
            self.tree.insert("", "end", iid="%s:%s" % (r["kind"], r["id"]), values=(
                STATUS_TXT.get(s, s), r.get("number") or "", str(r.get("d") or "")[:10],
                r.get("party") or "", typ, "{:,.2f}".format(float(r.get("total") or 0)),
                r.get("zatca_icv") or "—", str(msg).replace("\n", " · ")[:300]),
                tags=(s,) if s in ("rejected", "fix", "waiting") else ())
        self.log_v.set("\n".join("%s  %s" % x for x in E.LOG[-4:]))

    def _on_sent(self, _new):
        try:
            self._fill()
        except Exception:
            pass

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("ZATCA", "Select a document in the list first.", parent=self.frame)
            return None
        kind, did = sel[0].split(":")
        return kind, int(did)

    def _send_now(self):
        if self._busy:
            return
        items = E.next_items(50)
        if not items:
            self.log_v.set("Nothing is waiting — everything is sent ✓")
            return
        e = E.active()
        units = {}
        for it in items:                       # DB part first: each till's own unit
            try:
                units[it.get("egs_id")] = E.unit_for(it, e)
            except Exception as ex:
                self.log_v.set("⚠ %s" % str(ex)[:200])
                return
        self._busy = True
        self.log_v.set("📤 Sending %d document(s)…" % len(items))
        q = queue.Queue()

        def work():
            for it in items:
                st, d = E.send_one(units.get(it.get("egs_id")) or e, it)
                q.put((it, st, d))
                if st == 0:
                    break
            q.put(None)

        def poll():
            try:
                while True:
                    x = q.get_nowait()
                    if x is None:
                        self._busy = False
                        self._fill()
                        return
                    E.apply_result(*x)
                    self._fill()
            except queue.Empty:
                pass
            self.frame.after(200, poll)
        threading.Thread(target=work, daemon=True).start()
        self.frame.after(200, poll)

    def _resend(self):
        s = self._selected()
        if not s:
            return
        kind, did = s
        r = next((x for x in E.documents(500) if x["kind"] == kind and x["id"] == did), {})
        if r.get("zatca_status") not in ("fix", "rejected"):
            messagebox.showinfo("ZATCA", "Only documents with ✋ Fix needed or ❌ Rejected are sent "
                                "again.", parent=self.frame)
            return
        if r.get("zatca_status") == "rejected" and not messagebox.askyesno(
                "Send again", "ZATCA rejected this document.\n\nFixed the reason (customer / item / "
                "shop details)? DayBill signs it again with the next counter and sends it.",
                parent=self.frame):
            return
        res = E.rebuild(kind, did)
        if res and res.get("status") == "fix":
            messagebox.showwarning("Still needs a fix", "; ".join(res.get("problems", [])),
                                   parent=self.frame)
        self._fill()
        try:
            from ui import zatca_sender
            zatca_sender.kick()
        except Exception:
            pass

    def _view_xml(self):
        s = self._selected()
        if not s:
            return
        xml = E.xml_of(*s)
        if not xml:
            messagebox.showinfo("ZATCA", "No XML yet (it is signed when the problem is fixed).",
                                parent=self.frame)
            return
        top = tk.Toplevel(self.frame)
        top.title("ZATCA XML — %s %s" % s)
        top.geometry("900x620")
        top._no_close_confirm = True
        t = tk.Text(top, font=("Consolas", 9), wrap="none")
        sy = ttk.Scrollbar(top, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sy.set)
        sy.pack(side="right", fill="y"); t.pack(fill="both", expand=True)
        t.insert("1.0", xml)

    def _save_xml(self):
        s = self._selected()
        if not s:
            return
        xml = E.xml_of(*s)
        if not xml:
            return
        path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML", "*.xml")],
                                            initialfile="%s_%s.xml" % s, parent=self.frame)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)

    # ── v6.0: ZATCA key protection ─────────────────────────────
    def _protect_keys(self):
        if not messagebox.askyesno(
                "Protect ZATCA keys",
                "Lock the ZATCA private key and certificate secrets with SQL Server's own "
                "encryption?\n\nEvery DayBill PC on this server keeps signing as before. A backup "
                "restored on ANOTHER server needs the recovery code shown next — write it down.",
                parent=self.frame):
            return
        from modules.zatca import vault as V
        ok, msg, code = V.protect_all()
        if ok and code:
            msg += ("\n\nRECOVERY CODE (keep it safe — needed only when the database is moved "
                    "to another SQL Server):\n\n%s" % code)
        (messagebox.showinfo if ok else messagebox.showerror)("Protect ZATCA keys", msg,
                                                              parent=self.frame)
        self.render()

    def _recovery(self):
        from modules.zatca import vault as V
        from tkinter import simpledialog
        code = V.saved_code()
        txt = ("The recovery code saved on this PC:\n\n%s\n\n" % code) if code else ""
        val = simpledialog.askstring(
            "Recovery code", txt + "Database restored on a NEW SQL Server and bills can't be "
            "signed? Type the recovery code to open the keys there:", parent=self.frame)
        if val:
            ok, msg = V.recover(val)
            (messagebox.showinfo if ok else messagebox.showerror)("Recovery code", msg,
                                                                  parent=self.frame)

    def _disconnect(self):
        st = E.stats()
        extra = ("\n\n%d document(s) are still waiting to be sent." % st["waiting"]) if st["waiting"] else ""
        if messagebox.askyesno("Disconnect", "Stop signing and sending bills to ZATCA?" + extra,
                               parent=self.frame):
            E.disconnect()
            self.render()

    def _reconnect(self):
        if messagebox.askyesno("Reconnect", "Connect again with a new OTP (new certificate)?\n\n"
                               "Use it when the certificate ends or you move to Production.",
                               parent=self.frame):
            self._force_connect_page()

    def _force_connect_page(self):
        for w in self.frame.winfo_children():
            w.destroy()
        C = self.C
        top = tk.Frame(self.frame, bg=C["content_bg"]); top.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(top, text="🔐  ZATCA e-Invoicing (Phase 2) — reconnect", font=("Segoe UI", 17, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(top, text="← Back", font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  command=self.render).pack(side="right")
        self._connect_page()
