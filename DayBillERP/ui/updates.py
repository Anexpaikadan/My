# ============================================================
# DayBill ERP - Updates & Maintenance Screen
# Shows version, applies database updates with one click,
# and lists what's new.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.language import t
from config.database import db
from modules import db_updater as upd


class UpdatesView:
    def __init__(self, parent):
        self.parent = parent
        C = cfg.theme()
        self.frame = tk.Frame(parent, bg=C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self._build(C)

    def _build(self, C):
        # Header
        bar = tk.Frame(self.frame, bg=C["content_bg"])
        bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="🔄  Updates & Maintenance",
                 font=("Segoe UI", 18, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")

        # Version card
        vcard = tk.Frame(self.frame, bg=C["primary"], height=70)
        vcard.pack(fill="x", padx=24, pady=(14, 8)); vcard.pack_propagate(False)
        tk.Label(vcard, text=f"DayBill ERP  v{upd.APP_VERSION}",
                 font=("Segoe UI", 15, "bold"), bg=C["primary"], fg="white").pack(
                     side="left", padx=20)
        tk.Label(vcard, text="Saudi VAT & ZATCA compliant billing system",
                 font=("Segoe UI", 9), bg=C["primary"], fg="#CFE9DA").pack(
                     side="left")
        # v6.0: update the program itself
        tk.Button(vcard, text="🌐  Check online", font=("Segoe UI", 9), bg="white",
                  fg=C["primary"], relief="flat", padx=10, pady=4, cursor="hand2",
                  command=self._check_online).pack(side="right", padx=(6, 16))
        tk.Button(vcard, text="📦  Install a new version…", font=("Segoe UI", 10, "bold"),
                  bg="white", fg=C["primary"], relief="flat", padx=12, pady=4, cursor="hand2",
                  command=self._install_file).pack(side="right")

        # Two columns: DB updates | changelog
        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True, padx=24, pady=8)

        # ── Left: database updates ────────────────────────────
        left = tk.Frame(body, bg=C["content_bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        head = tk.Frame(left, bg=C["content_bg"]); head.pack(fill="x")
        tk.Label(head, text="Database Updates", font=("Segoe UI", 12, "bold"),
                 bg=C["content_bg"], fg=C["text_primary"]).pack(side="left")
        tk.Button(head, text="⚡ Apply All Updates", font=("Segoe UI", 10, "bold"),
                  bg=C["primary"], fg="white", relief="flat", padx=16, pady=7,
                  cursor="hand2", command=self._apply_all).pack(side="right")

        tk.Label(left,
                 text="Applies any new database changes that come with software "
                      "updates. Safe to run anytime — already-applied updates are "
                      "skipped automatically.",
                 font=("Segoe UI", 8), bg=C["content_bg"], fg=C["text_secondary"],
                 wraplength=380, justify="left").pack(anchor="w", pady=(2, 8))

        card = tk.Frame(left, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True)
        cols = ("status", "version", "desc")
        h = {"status": ("Status", 90, "center"), "version": ("Version", 70, "center"),
             "desc": ("Update", 280, "w")}
        vsb = ttk.Scrollbar(card, orient="vertical"); vsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)
        for col in cols:
            lbl, w, a = h[col]
            self.tree.heading(col, text=lbl); self.tree.column(col, width=w, anchor=a)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("applied", foreground="#16A34A")
        self.tree.tag_configure("pending", foreground="#D97706")
        self.tree.tag_configure("missing", foreground="#DC2626")

        self.status_var = tk.StringVar()
        tk.Label(left, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=C["content_bg"], fg=C["primary"]).pack(anchor="w", pady=6)

        # ── Preferences (feature toggles) ─────────────────────
        pref = tk.Frame(left, bg=C["card_bg"],
                        highlightbackground=C["border"], highlightthickness=1)
        pref.pack(fill="x", pady=(8, 0))
        pin = tk.Frame(pref, bg=C["card_bg"]); pin.pack(fill="x", padx=14, pady=10)
        tk.Label(pin, text="⚙ Feature Settings", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", pady=(0, 6))

        self.voice_var = tk.BooleanVar(value=bool(cfg.get("voice_search_enabled", False)))
        tk.Checkbutton(pin, text="🎤 Enable Voice Search in Sales window",
                       variable=self.voice_var, font=("Segoe UI", 9),
                       bg=C["card_bg"], activebackground=C["card_bg"],
                       command=self._toggle_voice).pack(anchor="w")
        tk.Label(pin, text="Needs a microphone + internet. Recognition of Arabic "
                           "names may be imperfect. Reopen the Sales window after "
                           "changing this.",
                 font=("Segoe UI", 7), bg=C["card_bg"], fg=C["text_secondary"],
                 wraplength=380, justify="left").pack(anchor="w", pady=(2, 0))

        # ── Right: changelog ──────────────────────────────────
        right = tk.Frame(body, bg=C["card_bg"], width=320,
                         highlightbackground=C["border"], highlightthickness=1)
        right.pack(side="right", fill="y"); right.pack_propagate(False)
        tk.Frame(right, bg=C["primary"], height=4).pack(fill="x")
        rin = tk.Frame(right, bg=C["card_bg"])
        rin.pack(fill="both", expand=True, padx=14, pady=12)
        tk.Label(rin, text="✨ What's New", font=("Segoe UI", 12, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", pady=(0, 8))

        canvas = tk.Canvas(rin, bg=C["card_bg"], highlightthickness=0)
        sb = ttk.Scrollbar(rin, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=C["card_bg"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for ver, items in upd.CHANGELOG:
            tk.Label(inner, text=f"Version {ver}", font=("Segoe UI", 10, "bold"),
                     bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", pady=(8, 2))
            for it in items:
                tk.Label(inner, text=f"  • {it}", font=("Segoe UI", 8),
                         bg=C["card_bg"], fg=C["text_secondary"],
                         wraplength=270, justify="left").pack(anchor="w")

        self._load()

    # ── v6.0: program update ──────────────────────────────────
    def _install_file(self, path=None):
        from tkinter import filedialog
        from modules import app_update as AU
        if path is None:
            path = filedialog.askopenfilename(
                title="DayBill update file", parent=self.frame,
                filetypes=[("DayBill update", "*.zip *.exe"), ("All files", "*.*")])
        if not path:
            return None
        info = AU.inspect(path)
        if not info["ok"]:
            messagebox.showwarning("Update", "This file can't be installed:\n\n• "
                                   + "\n• ".join(info["problems"]), parent=self.frame)
            return info
        return self._install(path, info)

    def _install(self, path, info):
        from modules import app_update as AU
        if not messagebox.askyesno(
                "Install update", "Install DayBill ERP %s (you have %s)?\n\nDayBill closes, the new "
                "version is copied (a backup of the old one is kept) and DayBill starts again. "
                "Settings, database settings and the product key are kept.\n\nClose other DayBill "
                "windows first." % (info.get("version") or "?", AU.current_version()), parent=self.frame):
            return info
        try:
            staging = AU.stage(path, info)
            bat = AU.write_helper(staging)
            AU.launch_helper(bat)
        except Exception as e:
            messagebox.showerror("Update", "Nothing was changed: %s" % str(e)[:300], parent=self.frame)
            return info
        try:
            self.frame.winfo_toplevel().destroy()
        except Exception:
            pass
        return info

    def _check_online(self):
        from modules import app_update as AU
        try:
            d = AU.check_online()
        except Exception as e:
            messagebox.showinfo("Check online", str(e)[:300], parent=self.frame)
            return
        if not d.get("newer"):
            messagebox.showinfo("Check online", "You have the newest version (%s)." % AU.current_version(),
                                parent=self.frame)
            return
        if not messagebox.askyesno("New version", "DayBill ERP %s is available. Download and install it "
                                   "now?" % d.get("version"), parent=self.frame):
            return
        try:
            path = AU.download(d)
        except Exception as e:
            messagebox.showerror("Download", str(e)[:300], parent=self.frame)
            return
        self._install_file(path)

    def _toggle_voice(self):
        cfg.set("voice_search_enabled", bool(self.voice_var.get()))
        try:
            cfg.save_settings()
        except Exception:
            pass
        state = "enabled" if self.voice_var.get() else "disabled"
        self.status_var.set(f"🎤 Voice Search {state}. Reopen the Sales window to apply.")

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        try:
            rows = upd.patch_status(db)
        except Exception as e:
            self.status_var.set(f"⚠️ Cannot read update status: {str(e)[:80]}")
            return
        pending = 0
        for r in rows:
            if not r["file_exists"]:
                status, tag = "❓ Missing file", "missing"
            elif r["applied"]:
                status, tag = "✅ Applied", "applied"
            else:
                status, tag = "⏳ Pending", "pending"; pending += 1
            self.tree.insert("", "end", values=(
                status, r["version"], r["description"]), tags=(tag,))
        if pending:
            self.status_var.set(f"⏳ {pending} update(s) pending — click 'Apply All Updates'.")
        else:
            self.status_var.set("✅ Your database is up to date.")

    def _apply_all(self):
        if not messagebox.askyesno("Apply Updates",
                "Apply all pending database updates now?\n\n"
                "This is safe and only adds new tables/columns. "
                "Already-applied updates are skipped."):
            return
        self.status_var.set("⏳ Applying updates…")
        self.frame.update_idletasks()
        try:
            res = upd.apply_all_pending(db)
        except Exception as e:
            messagebox.showerror("Update Failed", str(e))
            return

        applied = len(res["applied"])
        skipped = len(res["skipped"])
        if res["failed"]:
            fname, msg = res["failed"][0]
            messagebox.showerror("Update Failed",
                f"Applied {applied} update(s), then hit a problem:\n\n{msg}\n\n"
                "Fix this and run again. Already-applied updates are kept.")
        else:
            messagebox.showinfo("✅ Up to Date",
                f"Done!\n\nApplied: {applied}\nAlready current: {skipped}\n\n"
                "Your database now matches this software version.")
        self._load()
