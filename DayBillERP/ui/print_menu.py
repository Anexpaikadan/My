# ============================================================
# DayBill ERP - Print menu used by every document screen
# ------------------------------------------------------------
#   🖨 Print (default)        default layout → printer
#   🖨 Dot-matrix             text → impact printer
#   📄 PDF                    open / save the A4 PDF
#   🖨 Print design 2 / 3     the document's other designs (Invoice
#                             Designer ▸ Set as Design 2 / 3), if any
#   ─────
#   🖨 Print to… (choose printer)
#   ↺ Print previous <doc>    the last saved one of this kind
# The printer box appears only when Settings ▸ Printing ▸ "Print on
# the default printer without asking" is off (or for Print to…).
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg

SYSTEM_DEFAULT = "(Windows default printer)"

OPTION_LABELS = {
    "default":   "🖨  Print  (default layout)",
    "dotmatrix": "🖨  Dot-matrix",
    "pdf":       "📄  PDF  (open / save)",
}


def ask_printer(parent, label, printer=None, copies=1, dotmatrix=False, map_key=None):
    """Small modal box: printer + copies. Returns (printer, copies) or None."""
    C = cfg.theme()
    res = {}
    top = tk.Toplevel(parent)
    top.title("Print")
    top.configure(bg=C["card_bg"])
    try:
        top.transient(parent.winfo_toplevel())
    except Exception:
        pass
    top.resizable(False, False)
    tk.Label(top, text="🖨  " + label, font=("Segoe UI", 12, "bold"),
             bg=C["primary"], fg="white", anchor="w", padx=14, pady=8).pack(fill="x")
    body = tk.Frame(top, bg=C["card_bg"]); body.pack(fill="both", padx=16, pady=12)
    try:
        from modules import printer_service as ps
        names = ps.list_printers() or []
    except Exception:
        names = []
    tk.Label(body, text="Printer", font=("Segoe UI", 9), bg=C["card_bg"],
             fg=C["text_secondary"]).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
    pv = tk.StringVar(value=printer if printer in names else SYSTEM_DEFAULT)
    cb = ttk.Combobox(body, textvariable=pv, values=[SYSTEM_DEFAULT] + names,
                      state="readonly", width=36)
    cb.grid(row=0, column=1, sticky="ew", pady=4)
    tk.Label(body, text="Copies", font=("Segoe UI", 9), bg=C["card_bg"],
             fg=C["text_secondary"]).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
    cv = tk.StringVar(value=str(copies or 1))
    tk.Spinbox(body, from_=1, to=20, textvariable=cv, width=5,
               font=("Segoe UI", 10)).grid(row=1, column=1, sticky="w", pady=4)
    remember = tk.BooleanVar(value=False)
    tk.Checkbutton(body, text="Remember this printer for this document",
                   variable=remember, bg=C["card_bg"], activebackground=C["card_bg"],
                   font=("Segoe UI", 9)).grid(row=2, column=0, columnspan=2, sticky="w",
                                              pady=(6, 0))
    direct = tk.BooleanVar(value=False)
    tk.Checkbutton(body, text="Next time print on the default printer without asking",
                   variable=direct, bg=C["card_bg"], activebackground=C["card_bg"],
                   font=("Segoe UI", 9)).grid(row=3, column=0, columnspan=2, sticky="w")
    bar = tk.Frame(top, bg=C["card_bg"]); bar.pack(fill="x", padx=16, pady=(0, 12))

    def ok(_e=None):
        p = pv.get()
        p = None if p in ("", SYSTEM_DEFAULT) else p
        try:
            n = max(1, min(20, int(float(cv.get() or 1))))
        except ValueError:
            n = 1
        if remember.get() and p:
            key = "dotmatrix" if dotmatrix else map_key
            if key:
                m = dict(cfg.get("doc_printers", {}) or {})
                m[key] = p
                cfg.set("doc_printers", m)
        if direct.get():
            cfg.set("print_direct", True)
        if remember.get() or direct.get():
            try:
                cfg.save_settings()
            except Exception:
                pass
        res["v"] = (p, n)
        top.destroy()
    tk.Button(bar, text="Cancel", font=("Segoe UI", 10), relief="flat", padx=14, pady=6,
              bg=C["content_bg"], command=top.destroy).pack(side="left")
    tk.Button(bar, text="🖨  Print", font=("Segoe UI", 10, "bold"), relief="flat",
              padx=18, pady=6, bg=C["primary"], fg="white", command=ok).pack(side="right")
    top.bind("<Return>", ok)
    top.bind("<Escape>", lambda e: top.destroy())
    ask_printer.last = top
    try:
        top.grab_set()
    except Exception:
        pass
    cb.focus_set()
    top.wait_window()
    return res.get("v")


def run(parent, kind, doc_id, option="default", ask=None, status=None):
    """Print one document and tell the user what happened."""
    from modules import permissions as perm
    from modules import doc_print as DP
    if not doc_id:
        messagebox.showinfo("Print", "Select or save the document first.", parent=parent)
        return False
    if not perm.allowed(DP.KINDS[kind]["perm"], "print", parent=parent):
        return False
    try:
        ok, msg = DP.print_document(kind, doc_id, option, ask=ask, parent=parent)
    except ImportError as e:
        ok, msg = False, f"A print library is missing: {e}. Run install_requirements.py."
    except Exception as e:
        ok, msg = False, f"Print error: {str(e)[:200]}"
    if status is not None:
        try:
            status.set(msg.splitlines()[0] if ok else msg[:160])
        except Exception:
            pass
    if not ok and "cancelled" not in msg:
        messagebox.showwarning("Print", msg, parent=parent)
    if getattr(DP, "last_template_error", ""):
        messagebox.showwarning(
            "Your template",
            "Your own template could not be used, so the standard layout was "
            "printed.\n\n%s\n\nInvoice Designer ▸ Preview shows the problem."
            % DP.last_template_error, parent=parent)
        DP.last_template_error = ""
    elif ok and not getattr(DP, "last_qr_note", ""):
        try:
            from ui.ui_polish import toast
            toast(parent.winfo_toplevel(), msg.splitlines()[0], kind="success")
        except Exception:
            pass
    note = getattr(DP, "last_qr_note", "") if ok else ""
    if note:
        _tell_no_qr(parent, note, status)
    return ok


_QR_TOLD = set()     # each reason is explained once per run of the app


def _tell_no_qr(parent, note, status=None):
    """The invoice went out WITHOUT its ZATCA QR code — say why (once)."""
    if status is not None:
        try:
            status.set("⚠ No QR code: " + note.splitlines()[0][:140])
        except Exception:
            pass
    if note in _QR_TOLD:
        return
    _QR_TOLD.add(note)
    messagebox.showwarning(
        "No QR code",
        "This invoice was printed WITHOUT the ZATCA QR code.\n\n" + note,
        parent=parent)


def show_menu(parent, kind, get_id, widget=None, before=None, status=None, previous=True):
    """Pop the print menu. get_id() returns the document id (None if not
    saved). before() runs first (e.g. save the form) and returns False
    to stop."""
    from modules import doc_print as DP
    label = DP.KINDS[kind]["label"]
    menu = tk.Menu(parent, tearoff=0, font=("Segoe UI", 10))

    def go(option, ask=None, prev=False):
        if prev:
            doc_id = DP.last_id(kind)
            if not doc_id:
                messagebox.showinfo("Print", f"No saved {label.lower()} yet.", parent=parent)
                return
        else:
            if before is not None and before() is False:
                return
            doc_id = get_id()
        run(parent, kind, doc_id, option, ask=ask, status=status)

    for opt in DP.OPTIONS:
        menu.add_command(label=OPTION_LABELS[opt], command=lambda o=opt: go(o))
    for slot in DP.design_slots(kind):
        menu.add_command(label=f"🖨  Print design {slot}", command=lambda o=f"design{slot}": go(o))
    menu.add_separator()
    menu.add_command(label="🖨  Print to…  (choose printer)", command=lambda: go("default", ask=True))
    if previous:
        menu.add_command(label=f"↺  Print previous {label.lower()}",
                         command=lambda: go("default", prev=True))
    try:
        if widget is not None:
            x, y = widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height()
        else:
            x, y = parent.winfo_pointerx(), parent.winfo_pointery()
        menu.tk_popup(x, y)
    finally:
        try:
            menu.grab_release()
        except Exception:
            pass
    return menu


def print_button(parent, kind, get_id, before=None, status=None, text="🖨  Print ▾",
                 **style):
    """A 'Print ▾' button that opens the menu under itself."""
    C = cfg.theme()
    opts = dict(font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white",
                relief="flat", padx=14, pady=6, cursor="hand2")
    opts.update(style)
    b = tk.Button(parent, text=text, **opts)
    b.configure(command=lambda: show_menu(parent, kind, get_id, widget=b,
                                          before=before, status=status))
    return b


def send_pdf(parent, path, label, printer_key="a4", copies=None, printer=None):
    """Print a ready PDF (reports, vouchers, labels) the same way as
    documents: straight to the printer, or ask first when Settings ▸
    Printing ▸ 'without asking' is off. Returns True when sent."""
    from modules import printer_service as ps
    printer = printer or ps.printer_for(printer_key)
    try:
        copies = max(1, int(copies or cfg.get("print_copies", 1) or 1))
    except (TypeError, ValueError):
        copies = 1
    if not ps.print_direct():
        got = ask_printer(parent, label, printer, copies, map_key=printer_key)
        if not got:
            return False
        printer, copies = got
    ok = ps.print_pdf(path, printer, copies=copies)
    if not ok:
        messagebox.showwarning("Print", f"{label} could not be printed. {ps.last_error}",
                               parent=parent)
    return ok
