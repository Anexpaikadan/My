# ============================================================
# DayBill ERP - Product AI windows
#   CleanupDialog        #13  check the product list, approve fixes
#   InvoiceImportDialog  #11  supplier invoice (PDF / photo) → new
#                             products + a ready Purchase invoice
#   run_bg()             network work in a thread, result on the Tk thread
# ============================================================

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import product_ai as PA


def run_bg(widget, fn, done, fail=None):
    """fn() runs in a thread (network only — no Tk, no database);
    done(result) / fail(exception) run on the Tk thread."""
    box = {}

    def work():
        try:
            box["ok"] = fn()
        except Exception as e:          # noqa
            box["err"] = e
    threading.Thread(target=work, daemon=True).start()

    def poll():
        if "ok" not in box and "err" not in box:
            try:
                widget.after(150, poll)
            except Exception:
                pass
            return
        try:
            if "err" in box:
                (fail or (lambda e: messagebox.showwarning("AI", str(e))))(box["err"])
            else:
                done(box["ok"])
        except tk.TclError:
            pass                        # window closed meanwhile
    widget.after(150, poll)


def _ai_ready():
    try:
        from modules import ai_client
        return ai_client.enabled()
    except Exception:
        return False


def _win(parent, title, geo):
    C = cfg.theme()
    w = tk.Toplevel(parent)
    w.title(title)
    w.configure(bg=C["content_bg"])
    w.geometry(geo)
    try:
        w.transient(parent.winfo_toplevel())
    except Exception:
        pass
    w.bind("<Escape>", lambda e: w.destroy())
    return w, C


def _btn(parent, text, cmd, C, kind="normal", side="left"):
    bg, fg = {"primary": (C["primary"], "white"), "success": (C["success"], "white"),
              "normal": (C["card_bg"], C["text_primary"])}[kind]
    b = tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 9, "bold" if kind != "normal" else "normal"),
                  bg=bg, fg=fg, relief="flat", padx=12, pady=6, cursor="hand2",
                  highlightthickness=1 if kind == "normal" else 0,
                  highlightbackground=C["border"])
    b.pack(side=side, padx=3)
    return b


# ══════════════════════════════════════════════════════════════
#  #13  Clean-up assistant
# ══════════════════════════════════════════════════════════════
KIND_TEXT = {"price": "💲 Price", "vat": "🧾 VAT", "duplicate": "👯 Duplicate",
             "barcode": "🏷 Barcode", "arabic": "🔤 Arabic name", "category": "🗂 Category",
             "spelling": "✏ Spelling"}


class CleanupDialog:
    def __init__(self, parent, on_change=None):
        self.on_change = on_change
        self.win, C = _win(parent, "Product Clean-up Assistant", "1080x640")
        self.C = C
        head = tk.Frame(self.win, bg=C["primary"]); head.pack(fill="x")
        tk.Label(head, text="🧹  Product Clean-up Assistant", font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=14, pady=8)
        tk.Label(self.win, text="Checks every product for wrong prices, wrong VAT, duplicates, "
                 "missing barcodes and Arabic names. Tick the fixes you agree with and press "
                 "Fix selected — nothing changes until you do.",
                 font=("Segoe UI", 9), bg=C["content_bg"], fg=C["text_secondary"],
                 wraplength=1020, justify="left").pack(anchor="w", padx=16, pady=(8, 2))
        self.chips = tk.Frame(self.win, bg=C["content_bg"]); self.chips.pack(fill="x", padx=14)
        wrap = tk.Frame(self.win, bg=C["content_bg"]); wrap.pack(fill="both", expand=True, padx=14, pady=6)
        cols = ("sel", "kind", "code", "name", "problem", "fix")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended")
        for c, t_, w, anc in (("sel", "✔", 36, "center"), ("kind", "Type", 120, "w"),
                              ("code", "Code", 70, "w"), ("name", "Product", 230, "w"),
                              ("problem", "Problem", 360, "w"), ("fix", "Suggested fix", 200, "w")):
            self.tree.heading(c, text=t_)
            self.tree.column(c, width=w, anchor=anc, stretch=c in ("problem", "name"))
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("fixed", foreground=C["success"])
        self.tree.tag_configure("info", foreground=C["text_secondary"])
        self.tree.bind("<Button-1>", self._click)
        self.tree.bind("<Double-1>", self._open_product)
        self.tree.bind("<space>", lambda e: self._toggle_sel())
        bar = tk.Frame(self.win, bg=C["content_bg"]); bar.pack(fill="x", padx=14, pady=(0, 10))
        _btn(bar, "☑ Tick all fixable", self._tick_all, C)
        _btn(bar, "☐ Untick all", self._untick_all, C)
        self.spell_btn = _btn(bar, "✨ Check spelling (AI)", self._spelling, C)
        _btn(bar, "🔄 Scan again", self._scan, C)
        _btn(bar, "Close", self.win.destroy, C, side="right")
        self.fix_btn = _btn(bar, "✔ Fix selected", self._fix_selected, C, "success", side="right")
        self.status = tk.StringVar()
        tk.Label(self.win, textvariable=self.status, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", padx=16, pady=(0, 8))
        self.issues, self.ticked, self.done = [], set(), set()
        self._scan()

    def _scan(self):
        self.status.set("Checking products…"); self.win.update_idletasks()
        self.issues = PA.cleanup_scan()
        self.ticked = {i["id"] for i in self.issues if i["fix"]}
        self.done = set()
        self._fill()

    def _fill(self):
        C = self.C
        self.tree.delete(*self.tree.get_children())
        for i in self.issues:
            tag = "fixed" if i["id"] in self.done else ("" if i["fix"] else "info")
            mark = "✅" if i["id"] in self.done else ("☑" if i["id"] in self.ticked else
                                                    ("☐" if i["fix"] else "·"))
            self.tree.insert("", "end", iid=i["id"], tags=(tag,),
                             values=(mark, KIND_TEXT.get(i["kind"], i["kind"]), i["code"],
                                     i["name"], i["problem"],
                                     i["fix_label"] or "open the product (double-click)"))
        for w in self.chips.winfo_children():
            w.destroy()
        counts = {}
        for i in self.issues:
            if i["id"] not in self.done:
                counts[i["kind"]] = counts.get(i["kind"], 0) + 1
        if not counts:
            tk.Label(self.chips, text="✅  No problems found — your product list is clean.",
                     font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                     fg=C["success"]).pack(side="left", pady=4)
        for k, n in counts.items():
            tk.Label(self.chips, text=f" {KIND_TEXT.get(k, k)}  {n} ", font=("Segoe UI", 9, "bold"),
                     bg=C["card_bg"], fg=C["text_primary"], highlightthickness=1,
                     highlightbackground=C["border"]).pack(side="left", padx=(0, 6), pady=4)
        fixable = sum(1 for i in self.issues if i["fix"] and i["id"] not in self.done)
        self.status.set(f"{len(self.issues) - len(self.done)} problem(s), {fixable} can be "
                        f"fixed automatically. AI: {'on' if _ai_ready() else 'off (offline translation)'}")

    def _click(self, e):
        if self.tree.identify_column(e.x) != "#1":
            return
        iid = self.tree.identify_row(e.y)
        if iid:
            self._toggle(iid)
            return "break"

    def _toggle(self, iid):
        i = next((x for x in self.issues if x["id"] == iid), None)
        if not i or not i["fix"] or iid in self.done:
            return
        self.ticked.symmetric_difference_update({iid})
        self.tree.set(iid, "sel", "☑" if iid in self.ticked else "☐")

    def _toggle_sel(self):
        for iid in self.tree.selection():
            self._toggle(iid)

    def _tick_all(self):
        self.ticked = {i["id"] for i in self.issues if i["fix"] and i["id"] not in self.done}
        self._fill()

    def _untick_all(self):
        self.ticked = set(); self._fill()

    def _open_product(self, e=None):
        iid = self.tree.focus()
        i = next((x for x in self.issues if x["id"] == iid), None)
        if not i:
            return
        try:
            from ui.products import ProductForm
            ProductForm(self.win, product_id=i["product_id"], on_save=lambda *a: None)
        except Exception as ex:
            messagebox.showerror("Product", str(ex)[:200], parent=self.win)

    def _spelling(self):
        if not _ai_ready():
            messagebox.showinfo("AI", "Spelling check uses online AI.\n\nSettings ▸ AI ▸ paste "
                                      "your Claude API key first.", parent=self.win)
            return
        prods = PA._q("SELECT product_id, product_code, product_name_en FROM products "
                      "WHERE ISNULL(is_active,1)=1 ORDER BY product_id")[:300]
        names = [p["product_name_en"] for p in prods]
        self.spell_btn.configure(state="disabled", text="✨ Checking…")
        self.status.set(f"AI is checking {len(names)} names…")
        from modules import ai_client

        def work():
            out = {}
            for s in range(0, len(names), 80):
                for k, v in ai_client.spelling_fixes(names[s:s + 80]).items():
                    out[s + k] = v
            return out

        def done(fixes):
            self.spell_btn.configure(state="normal", text="✨ Check spelling (AI)")
            new = []
            for idx, fixed in fixes.items():
                p = prods[idx]
                new.append({"id": f"spelling:{p['product_id']}", "kind": "spelling",
                            "product_id": p["product_id"], "code": p["product_code"],
                            "name": p["product_name_en"],
                            "problem": f"Spelling: “{p['product_name_en']}” → “{fixed}”",
                            "fix_label": "Use the corrected name",
                            "fix": {"action": "rename", "name": fixed}})
            known = {i["id"] for i in self.issues}
            self.issues += [n for n in new if n["id"] not in known]
            self.ticked |= {n["id"] for n in new}
            self._fill()
            self.status.set(f"Spelling: {len(new)} name(s) to correct.  " + self.status.get())

        def fail(e):
            self.spell_btn.configure(state="normal", text="✨ Check spelling (AI)")
            messagebox.showwarning("AI", str(e), parent=self.win)
        run_bg(self.win, work, done, fail)

    def _fix_selected(self):
        from modules import permissions as _pm
        if not _pm.allowed("products", "edit"):
            return
        todo = [i for i in self.issues if i["id"] in self.ticked and i["id"] not in self.done]
        if not todo:
            self.status.set("Nothing ticked.")
            return
        if not messagebox.askyesno("Fix products", f"Apply {len(todo)} fix(es)?", parent=self.win):
            return
        ar_items = [i for i in todo if (i["fix"] or {}).get("action") == "arabic"]
        others = [i for i in todo if i not in ar_items]
        n_ok = 0
        for i in others:
            ok, _m = PA.apply_fix(i)
            if ok:
                self.done.add(i["id"]); n_ok += 1
        if not ar_items:
            self._after_fix(n_ok)
            return
        names = [i["name"] for i in ar_items]
        if _ai_ready():
            from modules import ai_client
            self.fix_btn.configure(state="disabled", text="✨ Translating…")

            def work():
                out = []
                for s in range(0, len(names), 60):
                    out += ai_client.translate_names(names[s:s + 60], "ar")
                return out

            def done(ars):
                self.fix_btn.configure(state="normal", text="✔ Fix selected")
                self._apply_arabic(ar_items, ars, n_ok, "AI")

            def fail(e):
                self.fix_btn.configure(state="normal", text="✔ Fix selected")
                messagebox.showwarning("AI", f"{e}\n\nUsing offline translation instead.",
                                       parent=self.win)
                self._apply_arabic(ar_items, [PA.translate_offline(n) for n in names], n_ok, "offline")
            run_bg(self.win, work, done, fail)
        else:
            self._apply_arabic(ar_items, [PA.translate_offline(n) for n in names], n_ok, "offline")

    def _apply_arabic(self, items, ars, n_ok, src):
        for i, ar in zip(items, ars):
            ok, _m = PA.apply_fix(i, arabic=ar)
            if ok:
                self.done.add(i["id"]); n_ok += 1
                self.tree.set(i["id"], "fix", f"→ {ar}")
        self._after_fix(n_ok, src)

    def _after_fix(self, n_ok, src=""):
        self.ticked -= self.done
        self._fill()
        self.status.set(f"✅ {n_ok} fix(es) applied" + (f" (Arabic: {src})" if src else "") +
                        ".  " + self.status.get())
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════
#  #11  Supplier invoice → products + purchase
# ══════════════════════════════════════════════════════════════
class InvoiceImportDialog:
    def __init__(self, parent, on_change=None, path=None):
        self.parent = parent
        self.on_change = on_change
        self.win, C = _win(parent, "Supplier Invoice → Products & Purchase", "1160x680")
        self.C = C
        head = tk.Frame(self.win, bg=C["primary"]); head.pack(fill="x")
        tk.Label(head, text="🧾  Supplier Invoice  →  Products & Purchase  (AI)",
                 font=("Segoe UI", 13, "bold"), bg=C["primary"], fg="white").pack(
                     side="left", padx=14, pady=8)
        top = tk.Frame(self.win, bg=C["content_bg"]); top.pack(fill="x", padx=14, pady=(10, 4))
        _btn(top, "📄 Choose invoice (PDF / photo)…", self._choose, C, "primary")
        self.file_var = tk.StringVar(value="No file chosen")
        tk.Label(top, textvariable=self.file_var, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=8)
        hdr = tk.Frame(self.win, bg=C["content_bg"]); hdr.pack(fill="x", padx=14, pady=4)
        self.sup_rows = PA._q("SELECT supplier_id, supplier_code, supplier_name_en FROM suppliers "
                              "ORDER BY supplier_name_en")
        tk.Label(hdr, text="Supplier", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left")
        self.sup_var = tk.StringVar()
        self.sup_cb = ttk.Combobox(hdr, textvariable=self.sup_var, state="readonly", width=34,
                                   values=[f"{s['supplier_code']} — {s['supplier_name_en']}"
                                           for s in self.sup_rows])
        self.sup_cb.pack(side="left", padx=(4, 4))
        self.sup_read = tk.StringVar()
        tk.Label(hdr, textvariable=self.sup_read, font=("Segoe UI", 8), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(side="left", padx=(0, 12))
        tk.Label(hdr, text="Supplier inv. no.", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left")
        self.inv_no = tk.StringVar()
        tk.Entry(hdr, textvariable=self.inv_no, width=16).pack(side="left", padx=(4, 12), ipady=2)
        tk.Label(hdr, text="Date", font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg=C["primary"]).pack(side="left")
        self.inv_date = tk.StringVar()
        tk.Entry(hdr, textvariable=self.inv_date, width=12).pack(side="left", padx=4, ipady=2)

        wrap = tk.Frame(self.win, bg=C["content_bg"]); wrap.pack(fill="both", expand=True, padx=14, pady=6)
        cols = ("n", "item", "barcode", "qty", "unit", "price", "vat", "total", "match")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for c, t_, w, anc in (("n", "#", 34, "center"), ("item", "Invoice item", 250, "w"),
                              ("barcode", "Barcode", 110, "w"), ("qty", "Qty", 55, "e"),
                              ("unit", "Unit", 80, "w"), ("price", "Price (excl VAT)", 100, "e"),
                              ("vat", "VAT %", 50, "e"), ("total", "Total", 90, "e"),
                              ("match", "In DayBill", 300, "w")):
            self.tree.heading(c, text=t_)
            self.tree.column(c, width=w, anchor=anc, stretch=c in ("item", "match"))
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("new", foreground=C["primary"])
        self.tree.tag_configure("skip", foreground=C["text_secondary"])
        self.tree.bind("<Double-1>", lambda e: self._change_match())
        bar = tk.Frame(self.win, bg=C["content_bg"]); bar.pack(fill="x", padx=14, pady=(0, 4))
        _btn(bar, "🔁 Change match…", self._change_match, C)
        _btn(bar, "✏ Edit line…", self._edit_line, C)
        _btn(bar, "⏭ Skip / include line", self._skip_line, C)
        _btn(bar, "Cancel", self.win.destroy, C, side="right")
        self.go_btn = _btn(bar, "✔ Create products & open Purchase", self._go, C, "success", side="right")
        self.go_btn.configure(state="disabled")
        self.status = tk.StringVar(value="Choose the supplier's invoice. AI reads the items, "
                                         "matches them to your products and makes the new ones.")
        tk.Label(self.win, textvariable=self.status, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"], wraplength=1100, justify="left").pack(
                     anchor="w", padx=16, pady=(0, 10))
        self.data, self.lines = None, []
        if not _ai_ready():
            self.status.set("⚠ Reading invoices needs online AI. Settings ▸ AI ▸ paste your "
                            "Claude API key, then come back.")
        if path:
            self._read(path)

    # ── read ─────────────────────────────────────────────────
    def _choose(self):
        path = filedialog.askopenfilename(
            parent=self.win, title="Supplier invoice",
            filetypes=[("Invoice PDF or photo", "*.pdf *.jpg *.jpeg *.png *.webp"),
                       ("All files", "*.*")])
        if path:
            self._read(path)

    def _read(self, path):
        if not _ai_ready():
            messagebox.showinfo("AI", "Reading invoices uses online AI.\n\nSettings ▸ AI ▸ paste "
                                      "your Claude API key first.", parent=self.win)
            return
        from modules import ai_client
        self.file_var.set(os.path.basename(path))
        self.status.set("✨ AI is reading the invoice… (10–40 seconds)")
        self.go_btn.configure(state="disabled")
        run_bg(self.win, lambda: ai_client.read_invoice(path), self._loaded,
               lambda e: (self.status.set("⚠ " + str(e)),
                          messagebox.showwarning("AI", str(e), parent=self.win)))

    def _loaded(self, data):
        self.data = data
        rows = PA._products()
        self.lines = []
        for ln in data.get("lines") or []:
            m = PA.match_line(ln, rows)
            self.lines.append({"src": ln, "match": m, "skip": False})
        sup = PA.match_supplier(data.get("supplier_name"), data.get("supplier_vat_no"))
        if sup:
            idx = next((k for k, s in enumerate(self.sup_rows)
                        if s["supplier_id"] == sup["supplier_id"]), None)
            if idx is not None:
                self.sup_cb.current(idx)
        self.sup_read.set(f"(invoice: {data.get('supplier_name') or '?'}"
                          + (f", VAT {data['supplier_vat_no']}" if data.get("supplier_vat_no") else "")
                          + ("" if sup else "  — not found, pick or add the supplier") + ")")
        self.inv_no.set(str(data.get("invoice_number") or ""))
        self.inv_date.set(str(data.get("invoice_date") or "")[:10])
        self._fill()
        self.go_btn.configure(state="normal" if self.lines else "disabled")

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        sub = vat = 0.0
        for k, L in enumerate(self.lines):
            s = L["src"]
            q, p, r = float(s["quantity"]), float(s["unit_price_excl_vat"]), float(s.get("vat_rate") or 0)
            tot = q * p * (1 + r / 100)
            if not L["skip"]:
                sub += q * p; vat += q * p * r / 100
            unit = str(s.get("unit") or "PCs")
            if float(s.get("pieces_per_unit") or 1) > 1:
                unit += f" ×{float(s['pieces_per_unit']):g}"
            if L["skip"]:
                mt, tag = "⏭ skipped", "skip"
            elif L["match"]:
                mt, tag = f"✓ {L['match']['name']}  ({L['match']['how']})", ""
            else:
                mt, tag = "✚ NEW product will be created", "new"
            self.tree.insert("", "end", iid=str(k), tags=(tag,),
                             values=(k + 1, s.get("description", ""), s.get("barcode", ""),
                                     f"{q:g}", unit, f"{p:,.2f}", f"{r:g}", f"{tot:,.2f}", mt))
        n_new = sum(1 for L in self.lines if not L["skip"] and not L["match"])
        n_old = sum(1 for L in self.lines if not L["skip"] and L["match"])
        msg = (f"{len(self.lines)} line(s): {n_old} matched, {n_new} new.  "
               f"Lines total {sub + vat:,.2f} (VAT {vat:,.2f})")
        t = (self.data or {}).get("total_incl_vat")
        try:
            if t:
                ok = abs(float(t) - (sub + vat)) <= max(1.0, float(t) * 0.005)
                msg += (f"  ·  invoice total {float(t):,.2f} " +
                        ("✓ matches" if ok else "⚠ differs — check the lines"))
        except Exception:
            pass
        self.status.set(msg + ".  Double-click a line to change its match.")

    def _sel(self):
        s = self.tree.focus() or (self.tree.selection() or [None])[0]
        return int(s) if s not in (None, "") else None

    def _skip_line(self):
        k = self._sel()
        if k is None:
            return
        self.lines[k]["skip"] = not self.lines[k]["skip"]
        self._fill(); self.tree.focus(str(k)); self.tree.selection_set(str(k))

    def _edit_line(self):
        k = self._sel()
        if k is None:
            return
        s = self.lines[k]["src"]
        w, C = _win(self.win, "Edit line", "460x300")
        vars_ = {}
        for key, lbl in (("description", "Name (English)"), ("name_ar", "Name (Arabic)"),
                         ("barcode", "Barcode"), ("quantity", "Quantity"),
                         ("unit", "Unit"), ("pieces_per_unit", "Pieces per unit"),
                         ("unit_price_excl_vat", "Price excl VAT"), ("vat_rate", "VAT %")):
            r = tk.Frame(w, bg=C["content_bg"]); r.pack(fill="x", padx=14, pady=2)
            tk.Label(r, text=lbl, width=16, anchor="w", bg=C["content_bg"]).pack(side="left")
            v = tk.StringVar(value=str(s.get(key, "") if s.get(key) is not None else ""))
            tk.Entry(r, textvariable=v).pack(side="left", fill="x", expand=True)
            vars_[key] = v

        def ok():
            for key, v in vars_.items():
                val = v.get().strip()
                if key in ("quantity", "pieces_per_unit", "unit_price_excl_vat", "vat_rate"):
                    try:
                        val = float(val or 0)
                    except ValueError:
                        messagebox.showwarning("Edit line", f"{key}: number please", parent=w)
                        return
                s[key] = val
            if s.get("barcode") and not self.lines[k]["match"]:
                self.lines[k]["match"] = PA.match_line(s)
            w.destroy(); self._fill()
        _btn(w, "OK", ok, C, "primary", side="right")

    def _change_match(self):
        k = self._sel()
        if k is None:
            return
        L = self.lines[k]
        w, C = _win(self.win, "Which product is this?", "560x430")
        tk.Label(w, text=f"Invoice item:  {L['src'].get('description', '')}",
                 font=("Segoe UI", 10, "bold"), bg=C["content_bg"]).pack(anchor="w", padx=14, pady=(10, 4))
        q = tk.StringVar(value=" ".join(PA._tokens(L["src"].get("description", ""))[:2]))
        e = tk.Entry(w, textvariable=q, font=("Segoe UI", 10)); e.pack(fill="x", padx=14, ipady=3)
        lb = tk.Listbox(w, font=("Segoe UI", 10), height=12); lb.pack(fill="both", expand=True, padx=14, pady=6)
        rows = PA._products()
        shown = []

        def refresh(*_a):
            text = q.get().strip()
            scored = sorted(rows, key=lambda p: -PA.similarity(text or "x", p["product_name_en"])
                            if text else 0)
            if text:
                low = text.lower()
                scored = [p for p in scored if low in p["product_name_en"].lower()
                          or low in str(p["product_code"]).lower()] or scored
            shown[:] = scored[:60]
            lb.delete(0, "end")
            lb.insert("end", "✚  Create as a NEW product")
            for p in shown:
                lb.insert("end", f"{p['product_code']}  ·  {p['product_name_en']}")
        q.trace("w", refresh); refresh()

        def ok(_e=None):
            sel = lb.curselection()
            if not sel:
                return
            if sel[0] == 0:
                L["match"] = None
            else:
                p = shown[sel[0] - 1]
                L["match"] = {"product_id": p["product_id"], "unit_name": None, "how": "you",
                              "name": p["product_name_en"]}
            L["skip"] = False
            w.destroy(); self._fill()
        lb.bind("<Double-1>", ok)
        _btn(w, "Use this", ok, C, "primary", side="right")

    # ── create products + purchase ───────────────────────────
    def _go(self):
        from modules import permissions as _pm
        if not (_pm.allowed("products", "add") and _pm.allowed("purchase", "add")):
            return
        if self.sup_cb.current() < 0:
            messagebox.showwarning("Supplier", "Pick the supplier (add it in Suppliers first if "
                                               "it is new).", parent=self.win)
            return
        new = [L for L in self.lines if not L["skip"] and not L["match"]]
        if new and not messagebox.askyesno(
                "Create products",
                f"Create {len(new)} new product(s)?\n\nArabic names, category and VAT are "
                f"filled automatically; selling price = cost + "
                f"{float(cfg.get('ai_markup_pct', 25) or 25):g}% (check them later in Products).",
                parent=self.win):
            return
        if new:
            names = [str(L["src"].get("description") or "") for L in new]
            need = [k for k, L in enumerate(new) if not str(L["src"].get("name_ar") or "").strip()]
            if need and _ai_ready():
                from modules import ai_client
                self.go_btn.configure(state="disabled", text="✨ Translating names…")

                def work():
                    return ai_client.translate_names([names[k] for k in need], "ar")

                def done(ars):
                    for k, ar in zip(need, ars):
                        new[k]["src"]["name_ar"] = ar
                    self._create_and_open(new)

                def fail(e):
                    for k in need:
                        new[k]["src"]["name_ar"] = PA.translate_offline(names[k])
                    self._create_and_open(new)
                run_bg(self.win, work, done, fail)
                return
            for k in need:
                new[k]["src"]["name_ar"] = PA.translate_offline(names[k])
        self._create_and_open(new)

    def _create_and_open(self, new):
        made = 0
        for L in new:
            s = L["src"]
            name = str(s.get("description") or "").strip()
            sug = PA.suggest_from_similar(name) or {}
            cat = sug.get("category_id") or (PA._q("SELECT TOP 1 category_id FROM product_categories "
                                                   "ORDER BY category_id") or [{}])[0].get("category_id")
            rate = __import__("modules.country", fromlist=["x"]).rate_or_std(s.get("vat_rate"))
            vat_id = PA.default_vat_for_rate(rate)
            ppu = float(s.get("pieces_per_unit") or 1) or 1.0
            unit = str(s.get("unit") or "PCs").strip() or "PCs"
            is_pack = ppu > 1 or unit.lower() in ("box", "carton", "ctn", "case", "pack", "dozen")
            if unit.lower() == "dozen" and ppu <= 1:
                ppu = 12.0
            cost_base = float(s["unit_price_excl_vat"]) / (ppu if ppu > 1 else 1)
            price = PA.selling_price_from_cost(cost_base, rate)
            try:
                pid = PA.create_product(name, s.get("name_ar") or name, cat, vat_id, cost_base,
                                        price, barcode=s.get("barcode") if not is_pack else "",
                                        pack=(unit.title() if unit.lower() not in ("pcs", "piece") else "Box",
                                              ppu, s.get("barcode") or "") if (is_pack and ppu > 1) else None,
                                        brand_id=sug.get("brand_id"))
            except Exception as e:
                messagebox.showerror("Create product", f"{name}:\n{str(e)[:200]}", parent=self.win)
                continue
            L["match"] = {"product_id": pid, "unit_name": (unit.title() if is_pack and ppu > 1 else "PCs"),
                          "how": "new", "name": name}
            made += 1
        self._open_purchase(made)

    def _open_purchase(self, made):
        import ui.purchases as PU
        try:
            f = PU.PurchaseForm(self.parent, None, None)
        except Exception as e:
            messagebox.showerror("Purchase", str(e)[:200], parent=self.win)
            return
        try:
            f.sup_cb.current(next(k for k, s in enumerate(f.suppliers)
                                  if s["supplier_id"] == self.sup_rows[self.sup_cb.current()]["supplier_id"]))
        except Exception:
            pass
        try:
            f.hdr["supinv"].set(self.inv_no.get().strip())
            if self.inv_date.get().strip():
                f.hdr["date"].set(self.inv_date.get().strip())
        except Exception:
            pass
        g = f.grid
        added = 0
        for L in self.lines:
            if L["skip"] or not L["match"]:
                continue
            s = L["src"]
            p = next((x for x in g.products if x["product_id"] == L["match"]["product_id"]), None)
            if p is None:
                continue
            idx = next((i for i, ln in enumerate(g.lines) if not ln.get("product_id")), None)
            if idx is None:
                g.add_blank_row(); idx = len(g.lines) - 1
            units = g.product_units.get(p["product_id"], [])
            want = L["match"].get("unit_name") or s.get("unit")
            ppu = float(s.get("pieces_per_unit") or 1) or 1.0
            u = None
            if want:
                u = next((x for x in units if str(x.get("unit_name_en", "")).lower() == str(want).lower()), None)
            if u is None and ppu > 1:
                u = next((x for x in units if abs(float(x.get("conversion_factor") or 1) - ppu) < 1e-6), None)
            if u is None and ppu <= 1:
                u = next((x for x in units if abs(float(x.get("conversion_factor") or 1) - 1) < 1e-6), None)
            g._apply_product(idx, p, matched_unit=u, merge=False)
            ln = g.lines[idx]
            price = float(s["unit_price_excl_vat"])
            if u is None and ppu > 1:
                price = price / ppu                   # no pack unit: buy in pieces
                ln["quantity"] = float(s["quantity"]) * ppu
            else:
                ln["quantity"] = float(s["quantity"])
            rate = float(ln.get("vat_rate") or 0)
            ln["unit_price"] = round(price * (1 + rate / 100.0), 4) \
                if getattr(g, "tax_mode", "exclusive") == "inclusive" else round(price, 4)
            g._recalc(ln)
            added += 1
        g._refresh()
        try:
            f._on_change()
        except Exception:
            pass
        self.win.destroy()
        try:
            from ui.fluent_widgets import show_toast
            show_toast(f.win if hasattr(f, "win") else self.parent,
                       f"✨ {made} new product(s) created · {added} line(s) filled — check and Save",
                       kind="success")
        except Exception:
            pass
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass
        self.purchase_form = f
