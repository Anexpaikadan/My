# ============================================================
# DayBill ERP - Product AI (offline part)
# ------------------------------------------------------------
#  #3  find_duplicates()      "looks like an existing product"
#  #4  suggest_from_similar() category / VAT / units / brand from the
#                             closest existing products
#  #9  translate_offline()    grocery dictionary EN → AR (the online AI
#                             in modules/ai_client.py does better)
#  #13 cleanup_scan() / apply_fix()   product master health check
# Works without internet. Only reads your own product list.
# ============================================================

import difflib
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.database import db


class _Row(dict):
    """A database row; a missing column reads as None (older databases)."""
    def __missing__(self, key):
        return None


def _q(sql, params=()):
    try:
        return [_Row(r) for r in (db.fetchall(sql, params) or [])]
    except Exception:
        return []


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ── name normalising ─────────────────────────────────────────
_UNIT_ALIASES = [
    (r"\b(litres?|liters?|ltrs?|lt)\b", "l"), (r"\b(millilitres?|milliliters?|mls?)\b", "ml"),
    (r"\b(kilograms?|kilos?|kgs)\b", "kg"), (r"\b(grams?|gms?|grms?|gr)\b", "g"),
    (r"\b(pieces?|pcs?|nos?)\b", "pcs"), (r"\b(packets?|pkts?|pkt)\b", "pack"),
]
_STOP = {"the", "and", "of", "with", "new", "a", "pcs", "x"}
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ml|l|kg|g|pcs|pack)\b")


def normalize(name):
    s = str(name or "").translate(_AR_DIGITS).lower()
    s = s.replace("×", " x ").replace("*", " x ")
    s = re.sub(r"[^\w\s.]", " ", s)
    s = re.sub(r"(\d)([a-z])", r"\1 \2", s)          # 1l → 1 l, 500ml → 500 ml
    for pat, rep in _UNIT_ALIASES:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s+", " ", s).strip()


def size_of(name):
    """'Milk 1 Litre' → ('1', 'l');  None when no size."""
    m = _SIZE_RE.search(normalize(name))
    if not m:
        return None
    num, unit = float(m.group(1)), m.group(2)
    if unit == "ml" and num >= 1000:
        num, unit = num / 1000, "l"
    if unit == "g" and num >= 1000:
        num, unit = num / 1000, "kg"
    return (f"{num:g}", unit)


def _tokens(name):
    n = _SIZE_RE.sub(" ", normalize(name))
    return [t for t in n.split() if t not in _STOP and not t.replace(".", "").isdigit()]


def similarity(a, b):
    """0..1 — words in common + spelling closeness (sizes ignored)."""
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return 0.0
    jac = len(ta & tb) / len(ta | tb)
    seq = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return round(0.55 * jac + 0.45 * seq, 3)


def _products(exclude_id=None):
    rows = _q("SELECT p.product_id, p.product_code, p.product_name_en, p.product_name_ar, "
              "p.category_id, p.vat_category_id, p.unit_of_measure_en, p.barcode, "
              "p.unit_price, ISNULL(p.is_active,1) AS is_active "
              "FROM products p")
    return [r for r in rows if r["product_id"] != exclude_id]


# ── #3 duplicates ────────────────────────────────────────────
def find_duplicates(name_en, name_ar="", barcode="", exclude_id=None, limit=3, rows=None):
    """Existing products that look like the same item: same barcode, or a
    very close name with the same size. [{product, score, why}]"""
    name_en = str(name_en or "").strip()
    out = []
    bc = str(barcode or "").strip()
    if bc:
        hits = _q("SELECT DISTINCT product_id FROM product_units WHERE barcode=?", (bc,))
        hit_ids = {h["product_id"] for h in hits}
    else:
        hit_ids = set()
    my_size = size_of(name_en)
    for p in rows if rows is not None else _products(exclude_id):
        if p["product_id"] == exclude_id:
            continue
        if bc and (p.get("barcode") == bc or p["product_id"] in hit_ids):
            out.append({"product": p, "score": 1.0, "why": f"same barcode {bc}"})
            continue
        if not name_en or not p["product_name_en"]:
            continue
        ps = size_of(p["product_name_en"])
        if my_size and ps and my_size != ps:
            continue                                # Milk 1L ≠ Milk 2L
        sc = similarity(name_en, p["product_name_en"])
        if normalize(name_en) == normalize(p["product_name_en"]):
            sc = 1.0
        ar = str(name_ar or "").strip()
        if ar and ar == str(p.get("product_name_ar") or "").strip():
            sc = max(sc, 0.95)
        if sc >= 0.78:
            out.append({"product": p, "score": sc,
                        "why": "same name" if sc >= 0.999 else f"{int(sc * 100)}% similar name"})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


# ── #4 auto-fill from similar products ───────────────────────
def suggest_from_similar(name_en, exclude_id=None, min_score=0.34):
    """Category, VAT, sales unit, extra units (Box = 12 …) and brand used
    by the closest existing products. None when nothing is similar."""
    name_en = str(name_en or "").strip()
    if len(name_en) < 3:
        return None
    scored = []
    for p in _products(exclude_id):
        sc = similarity(name_en, p["product_name_en"])
        if sc >= min_score:
            scored.append((sc, p))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    top = [p for _s, p in scored[:5]]

    def vote(key):
        vals = [p.get(key) for p in top if p.get(key) not in (None, "")]
        return Counter(vals).most_common(1)[0][0] if vals else None
    cat_id, vat_id, unit = vote("category_id"), vote("vat_category_id"), vote("unit_of_measure_en")
    best = top[0]
    extra = []
    for u in _q("SELECT unit_name_en, conversion_factor FROM product_units "
                "WHERE product_id=? AND ISNULL(is_active,1)=1 ORDER BY conversion_factor",
                (best["product_id"],)):
        if _f(u.get("conversion_factor")) > 1:
            extra.append((u["unit_name_en"], _f(u["conversion_factor"])))
    brand = None
    try:
        b = db.fetchone("SELECT brand_id FROM products WHERE product_id=?", (best["product_id"],))
        brand = (b or {}).get("brand_id")
    except Exception:
        brand = None
    cat = next((c for c in _q("SELECT category_id, category_name_en FROM product_categories")
                if c["category_id"] == cat_id), None)
    vat = next((v for v in _q("SELECT vat_category_id, category_code, category_name_en, vat_rate "
                               "FROM vat_categories") if v["vat_category_id"] == vat_id), None)
    sup = _q("SELECT TOP 1 s.supplier_name_en AS name FROM purchase_invoice_lines l "
             "JOIN purchase_invoices pi ON pi.purchase_id=l.purchase_id "
             "JOIN suppliers s ON s.supplier_id=pi.supplier_id "
             "WHERE l.product_id=? ORDER BY pi.purchase_id DESC", (best["product_id"],))
    return {"based_on": [p["product_name_en"] for p in top[:3]], "score": scored[0][0],
            "category_id": cat_id, "category_name": cat["category_name_en"] if cat else None,
            "vat_category_id": vat_id, "vat": vat, "unit": unit, "extra_units": extra,
            "brand_id": brand, "supplier": sup[0]["name"] if sup else None}


# ── #9 offline translation (grocery words) ───────────────────
WORDS = {
    # dairy & breakfast
    "milk": "حليب", "laban": "لبن", "yoghurt": "زبادي", "yogurt": "زبادي",
    "cheese": "جبن", "cream": "كريمة", "butter": "زبدة", "egg": "بيض", "eggs": "بيض",
    "labneh": "لبنة", "ghee": "سمن", "honey": "عسل", "jam": "مربى", "cornflakes": "كورن فليكس",
    "oats": "شوفان", "bread": "خبز", "toast": "توست", "croissant": "كرواسون", "cake": "كيك",
    # staples
    "rice": "أرز", "sugar": "سكر", "salt": "ملح", "flour": "دقيق", "oil": "زيت",
    "pasta": "مكرونة", "macaroni": "مكرونة", "spaghetti": "سباغيتي", "noodles": "نودلز",
    "lentils": "عدس", "lentil": "عدس", "beans": "فول", "chickpeas": "حمص", "hummus": "حمص",
    "tea": "شاي", "coffee": "قهوة", "dates": "تمر", "date": "تمر", "spices": "بهارات",
    "pepper": "فلفل", "cumin": "كمون", "cardamom": "هيل", "saffron": "زعفران",
    "vinegar": "خل", "ketchup": "كاتشب", "mayonnaise": "مايونيز", "sauce": "صلصة",
    "tomato": "طماطم", "paste": "معجون", "tuna": "تونة", "sardines": "سردين",
    "corn": "ذرة", "peas": "بازلاء", "olives": "زيتون", "olive": "زيتون",
    "sunflower": "دوار الشمس", "corn oil": "زيت ذرة", "chocolate": "شوكولاتة",
    "biscuits": "بسكويت", "biscuit": "بسكويت", "chips": "شيبس", "candy": "حلوى",
    "nuts": "مكسرات", "almonds": "لوز", "pistachio": "فستق",
    # drinks
    "water": "مياه", "juice": "عصير", "drink": "مشروب", "soda": "صودا",
    "orange": "برتقال", "apple": "تفاح", "mango": "مانجو", "lemon": "ليمون",
    "strawberry": "فراولة", "banana": "موز", "grape": "عنب", "pineapple": "أناناس",
    "guava": "جوافة", "pomegranate": "رمان", "mixed": "مشكل", "fruit": "فواكه", "fruits": "فواكه",
    # meat & veg
    "chicken": "دجاج", "meat": "لحم", "beef": "لحم بقري", "lamb": "لحم ضأن", "fish": "سمك",
    "shrimp": "روبيان", "breast": "صدور", "wings": "أجنحة", "thighs": "أفخاذ",
    "potato": "بطاطس", "potatoes": "بطاطس", "onion": "بصل", "garlic": "ثوم",
    "cucumber": "خيار", "carrot": "جزر", "lettuce": "خس", "vegetables": "خضروات",
    # household
    "detergent": "منظف", "soap": "صابون", "shampoo": "شامبو", "tissue": "مناديل",
    "tissues": "مناديل", "toothpaste": "معجون أسنان", "diapers": "حفاضات",
    "bleach": "مبيض", "dishwashing": "غسيل الصحون", "liquid": "سائل", "powder": "بودرة",
    "foil": "ورق ألمنيوم", "bags": "أكياس", "bag": "كيس",
    # packs
    "box": "علبة", "carton": "كرتون", "pack": "عبوة", "bottle": "قارورة", "can": "علبة",
    "jar": "برطمان", "sachet": "كيس", "piece": "حبة", "dozen": "دزينة",
}
ADJ = {
    "fresh": "طازج", "full": "كامل", "fat": "الدسم", "low": "قليل", "light": "لايت",
    "skimmed": "خالي الدسم", "frozen": "مجمد", "red": "أحمر", "green": "أخضر",
    "white": "أبيض", "brown": "بني", "black": "أسود", "sweet": "حلو", "hot": "حار",
    "spicy": "حار", "small": "صغير", "large": "كبير", "big": "كبير", "mini": "صغير",
    "long": "طويل", "grain": "الحبة", "plain": "سادة", "natural": "طبيعي",
    "organic": "عضوي", "premium": "ممتاز", "extra": "إكسترا", "virgin": "بكر",
    "basmati": "بسمتي", "sella": "سيلا", "pure": "نقي", "family": "عائلي",
    "classic": "كلاسيك", "original": "أصلي", "salted": "مملح", "unsalted": "غير مملح",
}
BRANDS = {
    "almarai": "المراعي", "nadec": "نادك", "alsafi": "الصافي", "al safi": "الصافي",
    "nestle": "نستله", "nido": "نيدو", "puck": "بوك", "kdd": "كي دي دي", "rani": "راني",
    "pepsi": "بيبسي", "coca": "كوكا", "cola": "كولا", "lipton": "ليبتون",
    "nescafe": "نسكافيه", "lays": "ليز", "galaxy": "جالكسي", "kitkat": "كيت كات",
    "afia": "عافية", "noor": "نور", "abu kass": "أبو كاس", "alwatania": "الوطنية",
    "fakieh": "فقيه", "sadia": "ساديا", "doux": "دو", "americana": "أمريكانا",
    "tide": "تايد", "ariel": "أريال", "persil": "برسيل", "clorox": "كلوركس",
    "fine": "فاين", "pampers": "بامبرز", "nova": "نوفا", "berain": "بيرين",
    "aquafina": "أكوافينا", "mirinda": "ميرندا", "7up": "سفن أب", "sun top": "صن توب",
}
PACKS = {"box", "carton", "pack", "bottle", "can", "jar", "sachet", "piece", "dozen", "bag"}
UNITS_AR = {"l": "لتر", "ml": "مل", "kg": "كجم", "g": "جم", "pcs": "حبة", "pack": "عبوة"}


def translate_offline(name_en):
    """Fresh Milk 1L → حليب طازج 1 لتر (dictionary + word order; unknown
    words / brands are written in Arabic letters)."""
    try:
        from modules.arabic_translit import transliterate_word
    except Exception:
        def transliterate_word(w):            # noqa
            return w
    s = normalize(name_en)
    if not s:
        return ""
    # two-word brands / words first
    phrases = {**{k: v for k, v in BRANDS.items() if " " in k},
               **{k: v for k, v in WORDS.items() if " " in k}}
    for k, v in phrases.items():
        s = re.sub(rf"\b{re.escape(k)}\b", "§" + v.replace(" ", "_"), s)
    toks = s.split()
    brand, nouns, adjs, packs, sizes = [], [], [], [], []
    i = 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if t.startswith("§"):
            (brand if t[1:].replace("_", " ") in BRANDS.values() else nouns).append(
                t[1:].replace("_", " "))
        elif re.fullmatch(r"\d+(\.\d+)?", t) and nxt in UNITS_AR:
            sizes.append(f"{t} {UNITS_AR[nxt]}"); i += 1
        elif re.fullmatch(r"\d+(\.\d+)?", t):
            sizes.append(t)
        elif t == "x" and sizes:
            sizes.append("×")
        elif t in BRANDS:
            brand.append(BRANDS[t])
        elif t in PACKS:
            packs.append(WORDS[t])
        elif t in WORDS:
            nouns.append(WORDS[t])
        elif t in ADJ:
            adjs.append(ADJ[t])
        elif t in UNITS_AR:
            sizes.append(UNITS_AR[t])
        elif t not in _STOP:
            brand.append(transliterate_word(t))     # unknown = brand / name
        i += 1
    # Arabic order: main noun first (English puts it last), then the
    # other nouns, brand, adjectives, pack, size:
    #   Afia Sunflower Oil 1.5L → زيت دوار الشمس عافية 1.5 لتر
    parts = nouns[::-1] + brand + adjs + packs + sizes
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def translate(names, to="ar", use_ai=True):
    """[names] → [translations]: online AI when set up, else offline.
    Returns (list, source) where source is 'ai' or 'offline'."""
    if use_ai:
        try:
            from modules import ai_client
            if ai_client.enabled():
                return ai_client.translate_names(names, to=to), "ai"
        except Exception:
            pass
    if to != "ar":
        return list(names), "offline"
    return [translate_offline(n) for n in names], "offline"


# ── #13 clean-up assistant ───────────────────────────────────
_LATIN = re.compile(r"[A-Za-z]")
_ARABIC = re.compile(r"[؀-ۿ]")


def cleanup_scan(include_dupes=True):
    """Problems in the product list. Each issue:
    {id, kind, product_id, code, name, problem, fix_label, fix (dict|None)}
    fix=None → info only (open the product to fix)."""
    prods = _q("SELECT p.product_id, p.product_code, p.product_name_en, p.product_name_ar, "
               "p.category_id, p.vat_category_id, p.unit_price, p.barcode, "
               "ISNULL(p.product_type,'product') AS product_type, "
               "ISNULL(p.purchase_price,0) AS purchase_price, ISNULL(p.average_cost,0) AS average_cost "
               "FROM products p WHERE ISNULL(p.is_active,1)=1")
    if not prods:       # older databases without cost columns
        prods = _q("SELECT p.product_id, p.product_code, p.product_name_en, p.product_name_ar, "
                   "p.category_id, p.vat_category_id, p.unit_price, p.barcode, "
                   "ISNULL(p.product_type,'product') AS product_type FROM products p "
                   "WHERE ISNULL(p.is_active,1)=1")
    vats = {v["vat_category_id"]: v for v in _q(
        "SELECT vat_category_id, category_code, vat_rate FROM vat_categories")}
    unit_bc = {}
    for u in _q("SELECT product_id, barcode FROM product_units "
                "WHERE barcode IS NOT NULL AND barcode<>'' AND ISNULL(is_active,1)=1"):
        unit_bc.setdefault(u["barcode"], set()).add(u["product_id"])
    has_bc = {pid for ids in unit_bc.values() for pid in ids}
    issues = []

    def add(kind, p, problem, fix_label="", fix=None):
        issues.append({"id": f"{kind}:{p['product_id']}", "kind": kind,
                       "product_id": p["product_id"], "code": p.get("product_code", ""),
                       "name": p.get("product_name_en", ""), "problem": problem,
                       "fix_label": fix_label, "fix": fix})

    # category VAT majority (≥3 items, ≥75 %)
    by_cat = {}
    for p in prods:
        if p.get("category_id") and p.get("vat_category_id"):
            by_cat.setdefault(p["category_id"], []).append(p["vat_category_id"])
    cat_vat = {}
    for cid, vids in by_cat.items():
        v, n = Counter(vids).most_common(1)[0]
        if len(vids) >= 3 and n / len(vids) >= 0.75:
            cat_vat[cid] = v

    for p in prods:
        en = str(p.get("product_name_en") or "").strip()
        ar = str(p.get("product_name_ar") or "").strip()
        # Arabic name missing / copied from English
        if not ar or ar == en or (_LATIN.search(ar) and not _ARABIC.search(ar)):
            add("arabic", p, "Arabic name missing or in English letters",
                "Translate to Arabic", {"action": "arabic"})
        # no category
        if not p.get("category_id"):
            add("category", p, "No category")
        # VAT different from the rest of its category
        cv = cat_vat.get(p.get("category_id"))
        if cv and p.get("vat_category_id") and p["vat_category_id"] != cv:
            mine = vats.get(p["vat_category_id"], {})
            want = vats.get(cv, {})
            add("vat", p, f"VAT {_f(mine.get('vat_rate')):g}% but its category uses "
                          f"{_f(want.get('vat_rate')):g}%",
                f"Set VAT {_f(want.get('vat_rate')):g}%", {"action": "vat", "vat_category_id": cv})
        if not p.get("vat_category_id"):
            add("vat", p, "No VAT category")
        # barcode
        if (p.get("product_type") != "service" and not str(p.get("barcode") or "").strip()
                and p["product_id"] not in has_bc):
            add("barcode", p, "No barcode (cannot be scanned at the POS)")
        # prices
        price = _f(p.get("unit_price"))
        cost = _f(p.get("average_cost")) or _f(p.get("purchase_price"))
        if price <= 0 and p.get("product_type") != "service":
            add("price", p, "Selling price is 0")
        elif cost > 0 and price > 0:
            rate = _f(vats.get(p.get("vat_category_id"), {}).get("vat_rate", 15))
            try:
                from config import settings as cfg
                incl = cfg.sales_price_includes_vat()
            except Exception:
                incl = True
            net = price / (1 + rate / 100) if incl else price
            if net >= cost * 8:
                for div in (10, 100):
                    if cost <= net / div <= cost * 3:
                        add("price", p, f"Price {price:g} looks {div}× too high (cost {cost:g})",
                            f"Change price to {price / div:g}",
                            {"action": "price", "price": round(price / div, 2)})
                        break
                else:
                    add("price", p, f"Price {price:g} is {net / cost:.0f}× the cost {cost:g}")
            elif net < cost:
                for mul in (10, 100):
                    if cost <= net * mul <= cost * 3:
                        add("price", p, f"Price {price:g} looks {mul}× too low (cost {cost:g})",
                            f"Change price to {price * mul:g}",
                            {"action": "price", "price": round(price * mul, 2)})
                        break
                else:
                    add("price", p, f"Selling below cost ({price:g} vs cost {cost:g} + VAT)")

    # same barcode on two products
    for bc, ids in unit_bc.items():
        if len(ids) > 1:
            for pid in sorted(ids):
                p = next((x for x in prods if x["product_id"] == pid), None)
                if p:
                    others = [x["product_name_en"] for x in prods
                              if x["product_id"] in ids and x["product_id"] != pid]
                    add("barcode", p, f"Barcode {bc} is also on: {', '.join(others)[:60]}")

    # possible duplicates (pairs, each reported once)
    if include_dupes:
        seen = set()
        for p in prods:
            for d in find_duplicates(p["product_name_en"], exclude_id=p["product_id"], rows=prods):
                q = d["product"]
                key = tuple(sorted((p["product_id"], q["product_id"])))
                if key in seen or d["why"].startswith("same barcode"):
                    continue
                seen.add(key)
                add("duplicate", p, f"Possible duplicate of {q['product_code']} "
                                    f"{q['product_name_en']} ({d['why']})")
    order = {"price": 0, "vat": 1, "duplicate": 2, "barcode": 3, "arabic": 4, "category": 5,
             "spelling": 6}
    issues.sort(key=lambda x: (order.get(x["kind"], 9), x["code"]))
    return issues


def spelling_issues(limit=300):
    """Online AI spelling check of English names (Clean-up ▸ ✨ Spelling)."""
    from modules import ai_client
    prods = _q("SELECT product_id, product_code, product_name_en FROM products "
               "WHERE ISNULL(is_active,1)=1 ORDER BY product_id")[:limit]
    issues = []
    for start in range(0, len(prods), 80):
        chunk = prods[start:start + 80]
        fixes = ai_client.spelling_fixes([p["product_name_en"] for p in chunk])
        for i, fixed in fixes.items():
            p = chunk[i]
            issues.append({"id": f"spelling:{p['product_id']}", "kind": "spelling",
                           "product_id": p["product_id"], "code": p["product_code"],
                           "name": p["product_name_en"],
                           "problem": f"Spelling: “{p['product_name_en']}” → “{fixed}”",
                           "fix_label": "Use the corrected name",
                           "fix": {"action": "rename", "name": fixed}})
    return issues


def apply_fix(issue, arabic=None):
    """Apply one approved fix. arabic: the translated name (for 'arabic').
    Returns (ok, message)."""
    fx = issue.get("fix") or {}
    pid = issue["product_id"]
    try:
        if fx.get("action") == "arabic":
            if not arabic:
                return False, "No Arabic name"
            db.execute("UPDATE products SET product_name_ar=? WHERE product_id=?", (arabic, pid))
        elif fx.get("action") == "vat":
            db.execute("UPDATE products SET vat_category_id=? WHERE product_id=?",
                       (fx["vat_category_id"], pid))
        elif fx.get("action") == "price":
            old = db.fetchone("SELECT unit_price FROM products WHERE product_id=?", (pid,)) or {}
            db.execute("UPDATE products SET unit_price=? WHERE product_id=?", (fx["price"], pid))
            # keep the base unit's price in step
            try:
                db.execute("UPDATE product_units SET selling_price=? WHERE product_id=? "
                           "AND conversion_factor=1 AND selling_price=?",
                           (fx["price"], pid, old.get("unit_price")))
            except Exception:
                pass
        elif fx.get("action") == "rename":
            db.execute("UPDATE products SET product_name_en=? WHERE product_id=?", (fx["name"], pid))
        else:
            return False, "Nothing to fix automatically"
    except Exception as e:
        return False, str(e)[:160]
    try:
        from modules import audit
        audit.log("product_ai_fix", "products", pid, f"{issue['kind']}: {issue['problem']}")
    except Exception:
        pass
    return True, "Fixed"


# ── #11 supplier invoice → match / create products ───────────
def match_supplier(name, vat_no=""):
    """Existing supplier for the invoice header (VAT no., then name)."""
    sups = _q("SELECT supplier_id, supplier_code, supplier_name_en, "
              "ISNULL(vat_registration_no,'') AS vat FROM suppliers WHERE ISNULL(is_active,1)=1")
    if not sups:
        sups = _q("SELECT supplier_id, supplier_code, supplier_name_en, '' AS vat FROM suppliers")
    v = "".join(ch for ch in str(vat_no or "") if ch.isdigit())
    if v:
        hit = next((s for s in sups if "".join(ch for ch in str(s["vat"]) if ch.isdigit()) == v), None)
        if hit:
            return hit
    best, bs = None, 0.0
    for s in sups:
        sc = similarity(name, s["supplier_name_en"])
        if sc > bs:
            best, bs = s, sc
    return best if bs >= 0.5 else None


def match_line(ln, rows=None):
    """{product_id, unit_name, how} for one invoice line, or None (new)."""
    bc = str(ln.get("barcode") or "").strip()
    if bc:
        try:
            from modules.product_lookup import barcode_owner
            o = barcode_owner(bc)
        except Exception:
            o = None
        if o:
            return {"product_id": o["product_id"], "unit_name": o.get("unit_name") or None,
                    "how": "barcode", "name": o["product_name"]}
    d = find_duplicates(ln.get("description"), ln.get("name_ar") or "", "",
                        rows=rows if rows is not None else _products(), limit=1)
    if d and d[0]["score"] >= 0.8:
        p = d[0]["product"]
        return {"product_id": p["product_id"], "unit_name": None, "how": "name",
                "name": p["product_name_en"]}
    return None


def _next_code():
    try:      # last created product's code + 1, unique in any format
        from modules.product_lookup import next_product_code
        return next_product_code()
    except Exception:
        pass
    mx = 0
    for r in _q("SELECT product_code FROM products"):
        c = str(r.get("product_code") or "").strip()
        if c.isdigit():
            mx = max(mx, int(c))
    return str(mx + 1) if mx else "1001"


def _product_cols():
    try:
        r = db.fetchone("SELECT TOP 1 * FROM products")
        if r:
            return set(dict(r).keys())
    except Exception:
        pass
    try:
        return {c["COLUMN_NAME"] for c in _q(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='products'")}
    except Exception:
        return set()


def selling_price_from_cost(cost_excl, vat_rate, markup_pct=None):
    """Suggested selling price (in the shop's price mode) from the cost."""
    try:
        from config import settings as cfg
        m = float(markup_pct if markup_pct is not None else cfg.get("ai_markup_pct", 25) or 25)
        incl = cfg.sales_price_includes_vat()
    except Exception:
        m, incl = 25.0, True
    net = _f(cost_excl) * (1 + m / 100.0)
    price = net * (1 + _f(vat_rate) / 100.0) if incl else net
    return round(price + 1e-9, 2)


def create_product(name_en, name_ar, category_id, vat_category_id, cost_base_excl,
                   sell_price, barcode="", pack=None, brand_id=None):
    """New product (base unit PCs) + optional pack unit (name, factor).
    Returns product_id."""
    from modules.barcode_gen import new_unique_barcode
    cols = _product_cols()
    code = _next_code()
    data = {"product_code": code, "product_name_en": name_en.strip()[:200],
            "product_name_ar": (name_ar or name_en).strip()[:200],
            "category_id": category_id, "product_type": "product",
            "unit_price": round(_f(sell_price), 2), "currency": "SAR",
            "unit_of_measure_en": "PCs", "unit_of_measure_ar": "حبة",
            "vat_category_id": vat_category_id, "barcode": None,
            "track_inventory": 1, "stock_quantity": 0, "reorder_level": 0, "is_active": 1}
    for k, v in (("purchase_price", round(_f(cost_base_excl), 2)),
                 ("list_in_sales", 1), ("list_in_purchase", 1), ("brand_id", brand_id)):
        if k in cols:
            data[k] = v
    db.execute(f"INSERT INTO products ({', '.join(data)}) VALUES ({', '.join('?' * len(data))})",
               tuple(data.values()))
    pid = db.execute_scalar("SELECT product_id FROM products WHERE product_code=?", (code,))
    try:
        from config import settings as _cfg
        locked = _cfg.flag("barcode_system_locked", True)
    except Exception:
        locked = False
    maker_base = barcode or ""
    maker_pack = (pack[2] if pack and len(pack) > 2 else "") or ""
    from modules.barcode_gen import has_system_column, new_system_barcode
    sys_on = has_system_column()
    if sys_on:
        # v6.9.5: the product's own 5-digit system barcode; the maker's barcode
        # is the product's Barcode (manual); the piece scans with both
        bc_base = new_system_barcode(exclude=[maker_base, maker_pack])
        db.execute("UPDATE products SET system_barcode=?, barcode=? WHERE product_id=?",
                   (bc_base, maker_base or None, pid))
    elif locked:
        # system barcodes (6 digits) on the product + units; the barcode
        # printed by the maker goes in as an EXTRA barcode, so it scans too
        bc_base = new_unique_barcode(exclude=[maker_base, maker_pack])
    else:
        bc_base = maker_base or new_unique_barcode()
    if not sys_on:
        db.execute("UPDATE products SET barcode=? WHERE product_id=?", (bc_base, pid))
    units = [("PCs", 1.0, _f(sell_price), _f(cost_base_excl), bc_base, 1, 0 if pack else 1)]
    if pack and _f(pack[1]) > 1:
        f_ = _f(pack[1])
        pack_bc = new_unique_barcode(exclude=[bc_base, maker_base, maker_pack]) if locked \
            else (maker_pack or new_unique_barcode(exclude=[bc_base]))
        units.append((pack[0] or "Box", f_, round(_f(sell_price) * f_, 2),
                      round(_f(cost_base_excl) * f_, 2), pack_bc, 0, 1))
    for k, (name, fac, sp, pp, bc, dflt, dpur) in enumerate(units):
        db.execute("INSERT INTO product_units (product_id, unit_name_en, conversion_factor, "
                   "selling_price, purchase_price, barcode, is_default, is_default_purchase, "
                   "is_sales_unit, is_purchase_unit, is_active) VALUES (?,?,?,?,?,?,?,?,1,1,1)",
                   (pid, name, fac, sp, pp, bc, dflt, dpur))
        maker = (("" if sys_on else maker_base) if k == 0 else maker_pack) if locked else ""
        if maker:
            try:
                uid = db.execute_scalar("SELECT MAX(unit_id) FROM product_units WHERE product_id=?",
                                        (pid,))
                db.execute("INSERT INTO product_unit_barcodes (product_id, unit_id, barcode, "
                           "is_active) VALUES (?,?,?,1)", (pid, uid, maker))
            except Exception:
                pass
    try:
        from modules import audit
        audit.log("add", "products", pid, f"{name_en} (from supplier invoice, AI)")
    except Exception:
        pass
    return pid


def default_vat_for_rate(rate):
    vats = _q("SELECT vat_category_id, vat_rate FROM vat_categories WHERE ISNULL(is_active,1)=1") \
        or _q("SELECT vat_category_id, vat_rate FROM vat_categories")
    hit = next((v for v in vats if abs(_f(v["vat_rate"]) - _f(rate)) < 0.01), None)
    return (hit or (vats[0] if vats else {})).get("vat_category_id")
