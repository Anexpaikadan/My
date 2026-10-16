# ============================================================
# DayBill ERP - batch no. + expiry date for each purchase line (v6.0)
# ------------------------------------------------------------
# Purchase ▸ ⏰ Expiry dates: one row per line; products with "Track
# expiry dates" are marked ●. The values are kept on the lines and saved
# with the purchase; confirming the purchase makes the batches.
# ============================================================
import tkinter as tk

from config import settings as cfg


def _tracked_ids(lines):
    try:
        from config.database import db
        ids = [int(l["product_id"]) for l in lines if l.get("product_id")]
        if not ids:
            return set()
        rows = db.fetchall("SELECT product_id FROM products WHERE ISNULL(track_expiry,0)=1 AND "
                           "product_id IN (%s)" % ",".join("?" * len(ids)), tuple(ids)) or []
        return {r["product_id"] for r in rows}
    except Exception:
        return set()


def missing(lines):
    """Lines of tracked products without an expiry date."""
    t = _tracked_ids(lines)
    return [l for l in lines if l.get("product_id") in t and not str(l.get("expiry_date") or "").strip()]


class ExpiryDialog(tk.Toplevel):
    def __init__(self, parent, lines, on_done=None):
        super().__init__(parent)
        C = cfg.theme()
        self.title("Batch & expiry dates  ·  رقم التشغيلة وتاريخ الانتهاء")
        self.configure(bg=C["content_bg"])
        self.transient(parent)
        self.lines = [l for l in lines if l.get("product_id")]
        self.on_done = on_done
        tracked = _tracked_ids(self.lines)
        tk.Label(self, text="Type the batch number and the expiry date of each product "
                            "(● = the product tracks expiry dates). Leave empty when not needed.",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"],
                 wraplength=640, justify="left").pack(anchor="w", padx=14, pady=(12, 6))
        box = tk.Frame(self, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="both", expand=True, padx=14)
        for c, h in enumerate(("", "Product", "Qty", "Batch no.", "Expiry date (YYYY-MM-DD)")):
            tk.Label(box, text=h, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                     fg=C["text_primary"]).grid(row=0, column=c, sticky="w", padx=6, pady=4)
        self.vars = []
        for i, ln in enumerate(self.lines, 1):
            tk.Label(box, text="●" if ln.get("product_id") in tracked else "", fg="#B45309",
                     bg=C["card_bg"]).grid(row=i, column=0, padx=(6, 0))
            tk.Label(box, text=str(ln.get("product_name_en") or "")[:40], bg=C["card_bg"],
                     font=("Segoe UI", 9)).grid(row=i, column=1, sticky="w", padx=6)
            tk.Label(box, text="%g %s" % (float(ln.get("quantity") or 0), ln.get("unit_of_measure_en") or ""),
                     bg=C["card_bg"], font=("Segoe UI", 9)).grid(row=i, column=2, sticky="e", padx=6)
            bv = tk.StringVar(value=str(ln.get("batch_no") or ""))
            ev = tk.StringVar(value=str(ln.get("expiry_date") or "")[:10])
            tk.Entry(box, textvariable=bv, width=14, relief="solid", bd=1).grid(row=i, column=3, padx=6, pady=2)
            e = tk.Entry(box, textvariable=ev, width=14, relief="solid", bd=1)
            e.grid(row=i, column=4, padx=6, pady=2)
            try:
                from ui.datefield import DateBox
                DateBox(e, ev)
            except Exception:
                pass
            self.vars.append((ln, bv, ev))
        self.msg = tk.Label(self, text="", font=("Segoe UI", 9), bg=C["content_bg"], fg=C["danger"])
        self.msg.pack(anchor="w", padx=14)
        f = tk.Frame(self, bg=C["content_bg"]); f.pack(fill="x", padx=14, pady=10)
        tk.Button(f, text="OK", font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=18, pady=4, command=self._ok).pack(side="right")
        tk.Button(f, text="Cancel", font=("Segoe UI", 10), relief="flat", padx=12, pady=4,
                  command=self.destroy).pack(side="right", padx=8)
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        try:
            self.grab_set()
        except Exception:
            pass

    def _ok(self):
        from datetime import datetime
        for ln, bv, ev in self.vars:
            e = ev.get().strip()
            if e:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        e = datetime.strptime(e, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
                else:
                    self.msg.configure(text="Expiry date of %s is not a date." % ln.get("product_name_en"))
                    return
            ln["batch_no"] = bv.get().strip() or None
            ln["expiry_date"] = e or None
        cb = self.on_done
        self.destroy()
        if cb:
            cb()
