# ============================================================
# DayBill ERP - Online forms (Tally or Jotform) (v6.8, Jotform v6.9)
# ------------------------------------------------------------
# Customers and suppliers fill a Tally web form on their phone
# (link, WhatsApp, or a QR code on the receipt). DayBill brings the
# answers in:
#   • Customer registration → review → becomes a customer
#   • Supplier registration → review → becomes a supplier
#   • "How was your visit?" → star rating + comment, linked to the bill
# Nothing is added on its own: every new entry waits in
# Customers ▸ 🌐 Online forms until someone opens it and saves.
#
# Settings ▸ Online forms:
#   tally_api_key        – Tally ▸ Settings ▸ API keys (kept only on this PC)
#   tally_form_customer  – form ID or link, e.g. https://tally.so/r/4aXjl5
#   tally_form_supplier
#   tally_form_feedback
#   receipt_feedback_qr  – print "Rate your visit" QR on POS receipts
#
# v6.9 — Jotform works the same way (forms_provider = "jotform"):
#   jotform_api_key        – Jotform ▸ Settings ▸ API ▸ Create New Key
#   jotform_form_customer  – form ID or link, e.g. https://form.jotform.com/2610…
#   jotform_form_supplier / jotform_form_feedback
#   jotform_region         – "us" (default) or "eu" (eu.jotform.com accounts)
# Questions are read by their title exactly as for Tally; the feedback
# form's hidden boxes are named bill and branch (?bill=… in the link).
# ============================================================
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

try:
    from config import settings as cfg
except Exception:                                   # pragma: no cover
    cfg = None

API = "https://api.tally.so"
API_VERSION = "2025-02-01"

KINDS = {
    "customer": ("tally_form_customer", "Customer registration", "تسجيل عميل"),
    "supplier": ("tally_form_supplier", "Supplier registration", "تسجيل مورد"),
    "feedback": ("tally_form_feedback", "Customer feedback", "تقييم العملاء"),
}
JOT_KEYS = {"customer": "jotform_form_customer", "supplier": "jotform_form_supplier",
            "feedback": "jotform_form_feedback"}
PROVIDERS = (("tally", "Tally (tally.so)"), ("jotform", "Jotform (jotform.com)"))

# Tally question title (English part, before " · ") → DayBill field.
# Matched by words, so a title can be reworded a little.
CUSTOMER_MAP = [
    (r"customer type|type", "customer_type"),
    (r"name.*arab|arabic", "customer_name_ar"),
    (r"name", "customer_name_en"),
    (r"mobile|phone", "phone"),
    (r"e-?mail", "email"),
    (r"vat", "vat_registration_no"),
    (r"\bcr\b|commercial", "cr_number"),
    (r"building", "building_number"),
    (r"street", "street_name_en"),
    (r"district", "district_en"),
    (r"city", "city_en"),
    (r"postal|zip", "postal_code"),
    (r"note", "notes"),
]
SUPPLIER_MAP = [
    (r"certificate|file|document", "files"),
    (r"name.*arab|arabic", "supplier_name_ar"),
    (r"company name|name", "supplier_name_en"),
    (r"contact", "contact_person_en"),
    (r"mobile|phone", "phone"),
    (r"e-?mail", "email"),
    (r"supply|products", "supplies"),
    (r"vat", "vat_registration_no"),
    (r"\bcr\b|commercial", "cr_number"),
    (r"city", "city_en"),
    (r"address", "address_en"),
    (r"iban", "iban"),
    (r"payment terms|terms", "payment_terms"),
    (r"note", "notes"),
]
FEEDBACK_MAP = [
    (r"rating|rate|stars", "rating"),
    (r"good|liked", "liked"),
    (r"comment|better", "comment"),
    (r"mobile|phone", "phone"),
    (r"^bill$|invoice", "bill"),
    (r"^branch$", "branch"),
]
MAPS = {"customer": CUSTOMER_MAP, "supplier": SUPPLIER_MAP, "feedback": FEEDBACK_MAP}


# ── settings ────────────────────────────────────────────────
def _get(key, default=""):
    try:
        return str(cfg.get(key, default) or default).strip()
    except Exception:
        return default


def provider():
    """'tally' or 'jotform' (Settings ▸ Online forms ▸ Forms from)."""
    p = _get("forms_provider").lower()
    if p.startswith("jot"):
        return "jotform"
    if p.startswith("tal"):
        return "tally"
    # not chosen yet: the one that has a key
    return "jotform" if _get("jotform_api_key") and not _get("tally_api_key") else "tally"


def provider_name():
    return dict(PROVIDERS)[provider()].split(" ")[0]


def form_id(kind):
    """The form ID for a kind — the setting may hold the ID or any link
    (tally.so/r/<id>, form.jotform.com/<id>, …)."""
    if kind not in KINDS:
        return ""
    if provider() == "jotform":
        return parse_jotform_id(_get(JOT_KEYS[kind]))
    return parse_form_id(_get(KINDS[kind][0]))


def parse_jotform_id(raw):
    """'https://form.jotform.com/261234567890123' / 'jotform.com/build/…' / the
    number itself → '261234567890123'."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = re.search(r"jotform\.com/(?:form/|build/|edit/|inbox/|tables/)?(\d{8,20})", raw)
    if m:
        return m.group(1)
    return raw if re.fullmatch(r"\d{8,20}", raw) else ""


def parse_form_id(raw):
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = re.search(r"tally\.so/(?:r|forms|embed|form)/([A-Za-z0-9]{4,12})", raw)
    if m:
        return m.group(1)
    return raw if re.fullmatch(r"[A-Za-z0-9]{4,12}", raw) else ""


def form_link(kind, **params):
    fid = form_id(kind)
    if not fid:
        return ""
    q = {k: v for k, v in params.items() if v not in (None, "")}
    tail = ("?" + urllib.parse.urlencode(q)) if q else ""
    if provider() == "jotform":
        host = "eu.jotform.com" if _get("jotform_region").lower() == "eu" else "form.jotform.com"
        return "https://%s/%s%s" % (host, fid, tail)
    return "https://tally.so/r/%s%s" % (fid, tail)


def api_key():
    return _get("jotform_api_key" if provider() == "jotform" else "tally_api_key")


def configured():
    return bool(api_key()) and any(form_id(k) for k in KINDS)


# ── Tally API ───────────────────────────────────────────────
class TallyError(Exception):
    pass


def _request(path, params=None, timeout=20):
    key = _get("tally_api_key")
    if not key:
        raise TallyError("Add your Tally API key in Settings ▸ Online forms.")
    url = API + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + key, "tally-version": API_VERSION,
        "Accept": "application/json", "User-Agent": "DayBillERP"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise TallyError("Tally did not accept the API key (%s). Make a new key in "
                             "Tally ▸ Settings ▸ API keys." % e.code)
        if e.code == 404:
            raise TallyError("Tally can't find that form — check the form ID in Settings.")
        if e.code == 429:
            raise TallyError("Tally says: too many requests. Try again in a minute.")
        raise TallyError("Tally error %s" % e.code)
    except (urllib.error.URLError, OSError) as e:
        raise TallyError("No internet connection to Tally (%s)." % getattr(e, "reason", e))


# ── Jotform API (v6.9) ──────────────────────────────────────
_JOT_SKIP = {"control_head", "control_button", "control_text", "control_divider",
             "control_pagebreak", "control_collapse", "control_image", "control_captcha"}


def _jot_request(path, params=None, timeout=20):
    key = _get("jotform_api_key")
    if not key:
        raise TallyError("Add your Jotform API key in Settings ▸ Online forms.")
    base = "https://eu-api.jotform.com" if _get("jotform_region").lower() == "eu" \
        else "https://api.jotform.com"
    q = dict(params or {})
    url = base + path + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"APIKEY": key, "Accept": "application/json",
                                               "User-Agent": "DayBillERP"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise TallyError("Jotform did not accept the API key (%s). Make a new key in "
                             "Jotform ▸ Settings ▸ API." % e.code)
        if e.code == 404:
            raise TallyError("Jotform can't find that form — check the form ID in Settings.")
        if e.code == 429:
            raise TallyError("Jotform says: too many requests (daily API limit). Try later.")
        raise TallyError("Jotform error %s" % e.code)
    except (urllib.error.URLError, OSError) as e:
        raise TallyError("No internet connection to Jotform (%s)." % getattr(e, "reason", e))
    if str(data.get("responseCode", 200)) not in ("200", "206"):
        raise TallyError("Jotform: %s" % (data.get("message") or data.get("responseCode")))
    return data


def jot_fetch(fid, max_pages=20):
    """All submissions of a Jotform form (newest first, deleted ones left out)."""
    subs, offset = [], 0
    for _ in range(max_pages):
        data = _jot_request("/form/%s/submissions" % fid,
                            {"limit": 1000, "offset": offset, "orderby": "created_at"})
        part = data.get("content") or []
        subs.extend(p for p in part if str(p.get("status", "ACTIVE")).upper() != "DELETED")
        if len(part) < 1000:
            break
        offset += 1000
    return subs


def _jot_value(a):
    """One Jotform answer → plain text (lists joined with ', ' like Tally)."""
    if isinstance(a.get("answer"), (list, tuple)):
        return answer_text(a["answer"])
    if a.get("prettyFormat") not in (None, ""):
        return re.sub(r"<[^>]+>", " ", str(a["prettyFormat"])).strip()
    val = a.get("answer")
    if isinstance(val, dict):
        if val.get("full"):                         # phone
            return str(val["full"])
        return " ".join(str(v) for v in val.values() if v not in (None, "")).strip()
    return answer_text(val)


def jot_normalize(subs):
    """Jotform submissions → [{id, submitted_at, answers: {title: text}}]
    (the same shape normalize() gives for Tally)."""
    out = []
    for s in subs or []:
        answers = {}
        items = (s.get("answers") or {}).values() if isinstance(s.get("answers"), dict) else []
        for a in sorted(items, key=lambda x: int(str(x.get("order") or 0) or 0)):
            if not isinstance(a, dict) or a.get("type") in _JOT_SKIP:
                continue
            name = str(a.get("name") or "")
            title = str(a.get("text") or name or "")
            if "answer" not in a and "prettyFormat" not in a:
                continue
            txt = _jot_value(a)
            if name.lower() in ("bill", "branch"):          # hidden boxes (?bill=…)
                answers[name.lower()] = txt
            elif title:
                answers[title] = txt
        out.append({"id": "jf-" + str(s.get("id") or ""), "answers": answers,
                    "submitted_at": str(s.get("created_at") or "")[:19]})
    return [e for e in out if e["id"] != "jf-"]


def fetch_raw(fid, max_pages=20):
    """All submissions of a form: (questions, submissions) as Tally sends them."""
    questions, subs, page = [], [], 1
    while page <= max_pages:
        data = _request("/forms/%s/submissions" % fid,
                        {"page": page, "limit": 100, "filter": "completed"})
        if page == 1:
            questions = data.get("questions") or []
        subs.extend(data.get("submissions") or [])
        if not data.get("hasMore"):
            break
        page += 1
    return questions, subs


# ── turning answers into plain text ─────────────────────────
def _english(title):
    """'Name (English) · الاسم بالإنجليزي' → 'name (english)'."""
    t = re.sub(r"<[^>]+>", "", str(title or ""))
    return t.split("·")[0].strip().lower()


def _option_texts(q):
    """{option id: text} for a choice question (any API shape)."""
    out = {}
    for f in (q.get("fields") or []):
        for o in (f.get("options") or []):
            if isinstance(o, dict) and o.get("id"):
                out[o["id"]] = o.get("text") or o.get("label") or o.get("value") or ""
    for o in (q.get("options") or []):
        if isinstance(o, dict) and o.get("id"):
            out[o["id"]] = o.get("text") or o.get("label") or ""
    return out


def answer_text(ans, options=None):
    options = options or {}
    if ans is None:
        return ""
    if isinstance(ans, bool):
        return "Yes" if ans else "No"
    if isinstance(ans, (int, float)):
        return ("%g" % ans)
    if isinstance(ans, str):
        return options.get(ans, ans)
    if isinstance(ans, dict):
        for k in ("text", "label", "value", "name", "url"):
            if ans.get(k):
                return answer_text(ans[k], options)
        return ""
    if isinstance(ans, (list, tuple)):
        parts = [answer_text(a, options) for a in ans]
        return ", ".join(p for p in parts if p)
    return str(ans)


def _first_text(s):
    """'Company · شركة' → 'Company' (the English side of a choice)."""
    return str(s or "").split("·")[0].strip()


def normalize(questions, subs):
    """[{id, submitted_at, answers: {title: text}}] — titles as written in Tally."""
    qmap = {}
    for q in questions or []:
        qmap[q.get("id")] = (q.get("title") or q.get("name") or "", _option_texts(q))
    out = []
    for s in subs or []:
        if s.get("isCompleted") is False:
            continue
        answers = {}
        for r in (s.get("responses") or []):
            title, opts = qmap.get(r.get("questionId"), ("", {}))
            if not title:
                title = r.get("questionTitle") or r.get("title") or r.get("questionId") or ""
            val = r.get("answer", r.get("value"))
            if isinstance(val, dict) and not any(k in val for k in ("text", "label", "value", "name", "url")):
                # hidden fields arrive as {"bill": "...", "branch": "..."}
                for hk, hv in val.items():
                    answers[str(hk)] = answer_text(hv)
                continue
            txt = answer_text(val, opts)
            if title in answers and txt:
                answers[title] = answers[title] + ", " + txt
            else:
                answers[title] = txt
        for hk, hv in (s.get("hiddenFields") or {}).items() if isinstance(s.get("hiddenFields"), dict) else []:
            answers.setdefault(str(hk), answer_text(hv))
        out.append({"id": str(s.get("id") or ""), "answers": answers,
                    "submitted_at": str(s.get("submittedAt") or s.get("createdAt") or "")[:19]})
    return out


def map_answers(kind, answers):
    """Tally answers → DayBill field values (first matching rule wins)."""
    rules = MAPS.get(kind, [])
    out = {}
    for title, val in (answers or {}).items():
        t = _english(title)
        for pat, field in rules:
            if field in out:
                continue
            if re.search(pat, t):
                out[field] = (val or "").strip()
                break
    if kind == "customer":
        typ = _first_text(out.get("customer_type", "")).lower()
        out["customer_type"] = "B2B" if ("company" in typ or "شركة" in str(out.get("customer_type", ""))
                                         or "b2b" in typ) else "B2C"
        if out.get("phone"):
            out["phone"] = clean_phone(out["phone"])
    if kind == "supplier":
        if out.get("phone"):
            out["phone"] = clean_phone(out["phone"])
        days = re.search(r"(\d+)", out.get("payment_terms", ""))
        out["payment_terms_days"] = days.group(1) if days else ("0" if out.get("payment_terms") else "")
        if out.get("supplies"):
            out["supplies"] = ", ".join(_first_text(x) for x in out["supplies"].split(", "))
    if kind == "feedback":
        try:
            out["rating"] = int(float(re.sub(r"[^\d.]", "", out.get("rating", "")) or 0))
        except ValueError:
            out["rating"] = 0
        if out.get("liked"):
            out["liked"] = ", ".join(_first_text(x) for x in out["liked"].split(", "))
    for k in ("vat_registration_no", "cr_number", "postal_code", "building_number", "iban"):
        if out.get(k):
            out[k] = re.sub(r"\s", "", out[k]).upper()
    return out


def clean_phone(p):
    """'+966551234567' → '0551234567' (Saudi mobiles); others unchanged."""
    d = re.sub(r"[\s\-()]", "", p or "")
    m = re.fullmatch(r"(?:\+|00)?966(5\d{8})", d)
    if m:
        return "0" + m.group(1)
    return d


# ── the inbox (table online_form_entries) ───────────────────
def _db():
    from config.database import db
    return db


def store(kind, entries):
    """Save new submissions (already-seen ones are skipped). → count added."""
    db = _db()
    n = 0
    for e in entries:
        sid = e.get("id")
        if not sid:
            continue
        if db.fetchone("SELECT entry_id FROM online_form_entries WHERE submission_id = ?", (sid,)):
            continue
        vals = map_answers(kind, e.get("answers"))
        name = vals.get("customer_name_en") or vals.get("supplier_name_en") or vals.get("comment", "")[:60]
        db.execute(
            "INSERT INTO online_form_entries (form_kind, submission_id, submitted_at, "
            "title, phone, rating, bill_no, payload_json, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')",
            (kind, sid, (e.get("submitted_at") or "").replace("T", " ")[:19] or None,
             (name or "")[:200], (vals.get("phone") or "")[:30] or None,
             vals.get("rating") if kind == "feedback" else None,
             (vals.get("bill") or "")[:40] or None,
             json.dumps({"answers": e.get("answers"), "values": vals}, ensure_ascii=False)))
        n += 1
    return n


def sync(kinds=None):
    """Bring new answers in from Tally / Jotform. → ({kind: added}, [problems])."""
    added, problems = {}, []
    jot = provider() == "jotform"
    for kind in (kinds or KINDS):
        fid = form_id(kind)
        if not fid:
            continue
        try:
            if jot:
                added[kind] = store(kind, jot_normalize(jot_fetch(fid)))
            else:
                q, s = fetch_raw(fid)
                added[kind] = store(kind, normalize(q, s))
        except TallyError as e:
            problems.append("%s: %s" % (KINDS[kind][1], e))
        except Exception as e:                          # never crash the app
            problems.append("%s: %s" % (KINDS[kind][1], str(e)[:120]))
    try:
        cfg.set("tally_last_sync", datetime.now().strftime("%Y-%m-%d %H:%M"))
        cfg.save_settings()
    except Exception:
        pass
    return added, problems


def entries(kind=None, status=None, limit=500):
    db = _db()
    sql = "SELECT * FROM online_form_entries WHERE 1=1"
    p = []
    if kind:
        sql += " AND form_kind = ?"; p.append(kind)
    if status:
        sql += " AND status = ?"; p.append(status)
    sql += " ORDER BY submitted_at DESC, entry_id DESC"
    rows = db.fetchall(sql, tuple(p)) or []
    out = []
    for r in rows[:limit]:
        r = dict(r)
        try:
            r["data"] = json.loads(r.get("payload_json") or "{}")
        except ValueError:
            r["data"] = {}
        out.append(r)
    return out


def counts():
    """{'customer': new, 'supplier': new, 'feedback': new}"""
    out = {k: 0 for k in KINDS}
    try:
        for r in _db().fetchall("SELECT form_kind, COUNT(*) n FROM online_form_entries "
                                "WHERE status = 'new' GROUP BY form_kind") or []:
            out[r["form_kind"]] = int(r["n"])
    except Exception:
        pass
    return out


def mark(entry_id, status, record_id=None, user=None):
    _db().execute(
        "UPDATE online_form_entries SET status = ?, record_id = ?, handled_by = ?, "
        "handled_at = ? WHERE entry_id = ?",
        (status, record_id, (user or "")[:50] or None,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), entry_id))


def find_existing(kind, vals):
    """A customer / supplier that already has this mobile or VAT number."""
    db = _db()
    table, key, name = (("customers", "customer_id", "customer_name_en") if kind == "customer"
                        else ("suppliers", "supplier_id", "supplier_name_en"))
    for col in ("vat_registration_no", "phone"):
        v = (vals.get(col) or "").strip()
        if v:
            r = db.fetchone("SELECT %s id, %s name FROM %s WHERE %s = ?" % (key, name, table, col), (v,))
            if r:
                return dict(r)
    return None


def feedback_summary(days=30):
    """Average stars, count, and how many were 1–2 stars, in the last N days."""
    rows = [r for r in entries("feedback") if r.get("rating")]
    try:
        from datetime import timedelta
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = [r for r in rows if str(r.get("submitted_at") or "")[:10] >= since]
    except Exception:
        pass
    n = len(rows)
    avg = (sum(int(r["rating"]) for r in rows) / n) if n else 0.0
    low = sum(1 for r in rows if int(r["rating"]) <= 2)
    return {"count": n, "average": round(avg, 1), "low": low}


def receipt_qr_link(invoice):
    """Link printed as a small QR on POS receipts (Settings ▸ Online forms)."""
    try:
        if not cfg.flag("receipt_feedback_qr", False):
            return ""
    except Exception:
        return ""
    if invoice.get("original_invoice_no") or str(invoice.get("invoice_type", "")).lower() in (
            "credit", "credit_note", "return", "sales_return"):
        return ""
    return form_link("feedback", bill=invoice.get("invoice_number") or "",
                     branch=invoice.get("branch_code") or invoice.get("branch_id") or "")
