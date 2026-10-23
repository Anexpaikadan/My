# ============================================================
# DayBill ERP - Multi-line Voucher window (v7.1)
# ------------------------------------------------------------
# Receipt · Payment · Contra · Journal in ONE window with many lines.
#   • every line picks its own Cash / Bank account — mix cash and bank
#   • Cash / Bank totals live, amount in words
#   • party balance shown while you type (before → after this voucher)
#   • cheque no. / date on bank lines, input VAT on payment lines
#   • save as separate CR + BR (CP + BP) vouchers or one voucher
#   • Journal: Dr / Cr columns, live difference, ⚖ Balance (Ctrl+B)
#   • templates (monthly rent, salaries …) and "copy last voucher"
#   • keys: Enter next field / add line · double-click / F2 change a line
#           Delete remove · Ctrl+D duplicate · Alt+↑/↓ move · Ctrl+S save
# Logic and posting: modules/multi_voucher.py
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date

from config import settings as cfg
from config.database import db
from modules import multi_voucher as mv
from modules import permissions as perm

PRESET_TITLES = {("receipt", "cash"): "Cash Receipt (CR)", ("receipt", "bank"): "Bank Receipt (BR)",
                 ("payment", "cash"): "Cash Payment (CP)", ("payment", "bank"): "Bank Payment (BP)",
                 ("journal", "cash"): "Journal Voucher (JV)", ("journal", "bank"): "Journal Voucher (JV)",
                 ("contra", "cash"): "Contra Voucher (CT)", ("contra", "bank"): "Contra Voucher (CT)"}
KIND_BUTTONS = (("receipt", "⬇  Receipt"), ("payment", "⬆  Payment"),
                ("contra", "⇄  Contra"), ("journal", "📒  Journal"))
MONEY_HEAD = {"receipt": "Received in", "payment": "Paid from", "contra": "From"}
ACCT_HEAD = {"receipt": "Received from (party / account)", "payment": "Paid to (party / account)",
             "contra": "To (cash / bank)", "journal": "Account / party"}
CUST, SUPP = "👤 ", "🏭 "


def _m(v):
    try:
        return "{:,.2f}".format(float(v or 0))
    except Exception:
        return "0.00"


def _num(v):
    s = "%.2f" % mv.f2(v)
    return s.rstrip("0").rstrip(".") if "." in s else s


class MultiVoucherForm:
    """kind 'receipt' | 'payment' | 'contra' | 'journal'; mode 'cash' | 'bank'
    picks the default money account; journal_id opens a saved voucher."""

    def __init__(self, parent, on_saved=None, kind=None, mode=None, journal_id=None,
                 on_save=None, preset=None):
        C = cfg.theme()
        self.C = C
        self.on_saved = on_saved or on_save
        self.on_save = self.on_saved
        self.journal_id = journal_id
        self.kind = kind if kind in mv.KINDS else "receipt"
        self.mode = mode if mode in ("cash", "bank") else "cash"
        self.preset = bool(kind in mv.KINDS) if preset is None else bool(preset)
        self.lines = []
        self._edit_idx = None
        self._loaded = None
        if journal_id:
            self._loaded = mv.load(journal_id)
            if self._loaded:
                self.kind = self._loaded["kind"]
        self.money = mv.money_accounts()
        self._load_choices()

        self.win = tk.Toplevel(parent)
        self.win.title(self._title())
        self.win.configure(bg=C["content_bg"])
        self.win.geometry("1080x660")
        self.win.minsize(900, 560)
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.grab_set()
        self.win.bind("<Escape>", self._on_escape)
        self._build()
        self._show_balance()
        if self._loaded:
            self._fill(self._loaded)
        self._kind_ui()
        self._clean = self._snapshot()
        try:      # connector bar: New · Edit · Save · Delete (user rights)
            from ui import txn_connector as _tc
            _tc.attach(self, "journal")
        except Exception:
            pass
        try:
            self.acct_cb.focus_set()
        except Exception:
            pass

    # ── title / data ──────────────────────────────────────────
    def _title(self):
        if self.journal_id and self._loaded:
            return "Edit %s  %s" % (mv.TITLES[self.kind].split(" (")[0], self._loaded["number"])
        if self.preset:
            return PRESET_TITLES.get((self.kind, self.mode), mv.TITLES[self.kind])
        return "New Voucher — " + mv.TITLES[self.kind]

    def _load_choices(self):
        """label → target. Accounts as 'CODE · Name' (ledgers only),
        customers '👤 Name', suppliers '🏭 Name'."""
        try:
            party_acc = set(r["account_id"] for r in db.fetchall(
                "SELECT account_id FROM customers WHERE account_id IS NOT NULL UNION "
                "SELECT account_id FROM suppliers WHERE account_id IS NOT NULL") or [])
        except Exception:
            party_acc = set()
        try:
            grp = "ISNULL(is_group,0)" if db.execute_scalar(
                "SELECT COL_LENGTH('accounts','is_group')") is not None else "0"
            rows = db.fetchall(
                "SELECT account_id, account_code, account_name_en FROM accounts a "
                "WHERE ISNULL(is_active,1)=1 AND %s=0 ORDER BY account_code" % grp) or []
        except Exception:
            rows = []
        party_acc -= set(m["account_id"] for m in self.money)    # Cash Customer → cash account
        self.accounts = [r for r in rows if r["account_id"] not in party_acc]
        self.acct_label = {}                    # account_id → label
        self.choice = {}                        # label → target
        for a in self.accounts:
            lab = "%s · %s" % (a["account_code"], a["account_name_en"])
            self.acct_label[a["account_id"]] = lab
            self.choice[lab] = ("account", a["account_id"])
        self.parties = []
        for kind, t, pre in (("customer", "customers", CUST), ("supplier", "suppliers", SUPP)):
            try:
                rs = db.fetchall("SELECT %s_id AS id, %s_name_en AS name, ISNULL(%s_code,'') AS code "
                                 "FROM %s WHERE ISNULL(is_active,1)=1 ORDER BY %s_name_en"
                                 % (kind, kind, kind, t, kind)) or []
            except Exception:
                rs = []
            for r in rs:
                lab = pre + str(r["name"] or "")
                if lab in self.choice:
                    lab = "%s (%s)" % (lab, r["code"] or r["id"])
                self.choice[lab] = (kind, r["id"])
                self.parties.append({"kind": kind, "id": r["id"], "label": lab, "code": r["code"]})
        self.money_ids = set(m["account_id"] for m in self.money)
        self.money_label = {m["account_id"]: "%s · %s" % (m["code"], m["name"]) for m in self.money}
        for aid, lab in self.money_label.items():
            self.acct_label.setdefault(aid, lab)
            self.choice.setdefault(lab, ("account", aid))

    def label_of(self, target):
        if not target:
            return ""
        k, i = target[:2]
        if k == "account":
            return self.acct_label.get(i) or str(i)
        return next((p["label"] for p in self.parties if p["kind"] == k and p["id"] == i), str(i))

    def _allowed_values(self):
        """Choices of the party / account box for this kind (box order)."""
        accs = ["%s · %s" % (a["account_code"], a["account_name_en"]) for a in self.accounts]
        pts = [p["label"] for p in self.parties]
        if self.kind == "contra":
            return [self.money_label[m["account_id"]] for m in self.money]
        if self.kind == "journal":
            return accs + pts                     # accounts first (journal habit)
        return pts + [a for a in accs if self.choice[a][1] not in self.money_ids]

    def _drop_source(self):
        """Tree for the type-ahead drop-down: Customers, Suppliers, then the
        chart of accounts (groups shown above their ledgers)."""
        allowed = set(self._allowed_values())
        out = []

        def parties():
            for kind, head in (("customer", "👤 Customers"), ("supplier", "🏭 Suppliers")):
                ps = [p for p in self.parties if p["kind"] == kind and p["label"] in allowed]
                if ps:
                    out.append({"label": head, "value": head, "depth": 0, "group": True})
                    out.extend({"label": p["label"], "value": p["label"], "depth": 1,
                                "search": p["code"]} for p in ps)

        def accounts():
            try:
                from modules import account_tree as _AT
                stack = []
                for it in _AT.items(value_fmt=lambda a: "%s · %s" % (a["code"], a["name"])):
                    while stack and stack[-1]["depth"] >= it["depth"]:
                        stack.pop()
                    if it["value"] in allowed:
                        out.extend(g for g in stack if not g.get("_in"))
                        for g in stack:
                            g["_in"] = True
                        out.append(dict(it, group=False))
                    elif it.get("group"):
                        stack.append(dict(it))
            except Exception:
                out.extend({"label": v, "value": v} for v in sorted(allowed)
                           if not v.startswith((CUST, SUPP)))
        if self.kind == "journal":
            accounts(); parties()
        else:
            parties(); accounts()
        return out

    # ── UI ────────────────────────────────────────────────────
    def _build(self):
        C = self.C
        hdr = tk.Frame(self.win, bg=C["primary"], height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        self.head_lbl = tk.Label(hdr, text="", font=("Segoe UI", 13, "bold"),
                                 bg=C["primary"], fg="white")
        self.head_lbl.pack(side="left", padx=16)

        # type buttons
        tb = tk.Frame(self.win, bg=C["content_bg"]); tb.pack(fill="x", padx=16, pady=(8, 2))
        self.kind_btns = {}
        for k, txt in KIND_BUTTONS:
            b = tk.Button(tb, text=txt, font=("Segoe UI", 10, "bold"), relief="flat",
                          padx=14, pady=5, cursor="hand2",
                          command=lambda k=k: self._switch_kind(k))
            b.pack(side="left", padx=(0, 6))
            self.kind_btns[k] = b
        self.no_var = tk.StringVar()
        tk.Label(tb, textvariable=self.no_var, font=("Segoe UI", 10, "bold"),
                 bg=C["content_bg"], fg=C["primary"]).pack(side="right")

        # header fields
        hf = tk.Frame(self.win, bg=C["content_bg"]); hf.pack(fill="x", padx=16, pady=4)

        def lab(t):
            tk.Label(hf, text=t, font=("Segoe UI", 9), bg=C["content_bg"],
                     fg=C["text_secondary"]).pack(side="left", padx=(0, 4))
        lab("Date")
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        tk.Entry(hf, textvariable=self.date_var, width=11, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 12))
        lab("Reference")
        self.ref_var = tk.StringVar()
        tk.Entry(hf, textvariable=self.ref_var, width=14, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", padx=(0, 12))
        lab("Narration")
        self.desc_var = tk.StringVar()
        tk.Entry(hf, textvariable=self.desc_var, font=("Segoe UI", 10),
                 relief="solid", bd=1).pack(side="left", fill="x", expand=True)

        # options row: default cash / bank, split, templates, copy last
        of = tk.Frame(self.win, bg=C["content_bg"]); of.pack(fill="x", padx=16, pady=(2, 6))
        self.opt_frame = of
        self.def_lbl = tk.Label(of, text="Default cash / bank", font=("Segoe UI", 9),
                                bg=C["content_bg"], fg=C["text_secondary"])
        self.def_lbl.pack(side="left")
        self.def_money_var = tk.StringVar()
        self.def_money_cb = ttk.Combobox(of, textvariable=self.def_money_var, width=28,
                                         state="readonly",
                                         values=[self.money_label[m["account_id"]] for m in self.money])
        self.def_money_cb.pack(side="left", padx=(4, 12))
        self.def_money_cb.bind("<<ComboboxSelected>>", lambda e: self._default_money_changed())
        d = mv.default_money(self.mode, self.money)
        if d in self.money_label:
            self.def_money_var.set(self.money_label[d])
        self.split_var = tk.BooleanVar(value=True)
        self.split_cb = tk.Checkbutton(of, text="Separate Cash and Bank vouchers (CR + BR)",
                                       variable=self.split_var, bg=C["content_bg"],
                                       fg=C["text_primary"], activebackground=C["content_bg"],
                                       font=("Segoe UI", 9), command=self._refresh)
        self.split_cb.pack(side="left")
        self.tpl_btn = tk.Menubutton(of, text="📋 Templates ▾", font=("Segoe UI", 9),
                                     bg=C["card_bg"], fg=C["text_primary"], relief="flat",
                                     padx=10, pady=3, cursor="hand2",
                                     highlightbackground=C["border"], highlightthickness=1)
        self.tpl_menu = tk.Menu(self.tpl_btn, tearoff=0, postcommand=self._fill_tpl_menu)
        self.tpl_btn.config(menu=self.tpl_menu)
        self.tpl_btn.pack(side="right")
        tk.Button(of, text="↺ Copy last", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_primary"], relief="flat", padx=10, pady=3, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self._copy_last).pack(side="right", padx=(0, 6))

        # line editor
        ed = tk.Frame(self.win, bg=C["primary_light"]); ed.pack(fill="x", padx=16)
        self.editor = ed
        top = tk.Frame(ed, bg=C["primary_light"]); top.pack(fill="x", padx=8, pady=(6, 0))
        bot = tk.Frame(ed, bg=C["primary_light"]); bot.pack(fill="x", padx=8, pady=(2, 6))
        self._cells = {}

        def cell(key, title, widget_fn, side_frame=top, **pack):
            f = tk.Frame(side_frame, bg=C["primary_light"])
            tl = tk.Label(f, text=title, font=("Segoe UI", 9), bg=C["primary_light"],
                          fg=C["primary"])
            tl.pack(anchor="w")
            w = widget_fn(f)
            w.pack(fill="x")
            f.pack(side="left", padx=(0, 6), **pack)
            self._cells[key] = (f, tl, w)
            return w
        self.acct_var = tk.StringVar()
        self.acct_cb = cell("acct", ACCT_HEAD["receipt"], lambda f: ttk.Combobox(
            f, textvariable=self.acct_var, font=("Segoe UI", 10), width=34), fill="x", expand=True)
        try:
            from ui import search_drop as _SD
            _SD.attach(self.acct_cb, self.acct_var, self._drop_source, tree=True,
                       pick_groups=False, width=460, on_pick=lambda it: self._after_pick())
        except Exception:
            pass
        self.money_var = tk.StringVar()
        self.money_cb = cell("money", "Received in", lambda f: ttk.Combobox(
            f, textvariable=self.money_var, state="readonly", width=24, font=("Segoe UI", 10),
            values=[self.money_label[m["account_id"]] for m in self.money]))
        self.money_cb.bind("<<ComboboxSelected>>", lambda e: self._money_kind_ui())
        ent = lambda var, w=11: (lambda f: tk.Entry(f, textvariable=var, width=w, justify="right",
                                                     font=("Segoe UI", 10, "bold"), relief="solid", bd=1))
        self.amount_var = tk.StringVar()
        self.amount_e = cell("amount", "Amount", ent(self.amount_var))
        self.dr_var = tk.StringVar(value="0")
        self.cr_var = tk.StringVar(value="0")
        self.dr_e = cell("dr", "Debit", ent(self.dr_var))
        self.cr_e = cell("cr", "Credit", ent(self.cr_var))
        self.vat_var = tk.StringVar()
        self.vat_e = cell("vat", "VAT", ent(self.vat_var, 8))
        self.chq_var = tk.StringVar()
        self.chqd_var = tk.StringVar()
        self.chq_e = cell("chq", "Cheque no.", lambda f: tk.Entry(
            f, textvariable=self.chq_var, width=10, font=("Segoe UI", 10), relief="solid", bd=1),
            side_frame=bot)
        self.chqd_e = cell("chqd", "Cheque date", lambda f: tk.Entry(
            f, textvariable=self.chqd_var, width=11, font=("Segoe UI", 10), relief="solid", bd=1),
            side_frame=bot)
        self.lnarr_var = tk.StringVar()
        self.lnarr_e = cell("lnarr", "Line narration", lambda f: tk.Entry(
            f, textvariable=self.lnarr_var, font=("Segoe UI", 10), relief="solid", bd=1),
            side_frame=bot, fill="x", expand=True)
        bf = tk.Frame(bot, bg=C["primary_light"]); bf.pack(side="left")
        tk.Label(bf, text=" ", font=("Segoe UI", 9), bg=C["primary_light"]).pack()
        self.add_btn = tk.Button(bf, text="＋ Add Line", font=("Segoe UI", 9, "bold"),
                                 bg=C["primary"], fg="white", relief="flat", padx=12, pady=3,
                                 cursor="hand2", command=self._add_line)
        self.add_btn.pack(side="left")
        self.vat_btn = tk.Button(bf, text="+VAT", font=("Segoe UI", 9), relief="flat",
                                 bg=C["card_bg"], cursor="hand2", command=self._fill_vat)
        self.bal_btn = tk.Button(bf, text="⚖ Balance", font=("Segoe UI", 9, "bold"), relief="flat",
                                 bg=C["card_bg"], cursor="hand2", command=self._balance)
        self.info_var = tk.StringVar()
        tk.Label(ed, textvariable=self.info_var, font=("Segoe UI", 9), bg=C["primary_light"],
                 fg=C["text_secondary"], anchor="w").pack(fill="x", padx=8, pady=(0, 4))
        self.acct_var.trace_add("write", lambda *a: self._show_balance())
        for v in (self.amount_var, self.vat_var, self.dr_var, self.cr_var):
            v.trace_add("write", lambda *a: self._show_balance())

        # Enter walks the editor; the last field adds the line
        order = [self.amount_e, self.dr_e, self.cr_e, self.vat_e, self.chq_e, self.chqd_e,
                 self.lnarr_e]
        for w in order:
            w.bind("<Return>", lambda e, w=w: self._enter_from(w))
            w.bind("<KP_Enter>", lambda e, w=w: self._enter_from(w))
        self.acct_cb.bind("<Return>", lambda e: self._enter_from(self.acct_cb), add="+")
        self.money_cb.bind("<Return>", lambda e: self._enter_from(self.money_cb))

        # lines grid
        wrap = tk.Frame(self.win, bg=C["card_bg"], highlightbackground=C["border"],
                        highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        cols = ("no", "acct", "money", "amount", "vat", "dr", "cr", "chq", "narr")
        vsb = ttk.Scrollbar(wrap, orient="vertical"); vsb.pack(side="right", fill="y")
        self.line_tree = ttk.Treeview(wrap, columns=cols, show="headings", height=9,
                                      yscrollcommand=vsb.set)
        vsb.config(command=self.line_tree.yview)
        for c, t, w, a in (("no", "#", 34, "center"), ("acct", "Party / Account", 280, "w"),
                           ("money", "Cash / Bank", 190, "w"), ("amount", "Amount", 110, "e"),
                           ("vat", "VAT", 80, "e"), ("dr", "Debit", 110, "e"),
                           ("cr", "Credit", 110, "e"), ("chq", "Cheque", 120, "w"),
                           ("narr", "Narration", 220, "w")):
            self.line_tree.heading(c, text=t)
            self.line_tree.column(c, width=w, anchor=a, stretch=c in ("acct", "narr"))
        self.line_tree.pack(fill="both", expand=True)
        self.line_tree.tag_configure("bank", foreground=C.get("primary", "#1E40AF"))
        try:
            from ui.grid_lines import excel_grid
            excel_grid(self.line_tree)
        except Exception:
            pass
        self.line_tree.bind("<Double-1>", lambda e: self._pick_line())
        self.line_tree.bind("<Return>", lambda e: (self._pick_line(), "break")[1])
        self.line_tree.bind("<F2>", lambda e: (self._pick_line(), "break")[1])
        self.line_tree.bind("<Delete>", self._delete_key)
        self.line_tree.bind("<Control-d>", lambda e: (self._duplicate(), "break")[1])
        self.line_tree.bind("<Alt-Up>", lambda e: (self._move(-1), "break")[1])
        self.line_tree.bind("<Alt-Down>", lambda e: (self._move(1), "break")[1])

        # footer: totals, words, buttons
        ft = tk.Frame(self.win, bg=C["card_bg"]); ft.pack(fill="x", side="bottom")
        fl = tk.Frame(ft, bg=C["card_bg"]); fl.pack(side="left", fill="x", expand=True, padx=16, pady=8)
        self.balance_var = tk.StringVar()
        tk.Label(fl, textvariable=self.balance_var, font=("Segoe UI", 11, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"], anchor="w").pack(fill="x")
        self.words_var = tk.StringVar()
        tk.Label(fl, textvariable=self.words_var, font=("Segoe UI", 9, "italic"),
                 bg=C["card_bg"], fg=C["text_secondary"], anchor="w").pack(fill="x")
        self.status_var = tk.StringVar()
        tk.Label(fl, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["card_bg"], fg=C["danger"], anchor="w").pack(fill="x")
        fr = tk.Frame(ft, bg=C["card_bg"]); fr.pack(side="right", padx=16, pady=8)
        self.save_btn = tk.Button(fr, text="💾 Save  (Ctrl+S)", font=("Segoe UI", 10, "bold"),
                                  bg=C["accent"], fg="white", relief="flat", padx=16, pady=6,
                                  cursor="hand2", command=self._save)
        self.save_btn.pack(side="right")
        tk.Button(fr, text="Cancel", font=("Segoe UI", 10), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=14, pady=6, cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=self.win.destroy).pack(side="right", padx=(0, 8))
        tk.Button(fr, text="Clear lines", font=("Segoe UI", 9), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", padx=10, pady=6, cursor="hand2",
                  command=self._clear_lines).pack(side="right", padx=(0, 8))

        for seq in ("<Control-s>", "<Control-S>"):
            self.win.bind(seq, lambda e: (self._save(), "break")[1])
        self.win.bind("<Control-b>", lambda e: (self._balance(), "break")[1])
        self.win.bind("<Insert>", lambda e: (self._add_line(), "break")[1])
        self.win.bind("<F2>", lambda e: (self.acct_cb.focus_set(), "break")[1])

    # ── kind ──────────────────────────────────────────────────
    def _kind_ui(self):
        C, k = self.C, self.kind
        self.win.title(self._title())
        icon = {"receipt": "⬇", "payment": "⬆", "contra": "⇄", "journal": "📒"}[k]
        self.head_lbl.config(text="%s  %s" % (icon, self._title()))
        for kk, b in self.kind_btns.items():
            on = kk == k
            b.config(bg=C["primary"] if on else C["card_bg"],
                     fg="white" if on else C["text_primary"],
                     state="normal" if (on or not (self.journal_id or self.preset)) else "disabled")
        show = {"acct": True, "money": k != "journal", "amount": k != "journal",
                "dr": k == "journal", "cr": k == "journal", "vat": k == "payment",
                "chq": k != "journal", "chqd": k != "journal", "lnarr": True}
        order = ["acct", "money", "amount", "dr", "cr", "vat"]
        for key in order:
            f = self._cells[key][0]
            f.pack_forget()
        for key in order:
            if show[key]:
                f = self._cells[key][0]
                if key == "acct":
                    f.pack(side="left", padx=(0, 6), fill="x", expand=True)
                else:
                    f.pack(side="left", padx=(0, 6))
        for key in ("chq", "chqd"):
            f = self._cells[key][0]
            if show[key]:
                if f.winfo_manager() != "pack":
                    f.pack(side="left", padx=(0, 6), before=self._cells["lnarr"][0])
            else:
                f.pack_forget()
        self._cells["acct"][1].config(text=ACCT_HEAD[k])
        if k != "journal":
            self._cells["money"][1].config(text=MONEY_HEAD[k])
        self.vat_btn.pack_forget(); self.bal_btn.pack_forget()
        if k == "payment":
            self.vat_btn.pack(side="left", padx=(4, 0))
        if k == "journal":
            self.bal_btn.pack(side="left", padx=(4, 0))
        # options row: Default cash / bank · Separate vouchers (left), Copy / Templates (right)
        for w in (self.def_lbl, self.def_money_cb, self.split_cb):
            w.pack_forget()
        if k != "journal":
            self.def_lbl.pack(side="left")
            self.def_money_cb.pack(side="left", padx=(4, 12))
        if k in ("receipt", "payment"):
            self.split_cb.config(text="Separate Cash and Bank vouchers (%s)"
                                 % ("CR + BR" if k == "receipt" else "CP + BP"))
            self.split_cb.pack(side="left")
        disp = {"receipt": ("no", "acct", "money", "amount", "chq", "narr"),
                "payment": ("no", "acct", "money", "amount", "vat", "chq", "narr"),
                "contra": ("no", "acct", "money", "amount", "chq", "narr"),
                "journal": ("no", "acct", "dr", "cr", "narr")}[k]
        self.line_tree.config(displaycolumns=disp)
        self.line_tree.heading("acct", text={"contra": "To"}.get(k, "Party / Account"))
        self.line_tree.heading("money", text=MONEY_HEAD.get(k, "Cash / Bank"))
        try:
            self.acct_cb.config(values=self._allowed_values())
        except Exception:
            pass
        if not self.money_var.get():
            self.money_var.set(self.def_money_var.get())
        self._money_kind_ui()
        self._refresh()

    def _switch_kind(self, k):
        if k == self.kind or self.journal_id:
            return
        if self.preset:
            return
        moving = {self.kind, k}
        keep = moving <= {"receipt", "payment"}
        if self.lines and not keep:
            if not messagebox.askyesno("Voucher type", "Change to %s? The lines are cleared."
                                       % mv.TITLES[k], parent=self.win):
                return
            self.lines = []
        if keep:      # a payment line's VAT has no meaning on a receipt
            for ln in self.lines:
                ln["vat"] = 0.0
        self.kind = k
        self._end_edit()
        self.acct_var.set("")
        self._kind_ui()

    def _default_money_changed(self):
        if not self.lines or self._edit_idx is None:
            self.money_var.set(self.def_money_var.get())
            self._money_kind_ui()

    def _money_kind_ui(self):
        """Cheque fields only for a bank account."""
        mid = self._money_id()
        bank = mid is not None and mv.money_kind(mid, self.money) == "bank"
        for w in (self.chq_e, self.chqd_e):
            try:
                w.config(state="normal" if bank else "disabled")
            except Exception:
                pass
        if not bank:
            self.chq_var.set(""); self.chqd_var.set("")

    def _money_id(self):
        t = self.choice.get(self.money_var.get())
        return t[1] if t else None

    # ── editor ────────────────────────────────────────────────
    def _target(self):
        t = self.choice.get(self.acct_var.get().strip())
        if t:
            return t
        try:                                 # the journal box may hold 'CODE Name'
            i = self.acct_cb.current()
            if i >= 0:
                return self.choice.get(self.acct_cb["values"][i])
        except Exception:
            pass
        return None

    def _after_pick(self):
        self._show_balance()
        nxt = self.amount_e if self.kind != "journal" else self.dr_e
        if self.kind == "journal":
            self._suggest_journal_amount()
        try:
            nxt.focus_set(); nxt.select_range(0, "end")
        except Exception:
            pass

    def _suggest_journal_amount(self):
        """Next journal line: the open difference goes on the other side."""
        if self.dr_var.get() not in ("", "0") or self.cr_var.get() not in ("", "0"):
            return
        t = mv.totals("journal", self.lines, self.money)
        if t["diff"] > 0:
            self.cr_var.set(_num(t["diff"])); self.dr_var.set("0")
        elif t["diff"] < 0:
            self.dr_var.set(_num(-t["diff"])); self.cr_var.set("0")

    def _enter_from(self, w):
        if w is self.acct_cb:
            try:
                sd = getattr(self.acct_cb, "_search_drop", None)
                if sd is not None and sd.panel is not None:
                    return None
            except Exception:
                pass
            nxt = self.money_cb if self.kind != "journal" else self.dr_e
            if self.kind == "journal":
                self._suggest_journal_amount()
            nxt.focus_set()
            return "break"
        seq = [self.money_cb, self.amount_e, self.vat_e] if self.kind == "payment" else \
            [self.money_cb, self.amount_e] if self.kind != "journal" else [self.dr_e, self.cr_e]
        if self.kind != "journal" and self._money_id() and \
                mv.money_kind(self._money_id(), self.money) == "bank":
            seq += [self.chq_e, self.chqd_e]
        seq.append(self.lnarr_e)
        if w in seq and seq.index(w) < len(seq) - 1 and w not in (self.lnarr_e,):
            # amount typed → Enter adds straight away when nothing else is needed
            if w is self.amount_e and self.kind != "payment" and not (
                    self._money_id() and mv.money_kind(self._money_id(), self.money) == "bank"):
                self._add_line()
                return "break"
            if w is self.cr_e or (w is self.dr_e and mv.f2(self.dr_var.get())):
                self._add_line()
                return "break"
            n = seq[seq.index(w) + 1]
            n.focus_set()
            try:
                n.select_range(0, "end")
            except Exception:
                pass
            return "break"
        self._add_line()
        return "break"

    def _show_balance(self):
        t = self._target()
        if not t:
            self.info_var.set("Type a name, code or account — the list drops down as a tree.  "
                              "Enter = next field / add line.")
            return
        k, i = t[:2]
        bal = mv.balance(t)
        if self.kind == "journal":
            amt = mv.f2(self.dr_var.get()) - mv.f2(self.cr_var.get())
        else:
            a = mv.f2(self.amount_var.get()) + (mv.f2(self.vat_var.get()) if self.kind == "payment" else 0)
            amt = -a if self.kind == "receipt" else a
        for ln in self.lines:                     # lines already in this voucher
            if ln.get("target") == t and ln is not self._editing_line():
                if self.kind == "journal":
                    amt += mv.f2(ln.get("debit")) - mv.f2(ln.get("credit"))
                else:
                    g = mv.f2(ln.get("amount")) + mv.f2(ln.get("vat"))
                    amt += -g if self.kind == "receipt" else g
        who = {"customer": "Customer", "supplier": "Supplier"}.get(k, "Account")
        txt = "%s balance: %s" % (who, mv.balance_text(bal))
        if amt:
            txt += "   →   after this voucher: %s" % mv.balance_text(bal + amt)
        if self.journal_id:
            txt += "   (this voucher's saved amount is already in the balance)"
        self.info_var.set(txt)

    def _editing_line(self):
        e = self._edit_idx
        return self.lines[e] if e is not None and 0 <= e < len(self.lines) else None

    def _fill_vat(self):
        try:
            from modules import country
            rate = country.std_rate()
        except Exception:
            rate = 15.0
        self.vat_var.set(_num(mv.f2(self.amount_var.get()) * rate / 100.0))

    def _add_line(self):
        t = self._target()
        if not t:
            self._say("Pick a party or account (type to search)."); return "break"
        lab = self.label_of(t) if t[0] != "account" else (self.acct_label.get(t[1]) or self.acct_var.get())
        line = {"target": t, "label": lab, "description": self.lnarr_var.get().strip(),
                "account_id": t[1] if t[0] == "account" else None}
        if self.kind == "journal":
            dr, cr = mv.f2(self.dr_var.get()), mv.f2(self.cr_var.get())
            if dr < 0:
                dr, cr = 0.0, cr - dr
            if cr < 0:
                cr, dr = 0.0, dr - cr
            if dr and cr:                         # net it: a line is one side
                dr, cr = (round(dr - cr, 2), 0.0) if dr >= cr else (0.0, round(cr - dr, 2))
            if not dr and not cr:
                self._say("Enter a debit or credit."); return "break"
            line.update(debit=dr, credit=cr)
        else:
            amt = mv.f2(self.amount_var.get())
            if amt <= 0:
                self._say("Enter an amount."); return "break"
            mid = self._money_id()
            if not mid:
                self._say("Pick the %s account." % MONEY_HEAD[self.kind].lower()); return "break"
            if t == ("account", mid):
                self._say("The account and the cash / bank account are the same."); return "break"
            if self.kind == "contra" and (t[0] != "account" or t[1] not in self.money_ids):
                self._say("Contra: pick a cash / bank account to move the money to."); return "break"
            line.update(amount=amt, money=mid, money_label=self.money_label.get(mid, ""),
                        vat=mv.f2(self.vat_var.get()) if self.kind == "payment" else 0.0,
                        cheque=self.chq_var.get().strip(), cheque_date=self.chqd_var.get().strip())
        e = self._edit_idx
        if e is not None and 0 <= e < len(self.lines):
            self.lines[e] = line
        else:
            self.lines.append(line)
        self._end_edit()
        self._clear_editor()
        self._refresh()
        self._say("")
        self.acct_cb.focus_set()
        return "break"

    def _clear_editor(self):
        for v in (self.acct_var, self.amount_var, self.vat_var, self.chq_var, self.chqd_var,
                  self.lnarr_var):
            v.set("")
        self.dr_var.set("0"); self.cr_var.set("0")

    def _end_edit(self):
        self._edit_idx = None
        try:
            self.add_btn.config(text="＋ Add Line")
        except Exception:
            pass

    def _sel_index(self):
        s = self.line_tree.selection()
        if not s:
            return None
        i = self.line_tree.index(s[0])
        return i if 0 <= i < len(self.lines) else None

    def _pick_line(self):
        i = self._sel_index()
        if i is None:
            return
        ln = self.lines[i]
        self.acct_var.set(ln.get("label") or self.label_of(ln.get("target")))
        if self.kind == "journal":
            self.dr_var.set(_num(ln.get("debit"))); self.cr_var.set(_num(ln.get("credit")))
        else:
            self.amount_var.set(_num(ln.get("amount")))
            self.vat_var.set(_num(ln.get("vat")) if mv.f2(ln.get("vat")) else "")
            self.money_var.set(self.money_label.get(ln.get("money"), ""))
            self._money_kind_ui()
            self.chq_var.set(ln.get("cheque") or ""); self.chqd_var.set(ln.get("cheque_date") or "")
        self.lnarr_var.set(ln.get("description") or "")
        self._edit_idx = i
        self.add_btn.config(text="✔ Update Line")
        self._say("Change the line and press Update Line (Enter).")
        self.acct_cb.focus_set()

    def _delete_key(self, e=None):
        if e is not None and (int(getattr(e, "state", 0) or 0) & 0x4):
            return None                            # Ctrl+Delete = connector delete
        self._remove_line(ask=True)
        return "break"

    def _remove_line(self, ask=False):
        i = self._sel_index()
        if i is None:
            return
        ln = self.lines[i]
        if ask and not messagebox.askyesno("Remove Line", "Remove line %d — %s?"
                                           % (i + 1, ln.get("label", "")), parent=self.win):
            return
        del self.lines[i]
        self._end_edit()
        self._refresh()

    def _duplicate(self):
        i = self._sel_index()
        if i is None:
            return
        self.lines.insert(i + 1, dict(self.lines[i]))
        self._refresh(select=i + 1)

    def _move(self, step):
        i = self._sel_index()
        if i is None:
            return
        j = i + step
        if 0 <= j < len(self.lines):
            self.lines[i], self.lines[j] = self.lines[j], self.lines[i]
            self._refresh(select=j)

    def _clear_lines(self):
        if self.lines and not messagebox.askyesno("Clear", "Remove all lines?", parent=self.win):
            return
        self.lines = []
        self._end_edit()
        self._refresh()

    def _balance(self):
        """Journal: put the open difference on the selected line (or in the
        editor for a new line)."""
        if self.kind != "journal":
            return
        t = mv.totals("journal", self.lines, self.money)
        diff = t["diff"]
        if not diff:
            self._say("Already balanced ✅"); return
        i = self._sel_index()
        if i is not None:
            ln = self.lines[i]
            net = mv.f2(ln.get("debit")) - mv.f2(ln.get("credit")) - diff
            ln["debit"], ln["credit"] = (round(net, 2), 0.0) if net >= 0 else (0.0, round(-net, 2))
            self._refresh(select=i)
            self._say("Line %d balanced the voucher." % (i + 1))
        else:
            self.dr_var.set("0"); self.cr_var.set("0")
            self._suggest_journal_amount()
            self._say("Pick the account for the difference and press Enter.")
            self.acct_cb.focus_set()

    def _say(self, text):
        self.status_var.set(text)

    # ── grid + totals ─────────────────────────────────────────
    def _refresh(self, select=None):
        tv = self.line_tree
        tv.delete(*tv.get_children())
        for n, ln in enumerate(self.lines, 1):
            chq = ""
            if ln.get("cheque"):
                chq = ln["cheque"] + ((" · " + ln["cheque_date"]) if ln.get("cheque_date") else "")
            bank = self.kind != "journal" and mv.money_kind(ln.get("money"), self.money) == "bank"
            tv.insert("", "end", values=(
                n, ln.get("label") or self.label_of(ln.get("target")),
                self.money_label.get(ln.get("money"), ""),
                _m(ln.get("amount")) if mv.f2(ln.get("amount")) else "",
                _m(ln.get("vat")) if mv.f2(ln.get("vat")) else "",
                _m(ln.get("debit")) if mv.f2(ln.get("debit")) else "",
                _m(ln.get("credit")) if mv.f2(ln.get("credit")) else "",
                chq, ln.get("description") or ""), tags=("bank",) if bank else ())
        if select is not None:
            kids = tv.get_children()
            if 0 <= select < len(kids):
                tv.selection_set(kids[select]); tv.see(kids[select])
        t = mv.totals(self.kind, self.lines, self.money)
        if self.kind == "journal":
            ok = abs(t["diff"]) < 0.01 and t["debit"] > 0
            txt = "%s  Dr %s   |   Cr %s" % ("✅" if ok else "⚠️", _m(t["debit"]), _m(t["credit"]))
            if not ok and (t["debit"] or t["credit"]):
                txt += "   |   Difference %s %s" % (_m(abs(t["diff"])), "Dr" if t["diff"] > 0 else "Cr")
            amount = t["debit"]
        elif self.kind == "contra":
            txt = "%d line(s)   ·   Moved %s" % (t["count"], _m(t["total"]))
            amount = t["total"]
        else:
            txt = "💵 Cash %s   ·   🏦 Bank %s   ·   Total %s" % (_m(t["cash"]), _m(t["bank"]),
                                                              _m(t["total"]))
            if t["vat"]:
                txt += "   (VAT %s)" % _m(t["vat"])
            amount = t["total"]
        self.balance_var.set(txt)
        try:
            from modules import country
            self.words_var.set(country.words(amount) if amount else "")
        except Exception:
            self.words_var.set("")
        self._number_preview()

    def _number_preview(self):
        if self.journal_id and self._loaded:
            self.no_var.set("No. " + self._loaded["number"])
            return
        lines = self.lines or [{"money": self._money_id() or mv.default_money(self.mode, self.money),
                                "amount": 1, "debit": 1}]
        try:
            from modules import voucher_types as vt
            codes = mv.preview_codes(self.kind, lines, self.split_var.get(), self.money)
            self.no_var.set("Saves as  " + "  +  ".join(vt.next_number(c) for c in codes))
        except Exception:
            self.no_var.set("")

    # ── fill from a saved voucher / template ──────────────────
    def _fill(self, data):
        self.date_var.set(data.get("date") or self.date_var.get())
        self.desc_var.set(data.get("narration") or "")
        self.ref_var.set(data.get("reference") or "")
        self.lines = []
        for ln in data.get("lines") or []:
            l = dict(ln)
            l["label"] = self.label_of(l.get("target")) or l.get("label") or ""
            self.lines.append(l)
        if self.kind != "journal" and self.lines:
            m = self.lines[0].get("money")
            if m in self.money_label:
                self.money_var.set(self.money_label[m])

    def _copy_last(self):
        codes = {"receipt": ("CR", "BR"), "payment": ("CP", "BP"), "contra": ("CT",),
                 "journal": ("JV",)}[self.kind]
        try:
            jid = db.execute_scalar(
                "SELECT TOP 1 journal_id FROM journal_entries WHERE voucher_type IN (%s) "
                "ORDER BY journal_id DESC" % ",".join("?" * len(codes)), codes)
        except Exception:
            jid = None
        data = mv.load(jid, self.kind) if jid else None
        if not data or not data["lines"]:
            self._say("No earlier %s to copy." % mv.TITLES[self.kind].lower()); return
        if self.lines and not messagebox.askyesno("Copy last", "Replace the lines with %s?"
                                                  % data["number"], parent=self.win):
            return
        d = date.today().strftime("%Y-%m-%d")
        data["date"], data["reference"] = self.date_var.get() or d, ""
        for l in data["lines"]:
            if (l.get("target") or ("",))[0] != "account":
                l["account_id"] = None
        self._fill(data)
        self._refresh()
        self._say("Copied from %s — change what you need and save." % data["number"])

    def _fill_tpl_menu(self):
        m = self.tpl_menu
        m.delete(0, "end")
        m.add_command(label="💾 Save these lines as a template…", command=self._save_tpl)
        tpls = mv.templates(self.kind)
        if tpls:
            m.add_separator()
            for name in tpls:
                m.add_command(label="📄 " + name, command=lambda n=name: self._load_tpl(n))
            dm = tk.Menu(m, tearoff=0)
            for name in tpls:
                dm.add_command(label=name, command=lambda n=name: self._del_tpl(n))
            m.add_separator()
            m.add_cascade(label="🗑 Delete template", menu=dm)
        else:
            m.add_command(label="(no templates for this voucher type yet)", state="disabled")

    def _save_tpl(self):
        if not self.lines:
            self._say("Add lines first, then save them as a template."); return
        name = simpledialog.askstring("Template", "Template name (e.g. Monthly rent):",
                                      parent=self.win)
        if name and mv.save_template(name, self.kind, self.lines, self.desc_var.get()):
            self._say("Template “%s” saved." % name.strip())

    def _load_tpl(self, name):
        t = mv.templates(self.kind).get(name)
        if not t:
            return
        if self.lines and not messagebox.askyesno("Template", "Replace the lines with “%s”?" % name,
                                                  parent=self.win):
            return
        self._fill({"date": self.date_var.get(), "narration": t.get("narration") or "",
                    "reference": self.ref_var.get(), "lines": mv.template_lines(t)})
        self._refresh()
        self._say("Template “%s” loaded." % name)

    def _del_tpl(self, name):
        if messagebox.askyesno("Template", "Delete template “%s”?" % name, parent=self.win):
            mv.delete_template(name)

    # ── unsaved work ──────────────────────────────────────────
    def _snapshot(self):
        return (self.date_var.get(), self.desc_var.get(), self.ref_var.get(), self.kind,
                tuple((str(l.get("target")), mv.f2(l.get("amount")), mv.f2(l.get("debit")),
                       mv.f2(l.get("credit")), mv.f2(l.get("vat")), l.get("money"),
                       l.get("description") or "") for l in self.lines))

    def _is_dirty(self):
        try:
            half = bool(self.acct_var.get().strip() or mv.f2(self.amount_var.get())
                        or mv.f2(self.dr_var.get()) or mv.f2(self.cr_var.get()))
            return half or self._snapshot() != self._clean
        except Exception:
            return False

    def _on_escape(self, e=None):
        sd = getattr(self.acct_cb, "_search_drop", None)
        if sd is not None and getattr(sd, "panel", None) is not None:
            return None
        if self._edit_idx is not None:
            self._end_edit(); self._clear_editor(); self._say("")
            return "break"
        self.win.destroy()
        return "break"

    # ── save ──────────────────────────────────────────────────
    def _update_existing(self):
        return mv.update(self.journal_id, self.kind, self.date_var.get().strip(), self.lines,
                         self.desc_var.get().strip(), self.ref_var.get().strip())

    def _save(self):
        right = mv.RIGHT[self.kind]
        if not perm.allowed(right, "edit" if self.journal_id else "add", parent=self.win):
            return
        if self.acct_var.get().strip() and (mv.f2(self.amount_var.get()) or
                                            mv.f2(self.dr_var.get()) or mv.f2(self.cr_var.get())):
            n = len(self.lines)                   # a typed line not added yet → add it
            self._add_line()
            if len(self.lines) == n and self._edit_idx is None:
                return
        if not self.lines:
            self._say("⚠️ Add lines first."); return
        vdate = self.date_var.get().strip() or date.today().strftime("%Y-%m-%d")
        try:
            if self.journal_id:
                num = self._update_existing()
                made = [(self.journal_id, num)]
            else:
                made = mv.post(self.kind, vdate, self.lines, self.desc_var.get().strip(),
                               self.ref_var.get().strip(),
                               split=bool(self.split_var.get()) and self.kind in ("receipt", "payment"))
        except mv.VoucherError as e:
            self._say("❌ " + str(e).split("\n")[0])
            messagebox.showwarning("Voucher", str(e), parent=self.win)
            return
        except Exception as e:
            self._say("❌ " + str(e)[:90])
            messagebox.showerror("Voucher", str(e)[:300], parent=self.win)
            return
        nums = ", ".join(n for _j, n in made)
        self._clean = self._snapshot()
        if self.on_saved:
            try:
                self.on_saved()
            except Exception:
                pass
        if self.journal_id:
            msg = "Voucher %s updated." % nums
        else:
            msg = ("Saved %d vouchers: %s" % (len(made), nums)) if len(made) > 1 else \
                "Voucher %s saved." % nums
        messagebox.showinfo("Voucher", msg, parent=self.win)
        from ui import after_save
        parent, kind, mode, preset = self.win.master, self.kind, self._mode_now(), self.preset
        cls, cb, edited = type(self), self.on_saved, bool(self.journal_id)
        keep_id = made[0][0] if len(made) == 1 else None

        def new():
            if cls is not MultiVoucherForm:
                return cls(parent, on_save=cb)
            return cls(parent, on_saved=cb, kind=kind, mode=mode, preset=preset)
        after_save.finish(self, nums, new=new,
                          keep=(lambda: open_voucher(parent, keep_id, cb)) if keep_id else None,
                          edited=edited)

    def _mode_now(self):
        mid = self.choice.get(self.def_money_var.get())
        if mid:
            return mv.money_kind(mid[1], self.money)
        return self.mode


class JournalForm(MultiVoucherForm):
    """Journal Voucher (JV) — the multi-line voucher window as a journal.
    Kept under its old name for the screens that open it."""

    def __init__(self, parent, on_save=None, journal_id=None):
        super().__init__(parent, on_saved=on_save, kind="journal", journal_id=journal_id)

    def _title(self):
        if self.journal_id and self._loaded:
            return "Edit Journal Entry  %s" % self._loaded["number"]
        return "New Journal Entry"


def open_voucher(parent, journal_id, on_save=None):
    """A saved typed voucher in the right window (journal → JournalForm)."""
    kind = mv.kind_of(journal_id)
    if kind == "journal":
        return JournalForm(parent, on_save=on_save, journal_id=journal_id)
    return MultiVoucherForm(parent, on_saved=on_save, journal_id=journal_id)
