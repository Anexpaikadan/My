# ============================================================
# DayBill ERP - Vouchers Module
# (Converted from BillPOS PHP: vouchers.php + voucher_form.php)
# ------------------------------------------------------------
# List of journal vouchers with expandable Dr/Cr lines, date/type
# filter. New / Edit open the multi-line voucher window (v7.1,
# ui/multi_voucher.py): Receipt · Payment · Contra · Journal, many lines,
# cash and bank mixed in one window.
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



def _typeable(cb, var, tree=False):
    """v7.0: type in the box → the matching names / accounts drop down
    (accounts as a tree of groups); the box keeps its own list too."""
    try:
        from ui import search_drop as _SD
        vals = list(cb["values"])
        if tree:
            from modules import account_tree as _AT
            have = set(vals)

            def src():
                out, stack = [], []          # a group shows only above its own choices
                for it in _AT.items(value_fmt=lambda a: "%s · %s" % (a["code"], a["name"])):
                    while stack and stack[-1]["depth"] >= it["depth"]:
                        stack.pop()
                    if it["value"] in have:
                        out.extend(g for g in stack if not g.get("_in"))
                        for g in stack:
                            g["_in"] = True
                        out.append(dict(it, group=False))
                    elif it.get("group"):
                        stack.append(dict(it))
                return out
            _SD.attach(cb, var, src, tree=True, pick_groups=False, width=420)
        else:
            _SD.attach(cb, var, vals)
    except Exception:
        pass
    return cb

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
        from ui.multi_voucher import open_voucher
        open_voucher(self.frame, jid, self._load)

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
        from ui.multi_voucher import MultiVoucherForm
        MultiVoucherForm(self.frame, on_saved=self._load)

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
def VoucherForm(parent, on_saved=None, vtype=None, mode=None):
    """v7.1: the voucher window is multi-line (ui/multi_voucher.py) —
    vtype 'receipt' | 'payment' | 'contra' | 'journal' and mode 'cash' |
    'bank' pre-set it (⭐ Cash Receipt (CR) / Cash Payment (CP) favourites)."""
    from ui.multi_voucher import MultiVoucherForm, JournalForm
    if vtype == "journal":
        return JournalForm(parent, on_save=on_saved)
    return MultiVoucherForm(parent, on_saved=on_saved, kind=vtype, mode=mode)
