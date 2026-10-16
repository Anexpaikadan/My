# ============================================================
# DayBill ERP - Smart Product Search
# Token-prefix matching: "pe co 25" → "Pepsi Cola 250 ml"
# Searches across name, alias, code, barcode.
# ============================================================


def _normalize(text: str) -> list:
    """Split text into lowercase word tokens, treating - / . as spaces."""
    if not text:
        return []
    t = str(text).lower()
    for ch in "-/.,()[]":
        t = t.replace(ch, " ")
    return [w for w in t.split() if w]


def smart_match(query: str, *fields) -> bool:
    """
    True if EVERY token in the query is a prefix of some word across the
    combined fields (name, alias, code, barcode...).

    "pe co 25" matches "Pepsi Cola 250 ml" because
      pe→pepsi, co→cola, 25→250.
    Also matches mid-word as a fallback (substring), so "ola" finds "cola".
    """
    q_tokens = _normalize(query)
    if not q_tokens:
        return True
    words = []
    for f in fields:
        words.extend(_normalize(f))
    if not words:
        return False
    for token in q_tokens:
        if any(w.startswith(token) for w in words):
            continue
        if any(token in w for w in words):   # substring fallback
            continue
        return False
    return True


def smart_score(query: str, *fields) -> int:
    """
    Relevance score for ranking (higher = better). Used to sort results.
    Exact word-prefix matches score higher than substring matches.
    """
    q_tokens = _normalize(query)
    if not q_tokens:
        return 0
    words = []
    for f in fields:
        words.extend(_normalize(f))
    score = 0
    for token in q_tokens:
        best = 0
        for w in words:
            if w == token:
                best = max(best, 100)          # exact word
            elif w.startswith(token):
                best = max(best, 60)           # word starts with token
            elif token in w:
                best = max(best, 20)           # substring
        score += best
    # Bonus if the first field (name) starts with the first token
    name_words = _normalize(fields[0]) if fields else []
    if name_words and q_tokens and name_words[0].startswith(q_tokens[0]):
        score += 30
    return score


def filter_products(query: str, products: list,
                    name_keys=("product_name_en", "product_name_ar"),
                    extra_keys=("alias_name", "product_code", "barcode")) -> list:
    """
    Filter + rank a list of product dicts by the query.
    Returns the matching products sorted by relevance.
    """
    keys = list(name_keys) + list(extra_keys)
    matched = []
    for p in products:
        fields = [p.get(k, "") for k in keys]
        if smart_match(query, *fields):
            matched.append((smart_score(query, *fields), p))
    matched.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in matched]


# ── Self-test ──────────────────────────────────────────────────
if __name__ == "__main__":
    products = [
        {"product_name_en": "Pepsi Cola 250 ml", "alias_name": "PC250", "product_code": "P001"},
        {"product_name_en": "Pepsi Cola 1 Litre", "alias_name": "PC1L", "product_code": "P002"},
        {"product_name_en": "Coca Cola 250 ml", "alias_name": "CC250", "product_code": "P003"},
        {"product_name_en": "Water Bottle 500 ml", "alias_name": "WB500", "product_code": "P004"},
    ]
    tests = [
        ("pe co 25", "Pepsi Cola 250 ml"),
        ("pepsi", "Pepsi Cola 250 ml"),
        ("co 25", "Pepsi Cola 250 ml"),    # both pepsi & coca match; ranking matters
        ("PC250", "Pepsi Cola 250 ml"),    # alias
        ("water", "Water Bottle 500 ml"),
    ]
    for q, expected in tests:
        res = filter_products(q, products)
        names = [p["product_name_en"] for p in res]
        print(f"  '{q}' → {names}")
        assert expected in names, f"FAIL: '{q}' expected {expected}"
    # "pe co 25" must ONLY match pepsi (not coca/water)
    r = [p["product_name_en"] for p in filter_products("pe co 25", products)]
    assert r == ["Pepsi Cola 250 ml"], f"FAIL: {r}"
    print("Smart search VERIFIED ✅")
