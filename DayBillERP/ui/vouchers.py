# ============================================================
# DayBill ERP - Vouchers Module
# (Converted from BillPOS PHP: vouchers.php + voucher_form.php)
# ------------------------------------------------------------
# List of journal vouchers with expandable Dr/Cr lines, date/type
# filter, and a New Voucher dialog with three modes:
#   Receipt (in)  - from customer (clears due) or other income
#   Payment (out) - to supplier (clears due) or expense
#   Journal       - simple Dr X / Cr Y
# Posts through modules/posting.py so account selection follows the
# Default Accounts map (cash/bank etc.).
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
from modules import posting
from modules import account_defaults as ad
from modules import permissions as perm

VOUCHER_TYPES = ["", "sales", "pos", "purchase", "receipt", "payment",
                 "journal", "adjustment", "expense", "sales_return",
                 "purchase_return", "salary_payment", "transfer", "payroll"]


def money(n):
    try:
        return f"{float(n):,.2f}"
    except Exception:
        return "0.00"


# ── which vouchers may be changed on this screen ─────────────
# Only typed vouchers (connector key 'journal') are edited / deleted
# here. A document's voucher is changed by changing the document;
# automatic ones (payroll, stock, year-end …) by the screen that made them.
def voucher_owner(journal_id):
    """(txn, reason). reason is '' for a typed voucher that may be edited
    or deleted here, else it says where to change it. txn is None when
    the voucher is gone."""
    try:
        from ui import txn_connector as tc
        txn = tc.resolve(journal_id)
    except Exception:
        txn = None
    if not txn:
        return None, "This voucher no longer exists."
    key = txn["key"]
    if key == "journal":
        return txn, ""
    num = txn.get("number") or "This voucher"
    if key == "opening":
        why = (f"{num} is an opening balance.\n\nChange or clear it in "
               "Accounts ▸ Opening Balances — its voucher is corrected automatically.")
    elif key == "system":
        src = (txn.get("source_type") or "system").replace("_", " ")
        why = (f"{num} was posted automatically ({src}).\n\nChange it from the "
               "screen that made it (HR & Payroll, Stock, Year-end …).")
    else:
        what = str(txn.get("label") or key).split(" (")[0].split(" /")[0]
        why = (f"{num} was posted by a {what.lower()}.\n\nChange or delete that "
               f"{what.lower()} itself — its voucher goes with it.")
    return txn, why


class VouchersView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._topbar(C)
        self._filters(C)
        self._table(C)
        self._load()

    # ── top bar ───────────────────────────────────────────────
    def _topbar(self, C):
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="🧾  Vouchers", font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(bar, text="🖨  Print", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["primary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._print_selected).pack(
                      side="right", padx=(0, 8))
        tk.Button(bar, text="➕  New Voucher", font=("Segoe UI", 9, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._new_voucher).pack(side="right")
        tk.Button(bar, text="🗑  Delete", font=("Segoe UI", 9, "bold"),
                  bg="#FEF2F2", fg=C["danger"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._delete_selected).pack(
                      side="right", padx=(0, 8))
        tk.Button(bar, text="✏  Edit", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat", padx=14, pady=7,
                  cursor="hand2", highlightbackground=C["border"],
                  highlightthickness=1, command=self._edit_selected).pack(
                      side="right", padx=(0, 8))
        tk.Button(bar, text="📥  Export", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._export_excel).pack(side="right", padx=(0, 8))

    @perm.guard("journal", "edit")
    def _edit_selected(self):
        """Edit a manual voucher (date, text, accounts, amounts). Vouchers
        posted by a document are changed by editing that document."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a voucher first.")
            return
        iid = self.tree.parent(sel[0]) or sel[0]
        try:
            jid = int(iid)
        except ValueError:
            return
        from ui import txn_connector as tc
        txn, why = voucher_owner(jid)
        if not txn:
            messagebox.showinfo("Edit Voucher", why, parent=self.frame)
            self._load()
            return
        if why:
            if txn["key"] in ("opening", "system"):
                messagebox.showinfo("Edit Voucher", why, parent=self.frame)
                return
            # a document's voucher → open that document (its own rights + lock)
            if messagebox.askyesno("Edit Voucher", why + "\n\nOpen it now?",
                                   parent=self.frame):
                tc.edit_txn(self.frame, txn, self._load)
            return
        if tc._locked(txn, self.frame, "Edit Voucher"):      # closed / other year
            return
        from ui.accounting import JournalForm
        JournalForm(self.frame, on_save=self._load, journal_id=jid)

    @perm.guard("journal", "delete")
    def _delete_selected(self):
        """Delete the selected voucher (journal entry). Lines cascade.
        A posted voucher affects the ledger, so it gets a stronger warning.
        Only typed vouchers are deleted here — documents' and automatic
        vouchers (payroll, stock, year-end …) are refused with where to go."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a voucher first.")
            return
        iid = sel[0]
        # child rows (Dr/Cr lines) have the journal parent's iid
        parent = self.tree.parent(iid)
        if parent:
            iid = parent
        try:
            jid = int(iid)
        except ValueError:
            return
        txn, why = voucher_owner(jid)
        if not txn:
            messagebox.showinfo("Delete Voucher", why, parent=self.frame)
            self._load()
            return
        if why:
            messagebox.showwarning("Delete Voucher", why, parent=self.frame)
            return
        from ui import txn_connector as tc
        if tc._locked(txn, self.frame, "Delete Voucher"):    # closed / other year
            return
        row = db.fetchone("SELECT journal_number, is_posted "
                          "FROM journal_entries WHERE journal_id=?", (jid,))
        if not row:
            return
        warn = f"Delete voucher {row['journal_number']}?"
        if row.get("is_posted"):
            warn = (f"{row['journal_number']} is POSTED — deleting it "
                    f"changes account balances.\n\nDelete anyway?")
        if not messagebox.askyesno("Delete Voucher", warn):
            return
        try:
            from modules.doc_actions import audit
            db.execute("DELETE FROM journal_entries WHERE journal_id=?", (jid,))
            audit("delete", "voucher", jid, row["journal_number"])
            self._load()
        except Exception as e:
            messagebox.showerror("Delete Voucher", str(e)[:300])

    @perm.guard("journal", "export")
    def _export_excel(self):
        """Export the filtered voucher list (header rows) to Excel."""
        try:
            from modules.report_export import export_excel
            rows = []
            for iid in self.tree.get_children():
                it = self.tree.item(iid)
                rows.append([it["text"]] + list(it["values"]))
            headers = ["Voucher #", "Date", "Type", "Narration",
                       "Debit", "Credit", "Posted"]
            export_excel(self.frame, "Vouchers", headers, rows,
                         title="Journal Vouchers")
        except Exception as e:
            messagebox.showerror("Export", str(e)[:300])

    # ── filter bar (from/to/type) ─────────────────────────────
    def _filters(self, C):
        f = tk.Frame(self.frame, bg=C["content_bg"])
        f.pack(fill="x", padx=24, pady=(12, 0))
        today = date.today()
        self.from_var = tk.StringVar(value=today.replace(day=1).strftime("%Y-%m-%d"))
        self.to_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        self.type_var = tk.StringVar(value="")

        def lab(txt):
            tk.Label(f, text=txt, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        lab("From")
        tk.Entry(f, textvariable=self.from_var, width=11, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 10))
        lab("To")
        tk.Entry(f, textvariable=self.to_var, width=11, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 10))
        lab("Type")
        from modules import voucher_types as _vt          # v6.9.3: SI / CR / CP …
        self._vt_values = ["All"] + ["%s · %s" % c for c in _vt.choices()]
        self.type_var.set("All")
        ttk.Combobox(f, textvariable=self.type_var, values=self._vt_values,
                     width=24, state="readonly").pack(side="left", padx=(0, 10))
        tk.Button(f, text="🔍 Filter", font=("Segoe UI", 9, "bold"),
                  bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                  padx=12, pady=5, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._load).pack(side="left")
        self.count_var = tk.StringVar(value="")
        tk.Label(f, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["text_secondary"]).pack(side="right")

    # ── tree: entries with expandable lines ───────────────────
    def _table(self, C):
        wrap = tk.Frame(self.frame, bg=C["card_bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=12)
        cols = ("date", "type", "narration", "debit", "credit", "posted")
        self.tree = ttk.Treeview(wrap, columns=cols, show="tree headings")
        heads = [("#0", "Voucher / Account", 240, "w"),
                 ("date", "Date", 90, "center"),
                 ("type", "Vch Type", 150, "w"),
                 ("narration", "Narration", 260, "w"),
                 ("debit", "Debit", 100, "e"),
                 ("credit", "Credit", 100, "e"),
                 ("posted", "Posted", 60, "center")]
        for cid, txt, w, anc in heads:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, anchor=anc)
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

    # ── data ──────────────────────────────────────────────────
    def _load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        params = [self.from_var.get(), self.to_var.get()]
        from modules import voucher_types as _vt
        sql = ("SELECT TOP 300 journal_id, journal_number, entry_date, reference, "
               "description_en, source_type, total_debit, total_credit, is_posted, "
               "%s AS voucher_type FROM journal_entries je "
               "WHERE entry_date BETWEEN ? AND ?" % _vt.col())
        want = (self.type_var.get() or "All").split(" · ")[0]
        if want and want != "All":
            if _vt.col() != "NULL":
                sql += " AND je.voucher_type=?"
                params.append(want)
            else:
                srcs = [k for k, v in _vt.BY_SOURCE.items() if v == want] or [want.lower()]
                sql += " AND source_type IN (%s)" % ",".join("?" * len(srcs))
                params.extend(srcs)
        sql += " ORDER BY journal_id DESC"
        try:
            rows = db.fetchall(sql, tuple(params)) or []
        except Exception as e:
            messagebox.showerror("Vouchers", str(e)[:200])
            return
        ids = [r["journal_id"] for r in rows]
        lines = {}
        if ids:
            marks = ",".join("?" * len(ids))
            try:
                lrows = db.fetchall(
                    "SELECT jl.journal_id, jl.debit, jl.credit, jl.description, "
                    "a.account_code, a.account_name_en "
                    "FROM journal_lines jl JOIN accounts a ON a.account_id=jl.account_id "
                    f"WHERE jl.journal_id IN ({marks}) ORDER BY jl.journal_id, jl.line_number",
                    tuple(ids)) or []
                for l in lrows:
                    lines.setdefault(l["journal_id"], []).append(l)
            except Exception:
                pass
        for r in rows:
            d = r["entry_date"]
            dtxt = d.strftime("%d %b %Y") if hasattr(d, "strftime") else str(d)[:10]
            parent = self.tree.insert(
                "", "end", iid=str(r["journal_id"]), text=r["journal_number"],
                values=(dtxt, _vt.label(_vt.of_journal(r)),
                        r["description_en"] or "", money(r["total_debit"]),
                        money(r["total_credit"]),
                        "✓" if r["is_posted"] else "draft"))
            for l in lines.get(r["journal_id"], []):
                self.tree.insert(
                    parent, "end",
                    text=f"   {l['account_code']} · {l['account_name_en']}",
                    values=("", "", l["description"] or "",
                            money(l["debit"]) if float(l["debit"] or 0) else "",
                            money(l["credit"]) if float(l["credit"] or 0) else "", ""))
        self.count_var.set(f"{len(rows)} vouchers")

    def _new_voucher(self):
        # v6.9.3: anyone who may post a receipt, a payment or a journal may
        # open it — Save checks the right for the type actually posted
        if not any(perm.can(m, "add") for m in ("receipt", "payment", "journal")):
            perm.allowed("journal", "add", parent=self.frame)
            return
        VoucherForm(self.frame, on_saved=self._load)

    @perm.guard("journal", "print")
    def _print_selected(self):
        import tempfile
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Print", "Select a voucher row first.")
            return
        item = sel[0]
        # if a child (ledger line) was clicked, use its parent voucher
        parent = self.tree.parent(item)
        jid = parent if parent else item
        try:
            je = db.fetchone(
                "SELECT journal_id, journal_number, entry_date, reference, "
                "description_en, source_type, total_debit, total_credit "
                "FROM journal_entries WHERE journal_id=?", (int(jid),))
        except Exception as e:
            messagebox.showerror("Print", str(e)[:200])
            return
        if not je:
            messagebox.showinfo("Print", "Voucher not found.")
            return
        try:
            lrows = db.fetchall(
                "SELECT jl.debit, jl.credit, a.account_name_en, a.account_type "
                "FROM journal_lines jl JOIN accounts a ON a.account_id=jl.account_id "
                "WHERE jl.journal_id=?", (int(jid),)) or []
        except Exception:
            lrows = []
        # the "other side" (not cash/bank) line is usually the party/account
        party_name = ""
        for l in lrows:
            if l.get("account_type") not in ("asset",) or "cash" not in \
                    str(l.get("account_name_en", "")).lower():
                party_name = l.get("account_name_en", "")
                break

        t = (je.get("source_type") or "").lower()
        doc_type = ("payment_voucher" if "payment" in t else
                    "receipt_voucher" if "receipt" in t else "journal_voucher")
        d = je["entry_date"]
        dtxt = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        header = {
            "number": je["journal_number"], "date": dtxt,
            "party_name": party_name, "narration": je.get("description_en", ""),
            "amount": je.get("total_debit") or je.get("total_credit") or 0,
            "payment": t,
        }
        try:
            company = db.fetchone("SELECT * FROM company WHERE company_id=1") or {}
        except Exception:
            company = {}

        path = os.path.join(tempfile.gettempdir(),
                            f"{doc_type}_{header['number']}.pdf")
        custom = None
        try:
            from modules.template_renderer import render_document
            inv_like = {"invoice_number": header["number"], "invoice_date": dtxt,
                       "customer_name_en": party_name, "total_amount": header["amount"]}
            custom = render_document(doc_type, inv_like, company, [], path)
        except Exception:
            custom = None
        if not custom:
            try:
                from modules.generic_doc_pdf import generate_generic_pdf
                generate_generic_pdf(doc_type, header, company, [], path,
                                     party_label="Party", with_items=False)
            except Exception as e:
                messagebox.showerror("Print", str(e)[:200])
                return
        from ui import print_menu
        try:
            from modules.template_renderer import get_template_printer
            tprinter = get_template_printer(doc_type)
        except Exception:
            tprinter = None
        print_menu.send_pdf(self.frame, path, f"Voucher {header['number']}", doc_type,
                            printer=tprinter)


# ============================================================
# New Voucher dialog (Receipt / Payment / Journal)
# ============================================================
class VoucherForm:
    """vtype 'receipt' | 'payment' | 'journal' and mode 'cash' | 'bank' pre-set
    the voucher (v6.9.3: ⭐ Cash Receipt (CR) / Cash Payment (CP) favourites)."""

    TITLES = {("receipt", "cash"): "Cash Receipt (CR)", ("receipt", "bank"): "Bank Receipt (BR)",
              ("payment", "cash"): "Cash Payment (CP)", ("payment", "bank"): "Bank Payment (BP)",
              ("journal", "cash"): "Journal Voucher (JV)", ("journal", "bank"): "Journal Voucher (JV)"}

    def __init__(self, parent, on_saved=None, vtype=None, mode=None):
        C = cfg.theme()
        self.C = C
        self.on_saved = on_saved
        self.win = tk.Toplevel(parent)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.title(self.TITLES.get((vtype, mode or "cash"), "New Voucher") if vtype
                       else "New Voucher")
        self.win.configure(bg=C["card_bg"])
        self.win.geometry("480x560")
        self.win.transient(parent.winfo_toplevel())
        self.win.grab_set()
        self._load_data()
        self._build(C)
        if vtype in ("receipt", "payment", "journal"):
            self.vtype.set(vtype)
            # a preset voucher (⭐ favourite) keeps its type: the right was
            # checked for THAT type only
            for rb in self._type_radios:
                rb.config(state="disabled")
        if mode in ("cash", "bank"):
            self.mode_var.set(mode)
        self._vtype_ui()
        self._clean = self._snapshot()

    # ── unsaved work (the generic close guard calls this) ─────
    def _snapshot(self):
        return tuple(v.get() for v in (
            self.date_var, self.amount_var, self.cust_var, self.income_var,
            self.sup_var, self.expense_var, self.jv_dr, self.jv_cr, self.narr_var))

    def _is_dirty(self) -> bool:
        """True when something was typed / picked and not saved yet."""
        try:
            return self._snapshot() != self._clean
        except Exception:
            return False

    def _load_data(self):
        try:
            self.customers = db.fetchall(
                "SELECT customer_id, customer_name_en FROM customers "
                "WHERE is_active=1 ORDER BY customer_name_en") or []
        except Exception:
            self.customers = []
        try:
            self.suppliers = db.fetchall(
                "SELECT supplier_id, supplier_name_en FROM suppliers "
                "WHERE is_active=1 ORDER BY supplier_name_en") or []
        except Exception:
            self.suppliers = []

        def accts(types):
            try:
                marks = ",".join("?" * len(types))
                return db.fetchall(
                    "SELECT account_id, account_code, account_name_en FROM accounts "
                    f"WHERE is_active=1 AND account_type IN ({marks}) "
                    "ORDER BY account_code", tuple(types)) or []
            except Exception:
                return []
        self.income_accts = accts(["revenue"])
        self.expense_accts = accts(["expense"])
        self.all_accts = accts(["asset", "liability", "equity", "revenue", "expense"])

    # ── UI ────────────────────────────────────────────────────
    def _build(self, C):
        head = tk.Frame(self.win, bg=C["primary"])
        head.pack(fill="x")
        tk.Label(head, text="New Voucher", font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=14, pady=8)

        body = tk.Frame(self.win, bg=C["card_bg"])
        body.pack(fill="both", expand=True, padx=16, pady=10)

        # type selector
        self.vtype = tk.StringVar(value="receipt")
        self._type_radios = []
        tr = tk.Frame(body, bg=C["card_bg"]); tr.pack(fill="x", pady=(0, 8))
        for val, lbl in [("receipt", "Receipt (in)"), ("payment", "Payment (out)"),
                         ("journal", "Journal")]:
            rb = tk.Radiobutton(tr, text=lbl, value=val, variable=self.vtype,
                                font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                                fg=C["text_primary"], activebackground=C["card_bg"],
                                selectcolor="white", command=self._vtype_ui)
            rb.pack(side="left", padx=(0, 10))
            self._type_radios.append(rb)

        # date + amount
        row = tk.Frame(body, bg=C["card_bg"]); row.pack(fill="x", pady=4)
        tk.Label(row, text="Date", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        tk.Entry(row, textvariable=self.date_var, width=12, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(6, 16))
        tk.Label(row, text="Amount *", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.amount_var = tk.StringVar()
        tk.Entry(row, textvariable=self.amount_var, width=12, font=("Segoe UI", 11, "bold"),
                 relief="solid", bd=1, justify="right").pack(side="left", padx=(6, 0))

        # cash/bank mode
        self.mode_frame = tk.Frame(body, bg=C["card_bg"])
        self.mode_frame.pack(fill="x", pady=4)
        tk.Label(self.mode_frame, text="Cash / Bank", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(side="left")
        self.mode_var = tk.StringVar(value="cash")
        ttk.Combobox(self.mode_frame, textvariable=self.mode_var,
                     values=["cash", "bank"], width=10,
                     state="readonly").pack(side="left", padx=(6, 0))

        # ── receipt section ──
        self.sec_receipt = tk.Frame(body, bg=C["card_bg"])
        rfrom = tk.Frame(self.sec_receipt, bg=C["card_bg"]); rfrom.pack(fill="x", pady=4)
        tk.Label(rfrom, text="Received from", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.receipt_from = tk.StringVar(value="customer")
        ttk.Combobox(rfrom, textvariable=self.receipt_from, width=24, state="readonly",
                     values=["customer", "other income"]).pack(side="left", padx=(6, 0))
        self.receipt_from.trace("w", lambda *a: self._vtype_ui())

        self.r_cust_frame = tk.Frame(self.sec_receipt, bg=C["card_bg"])
        tk.Label(self.r_cust_frame, text="Customer", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.cust_var = tk.StringVar()
        ttk.Combobox(self.r_cust_frame, textvariable=self.cust_var,
                     values=[c["customer_name_en"] for c in self.customers],
                     state="readonly").pack(fill="x")

        self.r_inc_frame = tk.Frame(self.sec_receipt, bg=C["card_bg"])
        tk.Label(self.r_inc_frame, text="Income account", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.income_var = tk.StringVar()
        ttk.Combobox(self.r_inc_frame, textvariable=self.income_var,
                     values=[f"{a['account_code']} · {a['account_name_en']}"
                             for a in self.income_accts],
                     state="readonly").pack(fill="x")

        # ── payment section ──
        self.sec_payment = tk.Frame(body, bg=C["card_bg"])
        pto = tk.Frame(self.sec_payment, bg=C["card_bg"]); pto.pack(fill="x", pady=4)
        tk.Label(pto, text="Paid to", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="left")
        self.payment_to = tk.StringVar(value="supplier")
        ttk.Combobox(pto, textvariable=self.payment_to, width=24, state="readonly",
                     values=["supplier", "expense"]).pack(side="left", padx=(6, 0))
        self.payment_to.trace("w", lambda *a: self._vtype_ui())

        self.p_sup_frame = tk.Frame(self.sec_payment, bg=C["card_bg"])
        tk.Label(self.p_sup_frame, text="Supplier", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.sup_var = tk.StringVar()
        ttk.Combobox(self.p_sup_frame, textvariable=self.sup_var,
                     values=[s["supplier_name_en"] for s in self.suppliers],
                     state="readonly").pack(fill="x")

        self.p_exp_frame = tk.Frame(self.sec_payment, bg=C["card_bg"])
        tk.Label(self.p_exp_frame, text="Expense account", font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.expense_var = tk.StringVar()
        exp_vals = [f"{a['account_code']} · {a['account_name_en']}"
                    for a in self.expense_accts]
        ttk.Combobox(self.p_exp_frame, textvariable=self.expense_var,
                     values=exp_vals, state="readonly").pack(fill="x")
        if exp_vals:
            self.expense_var.set(exp_vals[-1])     # Misc expense default

        # ── journal section ──
        self.sec_journal = tk.Frame(body, bg=C["card_bg"])
        all_vals = [f"{a['account_code']} · {a['account_name_en']}"
                    for a in self.all_accts]
        jr = tk.Frame(self.sec_journal, bg=C["card_bg"]); jr.pack(fill="x", pady=4)
        left = tk.Frame(jr, bg=C["card_bg"]); left.pack(side="left", fill="x",
                                                        expand=True, padx=(0, 6))
        tk.Label(left, text="Debit account", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.jv_dr = tk.StringVar()
        ttk.Combobox(left, textvariable=self.jv_dr, values=all_vals,
                     state="readonly").pack(fill="x")
        right = tk.Frame(jr, bg=C["card_bg"]); right.pack(side="left", fill="x", expand=True)
        tk.Label(right, text="Credit account", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w")
        self.jv_cr = tk.StringVar()
        ttk.Combobox(right, textvariable=self.jv_cr, values=all_vals,
                     state="readonly").pack(fill="x")

        # narration + buttons
        self._narr_label = tk.Label(body, text="Narration", font=("Segoe UI", 9),
                                    bg=C["card_bg"], fg=C["text_secondary"])
        self._narr_label.pack(anchor="w", pady=(8, 0))
        self.narr_var = tk.StringVar()
        tk.Entry(body, textvariable=self.narr_var, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(fill="x")

        btns = tk.Frame(self.win, bg=C["card_bg"])
        btns.pack(fill="x", padx=16, pady=12)
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg="#EEF1F6",
                  relief="flat", padx=16, pady=6, cursor="hand2",
                  command=self.win.destroy).pack(side="left", expand=True,
                                                 fill="x", padx=(0, 4))
        tk.Button(btns, text="✓  Save voucher", font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._save).pack(side="left", expand=True,
                                                           fill="x", padx=(4, 0))

    def _vtype_ui(self):
        """Show only the section for the chosen voucher type (mirrors the
        PHP vtypeUI() toggling)."""
        t = self.vtype.get()
        for f in (self.sec_receipt, self.sec_payment, self.sec_journal):
            f.pack_forget()
        for f in (self.r_cust_frame, self.r_inc_frame,
                  self.p_sup_frame, self.p_exp_frame):
            f.pack_forget()
        if t == "journal":
            self.mode_frame.pack_forget()
            self.sec_journal.pack(fill="x", pady=4, before=self._narr_label)
        else:
            if not self.mode_frame.winfo_ismapped():
                self.mode_frame.pack(fill="x", pady=4, before=self._narr_label)
            if t == "receipt":
                self.sec_receipt.pack(fill="x", pady=4, before=self._narr_label)
                if self.receipt_from.get() == "customer":
                    self.r_cust_frame.pack(fill="x", pady=4)
                else:
                    self.r_inc_frame.pack(fill="x", pady=4)
            else:
                self.sec_payment.pack(fill="x", pady=4, before=self._narr_label)
                if self.payment_to.get() == "supplier":
                    self.p_sup_frame.pack(fill="x", pady=4)
                else:
                    self.p_exp_frame.pack(fill="x", pady=4)

    # ── save (ported posting rules) ───────────────────────────
    # voucher type → the user right that may post it
    _RIGHT = {"receipt": "receipt", "payment": "payment", "journal": "journal"}

    def _save(self):
        t = self.vtype.get()
        # the right follows the TYPE being posted, not the button that opened it
        if not perm.allowed(self._RIGHT.get(t, "journal"), "add", parent=self.win):
            return
        try:
            amount = round(float((self.amount_var.get() or "0").replace(",", "")), 2)
        except Exception:
            amount = 0
        if amount <= 0:
            messagebox.showwarning("Voucher", "Enter an amount.", parent=self.win)
            return
        vdate = self.date_var.get() or date.today().strftime("%Y-%m-%d")
        try:            # closed year / outside the login year → say why
            from modules import financial_year as fy
            msg = fy.guard_active(str(vdate)[:10])
        except Exception:
            msg = ""
        if msg:
            messagebox.showwarning("Voucher", msg, parent=self.win)
            return
        narr = self.narr_var.get().strip()
        method = self.mode_var.get()
        jid = None
        try:
            if t == "receipt":
                if self.receipt_from.get() == "customer":
                    name = self.cust_var.get()
                    cid = next((c["customer_id"] for c in self.customers
                                if c["customer_name_en"] == name), None)
                    if not cid:
                        messagebox.showwarning("Voucher", "Select a customer.",
                                               parent=self.win)
                        return
                    posting.ensure_party_account("customer", cid)
                    jid = posting.post_receipt(None, vdate, cid, amount,
                                               method=method,
                                               reference=narr or f"Received from {name}")
                else:
                    code = (self.income_var.get() or "").split(" · ")[0]
                    if not code:
                        messagebox.showwarning("Voucher", "Pick an income account.",
                                               parent=self.win)
                        return
                    debit = ad.bank() if method == "bank" else ad.cash()
                    jid = posting.post_journal(
                        vdate, narr or "Other receipt",
                        [(debit, amount, 0, "Money received"),
                         (ad._id_from_code(code), 0, amount, "Other income")],
                        "receipt", None, reference=narr)
            elif t == "payment":
                if self.payment_to.get() == "supplier":
                    name = self.sup_var.get()
                    sid = next((s["supplier_id"] for s in self.suppliers
                                if s["supplier_name_en"] == name), None)
                    if not sid:
                        messagebox.showwarning("Voucher", "Select a supplier.",
                                               parent=self.win)
                        return
                    posting.ensure_party_account("supplier", sid)
                    jid = posting.post_payment(None, vdate, sid, amount,
                                               method=method,
                                               reference=narr or f"Paid to {name}")
                else:
                    code = (self.expense_var.get() or "").split(" · ")[0]
                    if not code:
                        messagebox.showwarning("Voucher", "Pick an expense account.",
                                               parent=self.win)
                        return
                    jid = posting.post_expense(None, vdate,
                                               ad._id_from_code(code), amount,
                                               vat=0, method=method,
                                               reference=narr,
                                               description=narr or "Expense payment")
            else:  # journal
                dr = (self.jv_dr.get() or "").split(" · ")[0]
                cr = (self.jv_cr.get() or "").split(" · ")[0]
                if not dr or not cr or dr == cr:
                    messagebox.showwarning("Voucher",
                                           "Pick two different accounts.",
                                           parent=self.win)
                    return
                jid = posting.post_adjustment(
                    vdate, [(dr, amount, 0, narr or "Journal Dr"),
                            (cr, 0, amount, narr or "Journal Cr")],
                    description=narr or "Journal voucher")
            if jid:
                num = db.execute_scalar("SELECT journal_number FROM journal_entries "
                                        "WHERE journal_id=?", (jid,)) or ""
                messagebox.showinfo("Voucher", "Voucher %s saved." % num, parent=self.win)
                if self.on_saved:
                    self.on_saved()
                # v6.9.3: stays open for the next voucher of the same kind
                from ui import after_save
                parent, vt, md = self.win.master, t, method
                after_save.finish(self, num,
                                  new=lambda: VoucherForm(parent, self.on_saved, vtype=vt,
                                                          mode=md if md in ("cash", "bank")
                                                          else None))
            else:
                messagebox.showerror(
                    "Voucher",
                    "Could not save. Check that the accounting tables exist "
                    "(run the accounting patches) and accounts resolve.",
                    parent=self.win)
        except Exception as e:
            messagebox.showerror("Voucher", str(e)[:300], parent=self.win)
