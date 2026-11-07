# ============================================================
# DayBill ERP - Integrations settings (Wathq CR lookup)
# ============================================================

import tkinter as tk
from tkinter import messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg


class IntegrationsView:
    def __init__(self, parent):
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build(C)

    def _build(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="🔌  Integrations", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="💾 Save", font=("Segoe UI", 9, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=14, pady=7, cursor="hand2",
                  command=self._save).pack(side="right")

        card = tk.LabelFrame(self.frame, text="  Wathq — Commercial Registration lookup  ",
                             bg=C["card_bg"], fg=C["primary"],
                             font=("Segoe UI", 10, "bold"))
        card.pack(fill="x", padx=24, pady=14)
        tk.Label(card, text="Auto-fill a customer/supplier by CR number using the "
                            "Saudi Ministry of Commerce (Wathq) API. Requires your own "
                            "Wathq beneficiary API key. Note: lookup is by CR number, "
                            "not VAT number.",
                 font=("Segoe UI", 9), bg=C["card_bg"], fg=C["text_secondary"],
                 wraplength=560, justify="left").pack(anchor="w", padx=14, pady=(8, 4))

        body = tk.Frame(card, bg=C["card_bg"]); body.pack(fill="x", padx=14, pady=6)
        body.columnconfigure(1, weight=1)

        self.enabled_var = tk.BooleanVar(value=bool(cfg.get("wathq_enabled", False)))
        tk.Checkbutton(body, text="Enable Wathq lookup", variable=self.enabled_var,
                       font=("Segoe UI", 10, "bold"), bg=C["card_bg"],
                       fg=C["text_primary"], activebackground=C["card_bg"],
                       selectcolor="white").grid(row=0, column=0, columnspan=2,
                                                 sticky="w", pady=(0, 6))

        def row(r, label, key, default="", show=None):
            tk.Label(body, text=label, font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=r, column=0, sticky="w",
                                                  pady=4, padx=(0, 8))
            var = tk.StringVar(value=str(cfg.get(key, default) or default))
            e = tk.Entry(body, textvariable=var, font=("Segoe UI", 10),
                         relief="solid", bd=1, show=show)
            e.grid(row=r, column=1, sticky="ew", pady=4)
            return var

        self.key_var = row(1, "API Key", "wathq_api_key", "", show="•")
        self.base_var = row(2, "Base URL", "wathq_base_url", "https://api.wathq.sa")
        self.endpoint_var = row(3, "Endpoint", "wathq_endpoint",
                                "/commercial-registration/fullinfo/{cr}")

        tk.Label(body, text="Keep {cr} in the endpoint — it's replaced by the CR number. "
                            "Older Wathq accounts use /commercialregistration/info/{cr}.",
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                 wraplength=560, justify="left").grid(row=4, column=0, columnspan=2,
                                                      sticky="w", pady=(2, 6))

        test = tk.Frame(card, bg=C["card_bg"]); test.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(test, text="Test CR #", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.test_cr = tk.StringVar()
        tk.Entry(test, textvariable=self.test_cr, width=16, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(6, 8))
        tk.Button(test, text="🔎 Test lookup", font=("Segoe UI", 9, "bold"),
                  bg=C["info"], fg="white", relief="flat", padx=12, pady=5,
                  cursor="hand2", command=self._test).pack(side="left")

    def _save(self):
        cfg.set("wathq_enabled", bool(self.enabled_var.get()))
        cfg.set("wathq_api_key", self.key_var.get().strip())
        cfg.set("wathq_base_url", self.base_var.get().strip() or "https://api.wathq.sa")
        cfg.set("wathq_endpoint", self.endpoint_var.get().strip()
                or "/commercial-registration/fullinfo/{cr}")
        try:
            cfg.save_settings()
            messagebox.showinfo("Integrations", "Saved.")
        except Exception as e:
            messagebox.showerror("Integrations", str(e)[:200])

    def _test(self):
        self._save()
        try:
            from modules.wathq import lookup_cr
            data, err = lookup_cr(self.test_cr.get())
            if err:
                messagebox.showwarning("Wathq test", err)
            else:
                name = data.get("name_ar") or data.get("name_en") or "—"
                messagebox.showinfo("Wathq test",
                                    f"OK!\nName: {name}\nStatus: {data.get('status') or '—'}\n"
                                    f"City: {data.get('city_ar') or '—'}")
        except Exception as e:
            messagebox.showerror("Wathq test", str(e)[:200])
