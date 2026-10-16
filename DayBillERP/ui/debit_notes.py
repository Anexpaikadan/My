# ============================================================
# DayBill ERP - Debit Notes page (Sales ▸ Debit Notes)  v6.0
# ------------------------------------------------------------
# Raise the amount of an invoice that is already issued (price too
# low, a forgotten delivery charge …). The note refers to the invoice,
# says why, goes on the customer's account (or is paid in cash), is
# signed for ZATCA (type 383) and printed like an invoice.
# ============================================================
import tkinter as tk
from tkinter import messagebox
from datetime import date

from modules import debit_note as DN
from ui import v6_kit as K


class DebitNotesView:
    def __init__(self, parent):
        self.page = K.Page(parent, "➕  Debit Notes",
                           "Add to an invoice that is already issued — a price that was too low or a "
                           "charge that was forgotten. To take something OFF an invoice, make a Sales "
                           "Return (credit note) instead.")
        self.C = C = self.page.C
        self.frame = self.page.frame
        self.org = None
        if not DN.ready():
            self.page.say("⚠ Debit notes need the v6.0 database update — Updates ▸ Apply All Updates.",
                          ok=False)
            return
        body = self.page.body
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        self._form(body, C).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._list(body, C).grid(row=0, column=1, sticky="nsew")
        self.load()

    def _form(self, parent, C):
        c = K.card(parent, C, "New debit note")
        r1 = tk.Frame(c, bg=C["card_bg"]); r1.pack(fill="x", padx=10)
        self.inv_v = tk.StringVar()
        e = K.entry(r1, C, "Original invoice number *", self.inv_v, 16)
        e.bind("<Return>", lambda ev: self._find())
        K.button(r1, C, "🔎 Find", self._find).pack_configure(pady=(14, 0))
        self.org_v = tk.StringVar(value="Type the invoice number and press Find.")
        tk.Label(c, textvariable=self.org_v, font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["text_secondary"], anchor="w", justify="left").pack(fill="x", padx=12, pady=(2, 6))
        self.lines = K.tree(c, [("desc", "What is added", 260, "w"), ("qty", "Qty", 60, "e"),
                                ("price", "Price (no VAT)", 100, "e"), ("vat", "VAT %", 60, "e"),
                                ("total", "Total with VAT", 110, "e")], height=6)
        r2 = tk.Frame(c, bg=C["card_bg"]); r2.pack(fill="x", padx=10)
        self.d_v, self.q_v, self.p_v, self.r_v = (tk.StringVar(), tk.StringVar(value="1"),
                                                  tk.StringVar(), tk.StringVar(value="15"))
        K.entry(r2, C, "Description *", self.d_v, 26)
        K.entry(r2, C, "Qty", self.q_v, 5, justify="right")
        K.entry(r2, C, "Price without VAT *", self.p_v, 10, justify="right")
        K.entry(r2, C, "VAT %", self.r_v, 5, justify="right")
        r3 = tk.Frame(c, bg=C["card_bg"]); r3.pack(fill="x", padx=10, pady=(4, 0))
        K.button(r3, C, "＋ Add line", self._add_line)
        K.button(r3, C, "✕ Remove line", self._del_line)
        r4 = tk.Frame(c, bg=C["card_bg"]); r4.pack(fill="x", padx=10, pady=(8, 0))
        self.reason_v = tk.StringVar()
        K.entry(r4, C, "Reason (shown to ZATCA and on the print) *", self.reason_v, 48)
        self.pay_v = tk.StringVar(value="On the customer's account")
        K.combo(r4, C, "Paid", self.pay_v, ["On the customer's account", "Cash now"], 22)
        self.tot_v = tk.StringVar(value="Total  0.00")
        tk.Label(c, textvariable=self.tot_v, font=("Segoe UI", 13, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="e", padx=14, pady=(6, 0))
        r5 = tk.Frame(c, bg=C["card_bg"]); r5.pack(fill="x", padx=10, pady=(6, 10))
        K.button(r5, C, "💾 Save debit note", lambda: self._save(False), primary=True)
        K.button(r5, C, "💾 Save + Print", lambda: self._save(True))
        K.button(r5, C, "Clear", self._clear)
        self._rows = []
        return c

    def _list(self, parent, C):
        c = K.card(parent, C, "Debit notes")
        self.tree = K.tree(c, [("no", "No.", 110, "w"), ("date", "Date", 85, "center"),
                               ("inv", "For invoice", 90, "w"), ("cust", "Customer", 150, "w"),
                               ("total", "Total", 90, "e"), ("z", "ZATCA", 80, "center")], height=16)
        r = tk.Frame(c, bg=C["card_bg"]); r.pack(fill="x", padx=10, pady=(0, 10))
        K.button(r, C, "🖨 Print selected", self._print_selected)
        K.button(r, C, "↻ Refresh", self.load)
        return c

    # ── actions ────────────────────────────────────────────────
    def _find(self):
        org = DN.find_invoice(self.inv_v.get())
        self.org = org
        if not org:
            self.org_v.set("❌ No invoice with this number.")
            return
        if str(org.get("invoice_status") or "").lower() != "confirmed":
            self.org_v.set("❌ This invoice is not confirmed (draft / cancelled).")
            self.org = None
            return
        prev = DN.notes_for(org.get("invoice_number"))
        self.org_v.set("✓ %s  ·  %s  ·  %s  ·  total %s%s"
                       % (org.get("invoice_number"), str(org.get("invoice_date"))[:10],
                          org.get("customer_name_en") or "", K.money(org.get("total_amount")),
                          ("  ·  %d earlier debit note(s)" % len(prev)) if prev else ""))

    def _add_line(self):
        q, p, r = K.num(self.q_v, 1.0), K.num(self.p_v), K.num(self.r_v, 15.0)
        d = self.d_v.get().strip()
        if not d or p is None or p <= 0 or q is None or q <= 0 or r is None or r < 0:
            self.page.say("A line needs a description, a quantity and a price above 0.", ok=False)
            return
        self._rows.append({"description": d, "quantity": q, "unit_price": p, "vat_rate": r})
        self.d_v.set(""); self.p_v.set(""); self.q_v.set("1")
        self._show_rows()

    def _del_line(self):
        sel = self.lines.selection()
        if sel:
            del self._rows[int(sel[0])]
            self._show_rows()

    def _show_rows(self):
        self.lines.delete(*self.lines.get_children())
        rows, taxable, vat, total = DN.compute(self._rows)
        for i, ln in enumerate(self._rows):
            amt = round(ln["quantity"] * ln["unit_price"], 2)
            self.lines.insert("", "end", iid=str(i), values=(
                ln["description"], "%g" % ln["quantity"], K.money(ln["unit_price"]),
                "%g" % ln["vat_rate"], K.money(amt * (1 + ln["vat_rate"] / 100.0))))
        self.tot_v.set("Taxable %s   VAT %s   Total  %s" % (K.money(taxable), K.money(vat), K.money(total)))

    def _clear(self):
        self.org = None
        self._rows = []
        for v in (self.inv_v, self.reason_v, self.d_v, self.p_v):
            v.set("")
        self.org_v.set("Type the invoice number and press Find.")
        self._show_rows()

    def _save(self, do_print):
        from modules import permissions as _pm
        if not _pm.allowed("sales", "add", parent=self.frame):
            return
        if not self.org:
            self.page.say("Find the original invoice first.", ok=False)
            return
        if self.d_v.get().strip() and K.num(self.p_v):
            self._add_line()
        try:
            iid, number = DN.create(self.org["invoice_id"], self._rows, self.reason_v.get(),
                                    pay="cash" if self.pay_v.get().startswith("Cash") else "credit",
                                    when=date.today().isoformat())
        except ValueError as e:
            self.page.say(str(e), ok=False)
            return
        except Exception as e:
            self.page.say("Not saved — nothing was kept: %s" % str(e)[:200], ok=False)
            return
        self.page.say("✓ Debit note %s saved for invoice %s." % (number, self.org.get("invoice_number")))
        self._clear()
        self.load()
        if do_print:
            self._print(iid)

    def _print(self, iid):
        try:
            from ui import print_menu
            print_menu.run(self.frame, "sales", iid, "default", status=self.page.status)
        except Exception as e:
            self.page.say("Print: %s" % str(e)[:120], ok=False)

    def _print_selected(self):
        sel = self.tree.selection()
        if sel:
            self._print(int(sel[0]))

    def load(self):
        self.tree.delete(*self.tree.get_children())
        for r in DN.list_notes():
            self.tree.insert("", "end", iid=str(r["invoice_id"]), values=(
                r.get("invoice_number"), str(r.get("invoice_date"))[:10], r.get("original_invoice_no"),
                r.get("customer_name_en") or "", K.money(r.get("total_amount")),
                r.get("zatca_status") or "—"))
