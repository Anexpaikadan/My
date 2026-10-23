# ============================================================
# DayBill ERP - 📱 QR sign-in window (v7.4)
# ------------------------------------------------------------
# Users ▸ 📱 QR sign-in  /  HR ▸ Employee ▸ 📱 QR sign-in
#   make a personal QR · send it on WhatsApp · print the staff card ·
#   copy the link · turn it off. The person scans it (phone camera or
#   the desktop login's barcode scanner) and is signed in as that user.
# ============================================================
import os
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox

from config import settings as cfg
from config.database import db
from modules import qr_login as Q
from modules import permissions as perm

VALID = [("Never expires", None), ("7 days", 7), ("30 days", 30), ("90 days", 90), ("1 year", 365)]
BASIC_MODULES = ["info", "price", "count"]


class QrLoginDialog:
    def __init__(self, parent, user_id, on_change=None):
        C = self.C = cfg.theme()
        self.user_id = int(user_id)
        self.on_change = on_change
        self.key = None
        self._img = None
        u = db.fetchone("SELECT user_id, username, full_name_en, phone, is_active FROM users WHERE user_id=?",
                        (self.user_id,)) or {}
        self.user = u
        self.win = tk.Toplevel(parent)
        self.win.title("📱 QR sign-in — %s" % (u.get("full_name_en") or u.get("username") or ""))
        self.win.configure(bg=C["content_bg"])
        self.win.geometry("720x560")
        self._no_close_confirm = True
        try:
            self.win.transient(parent.winfo_toplevel())
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        hdr = tk.Frame(self.win, bg=C["primary"], height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="📱  QR sign-in · %s (%s)" % (u.get("full_name_en") or "", u.get("username") or ""),
                 font=("Segoe UI", 12, "bold"), bg=C["primary"], fg="white").pack(side="left", padx=14)
        body = tk.Frame(self.win, bg=C["content_bg"]); body.pack(fill="both", expand=True, padx=14, pady=10)
        left = tk.Frame(body, bg=C["content_bg"]); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=C["card_bg"], width=260, height=300,
                         highlightbackground=C["border"], highlightthickness=1)
        right.pack(side="right", padx=(10, 0), anchor="n"); right.pack_propagate(False)
        self.qr_lbl = tk.Label(right, text="Press  🔄 Make new QR", bg=C["card_bg"], fg=C["text_secondary"],
                               font=("Segoe UI", 10), wraplength=230)
        self.qr_lbl.pack(expand=True)

        def lab(t):
            tk.Label(left, text=t, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                     fg=C["text_secondary"], anchor="w").pack(fill="x", pady=(8, 2))
        self.status_var = tk.StringVar()
        tk.Label(left, textvariable=self.status_var, font=("Segoe UI", 10, "bold"), bg=C["content_bg"],
                 fg=C["text_primary"], anchor="w", justify="left", wraplength=400).pack(fill="x")
        lab("Mobile (WhatsApp)")
        self.phone_var = tk.StringVar(value=Q.phone_of(self.user_id))
        tk.Entry(left, textvariable=self.phone_var, font=("Segoe UI", 11), relief="solid", bd=1).pack(fill="x")
        lab("Valid for")
        self.valid_var = tk.StringVar(value=VALID[0][0])
        ttk.Combobox(left, textvariable=self.valid_var, state="readonly", values=[v[0] for v in VALID],
                     width=18).pack(anchor="w")
        self.mob_var = tk.BooleanVar(value=True)
        self.desk_var = tk.BooleanVar(value=True)
        tk.Checkbutton(left, text="Phone app (DayBill Mobile on the shop Wi-Fi)", variable=self.mob_var,
                       bg=C["content_bg"], anchor="w").pack(fill="x", pady=(8, 0))
        tk.Checkbutton(left, text="Desktop sign-in (scan the QR card at the login)", variable=self.desk_var,
                       bg=C["content_bg"], anchor="w").pack(fill="x")
        self.mods_var = tk.StringVar()
        self.mods_lbl = tk.Label(left, textvariable=self.mods_var, font=("Segoe UI", 9), bg=C["content_bg"],
                                 fg=C["text_secondary"], anchor="w", justify="left", wraplength=400)
        self.mods_lbl.pack(fill="x", pady=(6, 0))
        self.mods_btn = tk.Button(left, text="Give basic phone modules (Product Info, Price Check, Stock Count)",
                                  font=("Segoe UI", 8), relief="flat", bg=C["card_bg"], cursor="hand2",
                                  command=self._give_modules)
        tk.Label(left, text="⚠ Anyone holding this QR can sign in as this user — treat it like a password. "
                            "Making a new QR stops the old one at once.", font=("Segoe UI", 8),
                 bg=C["content_bg"], fg=C["danger"], anchor="w", justify="left", wraplength=420).pack(fill="x",
                                                                                                      pady=(10, 0))
        self.msg_var = tk.StringVar()
        tk.Label(self.win, textvariable=self.msg_var, font=("Segoe UI", 9, "bold"), bg=C["content_bg"],
                 fg="#047857", anchor="w", wraplength=680, justify="left").pack(fill="x", padx=16)
        btns = tk.Frame(self.win, bg=C["content_bg"]); btns.pack(fill="x", padx=14, pady=10)

        def b(text, cmd, bg=None, fg="white", side="left"):
            w = tk.Button(btns, text=text, font=("Segoe UI", 9, "bold"), bg=bg or C["card_bg"],
                          fg=fg if bg else C["text_primary"], relief="flat", padx=10, pady=6, cursor="hand2",
                          command=cmd)
            w.pack(side=side, padx=(0, 6))
            return w
        b("🔄 Make new QR", self._make, C["primary"])
        b("💬 Send on WhatsApp", self._send, "#16A34A")
        b("🖨 Staff card (PDF)", self._card)
        b("📋 Copy link", self._copy)
        b("⛔ Turn off", self._off, fg=C["danger"])
        b("Close", self.win.destroy, side="right")
        self._paint()

    # ── state ─────────────────────────────────────────────────
    def _paint(self):
        st = Q.status(self.user_id)
        if not Q.ready():
            self.status_var.set("Run the database update first (Tools ▸ Database update).")
        elif not st:
            self.status_var.set("No QR yet.")
        else:
            bits = ["✅ Working" if st["working"] else ("⌛ Expired" if st["expired"] else "⛔ Turned off")]
            if st.get("expires_at"):
                bits.append("until %s" % str(st["expires_at"])[:10])
            bits.append("used %d time(s)%s" % (st.get("use_count") or 0,
                                               (", last %s" % str(st["last_used"])[:16]) if st.get("last_used") else ""))
            if st.get("sent_to"):
                bits.append("sent to %s on %s" % (st["sent_to"], str(st.get("sent_at") or "")[:10]))
            self.status_var.set(" · ".join(bits))
        try:
            from modules import mobile_api as M
            mods = M.access(self.user_id)["modules"]
        except Exception:
            mods = []
        if mods:
            self.mods_var.set("Phone modules: " + ", ".join(mods))
            self.mods_btn.pack_forget()
        else:
            self.mods_var.set("This user has no phone modules yet — the QR works only at the desktop until "
                              "modules are given (Mobile ▸ Users).")
            self.mods_btn.pack(anchor="w")

    def _allowed(self):
        return perm.allowed("users", "edit", parent=self.win)

    def _save_phone(self):
        ph = self.phone_var.get().strip()
        if ph and ph != (self.user.get("phone") or ""):
            try:
                db.execute("UPDATE users SET phone=? WHERE user_id=?", (ph[:20], self.user_id))
                self.user["phone"] = ph
            except Exception:
                pass
        return ph

    def _show(self):
        path = os.path.join(tempfile.gettempdir(), "daybill_qr_%d.png" % self.user_id)
        Q.png(Q.payload(self.key), path, box=6)
        try:
            self._img = tk.PhotoImage(file=path)
            self.qr_lbl.config(image=self._img, text="")
        except Exception:
            self.qr_lbl.config(text=Q.payload(self.key))

    # ── actions ───────────────────────────────────────────────
    def _make(self, quiet=False):
        if not self._allowed():
            return None
        if Q.status(self.user_id) and not quiet and not messagebox.askyesno(
                "QR sign-in", "Make a new QR? The old one stops working at once.", parent=self.win):
            return None
        days = dict(VALID).get(self.valid_var.get())
        try:
            self.key = Q.make(self.user_id, days, self.mob_var.get(), self.desk_var.get())
        except Q.QrError as e:
            messagebox.showwarning("QR sign-in", str(e), parent=self.win)
            return None
        self._show()
        self._paint()
        self.msg_var.set("✅ New QR made — send it on WhatsApp or print the staff card now "
                         "(it can't be shown again later; make a new one if needed).")
        if self.on_change:
            self.on_change()
        return self.key

    def _need_key(self):
        if self.key:
            return self.key
        if not messagebox.askyesno("QR sign-in", "A new QR will be made for this (the old one stops working). "
                                   "Go on?", parent=self.win):
            return None
        return self._make(quiet=True)

    def _send(self):
        if not self._allowed():
            return
        ph = self._save_phone()
        if not ph:
            messagebox.showwarning("WhatsApp", "Type the mobile number first.", parent=self.win)
            return
        key = self._need_key()
        if not key:
            return
        ok, how = Q.send_whatsapp(self.user_id, key, ph)
        self.msg_var.set(("✅ " if ok else "❌ ") + how)
        self._paint()

    def _card(self):
        if not self._allowed():
            return
        key = self._need_key()
        if not key:
            return
        try:
            path = Q.card_pdf(self.user_id, key)
        except Exception as e:
            messagebox.showerror("Staff card", str(e)[:300], parent=self.win)
            return None
        self.msg_var.set("✅ Staff card: %s" % path)
        try:
            from modules import printer_service as ps
            ps.open_file(path)
        except Exception:
            pass
        return path

    def _copy(self):
        key = self._need_key()
        if not key:
            return
        self.win.clipboard_clear()
        self.win.clipboard_append(Q.payload(key))
        self.msg_var.set("📋 Link copied: %s" % Q.payload(key))

    def _off(self):
        if not self._allowed():
            return
        if messagebox.askyesno("QR sign-in", "Turn off this user's QR sign-in?", parent=self.win):
            Q.revoke(self.user_id)
            self.key = None
            self._img = None
            self.qr_lbl.config(image="", text="QR turned off")
            self._paint()
            self.msg_var.set("⛔ QR sign-in turned off.")
            if self.on_change:
                self.on_change()

    def _give_modules(self):
        if not perm.allowed("users", "edit", parent=self.win):
            return
        from modules import mobile_api as M
        M.set_access(self.user_id, BASIC_MODULES, True)
        self._paint()


def qr_for_all(parent, user_ids, days=None):
    """Make a QR for every given active user and save their staff cards in
    one folder (WhatsApp API: sent to everyone with a mobile number)."""
    from modules import whatsapp as W
    made, sent, cards = 0, 0, []
    for uid in user_ids:
        try:
            key = Q.make(uid, days)
        except Q.QrError:
            continue
        made += 1
        try:
            cards.append(Q.card_pdf(uid, key))
        except Exception:
            pass
        if W.api_ready() and Q.phone_of(uid):
            ok, _how = Q.send_whatsapp(uid, key)
            sent += 1 if ok else 0
    return made, sent, cards
