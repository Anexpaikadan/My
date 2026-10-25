# ============================================================
# DayBill ERP - business modules (v7.0)
# ------------------------------------------------------------
# What kind of business the company is. Picked in the New Company
# wizard (more than one may be ticked) and changed later in
# Settings ▸ Company ▸ Business modules. Kept in the company's database
# (company.business_modules), so every PC behaves the same.
#
#   retail       counter sales, POS, invoices, stock         (always on)
#   supermarket  scale barcodes & PLU, expiry, offers, shelf labels,
#                fast scanning
#   restaurant   tables, dine-in / takeaway / delivery, kitchen order
#                tickets (KOT), recipes that use up ingredients
#   textiles     size / colour variants, selling by the metre, stock by
#                size and colour
#   production   bill of materials, production entries, finished-goods
#                cost
#
#   enabled()            set of module keys switched on
#   has(key)             one module on?
#   set_enabled(keys)    save the list (company database)
#   nav_items(key)       the menu pages a module adds
#   hidden_screens()     menu pages to hide for this company
#   defaults_for(keys)   settings a module switches on when chosen
# ============================================================

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

# key, title, icon, what it gives
MODULES = [
    ("retail", "Retail shop", "🛍",
     "Counter sales, POS, sales invoices, purchases, stock and accounts."),
    ("supermarket", "Supermarket / Grocery", "🛒",
     "Scale barcodes and PLU, expiry and batches, offers, shelf labels, fast scanning."),
    ("restaurant", "Restaurant / Café", "🍽",
     "Tables, dine-in / takeaway / delivery, kitchen order tickets (KOT), recipes "
     "that use up ingredients when a dish is sold."),
    ("textiles", "Textiles & Garments", "🧵",
     "Size and colour variants with their own barcodes, selling by the metre, "
     "stock by size and colour."),
    ("production", "Production / Manufacturing", "🏭",
     "Bill of materials, production entries (raw materials in, finished goods out), "
     "finished-goods cost."),
]
KEYS = [m[0] for m in MODULES]
TITLES = {m[0]: m[1] for m in MODULES}
ICONS = {m[0]: m[2] for m in MODULES}

# a database made before v7.0 keeps everything it had
OLD_DEFAULT = ("retail", "supermarket")

# menu pages each module adds: (group heading, [(key, icon, label)])
NAV = {
    "restaurant": ("Restaurant", [
        ("rest_tables", "🍽", "Tables & Orders"),
        ("rest_kot", "🧾", "Kitchen Orders (KOT)"),
        ("recipes", "📋", "Recipes"),
        ("rest_setup", "⚙", "Restaurant Setup"),
    ]),
    "production": ("Production", [
        ("production", "🏭", "Production Entry"),
        ("bom", "📋", "Bill of Materials"),
        ("production_report", "📊", "Production Report"),
    ]),
    "textiles": ("Textiles", [
        ("variants", "🧵", "Size & Colour Variants"),
        ("variant_stock", "📊", "Stock by Size & Colour"),
    ]),
}

# menu page → (python module, view class) that opens it
SCREENS = {
    "rest_tables": ("ui.restaurant", "TablesView"),
    "rest_kot": ("ui.restaurant", "KotView"),
    "rest_setup": ("ui.restaurant", "RestaurantSetupView"),
    "recipes": ("ui.bom_editor", "RecipesView"),
    "bom": ("ui.bom_editor", "BomView"),
    "production": ("ui.production", "ProductionView"),
    "production_report": ("ui.production", "ProductionReportView"),
    "variants": ("ui.textiles", "VariantsView"),
    "variant_stock": ("ui.textiles", "VariantStockView"),
}

# who may open each page (Users & Rights module, action)
RIGHTS = {
    "rest_tables": ("pos", "view"), "rest_kot": ("pos", "view"),
    "rest_setup": ("company_settings", "settings"),
    "recipes": ("products", "edit"), "bom": ("products", "edit"),
    "production": ("inventory", "edit"), "production_report": ("reports", "view"),
    "variants": ("products", "edit"), "variant_stock": ("inventory", "view"),
}

# existing pages that only make sense with a module
NEEDS = {
    "plu": "supermarket",            # scale PLU manager
}

# settings a module turns on when the company picks it (New Company)
DEFAULTS = {
    "supermarket": {"plu_enabled": True, "pos_voice_not_found": True,
                    "expiry_alert_days": 30, "pos_show_favorites": True},
    "restaurant": {"pos_enable_hold": True, "rest_order_types": "Dine-in,Takeaway,Delivery",
                   "rest_kot_print": True, "rest_service_charge_pct": 0},
    "textiles": {"qty_decimals": 2, "textile_sizes": "XS,S,M,L,XL,XXL",
                 "textile_colours": "White,Black,Blue,Red,Green,Grey"},
    "production": {"production_post_journal": True},
    "retail": {},
}

_CACHE = {"keys": None}


def invalidate():
    _CACHE["keys"] = None


def _parse(text):
    out = []
    for k in str(text or "").replace(";", ",").split(","):
        k = k.strip().lower()
        if k in KEYS and k not in out:
            out.append(k)
    return out


def enabled():
    if _CACHE["keys"] is not None:
        return set(_CACHE["keys"])
    keys = None
    try:
        v = db.execute_scalar("SELECT TOP 1 business_modules FROM company ORDER BY company_id")
        if v is not None:
            keys = _parse(v)
    except Exception:
        keys = None
    if not keys:
        keys = list(OLD_DEFAULT)
    if "retail" not in keys:
        keys.insert(0, "retail")
    _CACHE["keys"] = keys
    return set(keys)


def has(key):
    return key in enabled()


def ordered():
    enabled()
    return [k for k in KEYS if k in (_CACHE["keys"] or [])]


def text(keys=None):
    ks = list(keys) if keys is not None else ordered()
    return ",".join(k for k in KEYS if k in ks)


def set_enabled(keys):
    ks = _parse(",".join(keys or []))
    if "retail" not in ks:
        ks.insert(0, "retail")
    try:
        db.execute("UPDATE company SET business_modules=?", (text(ks),))
    except Exception:
        return False
    invalidate()
    return True


def nav_groups():
    """[(heading, [(key, icon, label)])] for the modules switched on."""
    out = []
    for k in KEYS:
        if k in NAV and has(k):
            out.append(NAV[k])
    return out


def all_module_screens():
    return {key for _g, items in NAV.values() for key, _i, _l in items}


def hidden_screens():
    """Menu pages this company does not use."""
    on = enabled()
    hide = {s for s, need in NEEDS.items() if need not in on}
    for k, (_g, items) in NAV.items():
        if k not in on:
            hide |= {key for key, _i, _l in items}
    # recipes are shared by restaurant and production
    if on & {"restaurant", "production"}:
        hide.discard("recipes")
        hide.discard("bom")
    return hide


def defaults_for(keys):
    out = {}
    for k in keys or []:
        out.update(DEFAULTS.get(k, {}))
    return out


def summary(keys=None):
    ks = list(keys) if keys is not None else ordered()
    return " · ".join("%s %s" % (ICONS[k], TITLES[k]) for k in KEYS if k in ks)
