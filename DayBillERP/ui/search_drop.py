# ============================================================
# DayBill ERP - type-to-search dropdown for any box (v7.0)
# ------------------------------------------------------------
# Type in a box → the matching choices drop down under it at once.
# ↓ / ↑ move, Enter or a click picks, Esc closes. ↓ in an empty box (or
# the ▾ of a combobox) shows everything. Works on tk.Entry and
# ttk.Combobox (a read-only combobox becomes typeable).
#
#   attach(widget, var, source, on_pick=None, tree=False, rows=12,
#          width=None, pick_groups=True)
#
#   source   list, or a function giving the list (read again each time),
#            of strings or dicts:
#              {"label": shown text, "value": text put in the box,
#               "search": more words to match (code, barcode …),
#               "depth": 0,1,2 … (tree), "group": True for a heading,
#               "path": "Assets › Current Assets" (shown when searching)}
#   tree     show the list as a tree (indented, headings bold); a
#            search shows the matching ledgers with their group path
#   on_pick  called with the picked item (dict) after the box is filled
#
# Matching: every word typed must be found (any order, any case) in the
# label, value, search words or path.
# ============================================================

import tkinter as tk
from tkinter import ttk

NAV_KEYS = {"Up", "Down", "Return", "KP_Enter", "Escape", "Tab", "ISO_Left_Tab", "Left", "Right",
            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Home", "End"}


def _norm(item):
    if isinstance(item, dict):
        d = dict(item)
        d.setdefault("label", str(d.get("value", "")))
        d.setdefault("value", d["label"])
        return d
    s = str(item)
    return {"label": s, "value": s}


def matches(items, query):
    words = [w for w in str(query or "").lower().split() if w]
    if not words:
        return list(items)
    out = []
    for it in items:
        hay = " ".join(str(it.get(k) or "") for k in ("label", "value", "search", "path")).lower()
        if all(w in hay for w in words):
            out.append(it)
    return out


class SearchDrop:
    def __init__(self, widget, var, source, on_pick=None, tree=False, rows=12, width=None,
                 pick_groups=True):
        self.w, self.var, self.source = widget, var, source
        self.on_pick, self.tree_mode, self.rows = on_pick, tree, rows
        self.width, self.pick_groups = width, pick_groups
        self.panel = None
        self.tv = None
        self._items = []
        self._shown = []
        self._busy = False
        if isinstance(widget, ttk.Combobox):
            try:
                if str(widget.cget("state")) == "readonly":
                    widget.configure(state="normal")
                widget.configure(postcommand=lambda: None)
            except tk.TclError:
                pass
            widget.bind("<Button-1>", self._on_click_combo, add="+")
        widget.bind("<KeyRelease>", self._on_key, add="+")
        widget.bind("<Down>", self._on_down, add="+")
        widget.bind("<Up>", self._on_up, add="+")
        widget.bind("<Return>", self._on_return, add="+")
        widget.bind("<KP_Enter>", self._on_return, add="+")
        widget.bind("<Escape>", self._on_escape, add="+")
        widget.bind("<FocusOut>", lambda e: widget.after(180, self._maybe_close), add="+")
        widget.bind("<Destroy>", lambda e: self.close(), add="+")
        widget._search_drop = self

    # ── data ──────────────────────────────────────────────────
    def _load(self):
        try:
            src = self.source() if callable(self.source) else self.source
        except Exception:
            src = []
        self._items = [_norm(x) for x in (src or [])]
        return self._items

    # ── events ────────────────────────────────────────────────
    def _on_key(self, e):
        if e.keysym in NAV_KEYS or self._busy:
            return
        q = self.var.get()
        if not q.strip():
            self.close()
            return
        self.open(q)

    def _on_down(self, e):
        if self.panel is None:
            self.open(self.var.get() if self._typed() else "")
            return "break"
        self._move(1)
        return "break"

    def _on_up(self, e):
        if self.panel is not None:
            self._move(-1)
            return "break"

    def _on_return(self, e):
        if self.panel is not None:
            self._pick_current()
            return "break"

    def _on_escape(self, e):
        if self.panel is not None:
            self.close()
            return "break"

    def _on_click_combo(self, e):
        # the ▾ part of a combobox: our list (the whole list, as a tree)
        try:
            if e.x >= self.w.winfo_width() - 22:
                self.w.after(1, lambda: self.open(""))
                return "break"
        except Exception:
            pass

    def _typed(self):
        """True when the box text is a search, not a choice already made."""
        t = self.var.get().strip()
        return bool(t) and not any(t == it["value"] for it in self._items)

    # ── panel ─────────────────────────────────────────────────
    def open(self, query=""):
        items = self._load()
        found = matches(items, query)
        searching = bool(str(query).strip())
        if self.tree_mode and searching:
            found = [it for it in found if self.pick_groups or not it.get("group")]
        if not found:
            self._show([{"label": "  No match for “%s”" % query.strip(), "value": None, "_none": True}])
            return
        self._show(found, flat=searching)

    def _show(self, items, flat=True):
        if self.panel is None:
            self.panel = p = tk.Toplevel(self.w)
            p.overrideredirect(True)
            try:
                p.attributes("-topmost", True)
            except tk.TclError:
                pass
            st = ttk.Style()
            try:
                st.configure("Drop.Treeview", rowheight=24, font=("Segoe UI", 10))
            except tk.TclError:
                pass
            self.tv = tv = ttk.Treeview(p, show="tree", selectmode="browse", style="Drop.Treeview")
            tv.tag_configure("grp", font=("Segoe UI", 10, "bold"))
            tv.tag_configure("none", foreground="#888888")
            vs = ttk.Scrollbar(p, orient="vertical", command=tv.yview)
            tv.configure(yscrollcommand=vs.set)
            vs.pack(side="right", fill="y")
            tv.pack(fill="both", expand=True)
            tv.bind("<ButtonRelease-1>", lambda e: self._pick_current())
            tv.bind("<Return>", lambda e: self._pick_current())
            tv.bind("<Escape>", lambda e: (self.close(), self.w.focus_set()))
            tv.bind("<FocusOut>", lambda e: self.w.after(180, self._maybe_close))
        tv = self.tv
        tv.delete(*tv.get_children())
        self._shown = []
        for i, it in enumerate(items[:500]):
            depth = 0 if flat else int(it.get("depth") or 0)
            text = it["label"]
            if flat and it.get("path"):
                text = "%s    · %s" % (it["label"], it["path"])
            tags = ("grp",) if it.get("group") else (("none",) if it.get("_none") else ())
            tv.insert("", "end", iid=str(i), text=("      " * depth) + text, tags=tags)
            self._shown.append(it)
        n = min(len(self._shown), self.rows)
        tv.configure(height=max(1, n))
        self._place()
        first = next((i for i, it in enumerate(self._shown)
                      if not it.get("_none") and (self.pick_groups or not it.get("group"))), None)
        if first is not None:
            tv.selection_set(str(first))
            tv.see(str(first))

    def _place(self):
        try:
            self.w.update_idletasks()
            x, y = self.w.winfo_rootx(), self.w.winfo_rooty() + self.w.winfo_height()
            w = max(self.width or 0, self.w.winfo_width(), 280)
            h = min(len(self._shown), self.rows) * 24 + 6
            sh = self.w.winfo_screenheight()
            if y + h > sh - 40:                 # no room below: open above the box
                y = max(0, self.w.winfo_rooty() - h)
            self.panel.geometry("%dx%d+%d+%d" % (w, h, x, y))
            self.panel.deiconify()
            self.panel.lift()
        except tk.TclError:
            pass

    def _move(self, step):
        tv = self.tv
        if tv is None or not self._shown:
            return
        sel = tv.selection()
        i = int(sel[0]) if sel else -1
        n = len(self._shown)
        for _ in range(n):
            i = (i + step) % n
            it = self._shown[i]
            if not it.get("_none") and (self.pick_groups or not it.get("group")):
                break
        tv.selection_set(str(i))
        tv.see(str(i))

    def _pick_current(self):
        tv = self.tv
        if tv is None:
            return
        sel = tv.selection()
        if not sel:
            return
        it = self._shown[int(sel[0])]
        if it.get("_none") or (it.get("group") and not self.pick_groups):
            return
        self._busy = True
        try:
            self.var.set(it["value"])
            try:
                self.w.icursor("end")
            except Exception:
                pass
        finally:
            self._busy = False
        self.close()
        try:
            self.w.focus_set()
        except tk.TclError:
            pass
        if self.on_pick:
            try:
                self.on_pick(it)
            except Exception:
                import traceback
                traceback.print_exc()

    def _maybe_close(self):
        try:
            f = self.w.focus_get()
        except (tk.TclError, KeyError):
            f = None
        if f is not None and (f is self.w or f is self.tv):
            return
        self.close()

    def close(self):
        if self.panel is not None:
            try:
                self.panel.destroy()
            except tk.TclError:
                pass
        self.panel = None
        self.tv = None

    def is_open(self):
        return self.panel is not None


def attach(widget, var, source, on_pick=None, tree=False, rows=12, width=None, pick_groups=True):
    return SearchDrop(widget, var, source, on_pick=on_pick, tree=tree, rows=rows, width=width,
                      pick_groups=pick_groups)


# ── ready-made sources ────────────────────────────────────────
def products_source(db, with_barcodes=True):
    """Products: 'CODE — Name' (barcode / system barcode searchable)."""
    def load():
        try:
            from modules.barcode_gen import sys_select
            rows = db.fetchall("SELECT p.product_code, p.product_name_en, ISNULL(p.barcode,'') AS barcode, "
                               + sys_select("p") + " FROM products p WHERE ISNULL(p.is_active,1)=1 "
                               "ORDER BY p.product_name_en") or []
        except Exception:
            rows = []
        return [{"label": "%s — %s" % (r["product_code"], r["product_name_en"]),
                 "value": str(r["product_code"] or r["product_name_en"]),
                 "search": "%s %s" % (r.get("barcode") or "", r.get("system_barcode") or "")}
                for r in rows]
    return load


def parties_source(db, kinds=("customer", "supplier")):
    """Customers / suppliers by name (code and phone searchable)."""
    def load():
        out = []
        for k in kinds:
            t = "customers" if k == "customer" else "suppliers"
            try:
                rows = db.fetchall("SELECT %s_code AS code, %s_name_en AS name, ISNULL(phone,'') AS phone "
                                   "FROM %s WHERE ISNULL(is_active,1)=1 ORDER BY %s_name_en" % (k, k, t, k)) or []
            except Exception:
                rows = []
            tag = "" if len(kinds) == 1 else ("  (customer)" if k == "customer" else "  (supplier)")
            out += [{"label": "%s%s" % (r["name"], tag), "value": r["name"],
                     "search": "%s %s" % (r["code"] or "", r["phone"] or "")} for r in rows]
        return out
    return load
