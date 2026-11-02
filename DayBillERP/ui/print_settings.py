# ============================================================
# DayBill ERP - Print & Invoice Settings
# (Converted from BillPOS PHP: print_settings.php + invoice_templates.php)
# ------------------------------------------------------------
# Paper size (58mm / 80mm / A4), print toggles, invoice footer,
# and A4 template picker (built-in + custom, stored in settings).
# Values persist in config/app_settings.json via config.settings.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg

BUILTIN_TEMPLATES = [
    {"id": "classic", "name": "Classic",     "accent": "#360DD9", "font": "sans",  "header": "split",   "table": "bordered"},
    {"id": "modern",  "name": "Modern Band", "accent": "#360DD9", "font": "sans",  "header": "band",    "table": "striped"},
    {"id": "minimal", "name": "Minimal",     "accent": "#1B1B2E", "font": "serif", "header": "minimal", "table": "clean"},
    {"id": "green",   "name": "Fresh Green", "accent": "#2E9E4F", "font": "sans",  "header": "band",    "table": "bordered"},
]

TOGGLES = [
    ("print_logo",     "Show logo on invoice",  "Company logo at the top", True),
    ("print_arabic",   "Arabic on invoice",     "Arabic item names + bilingual labels", True),
    ("print_barcode",  "Invoice barcode",       "Scannable invoice number at the bottom", True),
    ("print_zatca_qr", "ZATCA QR code (Saudi)", "Phase-1 TLV QR — needs company VAT number set", True),
    ("print_auto",     "Auto-print after save", "Invoice prints immediately after saving", False),
]

# Entry sections that print on the A4 invoice (each can be turned on/off)
SECTIONS = [
    ("print_amount_words", "Amount in words",   "Total written out under the totals box", True),
    ("print_payment_info", "Payment section",   "Method, paid amount, and balance", True),
    ("print_bank",         "Bank details",      "Your account details for transfers (text below)", False),
    ("print_terms",        "Terms & conditions", "Printed small at the bottom-left (text below)", False),
    ("print_signature",    "Signature area",    "Receiver + Authorized signature lines", False),
]


def custom_templates():
    try:
        j = json.loads(cfg.get("invoice_templates_custom", "[]") or "[]")
        return [t for t in j if t.get("id") and t.get("name")]
    except Exception:
        return []


def all_templates():
    return BUILTIN_TEMPLATES + custom_templates()


def active_template():
    tid = cfg.get("invoice_template_a4", "classic")
    for t in all_templates():
        if t["id"] == tid:
            return t
    return BUILTIN_TEMPLATES[0]


class PrintSettingsView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build(C)

    def _build(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="🖨  Print & Invoice", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="💾  Save settings", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._save).pack(side="right")
        tk.Button(bar, text="🎨  Invoice Designer", font=("Segoe UI", 9, "bold"),
                  bg="#8E44AD", fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._open_designer).pack(
                  side="right", padx=(0, 8))
        tk.Button(bar, text="🔍  Preview invoice", font=("Segoe UI", 9, "bold"),
                  bg="#16A085", fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._preview).pack(side="right",
                                                              padx=(0, 8))

        from ui.widgets import ScrollableFrame
        _sf = ScrollableFrame(self.frame)
        _sf.pack(fill="both", expand=True, padx=(24, 4), pady=12)
        body = tk.Frame(_sf.inner, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=(0, 16))

        # ── paper size card ──
        card1 = tk.LabelFrame(body, text="  Paper size  ", bg=C["card_bg"],
                              fg=C["primary"], font=("Segoe UI", 10, "bold"))
        card1.pack(fill="x", pady=(0, 10))
        self.paper_var = tk.StringVar(value=str(cfg.get("paper_width", "80")))
        prow = tk.Frame(card1, bg=C["card_bg"]); prow.pack(fill="x", padx=12, pady=8)
        for val, lbl, sub in [("58", "58 mm", "Small thermal"),
                              ("80", "80 mm", "Standard thermal"),
                              ("a4", "A4", "Laser / inkjet")]:
            f = tk.Frame(prow, bg=C["card_bg"], highlightbackground=C["border"],
                         highlightthickness=1)
            f.pack(side="left", expand=True, fill="x", padx=4)
            tk.Radiobutton(f, text=f"{lbl}\n{sub}", value=val,
                           variable=self.paper_var, font=("Segoe UI", 9, "bold"),
                           bg=C["card_bg"], fg=C["text_primary"], justify="center",
                           activebackground=C["card_bg"], selectcolor="white",
                           indicatoron=True).pack(fill="x", pady=6)
        tk.Label(card1, text="Thermal printers print via the Windows print "
                             "dialog — set margins to None once; Windows remembers.",
                 font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"], wraplength=520,
                 justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        # ── toggles card ──
        card2 = tk.LabelFrame(body, text="  Invoice options  ", bg=C["card_bg"],
                              fg=C["primary"], font=("Segoe UI", 10, "bold"))
        card2.pack(fill="x", pady=(0, 10))
        self.toggle_vars = {}
        for key, lbl, sub, default in TOGGLES:
            var = tk.BooleanVar(value=bool(cfg.get(key, default)))
            self.toggle_vars[key] = var
            row = tk.Frame(card2, bg=C["card_bg"]); row.pack(fill="x", padx=12, pady=3)
            tk.Checkbutton(row, text=lbl, variable=var, font=("Segoe UI", 10, "bold"),
                           bg=C["card_bg"], fg=C["text_primary"],
                           activebackground=C["card_bg"],
                           selectcolor="white").pack(side="left")
            tk.Label(row, text=sub, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(8, 0))

        # footer text
        frow = tk.Frame(card2, bg=C["card_bg"]); frow.pack(fill="x", padx=12, pady=(6, 10))
        tk.Label(frow, text="Invoice footer", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 8))
        self.footer_var = tk.StringVar(value=str(cfg.get("invoice_footer", "") or ""))
        tk.Entry(frow, textvariable=self.footer_var, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", fill="x", expand=True)

        # ── entry sections card ──
        card_s = tk.LabelFrame(body, text="  Invoice sections  ", bg=C["card_bg"],
                               fg=C["primary"], font=("Segoe UI", 10, "bold"))
        card_s.pack(fill="x", pady=(0, 10))
        self.section_vars = {}
        for key, lbl, sub, default in SECTIONS:
            var = tk.BooleanVar(value=bool(cfg.get(key, default)))
            self.section_vars[key] = var
            row = tk.Frame(card_s, bg=C["card_bg"]); row.pack(fill="x", padx=12, pady=3)
            tk.Checkbutton(row, text=lbl, variable=var, font=("Segoe UI", 10, "bold"),
                           bg=C["card_bg"], fg=C["text_primary"],
                           activebackground=C["card_bg"],
                           selectcolor="white").pack(side="left")
            tk.Label(row, text=sub, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(8, 0))
        # bank details text
        brow = tk.Frame(card_s, bg=C["card_bg"]); brow.pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(brow, text="Bank details", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.bank_txt = tk.Text(brow, height=3, font=("Segoe UI", 9),
                                relief="solid", bd=1, wrap="word")
        self.bank_txt.pack(fill="x")
        self.bank_txt.insert("1.0", str(cfg.get("invoice_bank", "") or ""))
        # terms text
        trow = tk.Frame(card_s, bg=C["card_bg"]); trow.pack(fill="x", padx=12, pady=(6, 10))
        tk.Label(trow, text="Terms & conditions", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.terms_txt = tk.Text(trow, height=3, font=("Segoe UI", 9),
                                 relief="solid", bd=1, wrap="word")
        self.terms_txt.pack(fill="x")
        self.terms_txt.insert("1.0", str(cfg.get("invoice_terms", "") or ""))

        # ── A4 template card ──
        card3 = tk.LabelFrame(body, text="  A4 invoice template  ", bg=C["card_bg"],
                              fg=C["primary"], font=("Segoe UI", 10, "bold"))
        card3.pack(fill="x")
        self.tmpl_var = tk.StringVar(value=str(cfg.get("invoice_template_a4", "classic")))
        self.tmpl_holder = tk.Frame(card3, bg=C["card_bg"])
        self.tmpl_holder.pack(fill="x", padx=12, pady=8)
        self._render_templates()
        tk.Button(card3, text="＋ New custom template", font=("Segoe UI", 9, "bold"),
                  bg=C["content_bg"], relief="flat", cursor="hand2",
                  command=self._new_template).pack(anchor="w", padx=12, pady=(0, 10))

        # ── dot-matrix template card ──
        card4 = tk.LabelFrame(body, text="  Dot-matrix invoice template  ",
                              bg=C["card_bg"], fg=C["primary"],
                              font=("Segoe UI", 10, "bold"))
        card4.pack(fill="x", pady=(10, 0))
        from modules.dotmatrix_receipt import get_templates
        drow = tk.Frame(card4, bg=C["card_bg"]); drow.pack(fill="x", padx=12, pady=8)
        tk.Label(drow, text="Active template", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left",
                                                               padx=(0, 8))
        self.dm_active_var = tk.StringVar(
            value=str(cfg.get("dotmatrix_template_active", "dm_default")))
        self.dm_combo = ttk.Combobox(drow, state="readonly", width=26)
        self.dm_combo.pack(side="left")
        self._reload_dm_combo()
        tk.Button(drow, text="✎ Edit", font=("Segoe UI", 9, "bold"),
                  bg=C["content_bg"], relief="flat", padx=10, pady=4,
                  cursor="hand2", command=self._dm_edit).pack(side="left", padx=(8, 0))
        tk.Button(drow, text="＋ New", font=("Segoe UI", 9, "bold"),
                  bg=C["content_bg"], relief="flat", padx=10, pady=4,
                  cursor="hand2", command=self._dm_new).pack(side="left", padx=(6, 0))
        tk.Button(drow, text="🗑", font=("Segoe UI", 9, "bold"), fg=C["danger"],
                  bg=C["card_bg"], relief="flat", cursor="hand2",
                  command=self._dm_delete).pack(side="left", padx=(6, 0))
        tk.Label(card4, text="Choose which sections print, their order, "
                             "items per page, party balance, and payment terms.",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                 wraplength=520, justify="left").pack(anchor="w", padx=12,
                                                      pady=(0, 8))

    # ── dot-matrix template helpers ──

    def _open_designer(self):
        """Designs for every document live in Report / Invoice Designer."""
        try:
            from ui import main_window as mw
            if getattr(mw, "APP", None):
                mw.APP._load_module("report_designer")
                return
        except Exception:
            pass
        messagebox.showinfo("Invoice Designer",
                            "Open System ▸ Report / Invoice Designer.")

    def _reload_dm_combo(self):
        from modules.dotmatrix_receipt import get_templates
        self._dm_templates = get_templates()
        names = ["%s (%s col)" % (t["name"], t.get("width", 80))
                 for t in self._dm_templates]
        self.dm_combo["values"] = names
        active = str(cfg.get("dotmatrix_template_active", "dm_default"))
        idx = next((i for i, t in enumerate(self._dm_templates)
                    if t["id"] == active), 0)
        self.dm_combo.current(idx)
        self.dm_combo.bind("<<ComboboxSelected>>", self._dm_activate)

    def _dm_activate(self, _e=None):
        t = self._dm_templates[self.dm_combo.current()]
        cfg.set("dotmatrix_template_active", t["id"])
        cfg.save_settings()

    def _dm_selected(self):
        return self._dm_templates[self.dm_combo.current()]

    def _dm_new(self):
        DMTemplateDialog(self.frame, template=None,
                         on_saved=self._reload_dm_combo)

    def _dm_edit(self):
        DMTemplateDialog(self.frame, template=self._dm_selected(),
                         on_saved=self._reload_dm_combo)

    def _dm_delete(self):
        t = self._dm_selected()
        if t["id"] == "dm_default":
            messagebox.showinfo("Templates", "The Default template can't be "
                                "deleted. Create a copy and edit that.")
            return
        if not messagebox.askyesno("Delete Template",
                                   "Delete dot-matrix template '%s'?" % t["name"]):
            return
        customs = [x for x in self._dm_templates
                   if x["id"] not in ("dm_default", t["id"])]
        cfg.set("dotmatrix_templates", json.dumps(customs))
        if str(cfg.get("dotmatrix_template_active", "")) == t["id"]:
            cfg.set("dotmatrix_template_active", "dm_default")
        cfg.save_settings()
        self._reload_dm_combo()

    def _render_templates(self):
        C = self.C
        for w in self.tmpl_holder.winfo_children():
            w.destroy()
        for t in all_templates():
            row = tk.Frame(self.tmpl_holder, bg=C["card_bg"])
            row.pack(fill="x", pady=2)
            tk.Radiobutton(row, text="", value=t["id"], variable=self.tmpl_var,
                           bg=C["card_bg"], activebackground=C["card_bg"],
                           selectcolor="white").pack(side="left")
            sw = tk.Frame(row, bg=t.get("accent", "#360DD9"), width=18, height=18)
            sw.pack(side="left", padx=(0, 8)); sw.pack_propagate(False)
            builtin = any(b["id"] == t["id"] for b in BUILTIN_TEMPLATES)
            tk.Label(row, text=t["name"], font=("Segoe UI", 10, "bold"),
                     bg=C["card_bg"], fg=C["text_primary"]).pack(side="left")
            tk.Label(row, text=f"{t.get('font','sans')} · {t.get('header','split')} "
                               f"header · {t.get('table','bordered')} table"
                               + ("" if builtin else "  (custom)"),
                     font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(8, 0))
            if not builtin:
                tk.Button(row, text="✕", font=("Segoe UI", 8, "bold"), fg=C["danger"],
                          bg=C["card_bg"], relief="flat", cursor="hand2",
                          command=lambda tid=t["id"]: self._del_template(tid)
                          ).pack(side="right")

    def _new_template(self):
        TemplateDialog(self.frame, on_saved=self._render_templates)

    def _del_template(self, tid):
        customs = [t for t in custom_templates() if t["id"] != tid]
        cfg.set("invoice_templates_custom", json.dumps(customs))
        if self.tmpl_var.get() == tid:
            self.tmpl_var.set("classic")
            cfg.set("invoice_template_a4", "classic")
        cfg.save_settings()
        self._render_templates()

    def _save(self):
        cfg.set("paper_width", self.paper_var.get())
        if self.paper_var.get() in ("58", "80"):
            cfg.set("pos_paper_size", self.paper_var.get() + "mm")
        for key, var in self.toggle_vars.items():
            cfg.set(key, bool(var.get()))
        for key, var in self.section_vars.items():
            cfg.set(key, bool(var.get()))
        cfg.set("invoice_footer", self.footer_var.get().strip())
        cfg.set("invoice_bank", self.bank_txt.get("1.0", "end").strip())
        cfg.set("invoice_terms", self.terms_txt.get("1.0", "end").strip())
        cfg.set("invoice_template_a4", self.tmpl_var.get())
        try:
            cfg.save_settings()
            try:
                from modules import audit
                audit.log("update", "settings", None, "Print settings updated")
            except Exception:
                pass
            messagebox.showinfo("Saved", "Print settings saved.")
        except Exception as e:
            messagebox.showerror("Settings", str(e)[:200])

    def _preview(self):
        """Save current choices, generate a sample A4 invoice with dummy
        data, and open it — so the template can be seen instantly."""
        self._save_silent()
        try:
            from modules.pdf_invoice import generate_invoice_pdf
            import tempfile, webbrowser
            invoice = {
                "invoice_number": "INV-PREVIEW-001",
                "invoice_date": "2026-07-10",
                "customer_name_en": "Sample Customer LLC",
                "customer_name_ar": "عميل تجريبي",
                "subtotal_amount": 500.00, "discount_amount": 20.00,
                "vat_amount": 72.00, "total_amount": 552.00,
                "payment_method": "cash", "paid_amount": 552.00,
            }
            company = {
                "company_name_en": "Your Company Name",
                "company_name_ar": "اسم شركتك",
                "vat_number": "300000000000003",
                "address_en": "Riyadh, Saudi Arabia", "phone": "011-000-0000",
            }
            lines = [
                {"product_name_en": "Sample Product A", "product_name_ar": "منتج أ",
                 "quantity": 2, "unit_of_measure_en": "PCs", "unit_price": 100.0,
                 "taxable_amount": 200.0, "vat_amount": 30.0, "line_total": 230.0},
                {"product_name_en": "Sample Product B", "product_name_ar": "منتج ب",
                 "quantity": 3, "unit_of_measure_en": "Box", "unit_price": 100.0,
                 "taxable_amount": 280.0, "vat_amount": 42.0, "line_total": 322.0},
            ]
            path = os.path.join(tempfile.gettempdir(), "daybill_invoice_preview.pdf")
            generate_invoice_pdf(invoice, company, lines, output_path=path)
            try:
                os.startfile(path)              # Windows
            except AttributeError:
                webbrowser.open("file://" + path)
        except Exception as e:
            messagebox.showerror("Preview", str(e)[:250])

    def _save_silent(self):
        cfg.set("paper_width", self.paper_var.get())
        if self.paper_var.get() in ("58", "80"):
            cfg.set("pos_paper_size", self.paper_var.get() + "mm")
        for key, var in self.toggle_vars.items():
            cfg.set(key, bool(var.get()))
        for key, var in self.section_vars.items():
            cfg.set(key, bool(var.get()))
        cfg.set("invoice_footer", self.footer_var.get().strip())
        cfg.set("invoice_bank", self.bank_txt.get("1.0", "end").strip())
        cfg.set("invoice_terms", self.terms_txt.get("1.0", "end").strip())
        cfg.set("invoice_template_a4", self.tmpl_var.get())
        try:
            cfg.save_settings()
        except Exception:
            pass


class TemplateDialog:
    """Tiny custom-template builder (name + accent + font + header + table)."""
    def __init__(self, parent, on_saved=None):
        C = cfg.theme()
        self.on_saved = on_saved
        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("New Template")
        self.win.configure(bg=C["card_bg"])
        self.win.transient(parent.winfo_toplevel())
        self.win.grab_set()
        body = tk.Frame(self.win, bg=C["card_bg"])
        body.pack(padx=16, pady=12)
        body.columnconfigure(1, weight=1)

        def field(r, label, widget):
            tk.Label(body, text=label, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=0, sticky="w",
                                                  pady=3, padx=(0, 8))
            widget.grid(row=r, column=1, sticky="ew", pady=3)

        self.name_var = tk.StringVar()
        field(0, "Name", tk.Entry(body, textvariable=self.name_var,
                                  font=("Segoe UI", 10), relief="solid", bd=1))
        self.accent_var = tk.StringVar(value="#360DD9")
        field(1, "Accent (hex)", tk.Entry(body, textvariable=self.accent_var,
                                          font=("Segoe UI", 10), relief="solid", bd=1))
        self.font_var = tk.StringVar(value="sans")
        field(2, "Font", ttk.Combobox(body, textvariable=self.font_var,
                                      values=["sans", "serif", "mono"],
                                      state="readonly"))
        self.header_var = tk.StringVar(value="split")
        field(3, "Header", ttk.Combobox(body, textvariable=self.header_var,
                                        values=["split", "band", "minimal"],
                                        state="readonly"))
        self.table_var = tk.StringVar(value="bordered")
        field(4, "Table", ttk.Combobox(body, textvariable=self.table_var,
                                       values=["bordered", "striped", "clean"],
                                       state="readonly"))
        btns = tk.Frame(self.win, bg=C["card_bg"]); btns.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#EEF1F6",
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self.win.destroy).pack(side="left", expand=True,
                                                 fill="x", padx=(0, 4))
        tk.Button(btns, text="✓ Save & activate", font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg="white", relief="flat", padx=14, pady=5,
                  cursor="hand2", command=self._save).pack(side="left",
                                                           expand=True, fill="x")

    def _save(self):
        import re as _re
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Template", "Give the template a name.",
                                   parent=self.win)
            return
        accent = self.accent_var.get().strip()
        if not _re.match(r"^#[0-9A-Fa-f]{6}$", accent):
            accent = "#360DD9"
        tid = "t_" + _re.sub(r"[^a-z0-9]+", "_", name.lower())[:24]
        customs = [t for t in custom_templates() if t["id"] != tid]
        customs.append({"id": tid, "name": name, "accent": accent,
                        "font": self.font_var.get(), "header": self.header_var.get(),
                        "table": self.table_var.get()})
        cfg.set("invoice_templates_custom", json.dumps(customs))
        cfg.set("invoice_template_a4", tid)
        cfg.save_settings()
        if self.on_saved:
            self.on_saved()
        self.win.destroy()


class DMTemplateDialog:
    """Dot-matrix template designer: arrange all invoice sections in your
    own order, toggle each on/off, set items-per-page, party balance,
    payment terms — with a live text preview."""

    def __init__(self, parent, template=None, on_saved=None):
        from modules.dotmatrix_receipt import ALL_SECTIONS, DEFAULT_TEMPLATE
        C = cfg.theme()
        self.C = C
        self.on_saved = on_saved
        base = dict(DEFAULT_TEMPLATE)
        if template:
            base.update(template)
        self.editing_id = base["id"] if template else None
        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title("Dot-Matrix Template Designer")
        self.win.configure(bg=C["card_bg"])
        self.win.transient(parent.winfo_toplevel())
        self.win.grab_set()

        left = tk.Frame(self.win, bg=C["card_bg"])
        left.pack(side="left", fill="y", padx=(16, 8), pady=12)

        # name / width / items per page
        tk.Label(left, text="Template name", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.name_var = tk.StringVar(value="" if not template else base["name"])
        tk.Entry(left, textvariable=self.name_var, font=("Segoe UI", 10),
                 relief="solid", bd=1, width=28).pack(anchor="w", pady=(0, 8))

        wrow = tk.Frame(left, bg=C["card_bg"]); wrow.pack(anchor="w", pady=(0, 8))
        tk.Label(wrow, text="Width", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 8))
        self.width_var = tk.StringVar(value=str(base.get("width", 80)))
        for v, l in (("80", "80 col"), ("132", "132 col (wide)")):
            tk.Radiobutton(wrow, text=l, value=v, variable=self.width_var,
                           bg=C["card_bg"], activebackground=C["card_bg"],
                           font=("Segoe UI", 9),
                           selectcolor="white").pack(side="left")

        prow = tk.Frame(left, bg=C["card_bg"]); prow.pack(anchor="w", pady=(0, 8))
        tk.Label(prow, text="Products per page", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left",
                                                               padx=(0, 8))
        self.ipp_var = tk.StringVar(value=str(base.get("items_per_page", 0)))
        tk.Spinbox(prow, from_=0, to=99, textvariable=self.ipp_var, width=5,
                   font=("Segoe UI", 10), relief="solid",
                   bd=1).pack(side="left")
        tk.Label(prow, text="(0 = continuous, no page break)",
                 font=("Segoe UI", 8), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(6, 0))

        # sections: ordered listbox with checkboxes emulated via prefix
        tk.Label(left, text="Sections — order top to bottom, "
                            "✓ = printed", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", pady=(4, 2))
        self._labels = dict(ALL_SECTIONS)
        enabled = list(base.get("sections", []))
        # display order: enabled first (template order), then the rest
        self.order = enabled + [k for k, _ in ALL_SECTIONS if k not in enabled]
        self.enabled = set(enabled)
        lb_wrap = tk.Frame(left, bg=C["card_bg"]); lb_wrap.pack(anchor="w")
        self.lb = tk.Listbox(lb_wrap, height=12, width=34,
                             font=("Segoe UI", 10), relief="solid", bd=1,
                             activestyle="none")
        self.lb.pack(side="left")
        bcol = tk.Frame(lb_wrap, bg=C["card_bg"]); bcol.pack(side="left",
                                                             padx=(6, 0))
        for txt, cmd in (("▲", lambda: self._move(-1)),
                         ("▼", lambda: self._move(1)),
                         ("✓", self._toggle)):
            tk.Button(bcol, text=txt, font=("Segoe UI", 10, "bold"), width=3,
                      relief="flat", bg=C["content_bg"], cursor="hand2",
                      command=cmd).pack(pady=2)
        self.lb.bind("<Double-1>", lambda e: self._toggle())
        self._refresh_lb()

        tk.Label(left, text="Payment terms (printed by the Terms section)",
                 font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(8, 0))
        self.terms_txt = tk.Text(left, height=3, width=34, font=("Segoe UI", 9),
                                 relief="solid", bd=1, wrap="word")
        self.terms_txt.pack(anchor="w")
        self.terms_txt.insert("1.0", base.get("terms_text", ""))

        btns = tk.Frame(left, bg=C["card_bg"]); btns.pack(fill="x", pady=(10, 0))
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#EEF1F6",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self.win.destroy).pack(side="left")
        tk.Button(btns, text="✓ Save & activate", font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._save).pack(side="right")

        # right: live preview
        right = tk.Frame(self.win, bg="#111318")
        right.pack(side="left", fill="both", expand=True, padx=(8, 16), pady=12)
        tk.Label(right, text=" PREVIEW (sample data) ", font=("Consolas", 9, "bold"),
                 bg="#111318", fg="#7ED957").pack(anchor="w")
        self.prev = tk.Text(right, font=("Consolas", 8), bg="#111318",
                            fg="#D7E1D9", relief="flat", width=86, height=40,
                            wrap="none")
        self.prev.pack(fill="both", expand=True)
        xsb = ttk.Scrollbar(right, orient="horizontal", command=self.prev.xview)
        self.prev.configure(xscrollcommand=xsb.set)
        xsb.pack(fill="x")
        self._preview()
        # refresh preview on any change
        for var in (self.width_var, self.ipp_var):
            var.trace("w", lambda *_: self._preview())
        self.terms_txt.bind("<KeyRelease>", lambda e: self._preview())

    # ── section list handling ──
    def _refresh_lb(self, keep=None):
        self.lb.delete(0, "end")
        for k in self.order:
            mark = "✓ " if k in self.enabled else "✗ "
            self.lb.insert("end", mark + self._labels[k])
        if keep is not None:
            self.lb.selection_set(keep)
            self.lb.see(keep)

    def _move(self, d):
        sel = self.lb.curselection()
        if not sel:
            return
        i = sel[0]; j = i + d
        if not (0 <= j < len(self.order)):
            return
        self.order[i], self.order[j] = self.order[j], self.order[i]
        self._refresh_lb(keep=j)
        self._preview()

    def _toggle(self):
        sel = self.lb.curselection()
        if not sel:
            return
        k = self.order[sel[0]]
        if k == "items":
            messagebox.showinfo("Sections", "The products table always prints.",
                                parent=self.win)
            return
        if k in self.enabled:
            self.enabled.discard(k)
        else:
            self.enabled.add(k)
        self._refresh_lb(keep=sel[0])
        self._preview()

    def _current_template(self):
        return {
            "id": self.editing_id or "",
            "name": self.name_var.get().strip() or "Untitled",
            "width": int(self.width_var.get() or 80),
            "items_per_page": max(0, int(float(self.ipp_var.get() or 0))),
            "sections": [k for k in self.order
                         if k in self.enabled or k == "items"],
            "terms_text": self.terms_txt.get("1.0", "end").strip(),
        }

    # ── live preview with sample data ──
    def _preview(self):
        try:
            from modules.dotmatrix_receipt import build_invoice_text
            t = self._current_template()
            invoice = {"invoice_number": "INV-000123", "invoice_date": "2026-07-10",
                       "customer_name_en": "Sample Customer LLC",
                       "payment_method": "credit", "subtotal_amount": 500.0,
                       "discount_amount": 20.0, "vat_amount": 72.0,
                       "total_amount": 552.0, "paid_amount": 200.0}
            company = {"company_name_en": "Your Company Name",
                       "vat_registration_no": "300000000000003",
                       "city_en": "Riyadh"}
            lines = [{"product_name_en": "Sample Product %d" % i,
                      "quantity": i, "unit_price": 50.0, "vat_rate": 15,
                      "vat_amount": 7.5 * i, "line_total": 57.5 * i}
                     for i in range(1, 8)]
            txt = build_invoice_text(invoice, company, lines,
                                     width=t["width"], template=t)
            txt = txt.replace("\f", "\n" + "· " * 20 + "PAGE BREAK " +
                              "· " * 20 + "\n")
            self.prev.configure(state="normal")
            self.prev.delete("1.0", "end")
            self.prev.insert("1.0", txt)
            self.prev.configure(state="disabled")
        except Exception as e:
            try:
                self.prev.configure(state="normal")
                self.prev.delete("1.0", "end")
                self.prev.insert("1.0", "Preview error: %s" % e)
                self.prev.configure(state="disabled")
            except Exception:
                pass

    def _save(self):
        import re as _re
        t = self._current_template()
        if not self.name_var.get().strip():
            messagebox.showwarning("Template", "Give the template a name.",
                                   parent=self.win)
            return
        if not t["id"] or t["id"] == "dm_default":
            t["id"] = "dm_" + _re.sub(r"[^a-z0-9]+", "_",
                                      t["name"].lower())[:24]
        from modules.dotmatrix_receipt import get_templates
        customs = [x for x in get_templates()
                   if x["id"] not in ("dm_default", t["id"])]
        customs.append(t)
        cfg.set("dotmatrix_templates", json.dumps(customs))
        cfg.set("dotmatrix_template_active", t["id"])
        cfg.save_settings()
        if self.on_saved:
            self.on_saved()
        self.win.destroy()
