# ============================================================
# DayBill ERP - WhatsApp sending
# ------------------------------------------------------------
# Two ways, chosen in Settings ▸ WhatsApp:
#   1. WhatsApp app (free)  - opens the chat with the message typed
#      in WhatsApp Desktop / WhatsApp Web; the PDF is saved and shown
#      in its folder so it can be dropped into the chat. The user
#      presses Send.
#   2. WhatsApp Cloud API   - fully automatic: uploads the PDF and
#      sends it with the message (Meta business number + token).
#      Outside the 24-hour customer window Meta requires an approved
#      template -> set "Cloud API Template" (document header +
#      body {{1}} name, {{2}} number, {{3}} total).
# ============================================================

import os
import sys
import webbrowser
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from config import settings as cfg
except Exception:                     # pragma: no cover
    cfg = None

GRAPH = "https://graph.facebook.com/v20.0"

DEFAULT_MESSAGES = {
    "sales": ("Dear {name},\nThank you for shopping with {company}.\n"
              "Invoice {number} dated {date}\nTotal: {total} SAR\n"
              "Balance due: {due} SAR"),
    "quotation": ("Dear {name},\nPlease find our quotation {number} for {total} SAR, "
                  "valid until {valid_until}.\nThank you — {company}"),
    "purchase_order": ("Dear {name},\nPlease supply the items in purchase order "
                       "{number} (total {total} SAR). Expected delivery: {expected}.\n"
                       "— {company}"),
    "receipt": ("Dear {name},\nWe received {amount} SAR ({number}) on {date}. "
                "Thank you!\nYour balance now: {balance} SAR\n— {company}"),
    "statement": ("Dear {name},\nYour account statement with {company} is attached.\n"
                  "Balance as of {date}: {balance} SAR"),
    "day_close": "{text}",
}

MSG_KEYS = {"sales": "wa_msg_invoice", "quotation": "wa_msg_quotation",
            "purchase_order": "wa_msg_po", "receipt": "wa_msg_receipt",
            "statement": "wa_msg_statement"}


def _get(key, default=""):
    try:
        return cfg.get(key, default) if cfg else default
    except Exception:
        return default


def enabled():
    try:
        return bool(cfg.flag("wa_enabled", False)) if cfg else False
    except Exception:
        return False


def mode():
    """'api' (Cloud API) or 'chat' (WhatsApp app / web)."""
    m = str(_get("wa_mode", "") or "").lower()
    return "api" if ("cloud" in m or m == "api") else "chat"


def api_ready():
    return bool(str(_get("wa_phone_id", "")).strip() and str(_get("wa_api_key", "")).strip())


def normalize_phone(raw, country=None):
    """'050 123 4567' -> '966501234567'. Returns '' if not usable."""
    s = "".join(ch for ch in str(raw or "") if ch.isdigit() or ch == "+")
    if not s:
        return ""
    cc = "".join(ch for ch in str(country or _get("wa_country_code", "966") or "966")
                 if ch.isdigit()) or "966"
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("00"):
        s = s[2:]
    elif s.startswith("0"):
        s = cc + s[1:]
    elif len(s) <= 9:
        s = cc + s
    s = "".join(ch for ch in s if ch.isdigit())
    return s if 10 <= len(s) <= 15 else ""


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def message_for(kind, ctx):
    tpl = str(_get(MSG_KEYS.get(kind, ""), "") or "") or DEFAULT_MESSAGES.get(kind, "{text}")
    tpl = tpl.replace("\\n", "\n")
    try:
        return _local(tpl.format_map(_SafeDict(ctx)))
    except Exception:
        return _local(tpl)


def _local(text):
    """v7.0: the message in the company's country words (SAR → AED / ₹)."""
    try:
        from modules import country as _K
        return _K.localize(text)
    except Exception:
        return text


# ── WhatsApp app / web ────────────────────────────────────────
def chat_urls(phone, text):
    q = quote(text or "")
    return (f"whatsapp://send?phone={phone}&text={q}",
            f"https://web.whatsapp.com/send?phone={phone}&text={q}",
            f"https://wa.me/{phone}?text={q}")


def open_chat(phone, text):
    """Open the chat with the message typed. Returns which way opened."""
    app_url, web_url, _ = chat_urls(phone, text)
    prefer_web = "web" in str(_get("wa_open_with", "") or "").lower()
    if not prefer_web and os.name == "nt":
        try:
            os.startfile(app_url)            # WhatsApp Desktop
            return "app"
        except Exception:
            pass
    webbrowser.open(web_url)
    return "web"


def pdf_folder():
    base = os.path.join(os.path.expanduser("~"), "Documents", "DayBill WhatsApp")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        import tempfile
        base = tempfile.gettempdir()
    return base


def show_file(path):
    """Open Explorer with the file selected, ready to drag into the chat."""
    try:
        if os.name == "nt":
            import subprocess
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return True
    except Exception:
        pass
    return False


# ── WhatsApp Cloud API ────────────────────────────────────────
def _post(url, token, **kw):
    import requests
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=40, **kw)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:300]}
    if r.status_code >= 300 or "error" in data:
        err = data.get("error", {}) if isinstance(data, dict) else {}
        raise RuntimeError(err.get("message") or f"HTTP {r.status_code}: {str(data)[:200]}")
    return data


def api_upload(pdf_path):
    pid = str(_get("wa_phone_id", "")).strip()
    tok = str(_get("wa_api_key", "")).strip()
    with open(pdf_path, "rb") as fh:
        data = _post(f"{GRAPH}/{pid}/media", tok,
                     data={"messaging_product": "whatsapp", "type": "application/pdf"},
                     files={"file": (os.path.basename(pdf_path), fh, "application/pdf")})
    return data.get("id")


def api_send(phone, text, pdf_path=None, template_params=None, template=None, kind="message",
             lang=None):
    """Send via Cloud API. Returns (ok, info).
    template: None = the documents template of Settings (wa_template_name),
    '' = no template (plain text / document — delivered only inside the
    24-hour window), or a template name (e.g. the evening-report one).
    Every message is counted (whatsapp_messages) — Meta charges them."""
    if not api_ready():
        return False, "Set the Cloud API Phone Number ID and Access Token in Settings ▸ WhatsApp."
    pid = str(_get("wa_phone_id", "")).strip()
    tok = str(_get("wa_api_key", "")).strip()
    tpl = (str(_get("wa_template_name", "") or "").strip() if template is None
           else str(template or "").strip())
    try:
        media_id = api_upload(pdf_path) if pdf_path else None
        if tpl:
            comps = []
            if media_id:
                comps.append({"type": "header", "parameters": [{
                    "type": "document", "document": {
                        "id": media_id, "filename": os.path.basename(pdf_path)}}]})
            if template_params:
                comps.append({"type": "body", "parameters": [
                    {"type": "text", "text": str(p)} for p in template_params]})
            body = {"messaging_product": "whatsapp", "to": phone, "type": "template",
                    "template": {"name": tpl,
                                 "language": {"code": str(lang or _get("wa_template_lang", "en") or "en")},
                                 "components": comps}}
        elif media_id:
            body = {"messaging_product": "whatsapp", "to": phone, "type": "document",
                    "document": {"id": media_id, "filename": os.path.basename(pdf_path),
                                 "caption": (text or "")[:1000]}}
        else:
            body = {"messaging_product": "whatsapp", "to": phone, "type": "text",
                    "text": {"body": text or ""}}
        data = _post(f"{GRAPH}/{pid}/messages", tok, json=body)
        mid = ((data.get("messages") or [{}])[0] or {}).get("id", "")
        record(phone, kind, tpl, bool(pdf_path), True, mid or "sent")
        return True, mid or "sent"
    except Exception as e:
        record(phone, kind, tpl, bool(pdf_path), False, str(e)[:300])
        return False, str(e)[:300]


# ── v6.5: how many Cloud API messages (Meta charges each one) ─
def record(phone, kind, template, has_pdf, ok, info=""):
    """One row per Cloud API message (sent or failed)."""
    try:
        from datetime import date as _date
        from config.database import db
        db.execute("INSERT INTO whatsapp_messages (sent_date, phone, kind, template, has_pdf, ok, info) "
                   "VALUES (?,?,?,?,?,?,?)",
                   (_date.today().isoformat(), str(phone or "")[:30], str(kind or "")[:40],
                    str(template or "")[:100] or None, 1 if has_pdf else 0, 1 if ok else 0,
                    str(info or "")[:300]))
    except Exception:
        pass


def price_per_msg():
    try:
        return max(0.0, float(_get("wa_price_per_msg", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def usage(today=None):
    """Cloud API messages this month / last month (+ cost at the price set
    in Settings ▸ WhatsApp). The free WhatsApp-app mode is not counted."""
    from datetime import date as _date, timedelta as _td
    d = today or _date.today()
    first = d.replace(day=1)
    prev_last = first - _td(days=1)
    prev_first = prev_last.replace(day=1)
    out = {"this_month": 0, "last_month": 0, "failed": 0, "by_kind": {}, "rate": price_per_msg()}
    try:
        from config.database import db
        for r in db.fetchall("SELECT kind, ok, COUNT(*) AS n FROM whatsapp_messages WHERE sent_date "
                             "BETWEEN ? AND ? GROUP BY kind, ok", (first.isoformat(), d.isoformat())) or []:
            n = int(r.get("n") or 0)
            if r.get("ok"):
                out["this_month"] += n
                out["by_kind"][r.get("kind") or "message"] = out["by_kind"].get(r.get("kind") or "message", 0) + n
            else:
                out["failed"] += n
        r = db.fetchone("SELECT COUNT(*) AS n FROM whatsapp_messages WHERE ok=1 AND sent_date BETWEEN ? AND ?",
                        (prev_first.isoformat(), prev_last.isoformat())) or {}
        out["last_month"] = int(r.get("n") or 0)
    except Exception:
        out["missing"] = True
    out["cost"] = round(out["this_month"] * out["rate"], 2)
    out["last_cost"] = round(out["last_month"] * out["rate"], 2)
    return out


def usage_text(today=None):
    u = usage(today)
    if u.get("missing"):
        return "Cloud API message count: the v6.5 database update is not applied yet."
    s = "Cloud API messages this month: %d" % u["this_month"]
    if u["rate"]:
        s += " ≈ %.2f SAR" % u["cost"]
    s += "  ·  last month: %d" % u["last_month"]
    if u["rate"]:
        s += " ≈ %.2f SAR" % u["last_cost"]
    if u["failed"]:
        s += "  ·  %d failed" % u["failed"]
    if u["by_kind"]:
        s += "\n" + ",  ".join("%s %d" % (k.replace("_", " "), n) for k, n in
                                sorted(u["by_kind"].items(), key=lambda x: -x[1]))
    s += "\nSince 1 Oct 2026 Meta charges every Cloud API message (also replies). " \
         "WhatsApp app mode is free." + ("" if u["rate"] else " Type your price per message to see the cost.")
    return _local(s)


def log(kind, doc_id, phone, ok, info=""):
    try:
        from modules import audit
        audit.log("whatsapp", kind, doc_id,
                  f"{'sent' if ok else 'FAILED'} to {phone} {info}"[:250])
    except Exception:
        pass
