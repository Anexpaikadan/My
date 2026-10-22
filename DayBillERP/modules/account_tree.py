# ============================================================
# DayBill ERP - chart of accounts as a tree of groups (v7.0)
# ------------------------------------------------------------
# Every ledger sits UNDER a group (master): Assets › Current Assets ›
# Cash. accounts.parent_account_id links them; accounts.is_group marks a
# group (it holds ledgers; postings go to ledgers). An account that has
# accounts under it is a group too.
#
#   rows(active_only=True)   all accounts {account_id, code, name, type,
#                            parent_id, is_group, depth, path, children}
#   ordered()                the same, in tree order (parent, then its
#                            children by code)
#   items(groups_only=False, value_fmt=None)
#                            ready for ui/search_drop (tree dropdown)
#   path(account_id)         'Assets › Current Assets'
#   next_code(parent_id)     a free code under the group (1100 → 1110 …)
#   type_of(parent_id)       the account type a child of that group has
#   can_move(account_id, parent_id)  (ok, why) — never under itself
#   is_group(account_id)
# ============================================================

try:
    from config.database import db
except Exception:            # pragma: no cover
    db = None

SEP = " › "
TYPES = ("asset", "liability", "equity", "revenue", "expense")


def has_group_col():
    try:
        return db.execute_scalar("SELECT COL_LENGTH('accounts','is_group')") is not None
    except Exception:
        return False


def rows(active_only=True):
    g = ", ISNULL(is_group,0) AS is_group" if has_group_col() else ", 0 AS is_group"
    try:
        data = db.fetchall("SELECT account_id, account_code, account_name_en, account_name_ar, account_type, "
                           "parent_account_id%s, ISNULL(is_active,1) AS is_active FROM accounts%s "
                           "ORDER BY account_code" % (g, " WHERE ISNULL(is_active,1)=1" if active_only else "")) or []
    except Exception:
        data = []
    by = {}
    for r in data:
        by[r["account_id"]] = {"account_id": r["account_id"], "code": str(r["account_code"] or ""),
                               "name": r["account_name_en"] or "", "name_ar": r.get("account_name_ar") or "",
                               "type": str(r["account_type"] or "").lower(),
                               "parent_id": r.get("parent_account_id"),
                               "is_group": bool(r.get("is_group")), "children": [],
                               "active": bool(r.get("is_active", 1))}
    for a in by.values():
        p = by.get(a["parent_id"])
        if p is not None and p is not a:
            p["children"].append(a["account_id"])
        else:
            a["parent_id"] = None                   # parent missing / inactive: a top group
    for a in by.values():
        if a["children"]:
            a["is_group"] = True
    # depth + path (guarded against a loop in old data)
    for a in by.values():
        names, seen, cur = [], set(), a
        while cur["parent_id"] and cur["parent_id"] not in seen:
            seen.add(cur["parent_id"])
            cur = by[cur["parent_id"]]
            names.append(cur["name"])
        a["depth"] = len(names)
        a["path"] = SEP.join(reversed(names))
    return by


def ordered(by=None):
    by = by if by is not None else rows()
    out, seen = [], set()

    def walk(aid):
        if aid in seen:
            return
        seen.add(aid)
        out.append(by[aid])
        for c in sorted(by[aid]["children"], key=lambda x: by[x]["code"]):
            walk(c)
    for a in sorted((a for a in by.values() if not a["parent_id"]), key=lambda x: x["code"]):
        walk(a["account_id"])
    for aid in by:                                  # anything left over (a loop)
        walk(aid)
    return out


def label(a):
    return "%s · %s" % (a["code"], a["name"])


def items(groups_only=False, ledgers_only=False, by=None, value_fmt=None, active_only=True):
    """Accounts for a tree dropdown (ui/search_drop). The box gets
    value_fmt(account) — default 'CODE · Name' — so a screen keeps its
    own way of writing an account."""
    fmt = value_fmt or label
    out = []
    for a in ordered(by if by is not None else rows(active_only=active_only)):
        if groups_only and not a["is_group"]:
            continue
        out.append({"label": label(a), "value": fmt(a), "depth": a["depth"],
                    "group": a["is_group"] and not groups_only, "path": a["path"],
                    "search": a["type"] + " " + a["name_ar"], "account_id": a["account_id"],
                    "code": a["code"]})
    return out


def id_of(text, by=None):
    """'1100 · Cash' / '1100' / 'Cash' → account_id."""
    t = str(text or "").strip()
    if not t:
        return None
    code = t.split(" · ")[0].strip()
    by = by if by is not None else rows(active_only=False)
    for a in by.values():
        if a["code"] == code:
            return a["account_id"]
    for a in by.values():
        if a["name"].lower() == t.lower():
            return a["account_id"]
    return None


def path(account_id, by=None):
    by = by if by is not None else rows(active_only=False)
    a = by.get(account_id)
    return a["path"] if a else ""


def is_group(account_id, by=None):
    by = by if by is not None else rows(active_only=False)
    a = by.get(account_id)
    return bool(a and a["is_group"])


def type_of(parent_id, by=None):
    """A child takes the type of its group (Assets → asset …)."""
    by = by if by is not None else rows(active_only=False)
    a = by.get(parent_id)
    return a["type"] if a and a["type"] in TYPES else None


def can_move(account_id, parent_id, by=None):
    if not parent_id:
        return True, ""
    if account_id and int(parent_id) == int(account_id):
        return False, "An account cannot be under itself."
    by = by if by is not None else rows(active_only=False)
    cur, seen = by.get(parent_id), set()
    while cur is not None and cur["parent_id"] and cur["account_id"] not in seen:
        seen.add(cur["account_id"])
        if account_id and cur["parent_id"] == account_id:
            return False, "That group is inside this account — pick another group."
        cur = by.get(cur["parent_id"])
    return True, ""


def _step(code):
    """Codes of a group's children: 1000 → 100 (1100, 1200), 2200 → 10,
    2210 → 1; None when the group code has no zero left at the end."""
    if not code.isdigit():
        return None
    zeros = len(code) - len(code.rstrip("0"))
    if zeros == 0:
        return None
    return 10 ** (zeros - 1)


def next_code(parent_id, by=None):
    by = by if by is not None else rows(active_only=False)
    used = {a["code"] for a in by.values()}
    p = by.get(parent_id) if parent_id else None
    if p is None:
        tops = sorted((a["code"] for a in by.values() if not a["parent_id"] and a["code"].isdigit()), key=int)
        n = (int(tops[-1]) + 1000) if tops else 1000
        while str(n) in used:
            n += 1000
        return str(n)
    kids = sorted((by[c]["code"] for c in p["children"] if by[c]["code"].isdigit()), key=lambda x: (len(x), int(x)))
    step = _step(p["code"])
    prefix = p["code"].rstrip("0") or p["code"]
    if kids:
        width = len(kids[-1])
        n = int(kids[-1]) + (step or 1)
        while str(n).zfill(width) in used:
            n += (step or 1)
        cand = str(n).zfill(width)
        if cand.startswith(prefix):               # still inside the group's numbers
            return cand
    if step is not None:
        n = int(p["code"]) + step
        cand = str(n)
        while cand in used:
            n += step
            cand = str(n)
        return cand
    i = 1
    while True:                                     # 2211 → 221101, 221102 …
        cand = "%s%02d" % (p["code"], i)
        if cand not in used:
            return cand
        i += 1
