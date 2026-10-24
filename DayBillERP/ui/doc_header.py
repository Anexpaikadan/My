# ============================================================
# DayBill ERP - document header blocks (v7.9)
# ------------------------------------------------------------
# One look for the top of every transaction window (Sales, Sales
# Return, Purchase, Purchase Return):
#
#   ┌ DOCUMENT ───────┐┌ CUSTOMER ──────────┐┌ CONTACT ─────┐┌ DETAILS ──┐ ╔ BALANCE ═══╗
#   │ No.   [1001]▲▼  ││ Customer [....▾] + ││ Mobile [...] ││ Store [▾] │ ║ 1,250.00 Dr║
#   │ Date  [....]    ││ Name     [.......] ││ Address[...] ││ ...       │ ║ last bill …║
#   └─────────────────┘└────────────────────┘└──────────────┘└───────────┘ ╚════════════╝
#
# Each block is a small titled column: labels on the left (right
# aligned), the boxes take the rest of the width. The balance card on
# the right shows the party's ledger balance (red = owes us / we owe,
# green = in credit), their last bill and this counter's last bill.
#
#   h = DocHeader(parent, C)
#   b = h.block("Customer", weight=3)
#   b.row("Name", lambda p: tk.Entry(p, ...))       → the widget
#   b.row("Date", factory, extra=lambda p: …)       → a second widget beside it
#   b.flags([("Credit", var), ("Draft", var2)])     → a row of check boxes
#   card = h.balance_card()  ;  card.show("customer", party_id, exclude_id)
# ============================================================
import tkinter as tk


class Block:
    def __init__(self, header, title, weight=1, minwidth=0):
        C = header.C
        self.C = C
        self.header = header
        self.frame = tk.Frame(header.frame, bg=C["card_bg"], highlightthickness=1,
                              highlightbackground=C.get("border", "#E2E6EE"))
        col = len(header.blocks)
        self.frame.grid(row=0, column=col, sticky="nsew", padx=(0, 6), pady=0)
        header.frame.columnconfigure(col, weight=weight, minsize=minwidth)
        cap = tk.Frame(self.frame, bg=C["card_bg"])
        cap.pack(fill="x", padx=8, pady=(4, 0))
        tk.Label(cap, text=title.upper(), font=("Segoe UI", 8, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left")
        tk.Frame(cap, bg=C.get("border", "#E2E6EE"), height=1).pack(side="left", fill="x",
                                                                  expand=True, padx=(6, 0), pady=(2, 0))
        self.body = tk.Frame(self.frame, bg=C["card_bg"])
        self.body.pack(fill="both", expand=True, padx=8, pady=(2, 6))
        self.body.columnconfigure(1, weight=1)
        self.n = 0
        self.labels = {}

    def row(self, label, factory, extra=None, required=False):
        """label + a box (and an optional small widget after it)."""
        C = self.C
        lb = tk.Label(self.body, text=label + (" *" if required else ""), font=("Segoe UI", 9),
                      bg=C["card_bg"], fg=C["text_secondary"], anchor="e")
        lb.grid(row=self.n, column=0, sticky="e", padx=(0, 6), pady=1)
        self.labels[label] = lb
        cell = tk.Frame(self.body, bg=C["card_bg"])
        cell.grid(row=self.n, column=1, sticky="ew", pady=1)
        w = factory(cell)
        x = extra(cell) if extra is not None else None
        # the small widget (buttons, a 2nd box) keeps its room on the right;
        # the box takes the rest of the width
        if x is not None and x.master is cell and not x.winfo_manager():
            x.pack(side="right", padx=(4, 0))
        if w is not None and w.master is cell and not w.winfo_manager():
            w.pack(side="left", fill="x", expand=True)
        self.n += 1
        return w

    def flags(self, items):
        """A row of check boxes: [(text, BooleanVar[, command[, fg]])]."""
        C = self.C
        fr = tk.Frame(self.body, bg=C["card_bg"])
        fr.grid(row=self.n, column=0, columnspan=2, sticky="w", pady=(2, 0))
        out = []
        for it in items:
            text, var = it[0], it[1]
            cmd = it[2] if len(it) > 2 else None
            fg = it[3] if len(it) > 3 else C["text_secondary"]
            cb = tk.Checkbutton(fr, text=text, variable=var, command=cmd, font=("Segoe UI", 9),
                                bg=C["card_bg"], fg=fg, activebackground=C["card_bg"],
                                highlightthickness=0, cursor="hand2")
            cb.pack(side="left", padx=(0, 10))
            out.append(cb)
        self.n += 1
        return out

    def widget_row(self, factory):
        """A full-width row of the caller's own widgets (buttons …)."""
        fr = tk.Frame(self.body, bg=self.C["card_bg"])
        fr.grid(row=self.n, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        factory(fr)
        self.n += 1
        return fr


class BalanceCard:
    """The party's balance in big figures + last bill + this counter's."""

    def __init__(self, header, title="Balance"):
        C = self.C = header.C
        self.frame = tk.Frame(header.frame, bg=C.get("primary_light", "#EEF3FF"), highlightthickness=1,
                              highlightbackground=C["primary"])
        col = len(header.blocks)
        self.frame.grid(row=0, column=col, sticky="nsew", padx=(0, 0))
        header.frame.columnconfigure(col, weight=0, minsize=190)
        bg = self.frame["bg"]
        self.title = tk.Label(self.frame, text=title.upper(), font=("Segoe UI", 8, "bold"), bg=bg,
                              fg=C["primary"])
        self.title.pack(anchor="w", padx=10, pady=(5, 0))
        self.amount = tk.Label(self.frame, text="—", font=("Segoe UI", 18, "bold"), bg=bg,
                               fg=C["text_primary"], anchor="w")
        self.amount.pack(fill="x", padx=10)
        self.line1 = tk.Label(self.frame, text="", font=("Segoe UI", 9), bg=bg, fg=C["text_secondary"],
                              anchor="w", justify="left")
        self.line1.pack(fill="x", padx=10)
        self.line2 = tk.Label(self.frame, text="", font=("Segoe UI", 9), bg=bg, fg=C["text_secondary"],
                              anchor="w", justify="left")
        self.line2.pack(fill="x", padx=10, pady=(0, 6))
        self.tools = tk.Frame(self.frame, bg=bg)
        self.tools.pack(fill="x", padx=8, pady=(0, 6))
        self.facts = None

    def show(self, kind, party_id, exclude_id=None):
        """Fill the card; → the one-line text (for older labels)."""
        try:
            from modules import party_info as PI
            f = PI.facts(kind, party_id, exclude_id)
            txt = PI.text(kind, party_id, exclude_id, f=f)
        except Exception:
            f, txt, PI = None, "", None
        self.facts = f
        if not f:
            self.amount.configure(text="—", fg=self.C["text_primary"])
            self.line1.configure(text=""); self.line2.configure(text="")
            return txt
        if f["balance"] is None:                     # the walk-in party
            self.title.configure(text="CASH SALE" if kind == "customer" else "CASH PURCHASE")
            self.amount.configure(text="No account", fg=self.C["text_secondary"],
                                  font=("Segoe UI", 13, "bold"))
            self.line1.configure(text="")
        else:
            b = f["balance"]
            owes = (b > 0) if kind == "customer" else (b < 0)
            self.title.configure(text="BALANCE")
            self.amount.configure(text=PI.balance_text(b), font=("Segoe UI", 18, "bold"),
                                  fg=(self.C.get("danger", "#B91C1C") if owes and abs(b) > 0.004
                                      else ("#15803D" if abs(b) > 0.004 else self.C["text_primary"])))
            lb = f["last"]
            self.line1.configure(text=("Last bill  #%s · %s · %s" % (lb["number"], PI.money(lb["total"]), lb["date"]))
                                 if lb else "Last bill  —")
        cl = f["counter"]
        self.line2.configure(text=("This counter  #%s · %s" % (cl["number"], PI.money(cl["total"]))) if cl else "")
        return txt


class DocHeader:
    def __init__(self, parent, C, pady=(4, 4)):
        self.C = C
        self.frame = tk.Frame(parent, bg=C["content_bg"] if "content_bg" in C else C["card_bg"])
        self.frame.pack(fill="x", padx=8, pady=pady)
        self.frame.rowconfigure(0, weight=1)
        self.blocks = []

    def block(self, title, weight=1, minwidth=0):
        b = Block(self, title, weight, minwidth)
        self.blocks.append(b)
        return b

    def balance_card(self, title="Balance"):
        card = BalanceCard(self, title)
        self.blocks.append(card)
        return card
