# ============================================================
# DayBill ERP - "Send on WhatsApp" dialog
# ------------------------------------------------------------
#   send_document(parent, kind, doc_id, auto=False, text=None)
#   kind: sales | quotation | purchase_order | receipt | statement
#         | day_close  (doc_id = customer_id for statement, None for
#         day_close with text=...)
# Builds the PDF + message, then sends through modules/whatsapp.py
# (WhatsApp app / web, or the Cloud API — Settings ▸ WhatsApp).
# ============================================================

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import whatsapp as wa

TITLES = {"sales": "Invoice", "quotation": "Quotation", "purchase_order": "Purchase Order",
          "receipt": "Receipt", "statement": "Statement", "day_close": "Day Close Summary"}


def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _m(v):
    return f"{_f(v):,.2f}"


def _iso(v):
    if v is None or v == "":
        return ""
    return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)[:10]


def _company():
    try:
        return db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
    except Exception:
        return {}


def _party(ptype, pid):
    if not pid:
        return {}
    try:
        if ptype == "customer":
            return db.fetchone("SELECT customer_id AS id, customer_code AS code, "
                               "customer_name_en AS name, phone, account_id "
                               "FROM customers WHERE customer_id=?", (pid,)) or {}
        return db.fetchone("SELECT supplier_id AS id, supplier_code AS code, "
                           "supplier_name_en AS name, phone, account_id "
                           "FROM suppliers WHERE supplier_id=?", (pid,)) or {}
    except Exception:
        try:
            tbl, key = (("customers", "customer_id") if ptype == "customer"
                        else ("suppliers", "supplier_id"))
            r = db.fetchone(f"SELECT * FROM {tbl} WHERE {key}=?", (pid,)) or {}
            return {"id": pid, "name": r.get(f"{ptype}_name_en", ""),
                    "phone": r.get("phone", ""), "account_id": r.get("account_id")}
        except Exception:
            return {}


def _ledger_balance(party, ptype):
    acc = party.get("account_id")
    if not acc:
        return 0.0
    try:
        b = _f(db.execute_scalar(
            "SELECT ISNULL(SUM(jl.debit),0) - ISNULL(SUM(jl.credit),0) FROM journal_lines jl "
            "JOIN journal_entries je ON je.journal_id=jl.journal_id "
            "WHERE je.is_posted=1 AND jl.account_id=?", (acc,)))
        return b if ptype == "customer" else -b
    except Exception:
        return 0.0


def build_context(kind, doc_id, text=None):
    """{party_type, party, phone, ctx (message fields), params (template
    body), pdf (callable → path or None), title, filename}"""
    comp = _company()
    cname = comp.get("company_name_en") or "DayBill"
    today = date.today().isoformat()
    out = {"kind": kind, "title": TITLES.get(kind, kind), "pdf": None,
           "party_type": None, "party": {}, "ctx": {"company": cname, "date": today},
           "params": []}
    if kind == "sales":
        inv = db.fetchone("SELECT * FROM sales_invoices WHERE invoice_id=?", (doc_id,)) or {}
        p = _party("customer", inv.get("customer_id"))
        out.update(party_type="customer", party=p)
        due = _f(inv.get("total_amount")) - min(_f(inv.get("paid_amount")), _f(inv.get("total_amount")))
        out["ctx"].update(name=p.get("name") or inv.get("customer_name_en") or "Customer",
                          number=inv.get("invoice_number", ""), date=_iso(inv.get("invoice_date")),
                          total=_m(inv.get("total_amount")), vat=_m(inv.get("vat_amount")),
                          due=_m(due))
        out["title"] = f"Invoice {inv.get('invoice_number', '')}"

        def pdf():
            from modules.pdf_invoice import generate_invoice_pdf
            lines = db.fetchall("SELECT * FROM sales_invoice_lines WHERE invoice_id=? "
                                "ORDER BY line_number", (doc_id,)) or []
            path = os.path.join(wa.pdf_folder(), f"Invoice_{inv.get('invoice_number')}.pdf")
            generate_invoice_pdf(inv, comp, lines, path)
            return path
        out["pdf"] = pdf
    elif kind in ("quotation", "purchase_order"):
        from ui import quotes as Q
        k = Q.CONF[kind]
        h, _lines = Q.load_doc(kind, doc_id)
        h = h or {}
        ptype = k["party"]
        p = _party(ptype, h.get(k["party_id"]))
        out.update(party_type=ptype, party=p)
        out["ctx"].update(name=p.get("name") or h.get(k["party_name"]) or "",
                          number=h.get(k["number"], ""), date=_iso(h.get(k["date"])),
                          total=_m(h.get("total_amount")),
                          valid_until=_iso(h.get("valid_until")),
                          expected=_iso(h.get("expected_date")))
        out["title"] = f"{k['title']} {h.get(k['number'], '')}"
        out["pdf"] = lambda: Q.make_pdf(kind, doc_id, os.path.join(
            wa.pdf_folder(), f"{k['title'].replace(' ', '_')}_{h.get(k['number'])}.pdf"))
    elif kind == "receipt":
        pay = db.fetchone("SELECT * FROM payments WHERE payment_id=?", (doc_id,)) or {}
        is_rec = (pay.get("payment_type") or "receipt") == "receipt"
        ptype = "customer" if is_rec else "supplier"
        p = _party(ptype, pay.get("customer_id") if is_rec else pay.get("supplier_id"))
        out.update(party_type=ptype, party=p)
        out["ctx"].update(name=p.get("name") or pay.get("party_name_en") or "",
                          number=pay.get("payment_number", ""), date=_iso(pay.get("payment_date")),
                          amount=_m(pay.get("amount")), total=_m(pay.get("amount")),
                          balance=_m(_ledger_balance(p, ptype)))
        out["title"] = f"{'Receipt' if is_rec else 'Payment'} {pay.get('payment_number', '')}"

        def pdf():
            from modules.generic_doc_pdf import generate_generic_pdf
            path = os.path.join(wa.pdf_folder(), f"{pay.get('payment_number')}.pdf")
            generate_generic_pdf("receipt_voucher" if is_rec else "payment_voucher",
                                 {"number": pay.get("payment_number"),
                                  "date": _iso(pay.get("payment_date")),
                                  "party_name": out["ctx"]["name"],
                                  "amount": _f(pay.get("amount")), "currency": "SAR",
                                  "narration": pay.get("notes_en") or "",
                                  "payment": pay.get("payment_method") or ""},
                                 comp, [], path,
                                 party_label="Received from" if is_rec else "Paid to",
                                 with_items=False)
            return path
        out["pdf"] = pdf
    elif kind == "statement":
        p = _party("customer", doc_id)
        out.update(party_type="customer", party=p)
        bal = _ledger_balance(p, "customer")
        out["ctx"].update(name=p.get("name", ""), balance=_m(bal), number="", total=_m(bal))
        out["title"] = f"Statement — {p.get('name', '')}"

        def pdf():
            from ui.party_statement import build_statement
            from modules import report_center as RC
            try:
                from config import settings as _cf
                f = _cf.fiscal_year_bounds()[0].isoformat()
            except Exception:
                f = date(date.today().year, 1, 1).isoformat()
            d = build_statement("customer", doc_id, f, today)
            rows = [{"date": f, "doc": "Opening balance", "ref": "", "debit": None,
                     "credit": None, "balance": d["opening"], "_style": "sub"}]
            rows += [dict(r) for r in d["rows"]]
            rows.append({"date": today, "doc": "Closing balance", "ref": "",
                         "debit": d["debit_total"], "credit": d["credit_total"],
                         "balance": d["closing"], "_style": "total"})
            res = {"title": f"Statement of Account — {d['name']}",
                   "subtitle": f"{f}  →  {today}",
                   "columns": [RC.col("date", "Date", width=90), RC.col("doc", "Document", width=160),
                               RC.col("ref", "Reference", width=140),
                               RC.col("debit", "Debit", "money"), RC.col("credit", "Credit", "money"),
                               RC.col("balance", "Balance", "money")],
                   "rows": rows, "totals": None,
                   "summary": [("Opening", d["opening"], "money"),
                               ("Closing balance", d["closing"], "money")], "notes": []}
            path = os.path.join(wa.pdf_folder(), f"Statement_{(d.get('code') or doc_id)}.pdf")
            RC.to_pdf(res, path, comp)
            return path
        out["pdf"] = pdf
    else:   # day_close
        out["party"] = {"name": "Owner", "phone": cfg.get("wa_owner_phone", "")}
        out["ctx"].update(text=text or "", name="Owner")
        out["title"] = "Day Close Summary"
    out["phone"] = wa.normalize_phone(out["party"].get("phone"))
    out["message"] = text if (text and kind != "day_close") else wa.message_for(kind, out["ctx"])
    c = out["ctx"]
    out["params"] = [c.get("name", ""), c.get("number", ""), c.get("total", "")]
    return out


def _send(info, phone, text, attach, parent=None):
    """Returns (ok, message for the user)."""
    pdf_path = None
    if attach and info.get("pdf"):
        pdf_path = info["pdf"]()
    if wa.mode() == "api":
        ok, res = wa.api_send(phone, text, pdf_path, info.get("params"), kind=info.get("kind") or "document")
        wa.log(info["kind"], info.get("doc_id"), phone, ok, res)
        return ok, ("Sent on WhatsApp ✔" if ok else "WhatsApp Cloud API: " + res)
    how = wa.open_chat(phone, text)
    wa.log(info["kind"], info.get("doc_id"), phone, True, "opened chat (" + how + ")")
    if pdf_path:
        wa.show_file(pdf_path)
        return True, ("WhatsApp opened with the message.\n\nThe PDF is saved here:\n"
                      f"{pdf_path}\n\nDrag it into the chat, then press Send.")
    return True, "WhatsApp opened with the message — press Send."


def send_document(parent, kind, doc_id, auto=False, text=None):
    if not wa.enabled():
        messagebox.showinfo("WhatsApp", "WhatsApp is turned off.\n\nTurn it on in "
                            "Settings ▸ WhatsApp (Enable WhatsApp).", parent=parent)
        return None
    info = build_context(kind, doc_id, text)
    info["doc_id"] = doc_id
    if auto and wa.mode() == "api" and info["phone"]:
        ok, msg = _send(info, info["phone"], info["message"], True, parent)
        return ok
    return SendDialog(parent, info)


class SendDialog:
    def __init__(self, parent, info):
        self.info = info
        C = self.C = cfg.theme()
        self.win = tk.Toplevel(parent)
        self.win.title("Send on WhatsApp")
        self.win.configure(bg=C["content_bg"])
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = 560, 470
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.win.minsize(480, 420)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.bind("<Control-Return>", lambda e: self.send())

        hdr = tk.Frame(self.win, bg="#128C7E", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="🟢  " + info["title"], font=("Segoe UI", 12, "bold"),
                 bg="#128C7E", fg="white").pack(side="left", padx=14)
        tk.Label(hdr, text=("Cloud API — sends automatically" if wa.mode() == "api"
                            else "Opens WhatsApp — you press Send"),
                 font=("Segoe UI", 8), bg="#128C7E", fg="#DCF8C6").pack(side="right", padx=14)

        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(fill="both", expand=True,
                                                               padx=16, pady=10)
        g = tk.Frame(body, bg=C["content_bg"]); g.pack(fill="x")
        tk.Label(g, text="To", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        tk.Label(g, text=info["party"].get("name") or "—", font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).grid(row=0, column=1, sticky="w")
        tk.Label(g, text="WhatsApp No. *", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.phone = tk.StringVar(value=info["party"].get("phone") or "")
        e = tk.Entry(g, textvariable=self.phone, width=20, font=("Segoe UI", 11),
                     relief="solid", bd=1)
        e.grid(row=1, column=1, sticky="w", ipady=3)
        tk.Label(g, text="e.g. 0501234567", font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["text_secondary"]).grid(row=1, column=2, sticky="w",
                                                                  padx=8)
        self.save_phone = tk.BooleanVar(value=not bool(info["party"].get("phone")))
        if info.get("party_type") and info["party"].get("id"):
            tk.Checkbutton(g, text="Save this number to the " + info["party_type"],
                           variable=self.save_phone, bg=C["content_bg"],
                           activebackground=C["content_bg"],
                           font=("Segoe UI", 9)).grid(row=2, column=1, columnspan=2, sticky="w")

        tk.Label(body, text="Message", font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(10, 2))
        self.text = tk.Text(body, height=9, font=("Segoe UI", 10), wrap="word",
                            relief="solid", bd=1)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", info["message"])
        self.attach = tk.BooleanVar(value=bool(info.get("pdf")))
        if info.get("pdf"):
            tk.Checkbutton(body, text="Attach PDF", variable=self.attach, bg=C["content_bg"],
                           activebackground=C["content_bg"],
                           font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))
        self.status = tk.StringVar()
        tk.Label(body, textvariable=self.status, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["danger"], wraplength=500, justify="left").pack(anchor="w")

        foot = tk.Frame(self.win, bg=C["card_bg"]); foot.pack(fill="x", side="bottom")
        fi = tk.Frame(foot, bg=C["card_bg"]); fi.pack(fill="x", padx=14, pady=8)
        tk.Button(fi, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(fi, text="🟢  Send  [Ctrl+Enter]", font=("Segoe UI", 10, "bold"),
                  bg="#25D366", fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self.send).pack(side="right")
        if info.get("pdf"):
            tk.Button(fi, text="📄  View PDF", font=("Segoe UI", 10), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", padx=12, pady=6, cursor="hand2",
                      highlightbackground=C["border"], highlightthickness=1,
                      command=self.view_pdf).pack(side="left")
        e.focus_set()
        e.icursor("end")

    def view_pdf(self):
        try:
            path = self.info["pdf"]()
            try:
                os.startfile(path)
            except Exception:
                pass
            self.status.set("PDF: " + path)
        except Exception as ex:
            self.status.set("⚠ " + str(ex)[:200])

    def send(self):
        phone = wa.normalize_phone(self.phone.get())
        if not phone:
            self.status.set("⚠ Enter a valid WhatsApp number (with or without country code).")
            return
        text = self.text.get("1.0", "end").strip()
        info = self.info
        if self.save_phone.get() and info.get("party_type") and info["party"].get("id"):
            try:
                tbl, key = (("customers", "customer_id") if info["party_type"] == "customer"
                            else ("suppliers", "supplier_id"))
                db.execute(f"UPDATE {tbl} SET phone=? WHERE {key}=?",
                           (self.phone.get().strip(), info["party"]["id"]))
            except Exception:
                pass
        try:
            ok, msg = _send(info, phone, text, self.attach.get(), self.win)
        except Exception as ex:
            ok, msg = False, str(ex)[:300]
        if ok:
            self.win.destroy()
            messagebox.showinfo("WhatsApp", msg)
        else:
            self.status.set("⚠ " + msg)
