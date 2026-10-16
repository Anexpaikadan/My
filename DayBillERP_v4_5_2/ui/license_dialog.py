# ============================================================
# DayBill ERP - Help ▸ Product Key
# ------------------------------------------------------------
# Shows the licence status and the INSTALLATION ID (send it to your
# DayBill dealer), takes a product key (offline activation), and — when
# the dealer runs a licence server — activates / checks online.
# ============================================================

import tkinter as tk
from tkinter import messagebox
import sys, os, threading, webbrowser, urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules import license as lic

MODE_TEXT = {
    "licensed": ("✅ Activated", "success"),
    "trial": ("⏳ Trial", "warning"),
    "trial_over": ("⛔ Trial ended — read-only", "danger"),
    "expired": ("⛔ Key expired — read-only", "danger"),
    "blocked": ("⛔ Licence blocked — read-only", "danger"),
    "invalid": ("⚠ Key not valid", "danger"),
}


class LicenseDialog:
    def __init__(self, parent, on_change=None):
        C = cfg.theme()
        self.C = C
        self.on_change = on_change
        self.win = tk.Toplevel(parent)
        self.win.title("Product Key")
        self.win.configure(bg=C["card_bg"])
        self.win.geometry("620x520")
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        head = tk.Frame(self.win, bg=C["primary"]); head.pack(fill="x")
        tk.Label(head, text="🔑  DayBill Product Key", font=("Segoe UI", 13, "bold"),
                 bg=C["primary"], fg="white").pack(side="left", padx=14, pady=8)
        self.body = tk.Frame(self.win, bg=C["card_bg"])
        self.body.pack(fill="both", expand=True, padx=18, pady=10)
        self._build()

    def _lbl(self, parent, text, bold=False, color=None, size=9):
        return tk.Label(parent, text=text, font=("Segoe UI", size, "bold" if bold else "normal"),
                        bg=self.C["card_bg"], fg=color or self.C["text_primary"],
                        anchor="w", justify="left")

    def _build(self):
        C = self.C
        for w in self.body.winfo_children():
            w.destroy()
        st = lic.status(refresh=True)
        txt, col = MODE_TEXT.get(st["mode"], (st["mode"], "text_primary"))
        box = tk.Frame(self.body, bg=C["content_bg"], highlightthickness=1,
                       highlightbackground=C["border"])
        box.pack(fill="x")
        self._lbl(box, txt, bold=True, color=C.get(col, C["text_primary"]), size=12).configure(
            bg=C["content_bg"])
        box.winfo_children()[-1].pack(anchor="w", padx=12, pady=(8, 2))
        lines = []
        if st["mode"] == "licensed":
            lines.append(f"Customer: {st['customer']}")
            lines.append(f"Branches: {st['branches'] or 'unlimited'}    "
                         f"Counters: {st['counters'] or 'unlimited'}")
            lines.append("Valid until: " + (f"{st['expiry']:%d/%m/%Y}  ({st['days_left']} days)"
                                            if st["expiry"] else "no expiry"))
            lines.append(f"Serial: {st['serial']}")
        elif st["mode"] == "trial":
            lines.append(f"{st['days_left']} day(s) left of the 30-day trial "
                         f"(1 branch, 2 counters).")
        else:
            lines.append(st.get("message") or "")
            lines.append("You can still open, print and export everything.")
        if st.get("online"):
            lines.append(f"Online check: {st['online']}")
        for ln in lines:
            l = self._lbl(box, ln); l.configure(bg=C["content_bg"]); l.pack(anchor="w", padx=12)
        tk.Frame(box, bg=C["content_bg"], height=8).pack()

        # ── 1. one box: licence code (online) or full product key ──
        act = tk.Frame(self.body, bg=C["card_bg"]); act.pack(fill="x", pady=(14, 0))
        self._lbl(act, "Enter your licence code", bold=True, size=11).pack(anchor="w")
        self._lbl(act, "From your dealer, like  K7QF-2MXR-9TPL   (a DB1-… key also works)",
                  color=C["text_secondary"]).pack(anchor="w", pady=(0, 4))
        row = tk.Frame(act, bg=C["card_bg"]); row.pack(fill="x")
        self.code_var = tk.StringVar()
        self.code_entry = tk.Entry(row, textvariable=self.code_var,
                                   font=("Consolas", 16, "bold"), justify="center",
                                   relief="solid", bd=1)
        self.code_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.code_entry.bind("<Return>", lambda e: self._activate())
        self.act_btn = tk.Button(row, text="🔑  Activate", font=("Segoe UI", 12, "bold"),
                                 bg=C["success"], fg="white", relief="flat", padx=18,
                                 cursor="hand2", activebackground=C["success"],
                                 activeforeground="white", command=self._activate)
        self.act_btn.pack(side="left", padx=(8, 0), ipady=6)
        self.msg_var = tk.StringVar()
        self.msg_lbl = self._lbl(act, "", size=9)
        self.msg_lbl.configure(textvariable=self.msg_var, wraplength=560)
        self.msg_lbl.pack(anchor="w", pady=(6, 0))
        self.code_entry.focus_set()

        # ── 2. no internet: send the installation ID for an offline key ──
        off = tk.Frame(self.body, bg=C["content_bg"], highlightthickness=1,
                       highlightbackground=C["border"])
        off.pack(fill="x", pady=(14, 0))
        l = self._lbl(off, "No code or no internet?  Send this Installation ID to your dealer "
                      "— you get a product key to paste above.", color=C["text_secondary"])
        l.configure(bg=C["content_bg"], wraplength=540); l.pack(anchor="w", padx=10, pady=(8, 4))
        r = tk.Frame(off, bg=C["content_bg"]); r.pack(fill="x", padx=10, pady=(0, 10))
        self.iid = lic.installation_id()
        e = tk.Entry(r, font=("Consolas", 13, "bold"), justify="center", relief="flat")
        e.insert(0, self.iid); e.config(state="readonly")
        e.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(r, text="📋 Copy", font=("Segoe UI", 9, "bold"), relief="flat",
                  bg=C["card_bg"], cursor="hand2", command=self._copy).pack(side="left", padx=(6, 0),
                                                                           ipady=3)
        tk.Button(r, text="WhatsApp", font=("Segoe UI", 9, "bold"), relief="flat",
                  bg="#25D366", fg="white", cursor="hand2", activebackground="#1EBE5A",
                  command=self._whatsapp).pack(side="left", padx=(6, 0), ipady=3)

        # ── bottom: advanced server box (hidden), remove key, close ──
        bot = tk.Frame(self.body, bg=C["card_bg"]); bot.pack(side="bottom", fill="x", pady=(10, 0))
        tk.Button(bot, text="Close", font=("Segoe UI", 10), bg=C["content_bg"], relief="flat",
                  padx=16, pady=5, command=self.win.destroy).pack(side="right")
        if st["mode"] in ("licensed", "expired", "invalid", "blocked"):
            tk.Button(bot, text="Remove key", font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["danger"], relief="flat", padx=10, pady=5, cursor="hand2",
                      command=self._remove).pack(side="right", padx=6)
        if st["mode"] == "licensed":
            tk.Button(bot, text="⟳ Check licence now", font=("Segoe UI", 9), bg=C["content_bg"],
                      relief="flat", padx=10, pady=5, cursor="hand2",
                      command=self._check).pack(side="left")
        tk.Button(bot, text="⚙ Server", font=("Segoe UI", 8), bg=C["card_bg"],
                  fg=C["text_secondary"], relief="flat", cursor="hand2",
                  command=self._toggle_adv).pack(side="left", padx=6)
        self.adv = tk.Frame(self.body, bg=C["card_bg"])
        self._lbl(self.adv, "Licence server (only change if your dealer tells you)",
                  color=C["text_secondary"]).pack(anchor="w")
        ar = tk.Frame(self.adv, bg=C["card_bg"]); ar.pack(fill="x")
        self.url_var = tk.StringVar(value=lic._server_url())
        tk.Entry(ar, textvariable=self.url_var, font=("Segoe UI", 9)).pack(
            side="left", fill="x", expand=True, ipady=2)
        tk.Button(ar, text="Default", font=("Segoe UI", 8), relief="flat", bg=C["content_bg"],
                  cursor="hand2", command=lambda: self.url_var.set(lic.DEFAULT_SERVER)).pack(
                      side="left", padx=4)
        self._adv_on = False

    # ── helpers ──
    def _toggle_adv(self):
        self._adv_on = not self._adv_on
        if self._adv_on:
            self.adv.pack(fill="x", pady=(10, 0))
        else:
            self.adv.pack_forget()

    def _copy(self):
        try:
            self.win.clipboard_clear(); self.win.clipboard_append(self.iid)
            self._say("Installation ID copied.", "success")
        except Exception:
            pass

    def _whatsapp(self):
        txt = "DayBill ERP - please send my product key.\nInstallation ID: " + self.iid
        try:
            webbrowser.open("https://wa.me/?text=" + urllib.parse.quote(txt))
        except Exception:
            self._copy()

    def _say(self, text, color="text_primary"):
        try:
            self.msg_var.set(text)
            self.msg_lbl.configure(fg=self.C.get(color, self.C["text_primary"]))
        except tk.TclError:
            pass

    def _done(self, ok, msg):
        (messagebox.showinfo if ok else messagebox.showwarning)("Product key", msg,
                                                                parent=self.win)
        self._build()
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    def _save_url(self):
        url = self.url_var.get().strip()
        cfg.set("license_server", "" if url == lic.DEFAULT_SERVER else url)
        try:
            cfg.save_settings()
        except Exception:
            pass

    def _busy(self, on):
        try:
            self.act_btn.configure(state="disabled" if on else "normal",
                                   text="⏳  Wait…" if on else "🔑  Activate")
            self.win.configure(cursor="watch" if on else "")
        except tk.TclError:
            pass

    def _run_online(self, payload, finish):
        """Network call in a thread (window stays alive), result handled
        here on the main thread."""
        box = {}

        def work():
            try:
                box["res"] = lic._post(payload)
            except Exception as e:
                box["err"] = str(e)
        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not box:
                try:
                    self.win.after(150, poll)
                except tk.TclError:
                    pass
                return
            self._busy(False)
            if "err" in box:
                self._say(box["err"], "danger")
                return
            ok, msg = finish(box["res"])
            if ok:
                self._done(True, msg)
            else:
                self._say(msg, "danger")
        poll()

    def _activate(self):
        text = self.code_var.get().strip()
        if not text:
            self._say("Type your licence code first.", "danger")
            return
        if lic.looks_like_key(text):
            ok, msg = lic.activate(text)
            if ok:
                self._done(True, msg)
            else:
                self._say(msg, "danger")
            return
        self._save_url()
        self._busy(True)
        self._say("Connecting to the licence server…", "text_secondary")
        self._run_online(lic.activate_payload(text), lic.finish_activate)

    def _remove(self):
        if messagebox.askyesno("Product key", "Remove the product key from this installation?",
                               parent=self.win):
            lic.remove_key()
            self._done(True, "Key removed.")

    def _check(self):
        self._save_url()
        self._say("Checking…", "text_secondary")
        self._run_online(lic._check_payload(), lambda res: (True, lic._apply_check(res)))
