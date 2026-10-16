# ============================================================
# DayBill ERP - 🌐 Online forms window (v6.8)
# ------------------------------------------------------------
# Answers from the Tally web forms wait here:
#   Customers · Suppliers · Feedback  (tabs, with the number of new ones)
# Left: the list.  Right: every answer of the chosen one, Tally style
# (question in small grey, answer below), and what you can do with it:
#   ✚ Review and add  → the normal Customer / Supplier window opens
#                        filled in; you check it and press Save
#   Ignore · Reply on WhatsApp · Share the form link / QR
# ============================================================
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from config import settings as cfg
from modules import online_forms as OF

STARS = lambda n: "★" * int(n or 0) + "☆" * (5 - int(n or 0))

_open = {}


def open_window(parent=None, kind="customer"):
    w = _open.get("win")
    try:
        if w is not None and w.win.winfo_exists():
            w.win.deiconify(); w.win.lift(); w.show(kind)
            return w
    except Exception:
        pass
    _open["win"] = OnlineFormsWindow(parent, kind)
    return _open["win"]


class OnlineFormsWindow:
    GEOM_KEY = "online_forms_geometry_v680"

    def __init__(self, parent=None, kind="customer"):
        from ui import form_kit as FK
        self.parent = parent
        self.C = C = cfg.theme()
        self.win = FK.popup("Online forms", (980, 560), (820, 460), self.GEOM_KEY,
                            parent=parent, modal=False)
        self.win.configure(bg=C["content_bg"])
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.bind("<F5>", lambda e: self.check_now())
        FK.header(self.win, C, "🌐  Online forms  ·  النماذج الإلكترونية",
                  "Tally — customers and suppliers fill them on their phone")
        self._build_top(C)
        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.tabs = {}
        for k in ("customer", "supplier", "feedback"):
            self.tabs[k] = self._build_tab(k, C)
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._tab_changed())
        self.refresh()
        self.show(kind)

    # ── top bar ─────────────────────────────────────────────
    def _build_top(self, C):
        bar = tk.Frame(self.win, bg=C["content_bg"])
        bar.pack(fill="x", padx=12, pady=(8, 2))
        self.status = tk.StringVar()
        tk.Label(bar, textvariable=self.status, font=("Segoe UI", 9), bg=C["content_bg"],
                 fg=C["text_secondary"], anchor="w").pack(side="left", fill="x", expand=True)
        self.show_all = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Show done / ignored too", variable=self.show_all,
                       bg=C["content_bg"], font=("Segoe UI", 9), activebackground=C["content_bg"],
                       command=self.refresh).pack(side="left", padx=(0, 10))
        mk = lambda txt, cmd, primary=False: tk.Button(
            bar, text=txt, command=cmd, font=("Segoe UI", 9, "bold" if primary else "normal"),
            bg=C["primary"] if primary else C["card_bg"], fg="white" if primary else C["text_primary"],
            relief="flat", padx=10, pady=4, cursor="hand2",
            highlightthickness=1, highlightbackground=C["primary"] if primary else C["border"])
        mk("🔗 Share form", self.share).pack(side="left", padx=(0, 6))
        mk("⚙ Settings", self.open_settings).pack(side="left", padx=(0, 6))
        self.check_btn = mk("⟳ Check for new answers  F5", self.check_now, True)
        self.check_btn.pack(side="left")

    def _build_tab(self, kind, C):
        page = tk.Frame(self.nb, bg=C["content_bg"])
        self.nb.add(page, text=OF.KINDS[kind][1])
        pw = tk.PanedWindow(page, orient="horizontal", sashwidth=6, bg=C["content_bg"], bd=0)
        pw.pack(fill="both", expand=True, pady=(6, 0))
        left = tk.Frame(pw, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        right = tk.Frame(pw, bg=C["card_bg"], highlightthickness=1, highlightbackground=C["border"])
        pw.add(left, minsize=360, stretch="always")
        pw.add(right, minsize=300, stretch="always")
        if kind == "feedback":
            cols = (("when", "Date", 120), ("stars", "Rating", 90), ("text", "Comment", 260),
                    ("bill", "Bill", 90), ("status", "Status", 70))
            self.fb_sum = tk.StringVar()
            tk.Label(left, textvariable=self.fb_sum, font=("Segoe UI", 10, "bold"),
                     bg=C["card_bg"], fg=C["text_primary"], anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        else:
            cols = (("when", "Date", 120), ("text", "Name", 220), ("phone", "Mobile", 110),
                    ("status", "Status", 70))
        tv = ttk.Treeview(left, columns=[c[0] for c in cols], show="headings", selectmode="browse")
        for key, head, w in cols:
            tv.heading(key, text=head)
            tv.column(key, width=w, anchor="w", stretch=key == "text")
        tv.tag_configure("new", font=("Segoe UI", 9, "bold"))
        tv.tag_configure("low", foreground=C["danger"])
        tv.tag_configure("old", foreground=C["text_secondary"])
        sb = ttk.Scrollbar(left, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=8)
        tv.pack(fill="both", expand=True, padx=(8, 0), pady=8)
        tv.bind("<<TreeviewSelect>>", lambda e, k=kind: self._show_detail(k))
        tv.bind("<Double-1>", lambda e, k=kind: self.primary_action(k))
        tv.bind("<Return>", lambda e, k=kind: self.primary_action(k))
        empty = tk.Label(left, text="", font=("Segoe UI", 10), bg=C["card_bg"],
                         fg=C["text_secondary"], justify="center")
        detail = tk.Frame(right, bg=C["card_bg"])
        detail.pack(fill="both", expand=True, padx=14, pady=10)
        return {"page": page, "tree": tv, "empty": empty, "detail": detail, "rows": {}}

    # ── data ────────────────────────────────────────────────
    def show(self, kind):
        try:
            self.nb.select(self.tabs[kind]["page"])
        except Exception:
            pass

    def current(self):
        try:
            idx = self.nb.index(self.nb.select())
            return ("customer", "supplier", "feedback")[idx]
        except Exception:
            return "customer"

    def _tab_changed(self):
        k = self.current()
        if not self.tabs[k]["tree"].selection():
            self._show_detail(k)

    def refresh(self):
        try:
            n = OF.counts()
        except Exception:
            n = {k: 0 for k in OF.KINDS}
        for k, tab in self.tabs.items():
            tv = tab["tree"]
            sel = tv.selection()
            tv.delete(*tv.get_children())
            tab["rows"] = {}
            try:
                rows = OF.entries(k, None if self.show_all.get() else "new")
            except Exception as e:
                rows = []
                self.status.set("Online forms table missing — run Database ▸ Update. (%s)" % str(e)[:80])
            for r in rows:
                iid = str(r["entry_id"])
                tab["rows"][iid] = r
                when = str(r.get("submitted_at") or "")[:16]
                st = {"new": "New", "added": "Added", "ignored": "Ignored", "done": "Done"}.get(
                    r.get("status"), r.get("status") or "")
                tags = ("new",) if r.get("status") == "new" else ("old",)
                if k == "feedback":
                    v = r["data"].get("values", {})
                    if int(r.get("rating") or 0) and int(r["rating"]) <= 2:
                        tags = tags + ("low",)
                    tv.insert("", "end", iid=iid, tags=tags, values=(
                        when, STARS(r.get("rating")), (v.get("comment") or v.get("liked") or "")[:80],
                        r.get("bill_no") or "", st))
                else:
                    tv.insert("", "end", iid=iid, tags=tags, values=(
                        when, r.get("title") or "", r.get("phone") or "", st))
            label = OF.KINDS[k][1] + ("  (%d new)" % n[k] if n.get(k) else "")
            try:
                self.nb.tab(tab["page"], text=label)
            except Exception:
                pass
            if rows:
                tab["empty"].place_forget()
            else:
                tab["empty"].configure(text=self._empty_text(k))
                tab["empty"].place(relx=0.5, rely=0.45, anchor="center")
            for s in sel:
                if tv.exists(s):
                    tv.selection_set(s)
        if "feedback" in self.tabs:
            try:
                f = OF.feedback_summary(30)
                self.fb_sum.set("Last 30 days:  %s  %.1f / 5  ·  %d answers  ·  %d unhappy (1–2 ★)" % (
                    STARS(round(f["average"])), f["average"], f["count"], f["low"]) if f["count"]
                    else "No ratings in the last 30 days yet.")
            except Exception:
                self.fb_sum.set("")
        if not self.status.get().startswith("Online forms table"):
            self._status_text()
        self._show_detail(self.current())

    def _empty_text(self, k):
        if not OF.form_id(k):
            return ("No %s form set yet.\n\nPress ⚙ Settings and paste the link of your Tally form."
                    % OF.KINDS[k][1].lower())
        return "Nothing new.\nPress ⟳ Check for new answers (F5)."

    def _status_text(self):
        last = str(cfg.get("tally_last_sync", "") or "")
        if not str(cfg.get("tally_api_key", "") or "").strip():
            self.status.set("⚠ Add your Tally API key in ⚙ Settings to bring answers in.")
        else:
            self.status.set("Last checked: %s" % (last or "never"))

    # ── right side: the answers ─────────────────────────────
    def _show_detail(self, kind):
        tab = self.tabs[kind]
        C = self.C
        for w in tab["detail"].winfo_children():
            w.destroy()
        sel = tab["tree"].selection()
        r = tab["rows"].get(sel[0]) if sel else None
        d = tab["detail"]
        if not r:
            tk.Label(d, text="Choose an answer on the left.", font=("Segoe UI", 10),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=20)
            return
        answers = (r.get("data") or {}).get("answers") or {}
        head = r.get("title") or (STARS(r.get("rating")) if kind == "feedback" else "Answer")
        tk.Label(d, text=head, font=("Segoe UI", 13, "bold"), bg=C["card_bg"],
                 fg=C["danger"] if kind == "feedback" and 0 < int(r.get("rating") or 0) <= 2
                 else C["text_primary"], anchor="w").pack(fill="x")
        tk.Label(d, text="Sent %s  ·  %s" % (str(r.get("submitted_at") or "")[:16],
                                            {"new": "new", "added": "added to DayBill",
                                             "ignored": "ignored", "done": "done"}.get(r.get("status"), "")),
                 font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"], anchor="w").pack(fill="x", pady=(0, 8))
        acts = tk.Frame(d, bg=C["card_bg"])
        acts.pack(side="bottom", fill="x", pady=(8, 0))
        body = tk.Frame(d, bg=C["card_bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        nice = {"bill": "Bill no.", "branch": "Branch"}
        row = 0
        for q, a in answers.items():
            if not (a or "").strip():
                continue
            qt = str(q).split("·")[0].strip()
            qt = nice.get(qt, qt)
            if kind == "feedback" and re.search(r"rating|rate", qt, re.I):
                try:
                    a = "%s  (%s / 5)" % (STARS(int(float(a))), a)
                except ValueError:
                    pass
            tk.Label(body, text=qt, font=("Segoe UI", 8), bg=C["card_bg"], fg=C["text_secondary"],
                     anchor="ne", justify="right", wraplength=130).grid(
                row=row, column=0, sticky="ne", padx=(0, 10), pady=3)
            tk.Label(body, text=a, font=("Segoe UI", 10), bg=C["card_bg"], fg=C["text_primary"],
                     anchor="w", justify="left", wraplength=300).grid(row=row, column=1, sticky="w", pady=2)
            row += 1
        mk = lambda txt, cmd, bg=None, fg=None: tk.Button(
            acts, text=txt, command=cmd, font=("Segoe UI", 9, "bold"), relief="flat",
            bg=bg or C["card_bg"], fg=fg or C["text_primary"], padx=12, pady=5, cursor="hand2",
            highlightthickness=1, highlightbackground=bg or C["border"])
        st = r.get("status")
        if kind in ("customer", "supplier") and st != "added":
            mk("✚ Review and add as %s" % kind, lambda: self.primary_action(kind),
               C["primary"], "white").pack(side="left")
        if kind == "feedback" and st == "new":
            mk("✔ Done", lambda: self._set_status(kind, "done"), C["primary"], "white").pack(side="left")
        if r.get("phone"):
            mk("💬 WhatsApp", lambda: self.whatsapp(kind)).pack(side="left", padx=(6, 0))
        if st == "new":
            mk("Ignore", lambda: self._set_status(kind, "ignored")).pack(side="right")
        elif st in ("ignored", "done"):
            mk("Back to new", lambda: self._set_status(kind, "new")).pack(side="right")

    def _selected(self, kind):
        tab = self.tabs[kind]
        sel = tab["tree"].selection()
        return tab["rows"].get(sel[0]) if sel else None

    def _user(self):
        try:
            from modules import session_info
            return session_info.username() if hasattr(session_info, "username") else ""
        except Exception:
            return ""

    def _set_status(self, kind, status):
        r = self._selected(kind)
        if not r:
            return
        OF.mark(r["entry_id"], status, r.get("record_id"), self._user())
        self.refresh()

    # ── actions ─────────────────────────────────────────────
    def primary_action(self, kind):
        if kind == "feedback":
            return self._set_status(kind, "done")
        r = self._selected(kind)
        if not r or r.get("status") == "added":
            return
        vals = dict((r.get("data") or {}).get("values") or {})
        try:
            old = OF.find_existing(kind, vals)
        except Exception:
            old = None
        if old and not messagebox.askyesno(
                "Already in DayBill",
                "%s already has this mobile / VAT number:\n%s\n\nAdd a new one anyway?"
                % ("A customer" if kind == "customer" else "A supplier", old.get("name")),
                parent=self.win):
            OF.mark(r["entry_id"], "added", old.get("id"), self._user())
            return self.refresh()
        self.open_prefilled(kind, r, vals)

    def open_prefilled(self, kind, r, vals):
        from config.database import db
        if kind == "customer":
            from ui.customers import CustomerForm as Form
            table, key, name_col = "customers", "customer_id", "customer_name_en"
        else:
            from ui.suppliers import SupplierForm as Form
            table, key, name_col = "suppliers", "supplier_id", "supplier_name_en"
        name = vals.get(name_col, "")

        def saved():
            try:
                row = db.fetchone("SELECT %s id FROM %s WHERE %s = ? ORDER BY %s DESC"
                                  % (key, table, name_col, key), (name,))
                OF.mark(r["entry_id"], "added", row["id"] if row else None, self._user())
            except Exception:
                pass
            try:
                self.refresh()
            except Exception:
                pass

        form = Form(self.win, None, on_save=saved)
        F = form.fields
        for k, v in vals.items():
            if k in F and v not in (None, "") and not isinstance(F[k], tk.BooleanVar):
                try:
                    F[k].set(str(v))
                except Exception:
                    pass
        if kind == "customer" and vals.get("customer_type") and hasattr(form, "type_var"):
            form.type_var.set(vals["customer_type"])
            try:
                form._on_type_change()
            except Exception:
                pass
        try:
            form.win.title(form.win.title() + "  —  from online form")
        except Exception:
            pass
        self._last_form = form
        return form

    def whatsapp(self, kind):
        r = self._selected(kind)
        if not r or not r.get("phone"):
            return
        try:
            company = str(cfg.get("company_name_en", "") or "")
        except Exception:
            company = ""
        if kind == "feedback":
            txt = ("Thank you for your feedback%s. We are sorry about your visit — how can we make it right?"
                   if int(r.get("rating") or 0) <= 2 else "Thank you for your feedback%s!") % (
                " on bill " + r["bill_no"] if r.get("bill_no") else "")
        elif kind == "customer":
            txt = "Hello %s, thank you for registering with us%s." % (
                r.get("title") or "", " at " + company if company else "")
        else:
            txt = "Hello, thank you for your supplier registration%s. We will contact you soon." % (
                " with " + company if company else "")
        try:
            from modules import whatsapp as WA
            WA.open_chat(r["phone"], txt)
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:200], parent=self.win)

    def check_now(self):
        if not OF.configured():
            self.status.set("⚠ Add your Tally API key and at least one form in ⚙ Settings first.")
            return
        self.check_btn.configure(state="disabled", text="⟳ Checking…")
        self.status.set("Checking Tally for new answers…")
        res = {}

        def work():
            try:
                res["v"] = OF.sync()
            except Exception as e:
                res["v"] = ({}, [str(e)[:200]])

        def done():
            if "v" not in res:
                return self.win.after(200, done)
            added, problems = res["v"]
            try:
                self.check_btn.configure(state="normal", text="⟳ Check for new answers  F5")
            except tk.TclError:
                return
            total = sum(added.values())
            self.refresh()
            msg = ("%d new answer%s." % (total, "" if total == 1 else "s")) if total else "No new answers."
            if problems:
                msg += "  ⚠ " + "  |  ".join(problems)
            self.status.set(msg)
        threading.Thread(target=work, daemon=True).start()
        self.win.after(200, done)

    def share(self):
        ShareDialog(self.win, self.current())

    def open_settings(self):
        SettingsDialog(self.win, on_save=self.refresh)


class ShareDialog:
    """The form link: copy it, send it on WhatsApp, or show a QR to print."""

    def __init__(self, parent, kind):
        from ui import form_kit as FK
        C = cfg.theme()
        self.kind = kind
        self.win = FK.popup("Share form", (520, 440), (460, 400), None, parent=parent)
        self.win.configure(bg=C["content_bg"])
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        FK.header(self.win, C, "🔗  Share: " + OF.KINDS[kind][1])
        link = OF.form_link(kind)
        body = tk.Frame(self.win, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=18, pady=12)
        if not link:
            tk.Label(body, text="No form set for this yet — add it in ⚙ Settings.",
                     bg=C["content_bg"], font=("Segoe UI", 10)).pack(pady=30)
            return
        self.link = link
        e = tk.Entry(body, font=("Segoe UI", 10))
        e.insert(0, link)
        e.configure(state="readonly")
        e.pack(fill="x", ipady=4)
        row = tk.Frame(body, bg=C["content_bg"])
        row.pack(fill="x", pady=8)
        tk.Button(row, text="📋 Copy link", relief="flat", bg=C["primary"], fg="white",
                  padx=10, pady=4, command=self.copy).pack(side="left")
        tk.Button(row, text="💬 Send on WhatsApp", relief="flat", bg=C["card_bg"], padx=10, pady=4,
                  highlightthickness=1, highlightbackground=C["border"],
                  command=self.send).pack(side="left", padx=6)
        self.msg = tk.Label(body, text="", bg=C["content_bg"], fg=C["success"], font=("Segoe UI", 9))
        self.msg.pack(anchor="w")
        try:
            import qrcode
            from PIL import ImageTk
            img = qrcode.make(link, border=2).resize((200, 200))
            self._img = ImageTk.PhotoImage(img)
            tk.Label(body, image=self._img, bg="white").pack(pady=6)
            tk.Label(body, text="Print this QR at the counter or on your door.",
                     bg=C["content_bg"], fg=C["text_secondary"], font=("Segoe UI", 9)).pack()
        except Exception:
            pass

    def copy(self):
        self.win.clipboard_clear()
        self.win.clipboard_append(self.link)
        self.msg.configure(text="Copied ✔")

    def send(self):
        from tkinter import simpledialog
        phone = simpledialog.askstring("WhatsApp", "Mobile number:", parent=self.win)
        if not phone:
            return
        txt = {"customer": "Please register here — it takes one minute: %s",
               "supplier": "Please send your company details here: %s",
               "feedback": "How was your visit? Tell us here: %s"}[self.kind] % self.link
        try:
            from modules import whatsapp as WA
            WA.open_chat(phone, txt)
        except Exception as e:
            messagebox.showerror("WhatsApp", str(e)[:200], parent=self.win)


class SettingsDialog:
    """Settings ▸ Online forms, right here (API key + the 3 form links)."""
    FIELDS = (("tally_api_key", "Tally API key", "tally.so ▸ Settings ▸ API keys ▸ Create API key", True),
              ("tally_form_customer", "Customer registration form", "link or ID, e.g. https://tally.so/r/4aXjl5", False),
              ("tally_form_supplier", "Supplier registration form", "link or ID", False),
              ("tally_form_feedback", "Customer feedback form", "link or ID", False))

    def __init__(self, parent, on_save=None):
        from ui import form_kit as FK
        C = cfg.theme()
        self.on_save = on_save
        self.win = FK.popup("Online forms settings", (600, 470), (520, 430), None, parent=parent)
        self.win.configure(bg=C["content_bg"])
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        FK.header(self.win, C, "⚙  Online forms (Tally)")
        foot = tk.Frame(self.win, bg=C["card_bg"])
        foot.pack(side="bottom", fill="x")
        self.note = tk.Label(foot, text="", bg=C["card_bg"], fg=C["danger"], font=("Segoe UI", 9))
        self.note.pack(side="left", padx=14)
        tk.Button(foot, text="Save", bg=C["primary"], fg="white", relief="flat", padx=18, pady=5,
                  font=("Segoe UI", 9, "bold"), command=self.save).pack(side="right", padx=12, pady=8)
        tk.Button(foot, text="Cancel", relief="flat", padx=12, pady=5,
                  command=self.win.destroy).pack(side="right", pady=8)
        g = FK.grid(self.win, C, cols=1)
        self.vars = {}
        for i, (key, label, hint, secret) in enumerate(self.FIELDS):
            v = tk.StringVar(value=str(cfg.get(key, "") or ""))
            self.vars[key] = v
            cell, e = FK.field(g, C, i, 0, label, v, hint=hint, check="")
            if secret:
                e.configure(show="•")
        self.auto = tk.BooleanVar(value=bool(cfg.flag("tally_auto_check", False)))
        self.qr = tk.BooleanVar(value=bool(cfg.flag("receipt_feedback_qr", False)))
        tk.Checkbutton(self.win, text="Check for new answers when DayBill opens and every hour",
                       variable=self.auto, bg=C["content_bg"], anchor="w").pack(fill="x", padx=14)
        tk.Checkbutton(self.win, text="Print a small 'Rate your visit' QR on POS receipts",
                       variable=self.qr, bg=C["content_bg"], anchor="w").pack(fill="x", padx=14)

    def save(self):
        for key in ("tally_form_customer", "tally_form_supplier", "tally_form_feedback"):
            raw = self.vars[key].get().strip()
            if raw and not OF.parse_form_id(raw):
                self.note.configure(text="That is not a Tally form link: %s" % raw[:40])
                return
        for key, v in self.vars.items():
            cfg.set(key, v.get().strip())
        cfg.set("tally_auto_check", bool(self.auto.get()))
        cfg.set("receipt_feedback_qr", bool(self.qr.get()))
        try:
            cfg.save_settings()
        except Exception:
            pass
        self.win.destroy()
        if self.on_save:
            self.on_save()


# ── automatic check (DayBill start + every hour) ─────────────
def start_auto(root):
    """Settings ▸ Online forms ▸ check automatically: quiet, in the
    background; a toast tells about new answers."""
    def tick():
        try:
            if cfg.flag("tally_auto_check", False) and OF.configured():
                res = {}

                def work():
                    try:
                        res["v"] = OF.sync()
                    except Exception:
                        res["v"] = ({}, [])
                t = threading.Thread(target=work, daemon=True)
                t.start()

                def done():
                    if "v" not in res:
                        return root.after(500, done)
                    n = sum(res["v"][0].values())
                    if n:
                        try:
                            from ui.ui_polish import toast
                            toast(root, "🌐 %d new online form answer%s — Customers ▸ Online forms"
                                  % (n, "" if n == 1 else "s"), "info", 6000)
                        except Exception:
                            pass
                root.after(500, done)
        except Exception:
            pass
        try:
            root.after(3600 * 1000, tick)
        except Exception:
            pass
    try:
        root.after(20 * 1000, tick)
    except Exception:
        pass
