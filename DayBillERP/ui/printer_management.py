# ============================================================
# DayBill ERP - Printer Management
# ------------------------------------------------------------
# Detect installed printers, set the default, choose a printer per
# document type, copies, "print without asking", and run a Test
# Print. Saves to settings; every document print reads these.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules import printer_service as ps

DOC_TYPES = [
    ("sales_invoice", "Sales Invoice"),
    ("pos_invoice", "POS Bill (thermal)"),
    ("credit_note", "Sales Return"),
    ("purchase_invoice", "Purchase / Purchase Return / PO"),
    ("quotation", "Quotation"),
    ("receipt_voucher", "Receipt Voucher"),
    ("payment_voucher", "Payment Voucher"),
    ("dotmatrix", "Dot-matrix (all documents)"),
    ("labels", "Barcode / Shelf Labels"),
    ("report", "Reports"),
]


class PrinterManagementView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.printers = ps.list_printers()
        self._build(C)

    def _card(self, parent, title):
        C = self.C
        card = tk.LabelFrame(parent, text=f"  {title}  ", bg=C["card_bg"],
                             fg=C["primary"], font=("Segoe UI", 10, "bold"))
        card.pack(fill="x", padx=24, pady=(0, 12))
        return card

    def _build(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 12))
        tk.Label(bar, text="🖨  Printer Management", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="🔄 Re-scan", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=12,
                  pady=6, cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._rescan).pack(side="right")
        tk.Button(bar, text="💾 Save", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=16, pady=6, cursor="hand2",
                  command=self._save).pack(side="right", padx=(0, 8))

        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True)

        if not self.printers:
            warn = tk.Label(body,
                text="No printers detected. On Windows make sure pywin32 is "
                     "installed (pip install pywin32) and printers are added. "
                     "You can still set names manually below.",
                font=("Segoe UI", 9), bg="#FFF7E6", fg="#9A6700",
                wraplength=900, justify="left")
            warn.pack(fill="x", padx=24, pady=(0, 10), ipady=8)

        names = self.printers or [cfg.get("default_printer") or ""]

        # ── General ──
        c1 = self._card(body, "Default printer & output")
        g = tk.Frame(c1, bg=C["card_bg"]); g.pack(fill="x", padx=14, pady=10)
        g.columnconfigure(1, weight=1)

        tk.Label(g, text="Default printer", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        self.default_var = tk.StringVar(
            value=cfg.get("default_printer") or ps.default_printer() or "")
        self.default_combo = ttk.Combobox(g, textvariable=self.default_var,
                                          values=names, font=("Segoe UI", 10))
        self.default_combo.grid(row=0, column=1, sticky="ew", pady=4)
        tk.Button(g, text="🖶 Test Print", font=("Segoe UI", 9, "bold"),
                  bg=C["info"], fg="white", relief="flat", padx=12, pady=5,
                  cursor="hand2", command=self._test).grid(row=0, column=2, padx=(8, 0))

        tk.Label(g, text="Copies", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
        self.copies_var = tk.StringVar(value=str(cfg.get("print_copies", 1)))
        tk.Spinbox(g, from_=1, to=99, textvariable=self.copies_var, width=6,
                   font=("Segoe UI", 10)).grid(row=1, column=1, sticky="w", pady=4)

        self.silent_var = tk.BooleanVar(value=ps.print_direct())
        tk.Checkbutton(g, text="Print on the default printer without asking  "
                               "(untick = ask which printer every time)",
                       variable=self.silent_var, font=("Segoe UI", 9, "bold"),
                       bg=C["card_bg"], fg=C["text_primary"],
                       activebackground=C["card_bg"],
                       selectcolor="white").grid(row=2, column=0, columnspan=2,
                                                 sticky="w", pady=(6, 0))

        # ── Per-document printer ──
        c3 = self._card(body, "Printer per document type")
        pg = tk.Frame(c3, bg=C["card_bg"]); pg.pack(fill="x", padx=14, pady=10)
        pg.columnconfigure(1, weight=1); pg.columnconfigure(3, weight=1)
        self.doc_vars = {}
        dp = cfg.get("doc_printers", {}) or {}
        opts = ["(use default)"] + names
        for i, (key, label) in enumerate(DOC_TYPES):
            r, col = i // 2, (i % 2) * 2
            tk.Label(pg, text=label, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=col, sticky="w",
                                                  pady=4, padx=(0, 8))
            v = tk.StringVar(value=dp.get(key, "(use default)"))
            ttk.Combobox(pg, textvariable=v, values=opts, font=("Segoe UI", 9),
                         width=22).grid(row=r, column=col + 1, sticky="ew", pady=4,
                                        padx=(0, 16))
            self.doc_vars[key] = v

    def _rescan(self):
        self.printers = ps.list_printers()
        for w in self.frame.winfo_children():
            w.destroy()
        self._build(self.C)
        messagebox.showinfo("Printers",
                            f"{len(self.printers)} printer(s) detected.")

    def _test(self):
        name = self.default_var.get().strip() or None
        ok = ps.test_print(name)
        messagebox.showinfo("Test Print",
                            "Sent to printer." if ok else
                            "Could not print — check the printer and drivers.")

    def _save(self):
        cfg.set("default_printer", self.default_var.get().strip())
        try:
            cfg.set("print_copies", int(float(self.copies_var.get() or 1)))
        except Exception:
            cfg.set("print_copies", 1)
        cfg.set("print_direct", bool(self.silent_var.get()))
        cfg.set("doc_printers", {k: v.get() for k, v in self.doc_vars.items()
                                 if v.get() and v.get() != "(use default)"})
        try:
            cfg.save_settings()
            if self.default_var.get().strip():
                ps.set_windows_default(self.default_var.get().strip())
            messagebox.showinfo("Saved", "Printer settings saved.")
        except Exception as e:
            messagebox.showerror("Save", str(e)[:200])
