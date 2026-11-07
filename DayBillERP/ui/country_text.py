# ============================================================
# DayBill ERP - country words on every screen (v7.0)
# ------------------------------------------------------------
# DayBill was written for Saudi Arabia: many screens say "SAR", "VAT",
# "VAT No.". For a UAE or India company those words are changed as the
# text reaches the screen — labels, buttons, table headings, boxes that
# show a value (StringVar) and message boxes:
#
#   UAE    SAR → AED · VAT No. → TRN · 15% → 5%
#   India  SAR → ₹ (₹1,234.50) · VAT → GST · VAT No. → GSTIN ·
#          Saudi Riyals / Halalas → Rupees / Paise
#
# A Saudi company sees everything exactly as before (nothing installed).
# Bills, PDFs, WhatsApp messages and reports use modules/country.py
# directly; this is the safety net for the screens.
#
#   install()    called after the company is opened (main window)
#   fix(text)    the text with the country's words (country.localize)
# ============================================================

import tkinter as tk
from tkinter import ttk

_STATE = {"on": False, "orig": {}}

def fix(text):
    if not _STATE["on"]:
        return text
    from modules import country as C
    return C.localize(text)


def _fix_opts(d):
    if d and isinstance(d, dict) and isinstance(d.get("text"), str):
        d = dict(d)
        d["text"] = fix(d["text"])
    return d


def install():
    """Switch the screen words to the company's country (idempotent)."""
    try:
        from modules import country as C
        code = C.code()
    except Exception:
        code = "SA"
    if code == "SA":
        uninstall()
        return False
    if _STATE["on"]:
        return True
    o = _STATE["orig"]
    o["base_init"] = tk.BaseWidget.__init__
    o["configure"] = tk.Misc._configure
    o["var_set"] = tk.StringVar.set
    o["heading"] = ttk.Treeview.heading
    try:
        from tkinter import messagebox as mb
        o["mb_show"] = mb._show
    except Exception:
        mb = None

    def base_init(self, master, widgetName, cnf={}, kw={}, extra=()):
        return o["base_init"](self, master, widgetName, _fix_opts(cnf), _fix_opts(kw), extra)

    def configure(self, cmd, cnf, kw):
        return o["configure"](self, cmd, _fix_opts(cnf), _fix_opts(kw))

    def var_set(self, value):
        return o["var_set"](self, fix(value) if isinstance(value, str) else value)

    def heading(self, column, option=None, **kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = fix(kw["text"])
        return o["heading"](self, column, option, **kw)

    tk.BaseWidget.__init__ = base_init
    tk.Misc._configure = configure
    tk.StringVar.set = var_set
    ttk.Treeview.heading = heading
    if mb is not None and "mb_show" in o:
        def mb_show(title=None, message=None, _icon=None, _type=None, **options):
            return o["mb_show"](fix(title), fix(message), _icon, _type, **options)
        mb._show = mb_show
    _STATE["on"] = True
    return True


def uninstall():
    if not _STATE["on"]:
        return
    o = _STATE["orig"]
    tk.BaseWidget.__init__ = o["base_init"]
    tk.Misc._configure = o["configure"]
    tk.StringVar.set = o["var_set"]
    ttk.Treeview.heading = o["heading"]
    try:
        from tkinter import messagebox as mb
        if "mb_show" in o:
            mb._show = o["mb_show"]
    except Exception:
        pass
    _STATE["on"] = False
