# ============================================================
# DayBill ERP - New Company wizard (v7.0)
# ------------------------------------------------------------
# Login ▸ ⚙ Database Settings ▸ 🆕 Create New Company…
#
#   1 Company    name (English / Arabic), database name, contact
#   2 Country    🇸🇦 Saudi Arabia · 🇦🇪 UAE · 🇮🇳 India
#                region / emirate / state, tax number (VAT No. / TRN /
#                GSTIN, checked as you type), currency symbol, prices
#                with or without tax, financial year start
#   3 Business   Retail (always) + Supermarket · Restaurant · Textiles ·
#                Production
#   4 Create     makes the database (all-in-one install script), then
#                modules/company_setup.setup() sets tax categories, tax
#                accounts, financial year and options for the country,
#                and switches DayBill to the new company
#
# NewCompanyWizard(parent, conf, on_done=None)
#   conf     the SQL Server connection (server / sign-in) to make it on
#   on_done  called with the new database name when it is ready
# ============================================================

import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from config import settings as cfg
from config.database import db, save_db_config
from modules import country as C
from modules import business as B

STEPS = ["Company", "Country", "Business", "Create"]
REG_LABEL = {"SA": "CR Number", "AE": "Trade Licence No.", "IN": "PAN / CIN (optional)"}
COUNTRY_LINE = {
    "SA": "VAT 15% · Saudi Riyal (SAR) · ZATCA e-invoice QR · VAT Return",
    "AE": "VAT 5% · UAE Dirham (AED) · TRN · VAT 201 return by emirate",
    "IN": "GST 5 / 18 / 40% · Rupee (₹) · GSTIN · CGST+SGST / IGST · GSTR-1, GSTR-3B",
}


def db_name_from(text):
    s = re.sub(r"[^A-Za-z0-9_]+", "_", str(text or "").strip()).strip("_")
    s = re.sub(r"_+", "_", s)[:40]
    return ("DayBill_" + s) if s else "DayBill_NewCompany"


class NewCompanyWizard:
    W, H = 820, 600

    def __init__(self, parent, conf, on_done=None):
        self.C = cfg.theme()
        self.conf = dict(conf or {})
        self.on_done = on_done
        self.step = 0
        self._busy = False
        self._db_touched = False
        self.win = tk.Toplevel(parent)
        self.win.title("New Company")
        self.win.configure(bg=self.C["content_bg"])
        self.win.geometry("%dx%d" % (self.W, self.H))
        self.win.minsize(760, 560)
        self.win._no_close_confirm = True
        self.win.protocol("WM_DELETE_WINDOW", self._close)
        try:
            self.win.transient(parent.winfo_toplevel())
            self.win.grab_set()
        except Exception:
            pass
        self._vars()
        self._build()
        self._show()
        self._center()

    # ── state ─────────────────────────────────────────────────
    def _vars(self):
        V = tk.StringVar
        self.v = {k: V() for k in ("name_en", "name_ar", "dbname", "phone", "email", "city",
                                   "address", "state", "tax_no", "reg_no", "symbol", "fy")}
        self.country = V(value="SA")
        self.price_incl = tk.BooleanVar(value=True)
        self.mods = {k: tk.BooleanVar(value=(k == "retail")) for k in B.KEYS}
        self.v["name_en"].trace_add("write", self._auto_dbname)
        self.v["tax_no"].trace_add("write", lambda *a: self._check_tax())
        self.v["symbol"].trace_add("write", lambda *a: self._preview())

    def _auto_dbname(self, *_):
        if not self._db_touched:
            self.v["dbname"].set(db_name_from(self.v["name_en"].get()))

    # ── layout ────────────────────────────────────────────────
    def _build(self):
        C = self.C
        head = tk.Frame(self.win, bg=C["primary"])
        head.pack(fill="x")
        tk.Label(head, text="🆕  New Company", font=("Segoe UI", 15, "bold"), bg=C["primary"],
                 fg="white").pack(side="left", padx=18, pady=12)
        self.chips = []
        chipbar = tk.Frame(head, bg=C["primary"])
        chipbar.pack(side="right", padx=14)
        for i, s in enumerate(STEPS):
            lb = tk.Label(chipbar, text="%d  %s" % (i + 1, s), font=("Segoe UI", 9, "bold"),
                          bg=C["primary"], fg="#D9D4FF", padx=10, pady=4)
            lb.pack(side="left", padx=2)
            self.chips.append(lb)
        self.body = tk.Frame(self.win, bg=C["content_bg"])
        self.body.pack(fill="both", expand=True, padx=22, pady=(14, 4))
        nav = tk.Frame(self.win, bg=C["content_bg"])
        nav.pack(fill="x", padx=22, pady=(4, 14))
        self.msg = tk.Label(nav, text="", font=("Segoe UI", 9), bg=C["content_bg"],
                            fg=C["danger"], anchor="w", justify="left", wraplength=480)
        self.msg.pack(side="left", fill="x", expand=True)
        self.next_btn = tk.Button(nav, text="Next  →", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                                  fg="white", relief="flat", padx=20, pady=7, cursor="hand2",
                                  command=self._next)
        self.next_btn.pack(side="right")
        self.back_btn = tk.Button(nav, text="←  Back", font=("Segoe UI", 10), bg=C["card_bg"],
                                  fg=C["text_primary"], relief="flat", padx=16, pady=7, cursor="hand2",
                                  highlightbackground=C["border"], highlightthickness=1,
                                  command=self._back)
        self.back_btn.pack(side="right", padx=(0, 8))
        self.win.bind("<Return>", lambda e: self._next() if not isinstance(e.widget, tk.Text) else None)
        self.win.bind("<Escape>", lambda e: self._close())
        self.pages = [self._page_company(), self._page_country(), self._page_business(),
                      self._page_create()]

    def _card(self, parent, title, sub=""):
        C = self.C
        f = tk.Frame(parent, bg=C["card_bg"], highlightbackground=C["border"], highlightthickness=1)
        tk.Label(f, text=title, font=("Segoe UI", 12, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(anchor="w", padx=16, pady=(12, 0))
        if sub:
            tk.Label(f, text=sub, font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                     wraplength=self.W - 100, justify="left").pack(anchor="w", padx=16, pady=(2, 6))
        inner = tk.Frame(f, bg=C["card_bg"])
        inner.pack(fill="both", expand=True, padx=16, pady=(4, 14))
        return f, inner

    def _field(self, parent, r, c, label, var, width=34, hint="", combo=None, readonly=False):
        C = self.C
        tk.Label(parent, text=label, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).grid(row=r, column=c, sticky="w", padx=(0, 12), pady=(6, 0))
        if combo is not None:
            w = ttk.Combobox(parent, textvariable=var, values=combo, width=width - 2,
                             state="readonly" if readonly else "normal", font=("Segoe UI", 10))
        else:
            w = ttk.Entry(parent, textvariable=var, width=width, font=("Segoe UI", 10))
        w.grid(row=r + 1, column=c, sticky="we", padx=(0, 12))
        if hint:
            tk.Label(parent, text=hint, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r + 2, column=c, sticky="w", padx=(0, 12))
        return w

    # page 1
    def _page_company(self):
        f, inner = self._card(self.body, "Company",
                              "The name prints on every bill. The database keeps this company's data "
                              "apart from any other company on this server.")
        e = self._field(inner, 0, 0, "Company name (English) *", self.v["name_en"])
        self._field(inner, 0, 1, "Company name (Arabic)", self.v["name_ar"], hint="optional")
        d = self._field(inner, 3, 0, "Database name *", self.v["dbname"],
                        hint="letters, numbers and _ only")
        d.bind("<Key>", lambda ev: setattr(self, "_db_touched", True))
        self._field(inner, 3, 1, "Phone", self.v["phone"])
        self._field(inner, 6, 0, "City", self.v["city"])
        self._field(inner, 6, 1, "Email", self.v["email"])
        self._field(inner, 9, 0, "Address", self.v["address"], width=72).grid(columnspan=2)
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)
        self._first = e
        return f

    # page 2
    def _page_country(self):
        C = self.C
        f, inner = self._card(self.body, "Country",
                              "DayBill works the way your country works: tax, currency, tax number, "
                              "bills, tax returns and reports.")
        row = tk.Frame(inner, bg=C["card_bg"])
        row.pack(fill="x")
        self.ccards = {}
        for i, code in enumerate(("SA", "AE", "IN")):
            card = tk.Frame(row, bg=C["content_bg"], highlightthickness=2, cursor="hand2",
                            highlightbackground=C["border"])
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            row.columnconfigure(i, weight=1)
            pr = _country(code)
            t1 = tk.Label(card, text="%s  %s" % (pr["flag"], pr["name"]), font=("Segoe UI", 12, "bold"),
                          bg=C["content_bg"], fg=C["text_primary"], cursor="hand2")
            t1.pack(anchor="w", padx=12, pady=(10, 2))
            t2 = tk.Label(card, text=COUNTRY_LINE[code], font=("Segoe UI", 8), bg=C["content_bg"],
                          fg=C["text_secondary"], wraplength=220, justify="left", cursor="hand2")
            t2.pack(anchor="w", padx=12, pady=(0, 10))
            for w in (card, t1, t2):
                w.bind("<Button-1>", lambda e, c=code: self._pick_country(c))
            self.ccards[code] = (card, t1, t2)
        form = tk.Frame(inner, bg=C["card_bg"])
        form.pack(fill="x", pady=(12, 0))
        self.state_lbl = tk.Label(form, text="", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                                  fg=C["text_primary"])
        self.state_lbl.grid(row=0, column=0, sticky="w", pady=(6, 0))
        self.state_cb = ttk.Combobox(form, textvariable=self.v["state"], width=32, state="readonly",
                                     font=("Segoe UI", 10))
        self.state_cb.grid(row=1, column=0, sticky="we", padx=(0, 12))
        self.tax_lbl = tk.Label(form, text="", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                                fg=C["text_primary"])
        self.tax_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))
        ttk.Entry(form, textvariable=self.v["tax_no"], width=34, font=("Segoe UI", 10)).grid(
            row=1, column=1, sticky="we", padx=(0, 12))
        self.tax_msg = tk.Label(form, text="", font=("Segoe UI", 8), bg=C["card_bg"],
                                fg=C["text_secondary"], wraplength=300, justify="left")
        self.tax_msg.grid(row=2, column=1, sticky="w")
        self.reg_lbl = tk.Label(form, text="", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                                fg=C["text_primary"])
        self.reg_lbl.grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(form, textvariable=self.v["reg_no"], width=34, font=("Segoe UI", 10)).grid(
            row=4, column=0, sticky="we", padx=(0, 12))
        tk.Label(form, text="Currency symbol", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).grid(row=3, column=1, sticky="w", pady=(6, 0))
        srow = tk.Frame(form, bg=C["card_bg"])
        srow.grid(row=4, column=1, sticky="we", padx=(0, 12))
        self.sym_cb = ttk.Combobox(srow, textvariable=self.v["symbol"], width=10, font=("Segoe UI", 10))
        self.sym_cb.pack(side="left")
        self.preview = tk.Label(srow, text="", font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                                fg=C["primary"])
        self.preview.pack(side="left", padx=10)
        tk.Label(form, text="Prices you type", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).grid(row=5, column=0, sticky="w", pady=(8, 0))
        prow = tk.Frame(form, bg=C["card_bg"])
        prow.grid(row=6, column=0, sticky="w")
        self.incl_rb = tk.Radiobutton(prow, text="include tax", variable=self.price_incl, value=True,
                                      bg=C["card_bg"], font=("Segoe UI", 9))
        self.incl_rb.pack(side="left")
        tk.Radiobutton(prow, text="without tax (tax added on the bill)", variable=self.price_incl,
                       value=False, bg=C["card_bg"], font=("Segoe UI", 9)).pack(side="left", padx=8)
        tk.Label(form, text="Financial year starts", font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).grid(row=5, column=1, sticky="w", pady=(8, 0))
        ttk.Combobox(form, textvariable=self.v["fy"], width=12, state="readonly",
                     values=["01-01  (January)", "04-01  (April)", "07-01  (July)", "10-01  (October)"],
                     font=("Segoe UI", 10)).grid(row=6, column=1, sticky="w")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        self._pick_country("SA")
        return f

    # page 3
    def _page_business(self):
        C = self.C
        f, inner = self._card(self.body, "Business",
                              "Tick what your business does. DayBill shows the screens and works the "
                              "way that business needs. You can change this later in Settings.")
        self.mcards = {}
        for i, (key, title, icon, desc) in enumerate(B.MODULES):
            card = tk.Frame(inner, bg=C["content_bg"], highlightthickness=2,
                            highlightbackground=C["border"], cursor="hand2")
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0, 8), pady=(0, 8))
            cb = tk.Checkbutton(card, text="%s  %s" % (icon, title), variable=self.mods[key],
                                font=("Segoe UI", 11, "bold"), bg=C["content_bg"],
                                activebackground=C["content_bg"], anchor="w",
                                command=self._paint_mods,
                                state="disabled" if key == "retail" else "normal")
            cb.pack(anchor="w", padx=8, pady=(8, 0))
            d = tk.Label(card, text=desc + ("  (always on)" if key == "retail" else ""),
                         font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"],
                         wraplength=330, justify="left", cursor="hand2")
            d.pack(anchor="w", padx=34, pady=(0, 10))
            if key != "retail":
                for w in (card, d):
                    w.bind("<Button-1>", lambda e, k=key: (self.mods[k].set(not self.mods[k].get()),
                                                         self._paint_mods()))
            self.mcards[key] = card
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)
        self._paint_mods()
        return f

    # page 4
    def _page_create(self):
        C = self.C
        f, inner = self._card(self.body, "Create",
                              "Check the details, then press Create company. It takes about a minute.")
        self.summary = tk.Label(inner, text="", font=("Consolas", 10), bg=C["card_bg"],
                                fg=C["text_primary"], justify="left", anchor="w")
        self.summary.pack(fill="x", anchor="w")
        self.bar = ttk.Progressbar(inner, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=(14, 4))
        self.status = tk.Label(inner, text="", font=("Segoe UI", 9), bg=C["card_bg"],
                               fg=C["text_secondary"], anchor="w", justify="left", wraplength=self.W - 100)
        self.status.pack(fill="x", anchor="w")
        return f

    # ── behaviour ─────────────────────────────────────────────
    def _pick_country(self, code):
        C = self.C
        self.country.set(code)
        for k, (card, t1, t2) in self.ccards.items():
            on = k == code
            bg = C.get("primary_light", "#EEF0FF") if on else C["content_bg"]
            card.configure(highlightbackground=C["primary"] if on else C["border"], bg=bg)
            t1.configure(bg=bg)
            t2.configure(bg=bg)
        p = _country(code)
        self.state_lbl.configure(text=p["states_label"] + (" *" if code in ("AE", "IN") else ""))
        vals = ["%s - %s" % (k, n) for k, n in p["states"]]
        self.state_cb.configure(values=vals)
        if self.v["state"].get() not in vals:
            self.v["state"].set("")
        self.tax_lbl.configure(text=p["tax_no_label"])
        self.reg_lbl.configure(text=REG_LABEL[code])
        self.sym_cb.configure(values=p["symbols"])
        if self.v["symbol"].get() not in p["symbols"]:
            self.v["symbol"].set(p["symbol"])
        fy = p["fiscal_start"]
        self.v["fy"].set("04-01  (April)" if fy == "04-01" else "01-01  (January)")
        self._check_tax()
        self._preview()

    def _check_tax(self):
        if not hasattr(self, "tax_msg"):
            return
        code = self.country.get()
        no = self.v["tax_no"].get()
        p = _country(code)
        if not no.strip():
            self.tax_msg.configure(text=p["tax_no_hint"] + (" — needed for tax invoices" if code != "IN"
                                                            else " — leave empty if not registered"),
                                   fg=self.C["text_secondary"])
            return
        ok, m = C.valid_tax_no(no, code)
        self.tax_msg.configure(text=("✓ looks right" if ok else "✗ " + m),
                               fg=self.C["success"] if ok else self.C["danger"])
        if ok and code == "IN":
            st = "".join(no.split()).upper()[:2]
            for k, n in p["states"]:
                if k == st:
                    self.v["state"].set("%s - %s" % (k, n))

    def _preview(self):
        if not hasattr(self, "preview"):
            return
        code = self.country.get()
        p = _country(code)
        s = self.v["symbol"].get().strip() or p["symbol"]
        n = C.num(123456.5, 2, code)
        txt = ("%s %s" % (n, s)) if p["symbol_after"] else (("%s%s" % (s, n)) if s == "₹" else "%s %s" % (s, n))
        self.preview.configure(text=txt)

    def _paint_mods(self):
        C = self.C
        for k, card in self.mcards.items():
            on = self.mods[k].get()
            bg = C.get("primary_light", "#EEF0FF") if on else C["content_bg"]
            card.configure(highlightbackground=C["primary"] if on else C["border"], bg=bg)
            for w in card.winfo_children():
                try:
                    w.configure(bg=bg)
                    if isinstance(w, tk.Checkbutton):
                        w.configure(activebackground=bg)
                except Exception:
                    pass

    def info(self):
        code = self.country.get()
        fy = self.v["fy"].get().split()[0] if self.v["fy"].get() else ""
        return {
            "company_name_en": self.v["name_en"].get().strip(),
            "company_name_ar": self.v["name_ar"].get().strip(),
            "country": code, "state": C.state_code_of(self.v["state"].get()) if self.v["state"].get() else "",
            "tax_no": "".join(self.v["tax_no"].get().split()).upper(),
            "cr_number": self.v["reg_no"].get().strip(), "address": self.v["address"].get().strip(),
            "city": self.v["city"].get().strip(), "phone": self.v["phone"].get().strip(),
            "email": self.v["email"].get().strip(), "currency_symbol": self.v["symbol"].get().strip(),
            "modules": [k for k in B.KEYS if self.mods[k].get()], "fiscal_start": fy,
            "price_incl_tax": bool(self.price_incl.get()),
            "language": "ar" if code == "SA" else "en",
        }

    def _validate(self, step):
        if step == 0:
            if not self.v["name_en"].get().strip():
                return "Type the company name."
            n = self.v["dbname"].get().strip()
            if not n or not re.match(r"^[A-Za-z0-9_\-]+$", n):
                return "The database name can have letters, numbers, _ and - only."
        if step == 1:
            from modules import company_setup as CS
            errs = [e for e in CS.validate(self.info()) if "company name" not in e]
            if errs:
                return errs[0]
        return ""

    def _show(self):
        for i, pg in enumerate(self.pages):
            if i == self.step:
                pg.pack(fill="both", expand=True)
            else:
                pg.pack_forget()
        for i, ch in enumerate(self.chips):
            ch.configure(bg="white" if i == self.step else self.C["primary"],
                         fg=self.C["primary"] if i == self.step else "#D9D4FF")
        self.back_btn.configure(state="normal" if self.step > 0 and not self._busy else "disabled")
        last = self.step == len(STEPS) - 1
        self.next_btn.configure(text="✓  Create company" if last else "Next  →")
        self.msg.configure(text="")
        if last:
            self._fill_summary()
        if self.step == 0:
            try:
                self._first.focus_set()
            except Exception:
                pass

    def _fill_summary(self):
        i = self.info()
        p = _country(i["country"])
        lines = [
            "Company      %s%s" % (i["company_name_en"], ("  /  " + i["company_name_ar"]) if i["company_name_ar"] else ""),
            "Database     %s   (server %s)" % (self.v["dbname"].get().strip(), self.conf.get("server", "")),
            "Country      %s %s" % (p["flag"], p["name"]),
            "%-12s %s" % (p["states_label"], C.state_label(i["state"], i["country"]) or "—"),
            "%-12s %s" % (p["tax_no_label"], i["tax_no"] or "— (not registered)"),
            "Tax          %s, standard %g%%" % (p["tax"], p["std_rate"]),
            "Currency     %s  (%s)" % (p["currency"], i["currency_symbol"] or p["symbol"]),
            "Prices       %s" % ("include tax" if i["price_incl_tax"] else "without tax"),
            "Year starts  %s" % (i["fiscal_start"] or p["fiscal_start"]),
            "Business     %s" % B.summary(i["modules"]),
        ]
        self.summary.configure(text="\n".join(lines))

    def _next(self):
        if self._busy:
            return
        if self.step < len(STEPS) - 1:
            err = self._validate(self.step)
            if err:
                self.msg.configure(text="⚠  " + err)
                return
            self.step += 1
            self._show()
            return
        self._create()

    def _back(self):
        if self._busy or self.step == 0:
            return
        self.step -= 1
        self._show()

    def _close(self):
        if self._busy:
            return
        try:
            self.win.grab_release()
        except Exception:
            pass
        self.win.destroy()

    def _center(self):
        try:
            self.win.update_idletasks()
            sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            self.win.geometry("%dx%d+%d+%d" % (self.W, self.H, max(0, (sw - self.W) // 2),
                                                max(0, (sh - self.H) // 2)))
        except Exception:
            pass

    # ── create ────────────────────────────────────────────────
    def _create(self):
        for s in (0, 1):
            err = self._validate(s)
            if err:
                self.msg.configure(text="⚠  " + err)
                return
        from modules import db_backup as dbb
        script = dbb.find_install_script()
        if not script:
            self.msg.configure(text="⚠  database\\INSTALL_DayBillERP_AllInOne.sql is missing.")
            return
        name = self.v["dbname"].get().strip()
        info = self.info()
        self._busy = True
        self.next_btn.configure(state="disabled")
        self.back_btn.configure(state="disabled")
        self._say("Making the database '%s'…" % name, 2)
        box = {"pct": 2, "text": "", "done": False, "ok": False, "msg": ""}

        def progress(done, total):
            box["pct"] = 5 + int(80 * done / max(total, 1))
            box["text"] = "Making tables… %d of %d" % (done, total)

        def work():
            try:
                base = dict(self.conf)
                save_db_config(base)
                ok, msg = dbb.create_database(name, install_script=script, progress=progress)
                if not ok:
                    box.update(done=True, ok=False, msg=msg)
                    return
                box.update(pct=88, text="Setting up %s…" % _country(info["country"])["name"])
                conf = dict(base, database="".join(ch for ch in name if ch.isalnum() or ch in "_-"))
                if not db.connect(conf):
                    box.update(done=True, ok=False, msg="The database was made but DayBill could not open it.")
                    return
                from modules import db_migrate
                db_migrate.run_pending()
                from modules import company_setup as CS
                ok2, msg2 = CS.setup(info)
                if ok2:
                    save_db_config(conf)
                box.update(done=True, ok=ok2, msg=msg2, pct=100, db=conf["database"])
            except Exception as e:
                box.update(done=True, ok=False, msg=str(e)[:300])

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not self.win.winfo_exists():
                return
            self.bar["value"] = box["pct"]
            if box["text"]:
                self.status.configure(text=box["text"])
            if not box["done"]:
                self.win.after(250, poll)
                return
            self._busy = False
            if box["ok"]:
                self._say("✅ " + box["msg"], 100)
                messagebox.showinfo("New Company",
                                    "%s\n\nDayBill now opens '%s'. Sign in with user  admin  — DayBill "
                                    "asks you to choose a password the first time." % (box["msg"], box.get("db")),
                                    parent=self.win)
                if self.on_done:
                    try:
                        self.on_done(box.get("db"))
                    except Exception:
                        pass
                self._close()
            else:
                self.next_btn.configure(state="normal")
                self.back_btn.configure(state="normal")
                self._say("❌ " + (box["msg"] or "Could not make the company."), box["pct"], err=True)
        self.win.after(250, poll)

    def _say(self, text, pct=None, err=False):
        self.status.configure(text=text, fg=self.C["danger"] if err else self.C["text_secondary"])
        if pct is not None:
            self.bar["value"] = pct


def _country(code):
    return C.COUNTRIES.get(code, C.COUNTRIES["SA"])
