# ============================================================
# DayBill ERP - Calculator (Windows menu)
# ============================================================

import tkinter as tk
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg


class Calculator(tk.Toplevel):
    def __init__(self, parent):
        C = cfg.theme()
        super().__init__(parent)
        self.title("Calculator")
        self.configure(bg=C["card_bg"])
        self.resizable(False, False)
        try:
            self.transient(parent)
        except Exception:
            pass
        self.expr = ""
        self.var = tk.StringVar(value="0")

        disp = tk.Label(self, textvariable=self.var, font=("Consolas", 22, "bold"),
                        bg="white", fg=C["text_primary"], anchor="e",
                        relief="solid", bd=1, padx=10)
        disp.pack(fill="x", padx=10, pady=(12, 6), ipady=10)

        grid = tk.Frame(self, bg=C["card_bg"]); grid.pack(padx=10, pady=(0, 12))
        layout = [
            ["C", "(", ")", "÷"],
            ["7", "8", "9", "×"],
            ["4", "5", "6", "−"],
            ["1", "2", "3", "+"],
            ["±", "0", ".", "="],
        ]
        for r, row in enumerate(layout):
            for cc, key in enumerate(row):
                op = key in "C÷×−+=±()"
                bg = (C["accent"] if key == "=" else
                      C["primary"] if op else "#F2F1FB")
                fg = "white" if (op or key == "=") else C["text_primary"]
                b = tk.Button(grid, text=key, font=("Segoe UI", 14, "bold"),
                              width=4, height=2, bg=bg, fg=fg, relief="flat",
                              cursor="hand2", command=lambda k=key: self._press(k))
                b.grid(row=r, column=cc, padx=3, pady=3)

        for seq in ("0123456789.+-*/()"):
            self.bind(seq, lambda e, k=seq: self._press(k))
        self.bind("<Return>", lambda e: self._press("="))
        self.bind("<BackSpace>", lambda e: self._backspace())
        self.bind("<Escape>", lambda e: self._press("C"))

    def _press(self, key):
        if key == "C":
            self.expr = ""; self.var.set("0"); return
        if key == "=":
            self._equals(); return
        if key == "±":
            try:
                self.expr = str(-float(self.expr or 0))
            except Exception:
                pass
            self.var.set(self.expr or "0"); return
        sym = {"÷": "/", "×": "*", "−": "-"}.get(key, key)
        self.expr += sym
        self.var.set(self.expr)

    def _backspace(self):
        self.expr = self.expr[:-1]
        self.var.set(self.expr or "0")

    def _equals(self):
        try:
            # safe arithmetic only
            if re_ok(self.expr):
                val = eval(self.expr, {"__builtins__": {}}, {})
                val = round(val, 6)
                if val == int(val):
                    val = int(val)
                self.expr = str(val)
                self.var.set(self.expr)
            else:
                self.var.set("Error")
                self.expr = ""
        except Exception:
            self.var.set("Error")
            self.expr = ""


def re_ok(s):
    import re
    return bool(s) and re.fullmatch(r"[0-9+\-*/(). ]+", s) is not None
