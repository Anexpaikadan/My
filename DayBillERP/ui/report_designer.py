# ============================================================
# DayBill ERP - Report Designer UI
# Layout: top toolbar · left toolbox · center canvas · right properties
# Drag elements from the toolbox onto the canvas, move them, edit props.
# Template manager (save/clone/default), themes, printer & paper settings.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from config.database import db
import modules.report_designer as rd

# toolbox key -> real rendering type (was hardcoded to "text" for everything)
_TYPE_OF_KEY = {
    "company_logo": "image", "image": "image", "qr_code": "qr",
    "barcode": "barcode", "table": "table", "line": "line",
    "signature": "signature", "stamp": "stamp",
}


# Paper sizes in mm → pixels at ~3px/mm for the canvas preview
PAPER = {
    "A4":   (210, 297), "A5": (148, 210), "Letter": (216, 279),
    "80mm": (80, 200),  "58mm": (58, 200),
}
PXMM = 2.2  # canvas pixels per mm


class ReportDesignerView:
    def __init__(self, parent):
        self.C = cfg.theme()
        self.frame = tk.Frame(parent, bg=self.C["content_bg"])
        self.frame.pack(fill="both", expand=True)
        self.template = None
        self.elements = []        # canvas elements [{id,key,label,type,x,y,w,h,font,bold,align}]
        self.sel_id = None
        self._undo = []
        self._redo = []
        self._drag = None

        if not rd.tables_ready():
            self._show_setup_needed()
            return
        self._build()
        self.zoom = 1.0
        self._load_templates()

    def _show_setup_needed(self):
        tk.Label(self.frame,
                 text="🧩  Report Designer needs its database tables.\n\n"
                      "Go to Updates → Apply All Updates (or run\n"
                      "database/patches/report_designer_patch.sql in SSMS), then reopen.",
                 font=("Segoe UI", 12), bg=self.C["content_bg"],
                 fg=self.C["text_primary"], justify="center").pack(expand=True)

    # ── Layout ────────────────────────────────────────────────
    def _build(self):
        C = self.C
        # Top command bar — white, Windows 11 style (fits a 1366 px screen)
        bar = tk.Frame(self.frame, bg=C["card_bg"], height=48)
        bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill="x")
        tk.Label(bar, text="🧩", font=("Segoe UI Emoji", 13), bg=C["card_bg"],
                 fg=C["primary"]).pack(side="left", padx=(14, 4))
        tk.Label(bar, text="Invoice Designer", font=("Segoe UI", 12, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left", padx=(0, 12))

        def tbtn(txt, cmd, primary=False):
            b = tk.Button(bar, text=txt, font=("Segoe UI", 9, "bold" if primary else "normal"),
                          bg=C["primary"] if primary else C["card_bg"],
                          fg="white" if primary else C["text_primary"],
                          activebackground=C["primary_dark"] if primary else C["content_bg"],
                          relief="flat", bd=0, padx=10, pady=5, cursor="hand2",
                          highlightthickness=0 if primary else 1,
                          highlightbackground=C.get("field_border", C["border"]),
                          command=cmd)
            b.pack(side="left", padx=3, pady=9)
            return b

        tbtn("💾 Save", self._save, primary=True)
        tbtn("👁 Preview", self._preview)
        tbtn("🖨 Print", self._print)
        tbtn("📄 PDF", lambda: self._export("pdf"))
        tk.Frame(bar, bg=C["border"], width=1).pack(side="left", fill="y", pady=12, padx=4)
        tbtn("↩ Undo", self._undo_action)
        tbtn("↪ Redo", self._redo_action)
        self.zoom_var = tk.StringVar(value="Fit Page")
        zoom_cb = ttk.Combobox(bar, textvariable=self.zoom_var, state="readonly",
                               font=("Segoe UI", 9), width=9,
                               values=["50%", "75%", "100%", "125%", "150%",
                                       "Fit Width", "Fit Page"])
        zoom_cb.pack(side="right", padx=(4, 12), pady=9)
        zoom_cb.bind("<<ComboboxSelected>>", lambda e: self._on_zoom_change())
        tk.Label(bar, text="🔍 Zoom", font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(side="right")

        # Document-type + Template selector strip
        strip = tk.Frame(self.frame, bg=C["card_bg"], height=42)
        strip.pack(fill="x"); strip.pack_propagate(False)
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill="x")
        tk.Label(strip, text="Document:", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left", padx=(14, 4))
        self.doc_type_var = tk.StringVar(value="sales_invoice")
        self._doc_types = [(k, lbl) for k, lbl, _kind in rd.DOC_TYPES]
        doc_cb = ttk.Combobox(strip, textvariable=self.doc_type_var, state="readonly",
                              font=("Segoe UI", 9), width=18,
                              values=[lbl for _, lbl in self._doc_types])
        doc_cb.set(self._doc_types[0][1])
        doc_cb.pack(side="left", padx=4, pady=8)
        doc_cb.bind("<<ComboboxSelected>>", lambda e: self._on_doc_type_change())
        tk.Frame(strip, bg=C["border"], width=1).pack(side="left", fill="y", pady=8, padx=6)
        tk.Label(strip, text="Template:", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(side="left", padx=(4, 4))
        self.tpl_var = tk.StringVar()
        self.tpl_cb = ttk.Combobox(strip, textvariable=self.tpl_var, state="readonly",
                                   font=("Segoe UI", 9), width=24)
        self.tpl_cb.pack(side="left", padx=4, pady=8)
        self.tpl_cb.bind("<<ComboboxSelected>>", lambda e: self._on_template_pick())
        for txt, cmd in (("＋ New", self._new_template),
                         ("⧉ Clone", self._clone_template),
                         ("⇄ Copy to…", self._copy_to_doc),
                         ("💾 Save to file", self._export_file),
                         ("📂 Open file", self._import_file),
                         ("★ Set Default", self._set_default),
                         ("🗑 Delete", self._delete_template)):
            tk.Button(strip, text=txt, font=("Segoe UI", 9), bg=C["card_bg"],
                      fg=C["text_primary"], relief="flat", bd=0, padx=9, pady=4,
                      cursor="hand2", activebackground=C["content_bg"],
                      highlightbackground=C.get("field_border", C["border"]),
                      highlightthickness=1, command=cmd).pack(side="left", padx=3)

        # Body: 3 panels
        body = tk.Frame(self.frame, bg=C["content_bg"])
        body.pack(fill="both", expand=True)

        # LEFT — toolbox
        left = tk.Frame(body, bg=C["card_bg"], width=218)
        left.pack(side="left", fill="y"); left.pack_propagate(False)
        tk.Label(left, text="🧰  Toolbox", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", padx=12, pady=(8, 2))
        tk.Label(left, text="Click a field to add it", font=("Segoe UI", 8),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=12, pady=(0, 4))
        tbcanvas = tk.Canvas(left, bg=C["card_bg"], highlightthickness=0, width=200)
        tbsb = ttk.Scrollbar(left, orient="vertical", command=tbcanvas.yview)
        tbinner = tk.Frame(tbcanvas, bg=C["card_bg"])
        tbinner.bind("<Configure>",
                     lambda e: tbcanvas.configure(scrollregion=tbcanvas.bbox("all")))
        _tbw = tbcanvas.create_window((0, 0), window=tbinner, anchor="nw")
        tbcanvas.bind("<Configure>", lambda e: tbcanvas.itemconfig(_tbw, width=e.width))
        tbcanvas.configure(yscrollcommand=tbsb.set)
        tbsb.pack(side="right", fill="y"); tbcanvas.pack(side="left", fill="both", expand=True)
        for group, items in rd.TOOLBOX.items():
            tk.Label(tbinner, text=group.upper(), font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", padx=10, pady=(8, 2))
            for key, label in items:
                b = tk.Label(tbinner, text="  ⠿ " + label, font=("Segoe UI", 9),
                             bg=C["primary_light"], fg=C["primary"], anchor="w",
                             padx=8, pady=4, cursor="hand2")
                b.pack(fill="x", padx=8, pady=1)
                b.bind("<Button-1>", lambda e, k=key, l=label: self._add_element(k, l))

        # CENTER — canvas (scrolls; page centred; "Fit Page" by default)
        center = tk.Frame(body, bg="#E4E7EE")
        center.pack(side="left", fill="both", expand=True)
        ctop = tk.Frame(center, bg="#E4E7EE"); ctop.pack(fill="x")
        tk.Label(ctop, text="Click a toolbox item to drop it · drag to move · "
                 "click to select · Delete key removes",
                 font=("Segoe UI", 8), bg="#E4E7EE", fg=C["text_secondary"]).pack(
                     side="left", padx=10, pady=4)
        cwrap = tk.Frame(center, bg="#E4E7EE")
        cwrap.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 0))
        cvs = ttk.Scrollbar(cwrap, orient="vertical")
        chs = ttk.Scrollbar(cwrap, orient="horizontal")
        self.canvas = tk.Canvas(cwrap, bg="#E4E7EE", highlightthickness=0,
                                yscrollcommand=cvs.set, xscrollcommand=chs.set)
        cvs.configure(command=self.canvas.yview)
        chs.configure(command=self.canvas.xview)
        cvs.pack(side="right", fill="y")
        chs.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._ox, self._oy = 20, 14           # page origin on the canvas
        self.canvas.bind("<Button-1>", self._canvas_click)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_drop)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.frame.winfo_toplevel().bind("<Delete>", self._delete_key, add="+")

        # RIGHT — properties (scrolls, so nothing is cut off on small screens)
        right = tk.Frame(body, bg=C["card_bg"], width=236)
        right.pack(side="right", fill="y"); right.pack_propagate(False)
        tk.Frame(body, bg=C["border"], width=1).pack(side="right", fill="y")
        tk.Label(right, text="⚙  Properties", font=("Segoe UI", 10, "bold"),
                 bg=C["card_bg"], fg=C["text_primary"]).pack(anchor="w", padx=12, pady=8)
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
        self._props_canvas = pcv
        self._build_template_props()

    # ── Template properties (paper, theme, header/footer, printer) ──
    def _build_template_props(self):
        for w in self.props.winfo_children():
            w.destroy()
        C = self.C
        if not self.template:
            tk.Label(self.props, text="Create or pick a template.",
                     font=("Segoe UI", 9), bg=C["card_bg"],
                     fg=C["text_secondary"]).pack(anchor="w", pady=10)
            return

        def lbl(t):
            tk.Label(self.props, text=t, font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(8, 1))

        def combo(var, values):
            cb = ttk.Combobox(self.props, textvariable=var, values=values,
                              state="readonly", font=("Segoe UI", 9))
            cb.pack(fill="x"); return cb

        self.p_paper = tk.StringVar(value=self.template.get("paper_size", "A4"))
        self.p_orient = tk.StringVar(value=self.template.get("orientation", "portrait"))
        self.p_theme = tk.StringVar(value=self.template.get("theme_name", "Modern"))
        self.p_copies = tk.StringVar(value=str(self.template.get("print_copies", 1)))
        self.p_printer = tk.StringVar(
            value=rd.get_template_printer(self.template["template_id"])
            or rd.get_default_printer() or "")
        self.p_header = tk.StringVar(value=self.template.get("header_text", "") or "")
        self.p_footer = tk.StringVar(value=self.template.get("footer_text", "") or "")

        lbl("Paper Size"); cb1 = combo(self.p_paper, list(PAPER.keys()))
        cb1.bind("<<ComboboxSelected>>", lambda e: self._redraw_page())
        lbl("Orientation"); cb2 = combo(self.p_orient, ["portrait", "landscape"])
        cb2.bind("<<ComboboxSelected>>", lambda e: self._redraw_page())
        lbl("Theme"); cb3 = combo(self.p_theme, [th["theme_name"] for th in rd.list_themes()])
        cb3.bind("<<ComboboxSelected>>", lambda e: self._apply_theme())

        lbl("Printer")
        own = rd.get_template_printer(self.template["template_id"])
        self.p_use_default = tk.BooleanVar(value=not own)
        printers = rd.list_printers()
        cb4 = combo(self.p_printer, printers)
        cb4.bind("<<ComboboxSelected>>", lambda e: self._save_printer_choice())

        def _tick():
            if self.p_use_default.get():
                rd.clear_template_printer(self.template["template_id"])
                cb4.configure(state="disabled")
            else:
                cb4.configure(state="readonly")
                self._save_printer_choice()
        tk.Checkbutton(self.props, text="Use the default printer", variable=self.p_use_default,
                       bg=C["card_bg"], activebackground=C["card_bg"], font=("Segoe UI", 9),
                       command=_tick).pack(anchor="w", pady=(2, 0))
        if self.p_use_default.get():
            cb4.configure(state="disabled")
        tk.Label(self.props, text=f"{len(printers)} system printer(s) detected"
                                  if printers != ["(no printers detected)"]
                                  else "No printers detected on this PC",
                 font=("Segoe UI", 7), bg=C["card_bg"],
                 fg=C["text_secondary"]).pack(anchor="w", pady=(2, 0))
        lbl("Print Copies")
        tk.Spinbox(self.props, from_=1, to=20, textvariable=self.p_copies,
                   font=("Segoe UI", 9)).pack(fill="x")

        lbl("Header Text")
        tk.Entry(self.props, textvariable=self.p_header, font=("Segoe UI", 9),
                 relief="solid", bd=1).pack(fill="x", ipady=3)
        lbl("Footer Text")
        tk.Entry(self.props, textvariable=self.p_footer, font=("Segoe UI", 9),
                 relief="solid", bd=1).pack(fill="x", ipady=3)

        # Colors
        lbl("Colors")
        self._color_btn("Header", "header_color")
        self._color_btn("Table", "table_color")
        self._color_btn("Accent", "accent_color")
        self._color_btn("Font", "font_color")
        tk.Button(self.props, text="✨ Use ready layout", font=("Segoe UI", 9, "bold"),
                  bg=C["primary_light"], fg=C["primary"], relief="flat", padx=10, pady=5,
                  cursor="hand2", command=self._use_ready_layout).pack(anchor="w", pady=(12, 0))

    def _color_btn(self, name, key):
        C = self.C
        row = tk.Frame(self.props, bg=C["card_bg"]); row.pack(fill="x", pady=1)
        tk.Label(row, text=name, font=("Segoe UI", 9), bg=C["card_bg"],
                 fg=C["text_primary"], width=8, anchor="w").pack(side="left")
        cur = self.template.get(key, "#3A1FD6")
        sw = tk.Label(row, text="     ", bg=cur, relief="solid", bd=1)
        sw.pack(side="left", padx=4)

        def pick():
            color = colorchooser.askcolor(color=cur, title=f"{name} color")[1]
            if color:
                self.template[key] = color
                sw.config(bg=color)
                self._redraw_page()
        tk.Button(row, text="Pick", font=("Segoe UI", 8), bg=C["card_bg"],
                  fg=C["primary"], relief="flat", cursor="hand2",
                  highlightbackground=C["border"], highlightthickness=1,
                  command=pick).pack(side="left")

    # ── Element properties ────────────────────────────────────
    def _build_element_props(self, el):
        for w in self.props.winfo_children():
            w.destroy()
        C = self.C
        tk.Label(self.props, text=f"Element: {el['label']}",
                 font=("Segoe UI", 9, "bold"), bg=C["card_bg"],
                 fg=C["primary"]).pack(anchor="w", pady=(6, 8))

        def field(label, key, val):
            tk.Label(self.props, text=label, font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(6, 1))
            v = tk.StringVar(value=str(val))
            e = tk.Entry(self.props, textvariable=v, font=("Segoe UI", 9),
                         relief="solid", bd=1)
            e.pack(fill="x", ipady=3)
            v.trace("w", lambda *a: self._update_el(el, key, v.get()))
            return v

        if el.get("type") == "item_col":
            self._build_col_props(el)
            return
        field("Label text", "label", el["label"])
        if el.get("type", "text") == "text" and el.get("key") not in ("text_label",):
            field("Text before the value (e.g. VAT No: )", "prefix", el.get("prefix", ""))
        field("X", "x", el["x"])
        field("Y", "y", el["y"])
        field("Width", "w", el["w"])
        field("Height", "h", el["h"])
        field("Font size", "font", el["font"])

        if el.get("type") == "table":
            tk.Button(self.props, text="✂ Split into separate columns",
                      font=("Segoe UI", 9, "bold"), bg=C["primary"], fg="white",
                      relief="flat", padx=10, pady=5, cursor="hand2",
                      command=lambda: self._split_table(el)).pack(anchor="w", pady=(8, 2))
            tk.Label(self.props, text="Columns", font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(6, 1))
            box = tk.Frame(self.props, bg=C["card_bg"]); box.pack(fill="x")
            cur = list(el.get("cols") or rd.DEFAULT_TABLE_COLS)
            from modules.template_renderer import COL_TITLES
            self._col_vars = {}

            def _cols_changed():
                chosen = [c_ for c_ in rd.TABLE_COLUMNS if self._col_vars[c_].get()]
                self._update_el(el, "cols", chosen or ["product_name"])
            for i, c_ in enumerate(rd.TABLE_COLUMNS):
                v = tk.BooleanVar(value=c_ in cur); self._col_vars[c_] = v
                tk.Checkbutton(box, text=COL_TITLES.get(c_, c_.replace("_", " ").title()),
                               variable=v, bg=C["card_bg"], activebackground=C["card_bg"],
                               font=("Segoe UI", 8), command=_cols_changed).grid(
                                   row=i // 2, column=i % 2, sticky="w")

        self.el_bold = tk.BooleanVar(value=el.get("bold", False))
        tk.Checkbutton(self.props, text="Bold", variable=self.el_bold,
                       font=("Segoe UI", 9), bg=C["card_bg"],
                       activebackground=C["card_bg"],
                       command=lambda: self._update_el(el, "bold", self.el_bold.get())
                       ).pack(anchor="w", pady=(8, 0))

        tk.Label(self.props, text="Align", font=("Segoe UI", 8, "bold"),
                 bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(6, 1))
        self.el_align = tk.StringVar(value=el.get("align", "left"))
        ac = ttk.Combobox(self.props, textvariable=self.el_align,
                          values=["left", "center", "right"], state="readonly",
                          font=("Segoe UI", 9))
        ac.pack(fill="x")
        ac.bind("<<ComboboxSelected>>",
                lambda e: self._update_el(el, "align", self.el_align.get()))

        if el.get("type") not in ("table",):
            tk.Label(self.props, text="When the item list is long", font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(8, 1))
            amap = {"auto": "Auto (low on page = stays at bottom)",
                    "follow": "Moves down with the items",
                    "bottom": "Stays at the page bottom"}
            self.el_anchor = tk.StringVar(value=amap.get(el.get("anchor") or "auto"))
            an = ttk.Combobox(self.props, textvariable=self.el_anchor, state="readonly",
                              values=list(amap.values()), font=("Segoe UI", 8))
            an.pack(fill="x")
            an.bind("<<ComboboxSelected>>", lambda e: self._update_el(
                el, "anchor", next(k for k, v in amap.items() if v == self.el_anchor.get())))

        tk.Button(self.props, text="🗑 Delete Element", font=("Segoe UI", 9),
                  bg="#FEF2F2", fg=C["danger"], relief="flat", padx=10, pady=6,
                  cursor="hand2", command=self._delete_element).pack(
                  anchor="w", pady=(16, 0))

    # ── one item column ───────────────────────────────────────
    def _build_col_props(self, el):
        C = self.C

        def lbl(t):
            tk.Label(self.props, text=t, font=("Segoe UI", 8, "bold"),
                     bg=C["card_bg"], fg=C["text_secondary"]).pack(anchor="w", pady=(6, 1))

        def entry(key, val, all_cols=False):
            v = tk.StringVar(value=str(val))
            tk.Entry(self.props, textvariable=v, font=("Segoe UI", 9), relief="solid",
                     bd=1).pack(fill="x", ipady=3)
            v.trace("w", lambda *a: self._update_col(el, key, v.get(), all_cols))
            return v

        def check(text, key, default, all_cols=False):
            v = tk.BooleanVar(value=bool(el.get(key, default)))
            tk.Checkbutton(self.props, text=text, variable=v, bg=C["card_bg"],
                           activebackground=C["card_bg"], font=("Segoe UI", 9), anchor="w",
                           command=lambda: self._update_col(el, key, v.get(), all_cols)
                           ).pack(anchor="w")
        info = rd.column_info(el.get("field", ""))
        tk.Label(self.props, text=f"Item column:  {info[1]}", font=("Segoe UI", 9, "bold"),
                 bg=C["card_bg"], fg=C["primary"]).pack(anchor="w", pady=(6, 2))
        tk.Label(self.props, text="Drag sideways to move · drag the ◢ corner to resize. "
                 "Moving up/down moves the whole table.", font=("Segoe UI", 7),
                 bg=C["card_bg"], fg=C["text_secondary"], wraplength=200,
                 justify="left").pack(anchor="w")
        lbl("Header (English)"); entry("label", el.get("label", ""))
        lbl("Header (Arabic)"); entry("label_ar", el.get("label_ar", ""))
        check("Show the Arabic header line", "header_ar", True)
        if el.get("field") == "product_name":
            check("Arabic product name on the 2nd line", "ar_second_line", True)
        lbl("X"); entry("x", el["x"])
        lbl("Width"); entry("w", el["w"])
        lbl("Table top (Y) — all columns"); entry("y", el["y"], all_cols=True)
        lbl("Table height — all columns"); entry("h", el["h"], all_cols=True)
        lbl("Font size"); entry("font", el.get("font", 8))
        check("Bold", "bold", False)
        lbl("Align")
        al = tk.StringVar(value=el.get("align", "left"))
        cb = ttk.Combobox(self.props, textvariable=al, values=["left", "center", "right"],
                          state="readonly", font=("Segoe UI", 9))
        cb.pack(fill="x")
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_col(el, "align", al.get()))
        lbl("Whole table")
        check("Cell borders (like Excel)", "cell_lines", True, all_cols=True)
        check("Striped rows", "stripes", True, all_cols=True)
        tk.Button(self.props, text="↔ Fit columns to the table width", font=("Segoe UI", 9),
                  bg=C["primary_light"], fg=C["primary"], relief="flat", padx=8, pady=4,
                  cursor="hand2", command=self._fit_columns).pack(anchor="w", pady=(8, 0))
        tk.Button(self.props, text="🗑 Remove this column", font=("Segoe UI", 9),
                  bg="#FEF2F2", fg=C["danger"], relief="flat", padx=10, pady=6,
                  cursor="hand2", command=self._delete_element).pack(anchor="w", pady=(12, 0))

    def _cols(self):
        return sorted([e for e in self.elements if e.get("type") == "item_col"],
                      key=lambda e: e["x"])

    def _shift_after(self, el, delta, old_w):
        if not delta:
            return
        edge = el["x"] + old_w
        for t in self._cols():
            if t is not el and t["x"] >= edge - 1:
                t["x"] += delta

    def _update_col(self, el, key, val, all_cols=False):
        if key == "w" and not all_cols:
            try:
                nw = max(8, int(float(val)))
            except ValueError:
                return
            old = el["w"]; el["w"] = nw
            self._shift_after(el, nw - old, old)
            self._redraw_page()
            return
        targets = self._cols() if all_cols else [el]
        for t in targets:
            if key in ("x", "y", "w", "h", "font"):
                try:
                    t[key] = int(float(val))
                except ValueError:
                    return
            else:
                t[key] = val
        self._redraw_page()

    def _fit_columns(self):
        """Columns side by side, no gaps, keeping their width ratios,
        across the page width (8 px margins)."""
        cols = self._cols()
        if not cols:
            return
        self._push_undo()
        w_mm, h_mm = PAPER.get(self.p_paper.get() if self.template else "A4", (210, 297))
        if (self.p_orient.get() if self.template else "portrait") == "landscape":
            w_mm = h_mm
        m = 4 if w_mm <= 80 else 8              # roll paper: thinner margins
        x0, x1 = min(m, int(min(c["x"] for c in cols))), int(round(w_mm * PXMM)) - m
        tot = float(sum(c["w"] for c in cols)) or 1
        cx = x0
        for i, c in enumerate(cols):
            w = (x1 - x0) * c["w"] / tot
            c["x"] = int(round(cx)); c["w"] = max(8, int(round(w)))
            cx += w
        for a, b in zip(cols, cols[1:]):
            b["x"] = a["x"] + a["w"]
        cols[-1]["w"] = x1 - cols[-1]["x"]
        self._redraw_page()

    def _split_table(self, el):
        self._push_undo()
        start = max([e["id"] for e in self.elements], default=0) + 1
        cols = rd.split_table(el, start)
        self.elements = [e for e in self.elements if e is not el] + cols
        self.sel_id = cols[0]["id"] if cols else None
        if cols:
            self._build_element_props(cols[0])
        self._redraw_page()

    # ── save to a file / open a file / copy to another document ──
    def _export_file(self):
        if not self.template:
            messagebox.showinfo("Template", "Pick a template first."); return
        from tkinter import filedialog
        nm = "".join(ch if ch.isalnum() or ch in " -_" else "_"
                     for ch in self.template.get("template_name", "template"))
        path = filedialog.asksaveasfilename(
            parent=self.frame, title="Save template to a file",
            defaultextension=".daybill-template.json",
            filetypes=[("DayBill template", "*.json")], initialfile=nm + ".daybill-template.json")
        if not path:
            return
        try:
            t = self._current_template_state()
            rd.export_template(path, t, self.elements, self._current_doc_type())
            messagebox.showinfo("Saved", f"Template saved to:\n{path}\n\nOpen it on any PC "
                                          "with 📂 Open file.", parent=self.frame)
        except Exception as e:
            messagebox.showerror("Save to file", str(e)[:200], parent=self.frame)

    def _import_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.frame, title="Open a template file",
                                          filetypes=[("DayBill template", "*.json"),
                                                     ("All files", "*.*")])
        if not path:
            return
        try:
            d = rd.read_template_file(path)
        except Exception as e:
            messagebox.showerror("Open file", str(e)[:200], parent=self.frame)
            return
        name = simpledialog.askstring(
            "Open template", f"Name for this design ({self.doc_type_var.get()}):",
            initialvalue=(d.get("template") or {}).get("template_name") or "Imported design",
            parent=self.frame)
        if not name:
            return
        tid = rd.create_from_dict(d, self._current_doc_type(), name)
        self._select_template(tid)

    def _copy_to_doc(self):
        """Use this design for another document (e.g. Sales Return)."""
        if not self.template:
            messagebox.showinfo("Template", "Pick a template first."); return
        C = self.C
        top = tk.Toplevel(self.frame); top.title("Copy design to…")
        top.configure(bg=C["card_bg"]); top.resizable(False, False)
        tk.Label(top, text="⇄  Use this design for another document", font=("Segoe UI", 11, "bold"),
                 bg=C["primary"], fg="white", anchor="w", padx=14, pady=8).pack(fill="x")
        body = tk.Frame(top, bg=C["card_bg"]); body.pack(padx=16, pady=10, fill="x")
        here = self._current_doc_type()
        choices = [(k, l) for k, l in self._doc_types if k != here]
        vars_ = {}
        for k, l in choices:
            v = tk.BooleanVar(value=(here == "sales_invoice" and k == "sales_return"))
            tk.Checkbutton(body, text=l, variable=v, bg=C["card_bg"], anchor="w",
                           activebackground=C["card_bg"], font=("Segoe UI", 10)).pack(anchor="w")
            vars_[k] = v
        dflt = tk.BooleanVar(value=True)
        tk.Checkbutton(body, text="Make it the default (★) there", variable=dflt,
                       bg=C["card_bg"], activebackground=C["card_bg"],
                       font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 0))
        res = {}

        def ok():
            res["to"] = [k for k, v in vars_.items() if v.get()]
            top.destroy()
        bar = tk.Frame(top, bg=C["card_bg"]); bar.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(bar, text="Cancel", relief="flat", padx=12, pady=5,
                  command=top.destroy).pack(side="left")
        tk.Button(bar, text="Copy", font=("Segoe UI", 10, "bold"), bg=C["primary"], fg="white",
                  relief="flat", padx=16, pady=5, command=ok).pack(side="right")
        self._copy_dialog = top
        try:
            top.grab_set()
        except Exception:
            pass
        top.wait_window()
        if not res.get("to"):
            return
        made = []
        for k in res["to"]:
            els = json.loads(json.dumps(self.elements, default=str))
            for e in els:                      # title / party label fit the new document
                e.pop("_box", None)
            tid = rd.copy_to(self.template["template_id"], k, make_default=dflt.get(), elements=els)
            try:
                rd.update_template(tid, {"header_text": rd.TITLES.get(k, "")})
            except Exception:
                pass
            made.append(next(l for kk, l in self._doc_types if kk == k))
        messagebox.showinfo("Copied", "Design copied to:\n  • " + "\n  • ".join(made) +
                            "\n\nPick the document above to edit it there.", parent=self.frame)

    def _select_template(self, tid):
        self._load_templates()
        for idx, t in enumerate(self._templates):
            if t["template_id"] == tid:
                self.tpl_cb.current(idx); self._on_template_pick(); break

    def _update_el(self, el, key, val):
        if key in ("x", "y", "w", "h", "font"):
            try:
                el[key] = int(float(val))
            except ValueError:
                return
        else:
            el[key] = val
        self._redraw_page()

    # ── Templates CRUD ────────────────────────────────────────
    def _current_doc_type(self):
        lbl = self.doc_type_var.get()
        for key, l in self._doc_types:
            if l == lbl:
                return key
        return "sales_invoice"

    def _on_doc_type_change(self):
        self._load_templates()

    def _load_templates(self, select_id=None):
        self._templates = rd.list_templates(self._current_doc_type())
        names = [f"{t['template_name']}" + ("  ★ prints" if t.get("is_default") else "")
                 for t in self._templates]
        self.tpl_cb["values"] = names
        if self._templates:
            idx = next((i for i, t in enumerate(self._templates)
                        if select_id is not None and t["template_id"] == select_id), 0)
            self.tpl_cb.current(idx)
            self._on_template_pick()

    def _on_template_pick(self):
        i = self.tpl_cb.current()
        if i < 0 or i >= len(self._templates):
            return
        self.template = dict(self._templates[i])
        self.elements = rd.load_layout(self.template["template_id"])
        self.sel_id = None
        self._build_template_props()
        self._redraw_page()

    def _new_template(self):
        """New design for the chosen document: name, paper, and whether to
        start from the ready layout (recommended) or an empty page."""
        C = self.C
        doc_type = self._current_doc_type()
        top = tk.Toplevel(self.frame)
        top.title("New template")
        top.configure(bg=C["card_bg"])
        top.resizable(False, False)
        tk.Label(top, text=f"＋  New {self.doc_type_var.get()} template",
                 font=("Segoe UI", 12, "bold"), bg=C["primary"], fg="white",
                 anchor="w", padx=14, pady=8).pack(fill="x")
        body = tk.Frame(top, bg=C["card_bg"]); body.pack(padx=16, pady=12, fill="x")
        name_v = tk.StringVar(value=f"{self.doc_type_var.get()} – My design")
        paper_v = tk.StringVar(value="80mm" if doc_type == "pos_invoice" else "A4")
        ready_v = tk.BooleanVar(value=True)
        default_v = tk.BooleanVar(value=not rd.list_templates(doc_type))
        tk.Label(body, text="Name", bg=C["card_bg"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        e = tk.Entry(body, textvariable=name_v, width=36, font=("Segoe UI", 10),
                     relief="solid", bd=1)
        e.grid(row=0, column=1, sticky="ew", pady=4, ipady=3)
        tk.Label(body, text="Paper", bg=C["card_bg"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        ttk.Combobox(body, textvariable=paper_v, values=list(PAPER.keys()), state="readonly",
                     width=10).grid(row=1, column=1, sticky="w", pady=4)
        tk.Checkbutton(body, text="Start with the ready layout (all fields placed)",
                       variable=ready_v, bg=C["card_bg"], activebackground=C["card_bg"]
                       ).grid(row=2, column=0, columnspan=2, sticky="w")
        tk.Checkbutton(body, text="Use it as the default for this document (★)",
                       variable=default_v, bg=C["card_bg"], activebackground=C["card_bg"]
                       ).grid(row=3, column=0, columnspan=2, sticky="w")
        res = {}

        def ok(_e=None):
            nm = name_v.get().strip()
            if not nm:
                return
            res.update(name=nm, paper=paper_v.get(), ready=ready_v.get(),
                       default=default_v.get())
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
        if not res:
            return None
        return self._create_template(res["name"], res["paper"], res["ready"], res["default"])

    def _create_template(self, name, paper="A4", ready=True, make_default=False):
        doc_type = self._current_doc_type()
        els = rd.starter_layout(doc_type, paper) if ready else []
        tid = rd.create_template({
            "template_name": name, "report_type": doc_type, "paper_size": paper,
            "orientation": "portrait", "theme_name": "Modern",
            "header_color": "#3A1FD6", "footer_color": "#2A14A8",
            "table_color": "#3A1FD6", "font_color": "#1A1438", "accent_color": "#7ED957",
            "header_text": rd.TITLES.get(doc_type, "") if paper not in ("80mm", "58mm") else "",
            "footer_text": ("Thank you for your business." if paper not in ("80mm", "58mm") else ""),
            "header_height": 38 if paper not in ("80mm", "58mm") else 0,
            "footer_height": 20 if paper not in ("80mm", "58mm") else 0,
            "print_copies": 1, "layout_json": json.dumps(els)})
        if make_default:
            rd.set_default(tid, doc_type)
        self._load_templates()
        for idx, t in enumerate(self._templates):
            if t["template_id"] == tid:
                self.tpl_cb.current(idx); self._on_template_pick(); break
        return tid

    def _use_ready_layout(self):
        if not self.template:
            return
        if self.elements and not messagebox.askyesno(
                "Ready layout", "Replace the fields on this page with the ready layout?"):
            return
        self._push_undo()
        self.elements = rd.starter_layout(self._current_doc_type(),
                                          self.p_paper.get() if hasattr(self, "p_paper") else "A4")
        self.sel_id = None
        self._redraw_page()

    def _save_printer_choice(self):
        if not self.template or self.p_printer.get() in ("", "(no printers detected)"):
            return
        try:
            rd.save_printer_setting(self.template["template_id"],
                                    self.p_printer.get())
        except Exception as e:
            messagebox.showerror("Printer", str(e)[:160])

    def _clone_template(self):
        if not self.template:
            return
        rd.clone_template(self.template["template_id"])
        self._load_templates()

    def _set_default(self):
        if not self.template:
            return
        rd.set_default(self.template["template_id"], self._current_doc_type())
        self._load_templates(select_id=self.template["template_id"])
        messagebox.showinfo("Default", f"★ This design now prints {self.doc_type_var.get()}.")

    def _delete_template(self):
        if not self.template:
            return
        if messagebox.askyesno("Delete", f"Delete '{self.template['template_name']}'?"):
            rd.delete_template(self.template["template_id"])
            self.template = None
            self.elements = []
            self._load_templates()
            self._redraw_page()

    def _save(self):
        if not self.template:
            messagebox.showinfo("Save", "Create a template first."); return
        data = {
            "paper_size": self.p_paper.get(), "orientation": self.p_orient.get(),
            "theme_name": self.p_theme.get(),
            "print_copies": int(self.p_copies.get() or 1),
            "header_text": self.p_header.get(), "footer_text": self.p_footer.get(),
            "header_color": self.template.get("header_color"),
            "table_color": self.template.get("table_color"),
            "accent_color": self.template.get("accent_color"),
            "font_color": self.template.get("font_color"),
            "layout_json": json.dumps(self.elements),
        }
        rd.update_template(self.template["template_id"], data)
        tid = self.template["template_id"]
        doc_name = self.doc_type_var.get() if hasattr(self, "doc_type_var") else "this document"
        is_def = bool(self.template.get("is_default"))
        if not is_def:
            try:
                fresh = rd.get_template(tid) or {}
                is_def = bool(fresh.get("is_default"))
            except Exception:
                pass
        if is_def:
            messagebox.showinfo("Saved", "Template saved.\n\n★ It is used when you print "
                                "%s." % doc_name)
        elif messagebox.askyesno(
                "Saved", "Template saved.\n\nIt is NOT used for printing yet — %s still "
                "prints with another layout.\n\nUse THIS design when printing %s?  (★ default)"
                % (doc_name, doc_name)):
            rd.set_default(tid, self._current_doc_type())
        self._load_templates(select_id=tid)

    # ── Canvas drawing ────────────────────────────────────────
    def _page_px(self):
        w_mm, h_mm = PAPER.get(self.p_paper.get() if self.template else "A4", (210, 297))
        if (self.p_orient.get() if self.template else "portrait") == "landscape":
            w_mm, h_mm = h_mm, w_mm
        return int(w_mm * PXMM * self.zoom), int(h_mm * PXMM * self.zoom)

    def _fit_zoom(self):
        """Zoom for 'Fit Width' / 'Fit Page' from the visible canvas size."""
        val = self.zoom_var.get() if hasattr(self, "zoom_var") else "100%"
        if not str(val).startswith("Fit"):
            return False
        w_mm, h_mm = PAPER.get(self.p_paper.get() if self.template else "A4", (210, 297))
        if (self.p_orient.get() if self.template else "portrait") == "landscape":
            w_mm, h_mm = h_mm, w_mm
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 640, 520
        zw = (cw - 40) / (w_mm * PXMM)
        zh = (ch - 28) / (h_mm * PXMM)
        self.zoom = max(0.2, min(3.0, zw if val == "Fit Width" else min(zw, zh)))
        return True

    def _on_canvas_resize(self, e=None):
        if self._fit_zoom() or self.template:
            if getattr(self, "_rs_after", None):
                try:
                    self.canvas.after_cancel(self._rs_after)
                except Exception:
                    pass
            self._rs_after = self.canvas.after(60, self._redraw_page)

    def _on_zoom_change(self):
        val = self.zoom_var.get()
        if not self._fit_zoom():
            try:
                self.zoom = int(val.rstrip("%")) / 100.0
            except Exception:
                self.zoom = 1.0
        self._redraw_page()

    def _redraw_page(self):
        self._rs_after = None
        self.canvas.delete("all")
        if not self.template:
            return
        self._fit_zoom()
        pw, ph = self._page_px()
        # centre the page in the visible area; scroll when it is bigger
        cw = max(self.canvas.winfo_width(), 100)
        self._ox = max(20, int((cw - pw) / 2))
        self._oy = 14
        OX, OY = self._ox, self._oy
        self.canvas.configure(scrollregion=(0, 0, max(cw, pw + 2 * OX), ph + 2 * OY))
        # page with a soft shadow
        self.canvas.create_rectangle(OX + 3, OY + 3, OX + pw + 3, OY + ph + 3,
                                     fill="#C9CED8", outline="")
        self.canvas.create_rectangle(OX, OY, OX + pw, OY + ph,
                                     fill="white", outline="#B8BECB")
        # header band
        hc = self.template.get("header_color") or "#3A1FD6"
        hh = int(float(self.template.get("header_height") or 38)
                 * PXMM / 3 * self.zoom)
        self.canvas.create_rectangle(OX, OY, OX + pw, OY + hh,
                                     fill=hc, outline="")
        ht = self.p_header.get() if hasattr(self, "p_header") else ""
        self.canvas.create_text(OX + 10, OY + hh / 2, text=ht or "Header",
                                anchor="w", fill="white",
                                font=("Segoe UI", 11, "bold"))
        # footer band
        fc = self.template.get("footer_color") or \
            self.template.get("header_color") or "#3A1FD6"
        fh = int(float(self.template.get("footer_height") or 20)
                 * PXMM / 3 * self.zoom)
        self.canvas.create_rectangle(OX, OY + ph - fh, OX + pw, OY + ph,
                                     fill=fc, outline="")
        ft = self.p_footer.get() if hasattr(self, "p_footer") else ""
        self.canvas.create_text(OX + 10, OY + ph - fh / 2, text=ft or "Footer",
                                anchor="w", fill="white", font=("Segoe UI", 8))
        # elements
        for el in self.elements:
            self._draw_element(el)

    _SAMPLE = {"line_no": ("1", ""), "item_code": ("P0001", ""), "barcode": ("6281000000017", ""),
               "product_name": ("Basmati Rice 5kg", "أرز بسمتي 5 كجم"),
               "product_name_ar": ("أرز بسمتي 5 كجم", ""), "quantity": ("2", ""),
               "unit": ("Pcs", ""), "rate": ("25.00", ""), "discount": ("0.00", ""),
               "line_amount": ("50.00", ""), "vat_rate": ("15%", ""), "tax": ("7.50", ""),
               "line_total": ("57.50", "")}

    def _draw_col(self, el, x, y, w, h, sel):
        """An item column: coloured header + sample rows, like the print."""
        cv, z = self.canvas, self.zoom
        tc = self.template.get("table_color") or "#3A1FD6"
        two = bool(el.get("header_ar") and el.get("label_ar"))
        hh = (6.5 * (1.55 if two else 1.0)) * PXMM * z
        cv.create_rectangle(x, y, x + w, y + h, outline="#C9D2DE", fill="white")
        cv.create_rectangle(x, y, x + w, y + min(hh, h), outline="", fill=tc)
        fs = -max(7, int(round(max(6, int(el.get("font") or 8)) * 0.3528 * PXMM * z * 1.15)))
        anchor = {"left": "w", "center": "center", "right": "e"}[el.get("align", "left")]
        tx = x + (3 if anchor == "w" else (w - 3 if anchor == "e" else w / 2))
        if two:
            cv.create_text(tx, y + hh * 0.32, text=el.get("label", ""), anchor=anchor,
                           fill="white", font=("Segoe UI", fs, "bold"))
            cv.create_text(tx, y + hh * 0.74, text=el.get("label_ar", ""), anchor=anchor,
                           fill="white", font=("Segoe UI", fs))
        else:
            cv.create_text(tx, y + hh / 2, text=el.get("label", ""), anchor=anchor,
                           fill="white", font=("Segoe UI", fs, "bold"))
        en, ar = self._SAMPLE.get(el.get("field", ""), ("…", ""))
        ry = y + hh
        two_rows = any(c.get("field") == "product_name" and c.get("ar_second_line", True)
                       for c in self._cols())
        rh = 6.5 * PXMM * z * (1.6 if two_rows else 1.0)
        k = 0
        while (k == 0 or ry + rh <= y + h + 1) and k < 6:
            if k % 2 and el.get("stripes", True):
                cv.create_rectangle(x, ry, x + w, ry + rh, outline="", fill="#F5F6FA")
            if ar and el.get("ar_second_line", True):
                cv.create_text(tx, ry + rh * 0.33, text=en, anchor=anchor, font=("Segoe UI", fs),
                               fill=self.template.get("font_color", "#1A1438"))
                cv.create_text(x + w - 3, ry + rh * 0.75, text=ar, anchor="e",
                               font=("Segoe UI", fs), fill="#555")
            else:
                cv.create_text(tx, ry + rh / 2, text=en, anchor=anchor, font=("Segoe UI", fs),
                               fill=self.template.get("font_color", "#1A1438"))
            if el.get("cell_lines", True):
                cv.create_line(x, ry + rh, x + w, ry + rh, fill="#C9D2DE")
            ry += rh; k += 1
        box = cv.create_rectangle(x, y, x + w, y + h,
                                  outline=(self.C["accent"] if sel else "#AEB9C7"),
                                  width=(2 if sel else 1))
        el["_box"] = box
        if sel:
            self._draw_handle(x + w, y + h)

    def _draw_handle(self, x, y):
        self.canvas.create_rectangle(x - 6, y - 6, x + 2, y + 2, fill=self.C["accent"],
                                     outline="white", tags=("handle",))

    def _draw_element(self, el):
        z = self.zoom
        x, y = self._ox + el["x"] * z, self._oy + el["y"] * z
        w, h = el["w"] * z, el["h"] * z
        sel = (el["id"] == self.sel_id)
        etype = el.get("type", "text")
        if etype == "item_col":
            self._draw_col(el, x, y, w, h, sel)
            return
        icon = {"image": "🖼", "qr": "▦", "barcode": "|||", "table": "▤",
               "signature": "✎", "stamp": "◉", "line": "—"}.get(etype)
        dashed = etype in ("image", "qr", "barcode", "signature", "stamp")
        box = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            outline=(self.C["accent"] if sel else "#C7CCDA"),
            width=(2 if sel else 1),
            dash=(4, 2) if dashed else (),
            fill=("#F4F7FF" if sel else ("#F0F0FA" if etype == "table" else "")))
        if etype == "line":
            self.canvas.create_line(x, y + h / 2, x + w, y + h / 2,
                                    fill="#AAAAAA", width=2)
            el["_box"] = box
            return
        # true to scale: 1 pt = 0.353 mm on paper (negative size = pixels)
        font = ("Segoe UI", -max(7, int(round(el["font"] * 0.3528 * PXMM * z * 1.15))),
                "bold" if el.get("bold") else "normal")
        anchor = {"left": "w", "center": "center", "right": "e"}[el.get("align", "left")]
        tx = x + (4 if anchor == "w" else (w - 4 if anchor == "e" else w / 2))
        label = (f"{icon}  {el['label']}" if icon else el["label"])
        self.canvas.create_text(tx, y + h / 2, text=label,
                                anchor=anchor, font=font,
                                fill=self.template.get("font_color", "#1A1438"))
        el["_box"] = box
        if sel:
            self._draw_handle(x + w, y + h)

    def _add_element(self, key, label):
        if not self.template:
            messagebox.showinfo("Template", "Create or pick a template first."); return
        self._push_undo()
        eid = max([e["id"] for e in self.elements], default=0) + 1
        if key.startswith("col:"):
            field = key[4:]
            legacy = next((e for e in self.elements
                           if e.get("type") == "table" or e.get("key") == "table"), None)
            if legacy is not None and not self._cols():
                # old one-block table: make it separate columns first, so the
                # new column joins it (it used to replace the whole table)
                start = max([e["id"] for e in self.elements], default=0) + 1
                self.elements = [e for e in self.elements if e is not legacy] + \
                    rd.split_table(legacy, start)
                eid = max([e["id"] for e in self.elements], default=0) + 1
            cols = self._cols()
            info = rd.column_info(field)
            if any(c.get("field") == field for c in cols):
                messagebox.showinfo("Item columns", f"“{info[1]}” is already on the page.")
                return
            if cols:
                last = cols[-1]
                x, y, h = last["x"] + last["w"], last["y"], last["h"]
                font = last.get("font", 8)
            else:
                x, y, h, font = 8, 134, 40, 8
            scale = 1.0
            if cols:      # same scale as the columns already there (80 mm roll ≈ 0.4)
                base = sum(rd.column_info(c_.get("field"))[3] * 4.4 for c_ in cols) or 1
                scale = max(0.3, min(1.5, sum(float(c_["w"]) for c_ in cols) / base))
            el = rd.item_columns([field], x, y, info[3] * 4.4 * scale, h, font=font)[0]
            el["id"] = eid
            if cols:
                for k in ("cell_lines", "stripes", "header_ar"):
                    el[k] = cols[0].get(k, True)
            self.elements.append(el)
            self.sel_id = eid
            w_mm = PAPER.get(self.p_paper.get() if hasattr(self, "p_paper") else "A4", (210, 297))[0]
            if el["x"] + el["w"] > w_mm * PXMM - (4 if w_mm <= 80 else 8):
                self._fit_columns()              # no room: all columns share the width
            self._build_element_props(el)
            self._redraw_page()
            return
        etype = _TYPE_OF_KEY.get(key, "text")
        # tables/logos/signatures get a larger default box
        default_w, default_h = (160, 22)
        if etype == "table":
            default_w, default_h = (500, 30)
        elif etype in ("image", "qr", "barcode"):
            default_w, default_h = (70, 70) if etype != "barcode" else (140, 40)
        elif etype in ("signature", "stamp"):
            default_w, default_h = (140, 50)
        fx, fy = self._free_spot(default_w, default_h)
        el = {"id": eid, "key": key, "label": label, "type": etype,
              "x": fx, "y": fy,
              "w": default_w, "h": default_h, "font": 9, "bold": False,
              "align": "left"}
        if etype == "table":
            el["cols"] = list(rd.DEFAULT_TABLE_COLS if hasattr(rd, "DEFAULT_TABLE_COLS")
                              else ["item_code", "product_name", "quantity",
                                    "rate", "tax", "line_total"])
        self.elements.append(el)
        self.sel_id = eid
        self._redraw_page()

    def _free_spot(self, w, h):
        """First place on the page (left column, then right) where a new
        element does not cover another one."""
        pw, ph = PAPER.get(self.p_paper.get() if hasattr(self, "p_paper") else "A4", (210, 297))
        pw, ph = pw * PXMM, ph * PXMM

        def hits(x, y):
            for e in self.elements:
                ex, ey = float(e.get("x", 0)), float(e.get("y", 0))
                ew, eh = float(e.get("w", 0)), float(e.get("h", 0))
                if x < ex + ew and ex < x + w and y < ey + eh and ey < y + h:
                    return True
            return False
        for x in (30, pw / 2 + 4, 8):
            if x + w > pw:
                continue
            y = 60
            while y + h < ph - 20:
                if not hits(x, y):
                    return x, y
                y += 6
        return 30, 60

    def _canvas_click(self, event):
        z = self.zoom
        dx = (self.canvas.canvasx(event.x) - self._ox) / z
        dy = (self.canvas.canvasy(event.y) - self._oy) / z
        cur = next((e for e in self.elements if e["id"] == self.sel_id), None)
        if cur is not None and abs(dx - (cur["x"] + cur["w"])) <= 8 / z + 2 \
                and abs(dy - (cur["y"] + cur["h"])) <= 8 / z + 2:
            self._push_undo()
            self._drag = (dx, dy, cur, "resize")
            return
        hit = None
        for el in reversed(self.elements):
            if el["x"] <= dx <= el["x"] + el["w"] and el["y"] <= dy <= el["y"] + el["h"]:
                hit = el; break
        if hit:
            self.sel_id = hit["id"]
            self._push_undo()
            self._drag = (dx, dy, hit, "move")
            self._build_element_props(hit)
        else:
            self.sel_id = None
            self._drag = None
            self._build_template_props()
        self._redraw_page()

    def _canvas_drag(self, event):
        if not self._drag:
            return
        z = self.zoom
        dx = (self.canvas.canvasx(event.x) - self._ox) / z
        dy = (self.canvas.canvasy(event.y) - self._oy) / z
        ox, oy, el, mode = self._drag
        cols = self._cols() if el.get("type") == "item_col" else []
        if mode == "resize":
            old_w = el["w"]
            el["w"] = max(8, int(round(el["w"] + dx - ox)))
            nh = max(8, int(round(el["h"] + dy - oy)))
            for t in (cols or [el]):              # columns share one height
                t["h"] = nh
            if cols:                              # like Excel: push the next columns
                self._shift_after(el, el["w"] - old_w, old_w)
        elif cols:
            el["x"] = max(0, int(round(el["x"] + dx - ox)))  # sideways: this column
            for t in cols:                                    # up / down: whole table
                t["y"] = max(0, int(round(t["y"] + dy - oy)))
        else:
            el["x"] += dx - ox
            el["y"] += dy - oy
            el["x"] = max(0, int(el["x"])); el["y"] = max(0, int(el["y"]))
        self._drag = (dx, dy, el, mode)
        self._redraw_page()

    def _canvas_drop(self, event):
        if self._drag:
            el = self._drag[2]
            if el.get("id") == self.sel_id:
                try:
                    self._build_element_props(el)      # show the new X / W
                except Exception:
                    pass
        self._drag = None

    def _delete_key(self, e=None):
        """Delete key removes the selected element — but never while typing
        in a box (it used to delete the element instead of a letter), and
        never after leaving the designer for another screen."""
        try:
            if not self.frame.winfo_exists() or not self.frame.winfo_ismapped():
                return
            w = getattr(e, "widget", None)
            if isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text, tk.Spinbox,
                              ttk.Spinbox, ttk.Treeview, tk.Listbox)):
                return
        except Exception:
            return
        self._delete_element()

    def _delete_element(self):
        if self.sel_id is None:
            return
        self._push_undo()
        self.elements = [e for e in self.elements if e["id"] != self.sel_id]
        self.sel_id = None
        self._build_template_props()
        self._redraw_page()

    def _apply_theme(self):
        th = rd.get_theme(self.p_theme.get())
        if th:
            for k in ("header_color", "footer_color", "table_color",
                      "font_color", "accent_color"):
                self.template[k] = th.get(k)
            self.template["theme_name"] = self.p_theme.get()
            self._build_template_props()
            self._redraw_page()

    # ── Undo / Redo ───────────────────────────────────────────
    def _push_undo(self):
        self._undo.append(json.dumps(self.elements))
        self._redo.clear()
        if len(self._undo) > 50:
            self._undo.pop(0)

    def _undo_action(self):
        if not self._undo:
            return
        self._redo.append(json.dumps(self.elements))
        self.elements = json.loads(self._undo.pop())
        self.sel_id = None
        self._redraw_page()

    def _redo_action(self):
        if not self._redo:
            return
        self._undo.append(json.dumps(self.elements))
        self.elements = json.loads(self._redo.pop())
        self.sel_id = None
        self._redraw_page()

    # ── Preview / Print / Export ──────────────────────────────
    def _current_template_state(self):
        """The template as it is on screen now (unsaved edits included)."""
        t = dict(self.template or {})
        if hasattr(self, "p_paper"):
            t.update(paper_size=self.p_paper.get(), orientation=self.p_orient.get(),
                     header_text=self.p_header.get(), footer_text=self.p_footer.get())
            try:
                t["print_copies"] = int(self.p_copies.get() or 1)
            except ValueError:
                pass
        return t

    def _sample(self):
        """Latest real document of this type, or sample data."""
        try:
            from modules import doc_print as DP
            kind = rd.kind_of(self._current_doc_type())
            did = DP.last_id(kind)
            doc = DP.load(kind, did) if did else None
            if doc:
                return doc["inv"], doc["company"], doc["lines"], doc["number"]
        except Exception:
            pass
        from modules.template_renderer import demo_data
        inv, comp, lines = demo_data()
        try:
            real = db.fetchone("SELECT * FROM company WHERE company_id=1")
            if real:
                comp = dict(real)
        except Exception:
            pass
        return inv, comp, lines, "sample"

    def _render(self, out=None):
        if not self.template:
            messagebox.showinfo("Template", "Create or pick a template first.")
            return None
        if not self.elements:
            messagebox.showinfo("Template", "Add some fields first "
                                "(or ✨ Use ready layout on the right).")
            return None
        import tempfile
        from modules.template_renderer import render_template
        inv, comp, lines, num = self._sample()
        out = out or os.path.join(tempfile.gettempdir(),
                                  f"design_{self.template['template_id']}_{num}.pdf")
        render_template(self._current_template_state(), self.elements, inv, comp, lines, out,
                        preview=True)
        self.last_render = out
        return out

    def _preview(self):
        try:
            out = self._render()
        except Exception as e:
            messagebox.showerror("Preview", f"Could not render.\n{str(e)[:200]}")
            return
        if out:
            from modules import printer_service as ps
            ps.open_file(out)

    def _preview_pdf(self):
        self._preview()

    def _print(self):
        try:
            out = self._render()
        except Exception as e:
            messagebox.showerror("Print", f"Could not render.\n{str(e)[:200]}")
            return
        if not out:
            return
        from ui import print_menu
        own = None if getattr(self, "p_use_default", tk.BooleanVar(value=True)).get() \
            else (self.p_printer.get() or None)
        print_menu.send_pdf(self.frame, out, self.template.get("template_name", "Template"),
                            printer_key=self._current_doc_type(), printer=own,
                            copies=self._current_template_state().get("print_copies", 1))

    def _export(self, fmt="pdf"):
        if not self.template:
            messagebox.showinfo("PDF", "Create or pick a template first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile=f"{self.template.get('template_name', 'template')}.pdf")
        if not path:
            return
        try:
            if self._render(path):
                from modules import printer_service as ps
                ps.open_file(path)
        except Exception as e:
            messagebox.showerror("PDF", str(e)[:200])
