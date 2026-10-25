# ============================================================
# DayBill ERP - Barcode Label Designer UI
# Tab 1: Designer (toolbox · canvas · properties)
# Tab 2: Batch Print (pick products, set copies, print/PDF)
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
import modules.barcode_designer as bd

PXMM = 3.0  # canvas pixels per mm (labels are small, so zoom up)


class BarcodeDesignerView:
    def __init__(self, parent, start="design"):
        self.start = start
        self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=self.C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.template = None
        self.elements = []
        self.sel_id = None
        self._drag = None

        if not bd.tables_ready():
            tk.Label(self.frame,
                     text="🏷  Barcode Designer needs its tables.\n\n"
                          "Updates → Apply All Updates (or run\n"
                          "database/barcode_designer_patch.sql), then reopen.",
                     font=("Segoe UI", 12), bg=self.C["content_bg"],
                     fg=self.C["text_primary"], justify="center").pack(expand=True)
            return
        self._build()

    def _build(self):
        C = self.C
        nb = ttk.Notebook(self.frame)
        nb.pack(fill="both", expand=True)
        self.nb = nb
        self.tab_design = tk.Frame(nb, bg=C["content_bg"])
        self.tab_batch = tk.Frame(nb, bg=C["content_bg"])
        nb.add(self.tab_batch, text="  🖨  Print Labels  ")
        nb.add(self.tab_design, text="  🎨  Label Designer  ")
        self._build_designer(self.tab_design)
        self._build_batch(self.tab_batch)
        self._load_templates()
        nb.select(self.tab_batch if self.start == "print" else self.tab_design)

    # ── Designer tab ──────────────────────────────────────────
    def _build_designer(self, root):
        C = self.C
        bar = tk.Frame(root, bg=C["card_bg"], height=46)
        bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Frame(root, bg=C["border"], height=1).pack(fill="x")
        tk.Label(bar, text="🏷", font=("Segoe UI Emoji", 13), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left", padx=(14, 4))
        tk.Label(bar, text="Barcode Label Designer",
                 font=("Segoe UI", 12, "bold"), bg=C["card_bg"],
                 fg=C["text_primary"]).pack(side="left", padx=(0, 12))
        for i, (txt, cmd) in enumerate((("💾 Save", self._save), ("👁 Preview", self._preview),
                                        ("📄 PDF", self._export_pdf),
                                        ("🖨 Test Print", self._test_print))):
            prim = (i == 0)
            tk.Button(bar, text=txt, font=("Segoe UI", 9, "bold" if prim else "normal"),
                      bg=C["primary"] if prim else C["card_bg"],
                      fg="white" if prim else C["text_primary"],
                      activebackground=C["primary_dark"] if prim else C["content_bg"],
                      relief="flat", bd=0, padx=10, pady=5, cursor="hand2",
                      highlightthickness=0 if prim else 1,
                      highlightbackground=C.get("field_border", C["border"]),
                      command=cmd).pack(side="left", padx=3, pady=8)

        strip = tk.Frame(root, bg=C["card_bg"], height=42)
        strip.pack(fill="x"); strip.pack_propagate(False)
        tk.Frame(root, bg=C["border"], height=1).pack(fill="x")
        tk.Label(strip, text="Template:", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left", padx=(12, 4))
        self.tpl_var = tk.StringVar()
        self.tpl_cb = ttk.Combobox(strip, textvariable=self.tpl_var, state="readonly",
                                   font=("Segoe UI", 9), width=28)
        self.tpl_cb.pack(side="left", pady=7)
        self.tpl_cb.bind("<<ComboboxSelected>>", lambda e: self._on_pick())
        for txt, cmd in (("＋ New", self._new), ("⧉ Clone", self._clone),
                         ("★ Default", self._set_default), ("🗑 Delete", self._delete)):
            tk.Button(strip, text=txt, font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", padx=9, pady=4,
                      cursor="hand2", highlightbackground=C["border"],
                      highlightthickness=1, command=cmd).pack(side="left", padx=2)

        body = tk.Frame(root, bg=C["content_bg"])
        body.pack(fill="both", expand=True)

        # left toolbox
        left_outer = tk.Frame(body, bg=C["card_bg"], width=200)
        left_outer.pack(side="left", fill="y"); left_outer.pack_propagate(False)
        tk.Label(left_outer, text="🧰 Fields  (click to add)", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", padx=10, pady=6)
        from ui.widgets import ScrollableFrame
        _sf = ScrollableFrame(left_outer)
        _sf.pack(fill="both", expand=True)
        _sf.inner.configure(bg=C["card_bg"]); _sf.canvas.configure(bg=C["card_bg"])
        left = _sf.inner
        for group, items in bd.TOOLBOX.items():
            tk.Label(left, text=group.upper(), font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 1))
            for key, label in items:
                b = tk.Label(left, text="  ⠿ " + label, font=("Segoe UI", 9),
                             bg=C["primary_light"], fg=C["primary"], anchor="w",
                             padx=6, pady=3, cursor="hand2")
                b.pack(fill="x", padx=6, pady=1)
                b.bind("<Button-1>", lambda e, k=key, l=label: self._add_el(k, l))

        # center canvas
        center = tk.Frame(body, bg="#E4E7EE")
        center.pack(side="left", fill="both", expand=True)
        tk.Label(center, text="Click a field to drop · drag to move · Delete removes",
                 font=("Segoe UI", 8), bg="#E4E7EE", fg=C["text_secondary"]).pack(
                     anchor="w", padx=8, pady=3)
        self.canvas = tk.Canvas(center, bg="#E4E7EE", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))
        self.frame.winfo_toplevel().bind("<Delete>", self._del_key, add="+")

        # right properties
        right = tk.Frame(body, bg=C["card_bg"], width=250)
        right.pack(side="right", fill="y"); right.pack_propagate(False)
        tk.Label(right, text="⚙ Properties", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", padx=10, pady=6)
        # scrolls, so nothing is cut off on a small screen
        pwrap = tk.Frame(right, bg=C["card_bg"]); pwrap.pack(fill="both", expand=True)
        pcv = tk.Canvas(pwrap, bg=C["card_bg"], highlightthickness=0, bd=0)
        psb = ttk.Scrollbar(pwrap, orient="vertical", command=pcv.yview)
        pcv.configure(yscrollcommand=psb.set)
        psb.pack(side="right", fill="y")
        pcv.pack(side="left", fill="both", expand=True)
        self.props = tk.Frame(pcv, bg=C["card_bg"])
        _pw = pcv.create_window((10, 0), window=self.props, anchor="nw")
        pcv.bind("<Configure>", lambda e: pcv.itemconfig(_pw, width=max(80, e.width - 18)))
        self.props.bind("<Configure>",
                        lambda e: pcv.configure(scrollregion=(0, 0, pcv.winfo_width(),
                                                              self.props.winfo_reqheight() + 16)))

    def _tpl_props(self):
        for w in self.props.winfo_children():
            w.destroy()
        C = self.C
        if not self.template:
            tk.Label(self.props, text="Pick or create a template.",
                     font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", pady=8)
            return

        def lbl(t):
            tk.Label(self.props, text=t, font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(8, 1))

        self.p_type = tk.StringVar(value=self.template.get("barcode_type", "code128"))
        self.p_w = tk.StringVar(value=str(self.template.get("label_width_mm", 50)))
        self.p_h = tk.StringVar(value=str(self.template.get("label_height_mm", 25)))
        self.p_mode = tk.StringVar(value=self.template.get("paper_mode", "thermal"))

        lbl("Barcode Type")
        cb = ttk.Combobox(self.props, textvariable=self.p_type, state="readonly",
                          values=[f[0] for f in __import__("modules.barcode_gen",
                                  fromlist=["SUPPORTED_FORMATS"]).SUPPORTED_FORMATS],
                          font=("Segoe UI", 9))
        cb.pack(fill="x"); cb.bind("<<ComboboxSelected>>", lambda e: self._redraw())
        lbl("Label Width (mm)")
        e1 = tk.Entry(self.props, textvariable=self.p_w, font=("Segoe UI", 9),
                      relief="solid", bd=1); e1.pack(fill="x", ipady=3)
        e1.bind("<KeyRelease>", lambda e: self._redraw())
        lbl("Label Height (mm)")
        e2 = tk.Entry(self.props, textvariable=self.p_h, font=("Segoe UI", 9),
                      relief="solid", bd=1); e2.pack(fill="x", ipady=3)
        e2.bind("<KeyRelease>", lambda e: self._redraw())
        lbl("Paper")
        cb2 = ttk.Combobox(self.props, textvariable=self.p_mode, state="readonly",
                           values=["thermal", "a4sheet"], font=("Segoe UI", 9))
        cb2.pack(fill="x")
        tk.Label(self.props, text="thermal = roll · a4sheet = sticker sheet",
                 font=("Segoe UI", 7), bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w")
        self.sheet_box = tk.Frame(self.props, bg=C["card_bg"])
        self.p_sheet = {}
        for i, (key, label, dflt) in enumerate((("cols_per_sheet", "Columns", 3),
                                                ("rows_per_sheet", "Rows", 8),
                                                ("margin_mm", "Margin mm", 5),
                                                ("gap_x_mm", "Gap X mm", 2),
                                                ("gap_y_mm", "Gap Y mm", 2))):
            v = tk.StringVar(value=str(self.template.get(key) if self.template.get(key)
                                       not in (None, "") else dflt))
            self.p_sheet[key] = v
            tk.Label(self.sheet_box, text=label, font=("Segoe UI", 8), bg=C["card_bg"],
                     fg=C["text_secondary"]).grid(row=i // 2, column=(i % 2) * 2, sticky="w")
            tk.Entry(self.sheet_box, textvariable=v, width=5, relief="solid", bd=1,
                     font=("Segoe UI", 9)).grid(row=i // 2, column=(i % 2) * 2 + 1,
                                                sticky="w", padx=(2, 8), pady=1)

        def _mode_changed(_e=None):
            if self.p_mode.get() == "a4sheet":
                self.sheet_box.pack(fill="x", pady=(4, 0), after=cb2)
            else:
                self.sheet_box.pack_forget()
        cb2.bind("<<ComboboxSelected>>", _mode_changed)
        _mode_changed()
        self.p_border = tk.BooleanVar(value=bool(self.template.get("show_border", 1)
                                                 if self.template.get("show_border") is not None else 1))
        tk.Checkbutton(self.props, text="Border around each label",
                       variable=self.p_border, bg=C["card_bg"], activebackground=C["card_bg"],
                       font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))

        # quick size presets
        lbl("Quick Sizes")
        presets = tk.Frame(self.props, bg=C["card_bg"]); presets.pack(fill="x")
        for i, (label, w, h) in enumerate((("50×25", 50, 25), ("40×25", 40, 25),
                                           ("30×20", 30, 20), ("60×40", 60, 40),
                                           ("75×50", 75, 50), ("100×50", 100, 50))):
            tk.Button(presets, text=label, font=("Segoe UI", 8), bg=C["primary_light"],
                      fg=C["primary"], relief="flat", padx=6, pady=3, cursor="hand2",
                      command=lambda w=w, h=h: self._set_size(w, h)).grid(
                      row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")
        for c_ in range(3):
            presets.columnconfigure(c_, weight=1)
        tk.Button(self.props, text="✨ Ready fields: name · price · barcode",
                  font=("Segoe UI", 8, "bold"), bg=C["primary_light"], fg=C["primary"],
                  relief="flat", padx=6, pady=4, cursor="hand2",
                  command=self._ready_fields).pack(anchor="w", pady=(10, 0))

    def _el_props(self, el):
        for w in self.props.winfo_children():
            w.destroy()
        C = self.C
        tk.Label(self.props, text=f"Field: {el['label']}",
                 font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", pady=(6, 8))

        def fld(label, key):
            tk.Label(self.props, text=label, font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(6, 1))
            v = tk.StringVar(value=str(el.get(key, "")))
            e = tk.Entry(self.props, textvariable=v, font=("Segoe UI", 9),
                         relief="solid", bd=1); e.pack(fill="x", ipady=3)
            v.trace("w", lambda *a: self._set_el(el, key, v.get()))
        fld("Label / text", "label")
        fld("X (mm)", "x"); fld("Y (mm)", "y")
        fld("Width (mm)", "w")
        if el.get("key") == "barcode":
            if "bh" not in el:
                el["bh"] = 14
            fld("Barcode height (mm)", "bh")
        elif el.get("key") != "qr":
            fld("Font size", "font")
            tk.Label(self.props, text="Align", font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(6, 1))
            av = tk.StringVar(value=el.get("align") or "left")
            acb = ttk.Combobox(self.props, textvariable=av, state="readonly",
                               values=["left", "center", "right"], font=("Segoe UI", 9))
            acb.pack(fill="x")
            acb.bind("<<ComboboxSelected>>", lambda e_: self._set_el(el, "align", av.get()))
        self.elb = tk.BooleanVar(value=el.get("bold", False))
        tk.Checkbutton(self.props, text="Bold", variable=self.elb,
                       font=("Segoe UI", 9), bg=C["card_bg"], activebackground=C["card_bg"],
                       command=lambda: self._set_el(el, "bold", self.elb.get())).pack(anchor="w", pady=6)
        tk.Button(self.props, text="🗑 Delete Field", font=("Segoe UI", 9),
                  bg="#FEF2F2", fg=C["danger"], relief="flat", padx=10, pady=5,
                  cursor="hand2", command=self._del_el).pack(anchor="w", pady=10)

    def _set_el(self, el, key, val):
        if key in ("x", "y", "w", "font", "bh"):
            try: el[key] = float(val)
            except ValueError: return
        else:
            el[key] = val
        self._redraw()

    def _set_size(self, w, h):
        self.p_w.set(str(w)); self.p_h.set(str(h)); self._redraw()

    # ── Templates ─────────────────────────────────────────────
    def _load_templates(self):
        self._templates = bd.list_templates()
        self.tpl_cb["values"] = [t["template_name"] + ("  ★" if t.get("is_default") else "")
                                 for t in self._templates]
        if self._templates:
            self.tpl_cb.current(0); self._on_pick()
        # the Print Labels tab shows the same designs
        if getattr(self, "print_panel", None) is not None:
            try:
                self.print_panel.reload_designs()
            except Exception:
                pass

    def _on_pick(self):
        i = self.tpl_cb.current()
        if i < 0:
            return
        self.template = dict(self._templates[i])
        self.elements = bd.load_layout(self.template["template_id"])
        self.sel_id = None
        self._tpl_props(); self._redraw()

    SIZES = [("50 × 25 mm", 50, 25), ("40 × 25 mm", 40, 25), ("38 × 25 mm", 38, 25),
             ("30 × 20 mm", 30, 20), ("60 × 40 mm", 60, 40), ("75 × 50 mm", 75, 50),
             ("100 × 50 mm", 100, 50), ("A4 sheet 3 × 8 (70 × 37 mm)", 70, 37),
             ("A4 sheet 3 × 7 (63.5 × 38.1 mm)", 63.5, 38.1)]

    def _new(self):
        """New label template: name, size and roll/sheet, starting with name ·
        price · barcode already placed."""
        C = self.C
        top = tk.Toplevel(self.frame)
        top.title("New label template")
        top.configure(bg=C["card_bg"]); top.resizable(False, False)
        tk.Label(top, text="＋  New label template", font=("Segoe UI", 12, "bold"),
                 bg=C["primary"], fg="white", anchor="w", padx=14, pady=8).pack(fill="x")
        body = tk.Frame(top, bg=C["card_bg"]); body.pack(padx=16, pady=12)
        name_v = tk.StringVar(value="Shelf label 50x25")
        size_v = tk.StringVar(value=self.SIZES[0][0])
        ready_v = tk.BooleanVar(value=True)
        tk.Label(body, text="Name", bg=C["card_bg"]).grid(row=0, column=0, sticky="w")
        e = tk.Entry(body, textvariable=name_v, width=34, relief="solid", bd=1,
                     font=("Segoe UI", 10))
        e.grid(row=0, column=1, sticky="w", pady=4, ipady=3)
        tk.Label(body, text="Size", bg=C["card_bg"]).grid(row=1, column=0, sticky="w")
        ttk.Combobox(body, textvariable=size_v, values=[x[0] for x in self.SIZES],
                     state="readonly", width=32).grid(row=1, column=1, sticky="w", pady=4)
        tk.Checkbutton(body, text="Start with name · price · barcode placed",
                       variable=ready_v, bg=C["card_bg"], activebackground=C["card_bg"]
                       ).grid(row=2, column=0, columnspan=2, sticky="w")
        res = {}

        def ok(_e=None):
            if name_v.get().strip():
                res.update(name=name_v.get().strip(), size=size_v.get(), ready=ready_v.get())
                top.destroy()
        bar = tk.Frame(top, bg=C["card_bg"]); bar.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(bar, text="Cancel", relief="flat", padx=12, pady=5,
                  command=top.destroy).pack(side="left")
        tk.Button(bar, text="Create", font=("Segoe UI", 10, "bold"), bg=C["primary"],
                  fg="white", relief="flat", padx=16, pady=5, command=ok).pack(side="right")
        top.bind("<Return>", ok); top.bind("<Escape>", lambda _e: top.destroy())
        e.focus_set(); e.select_range(0, "end")
        try:
            top.grab_set()
        except Exception:
            pass
        self._new_dialog = top
        top.wait_window()
        if res:
            return self._create(res["name"], res["size"], res["ready"])

    def _create(self, name, size_label, ready=True):
        lbl, w, h = next((x for x in self.SIZES if x[0] == size_label), self.SIZES[0])
        sheet = "sheet" in lbl
        data = {"template_name": name, "barcode_type": "code128",
                "label_width_mm": w, "label_height_mm": h,
                "paper_mode": "a4sheet" if sheet else "thermal",
                "cols_per_sheet": 3 if sheet else 1,
                "rows_per_sheet": (8 if "3 × 8" in lbl else 7) if sheet else 1,
                "gap_x_mm": 0 if sheet else 2, "gap_y_mm": 0 if sheet else 2,
                "margin_mm": 5 if sheet else 0,
                "layout_json": json.dumps(bd.starter_label_layout(w, h) if ready else [])}
        tid = bd.create_template(data)
        self._load_templates()
        for idx, t in enumerate(self._templates):
            if t["template_id"] == tid:
                self.tpl_cb.current(idx); self._on_pick(); break
        return tid

    def _ready_fields(self):
        if not self.template:
            return
        try:
            w, h = float(self.p_w.get()), float(self.p_h.get())
        except ValueError:
            w, h = 50, 25
        self.elements = bd.starter_label_layout(w, h)
        self.sel_id = None
        self._redraw()

    def _test_print(self):
        self._to_printer = True
        try:
            self._export_pdf(preview=True)
        finally:
            self._to_printer = False

    def _clone(self):
        if self.template:
            bd.clone_template(self.template["template_id"]); self._load_templates()

    def _set_default(self):
        if self.template:
            bd.set_default(self.template["template_id"]); self._load_templates()

    def _delete(self):
        if self.template and messagebox.askyesno("Delete", "Delete this template?"):
            bd.delete_template(self.template["template_id"])
            self.template = None; self.elements = []
            self._load_templates(); self._redraw()

    def _save(self):
        if not self.template:
            messagebox.showinfo("Save", "Create a template first."); return
        def _num(v, d):
            try:
                return float(v.get() or d)
            except (ValueError, AttributeError):
                return d
        data = {"barcode_type": self.p_type.get(),
                "label_width_mm": _num(self.p_w, 50),
                "label_height_mm": _num(self.p_h, 25),
                "paper_mode": self.p_mode.get(),
                "layout_json": json.dumps(self.elements)}
        for key, v in getattr(self, "p_sheet", {}).items():
            d = {"cols_per_sheet": 3, "rows_per_sheet": 8}.get(key, 2)
            data[key] = int(_num(v, d)) if key.endswith("sheet") else _num(v, d)
        if hasattr(self, "p_border"):
            data["show_border"] = 1 if self.p_border.get() else 0
        try:
            bd.update_template(self.template["template_id"], data)
        except Exception:
            # older database without the sheet columns: save the basics
            for k_ in ("cols_per_sheet", "rows_per_sheet", "margin_mm", "gap_x_mm",
                       "gap_y_mm", "show_border"):
                data.pop(k_, None)
            bd.update_template(self.template["template_id"], data)
        self.template.update(data)
        if not getattr(self, "_quiet_save", False):
            messagebox.showinfo("Saved", "Label template saved.")
        keep = self.template["template_id"]
        self._load_templates()
        for idx, t in enumerate(self._templates):
            if t["template_id"] == keep:
                self.tpl_cb.current(idx); self._on_pick(); break

    # ── Canvas ────────────────────────────────────────────────
    def _redraw(self):
        self.canvas.delete("all")
        if not self.template:
            return
        try:
            lw = float(self.p_w.get()); lh = float(self.p_h.get())
        except ValueError:
            lw, lh = 50, 25
        pw, ph = int(lw * PXMM), int(lh * PXMM)
        ox, oy = 40, 40
        self.canvas.create_rectangle(ox, oy, ox + pw, oy + ph,
                                     fill="white", outline="#9CA3AF", width=1)
        self.canvas.create_text(ox, oy - 12, anchor="w",
                                text=f"{lw:g} × {lh:g} mm  ·  {self.p_type.get()}",
                                fill="#4B5563", font=("Segoe UI", 9, "bold"))
        for el in self.elements:
            self._draw_el(ox, oy, el)

    def _draw_el(self, ox, oy, el):
        x = ox + float(el.get("x", 2)) * PXMM
        y = oy + float(el.get("y", 2)) * PXMM
        w = float(el.get("w", 30)) * PXMM
        sel = (el["id"] == self.sel_id)
        if el["key"] in ("barcode", "qr"):
            h = float(el.get("bh", 14) or 14) * PXMM if el["key"] == "barcode" else w
            self.canvas.create_rectangle(x, y, x + w, y + h,
                                         outline=(self.C["accent"] if sel else "#888"),
                                         width=(2 if sel else 1), dash=(3, 2))
            self.canvas.create_text(x + w / 2, y + h / 2,
                                    text=("▮▮▮ BARCODE ▮▮▮" if el["key"] == "barcode"
                                          else "▣ QR"),
                                    font=("Segoe UI", 8), fill="#333")
            el["_h"] = h / PXMM
        else:
            h = 8 * PXMM
            font = ("Segoe UI", max(6, int(el.get("font", 8))),
                    "bold" if el.get("bold") else "normal")
            if sel:
                self.canvas.create_rectangle(x, y, x + w, y + h,
                                             outline=self.C["accent"], width=2)
            al = el.get("align") or "left"
            if al == "center":
                self.canvas.create_text(x + w / 2, y + h / 2, anchor="center",
                                        text=el["label"], font=font, fill="#111")
            elif al == "right":
                self.canvas.create_text(x + w - 2, y + h / 2, anchor="e",
                                        text=el["label"], font=font, fill="#111")
            else:
                self.canvas.create_text(x + 2, y + h / 2, anchor="w",
                                        text=el["label"], font=font, fill="#111")

    def _add_el(self, key, label):
        if not self.template:
            messagebox.showinfo("Template", "Create or pick a template first."); return
        eid = max([e["id"] for e in self.elements], default=0) + 1
        self.elements.append({"id": eid, "key": key, "label": label,
                              "x": 3, "y": 3 + (len(self.elements) % 6) * 5,
                              "w": 40, "h": 8, "font": 8, "bold": False})
        self.sel_id = eid
        self._redraw()

    def _click(self, event):
        ox, oy = 40, 40
        hit = None
        for el in reversed(self.elements):
            x = ox + float(el.get("x", 2)) * PXMM
            y = oy + float(el.get("y", 2)) * PXMM
            w = float(el.get("w", 30)) * PXMM
            h = float(el.get("_h", el.get("h", 8))) * PXMM
            if x <= event.x <= x + w and y <= event.y <= y + h:
                hit = el; break
        if hit:
            self.sel_id = hit["id"]; self._drag = (event.x, event.y, hit)
            self._el_props(hit)
        else:
            self.sel_id = None; self._drag = None; self._tpl_props()
        self._redraw()

    def _move(self, event):
        if not self._drag:
            return
        px, py, el = self._drag
        el["x"] = max(0, float(el.get("x", 0)) + (event.x - px) / PXMM)
        el["y"] = max(0, float(el.get("y", 0)) + (event.y - py) / PXMM)
        self._drag = (event.x, event.y, el)
        self._redraw()

    def _del_key(self, e=None):
        """Delete key: removes the selected FIELD only while the designer
        canvas is on screen and no text box has the cursor."""
        try:
            if not self.frame.winfo_exists() or self.nb.select() != str(self.tab_design):
                return
            if isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text, ttk.Treeview)):
                return
        except Exception:
            return
        self._del_el()

    def _del_el(self):
        if self.sel_id is None:
            return
        self.elements = [e for e in self.elements if e["id"] != self.sel_id]
        self.sel_id = None; self._tpl_props(); self._redraw()

    def _preview(self):
        self._export_pdf(preview=True)

    def _export_pdf(self, preview=False):
        if not self.template:
            return
        self._quiet_save = True
        try:
            self._save()
        finally:
            self._quiet_save = False
        sample = [{"product_name_en": "Sample Product 1kg", "product_name_ar": "منتج تجريبي",
                   "product_code": "PRD000001", "unit_price": 9.50, "purchase_price": 7.25,
                   "category_name": "Grocery", "brand_name": "DayBill", "stock_quantity": 24,
                   "barcode_value": "10001", "system_barcode": "10001",
                   "manual_barcode": "6281000000014", "copies": 1}]
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "daybill_label_preview.pdf")
        try:
            bd.render_labels_pdf(self.template, sample, path)
            self.last_pdf = path
            if getattr(self, "_to_printer", False):
                from ui import print_menu
                print_menu.send_pdf(self.frame, path, "Test label", "labels")
            else:
                from modules import printer_service as ps
                ps.open_file(path)
        except ImportError:
            messagebox.showerror("Missing Library", "pip install reportlab python-barcode qrcode pillow")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Print Labels tab (scan / search, units, copies, design, print) ──
    def _build_batch(self, root):
        from ui.label_printer import LabelPrintPanel
        self.print_panel = LabelPrintPanel(root, on_edit_design=self._edit_from_print)

    def _edit_from_print(self, tid):
        """✏ Edit design on the Print tab → the designer, on that design."""
        self.nb.select(self.tab_design)
        for idx, t in enumerate(getattr(self, "_templates", [])):
            if t["template_id"] == tid:
                self.tpl_cb.current(idx); self._on_pick(); break
