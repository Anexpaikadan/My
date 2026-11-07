# ============================================================
# DayBill ERP - AI client (Claude API)
# ------------------------------------------------------------
# Online AI features: product name translation (EN → AR / AR → EN),
# reading supplier invoices (PDF / photo), spelling clean-up.
# Settings ▸ AI: API key (console.anthropic.com), models.
# Nothing is sent unless the user presses an AI button (or turns on
# "translate automatically"). Only product names / the chosen invoice
# file are sent — never customers, prices or the database.
# ============================================================

import base64
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MODEL_FAST = "claude-haiku-5-5"                # names, spelling (cheap, fast)
MODEL_VISION = "claude-sonnet-5-5"             # reading supplier invoices
MODELS = [MODEL_FAST, MODEL_VISION, "claude-opus-5-5"]
# v6.5: older model names saved in Settings → the current model of that family
RENAMED = {"claude-haiku-4-5-20251001": MODEL_FAST, "claude-haiku-4-5": MODEL_FAST}
MAX_FILE_MB = 20


class AIError(Exception):
    """A friendly, user-facing error message."""


def _cfg():
    from config import settings as cfg
    return cfg


def api_key():
    try:
        k = str(_cfg().get("ai_api_key", "") or "").strip()
    except Exception:
        k = ""
    return k or os.environ.get("ANTHROPIC_API_KEY", "").strip()


def enabled():
    try:
        on = _cfg().flag("ai_enabled", True)
    except Exception:
        on = True
    return bool(on and api_key())


def _model(kind):
    try:
        c = _cfg()
        m = c.get("ai_model_vision" if kind == "vision" else "ai_model_fast", "") or ""
    except Exception:
        m = ""
    m = str(m).strip()
    return RENAMED.get(m, m) or (MODEL_VISION if kind == "vision" else MODEL_FAST)


# ── HTTP ─────────────────────────────────────────────────────
def _post(payload, timeout=60):
    """POST to the Messages API, returns the JSON reply (test hook)."""
    key = api_key()
    if not key:
        raise AIError("No AI key yet. Settings ▸ AI ▸ paste your Claude API key.")
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": API_VERSION, "user-agent": "DayBillERP"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        if e.code == 401:
            raise AIError("The AI key is not valid. Check Settings ▸ AI.")
        if e.code == 429:
            raise AIError("AI is busy (rate limit). Try again in a minute.")
        if e.code == 400 and "credit" in msg.lower():
            raise AIError("Your AI account has no credit left (console.anthropic.com ▸ Billing).")
        raise AIError(f"AI error {e.code}: {msg[:160] or e.reason}")
    except urllib.error.URLError as e:
        raise AIError(f"No internet / AI not reachable ({str(e.reason)[:80]}).")
    except TimeoutError:
        raise AIError("AI took too long. Try again.")


def call_tool(content, tool, kind="fast", max_tokens=4096, system=None):
    """One Messages call that MUST answer through `tool` (structured
    output). Returns the tool input dict."""
    payload = {
        "model": _model(kind), "max_tokens": max_tokens,
        "tools": [tool], "tool_choice": {"type": "tool", "name": tool["name"]},
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        payload["system"] = system
    res = _post(payload, timeout=120 if kind == "vision" else 45)
    for block in res.get("content") or []:
        if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
            return block.get("input") or {}
    if res.get("stop_reason") == "max_tokens":
        raise AIError("The answer was too long — try fewer items / a shorter invoice.")
    raise AIError("AI did not return the expected data. Try again.")


def test_key():
    """(ok, message) — a tiny call to check the key."""
    try:
        out = translate_names(["Fresh Milk 1L"])
        return True, f"AI is working ✓  (Fresh Milk 1L → {out[0]})"
    except AIError as e:
        return False, str(e)


# ── #9  product names: English ↔ Arabic ──────────────────────
_TRANSLATE_TOOL = {
    "name": "product_names",
    "description": "Return the translated product names in the same order.",
    "input_schema": {
        "type": "object",
        "properties": {"names": {"type": "array", "items": {"type": "string"}}},
        "required": ["names"],
    },
}


def translate_names(names, to="ar"):
    """Supermarket product names → Arabic (to='ar') or English (to='en').
    Brands are written the way Saudi shops print them (المراعي, نادك),
    sizes kept with Arabic unit words (1 لتر, 500 جم, 5 كجم)."""
    names = [str(n or "").strip() for n in names]
    if not any(names):
        return names
    if to == "ar":
        task = ("Translate these supermarket product names from English to Arabic, as "
                "they are printed on shelf labels and invoices in Saudi Arabia. Keep "
                "brand names in their usual Arabic spelling (Almarai → المراعي, Nadec → "
                "نادك, Nestle → نستله); if a brand has no known Arabic form, write it in "
                "Arabic letters. Keep numbers as digits and use Arabic unit words "
                "(L → لتر, ml → مل, kg → كجم, g → جم, pcs → حبة). Do not add words.")
    else:
        task = ("Translate these supermarket product names from Arabic to English as "
                "printed on shelf labels in Saudi Arabia. Keep brand names in their "
                "usual English spelling, numbers as digits, units as L, ml, kg, g, pcs.")
    text = task + "\n\nNames (one per line, keep the order and count):\n" + \
        "\n".join(f"{i + 1}. {n}" for i, n in enumerate(names))
    out = call_tool([{"type": "text", "text": text}], _TRANSLATE_TOOL, "fast",
                    max_tokens=60 * len(names) + 200).get("names") or []
    out = [str(x or "").strip() for x in out]
    if len(out) != len(names):
        raise AIError("AI returned a different number of names. Try again.")
    return out


# ── #13 spelling check for the clean-up assistant ────────────
_SPELL_TOOL = {
    "name": "spelling_fixes",
    "description": "Only the names that have a clear spelling mistake.",
    "input_schema": {
        "type": "object",
        "properties": {"fixes": {"type": "array", "items": {
            "type": "object",
            "properties": {"index": {"type": "integer"},
                           "fixed": {"type": "string"}},
            "required": ["index", "fixed"]}}},
        "required": ["fixes"],
    },
}


def spelling_fixes(names):
    """{index: fixed_name} for English product names with clear typos
    (Choclate → Chocolate). Brands and sizes are left alone."""
    if not names:
        return {}
    text = ("These are supermarket product names (English). Return ONLY names with a "
            "clear spelling mistake, with the corrected name. Do not change brand "
            "names, sizes, capitalisation style or word order.\n\n" +
            "\n".join(f"{i}. {n}" for i, n in enumerate(names)))
    res = call_tool([{"type": "text", "text": text}], _SPELL_TOOL, "fast",
                    max_tokens=40 * len(names) + 300)
    out = {}
    for f in res.get("fixes") or []:
        try:
            i = int(f.get("index"))
            fixed = str(f.get("fixed") or "").strip()
            if 0 <= i < len(names) and fixed and fixed != names[i]:
                out[i] = fixed
        except Exception:
            continue
    return out


# ── #11 supplier invoice (PDF / photo) → structured lines ────
_INVOICE_TOOL = {
    "name": "supplier_invoice",
    "description": "The data read from the supplier's tax invoice.",
    "input_schema": {
        "type": "object",
        "properties": {
            "supplier_name": {"type": "string"},
            "supplier_vat_no": {"type": "string", "description": "15 digits, or empty"},
            "invoice_number": {"type": "string"},
            "invoice_date": {"type": "string", "description": "YYYY-MM-DD"},
            "currency": {"type": "string"},
            "lines": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "English product name as printed"},
                    "name_ar": {"type": "string", "description": "Arabic name if printed, else empty"},
                    "barcode": {"type": "string", "description": "item barcode / EAN if printed, else empty"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string", "description": "PCs, Box, Carton, Kg … as printed"},
                    "pieces_per_unit": {"type": "number", "description": "e.g. 12 for 'Box of 12', else 1"},
                    "unit_price_excl_vat": {"type": "number"},
                    "vat_rate": {"type": "number", "description": "percent, e.g. 15"},
                    "line_total_incl_vat": {"type": "number"},
                },
                "required": ["description", "quantity", "unit_price_excl_vat"]}},
            "subtotal_excl_vat": {"type": "number"},
            "vat_total": {"type": "number"},
            "total_incl_vat": {"type": "number"},
        },
        "required": ["supplier_name", "lines"],
    },
}


def _file_block(path):
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    if size > MAX_FILE_MB * 1024 * 1024:
        raise AIError(f"The file is bigger than {MAX_FILE_MB} MB.")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("ascii")
    if ext == ".pdf":
        return {"type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
    media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
             ".webp": "image/webp", ".gif": "image/gif"}.get(ext)
    if not media:
        raise AIError("Choose a PDF or a photo (JPG / PNG).")
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def read_invoice(path):
    """Read a supplier tax invoice (PDF or photo). Returns the dict of
    _INVOICE_TOOL (unit prices WITHOUT VAT)."""
    text = ("This is a supplier's tax invoice from Saudi Arabia (it may be in English, "
            "Arabic or both). Read the supplier, invoice number, date and EVERY item "
            "line. unit_price_excl_vat must be the price of ONE unit as invoiced, "
            "without VAT (if the invoice shows prices including VAT, divide by 1.15 "
            "or the printed VAT rate). Use numbers only (no commas, no currency). "
            "If a value is not printed, leave it empty / 0.")
    res = call_tool([_file_block(path), {"type": "text", "text": text}],
                    _INVOICE_TOOL, "vision", max_tokens=8000)
    lines = []
    for ln in res.get("lines") or []:
        try:
            q = float(ln.get("quantity") or 0)
            p = float(ln.get("unit_price_excl_vat") or 0)
        except (TypeError, ValueError):
            continue
        if not str(ln.get("description") or "").strip() or q <= 0:
            continue
        ln["quantity"], ln["unit_price_excl_vat"] = q, p
        try:
            ln["vat_rate"] = float(ln.get("vat_rate") if ln.get("vat_rate") not in (None, "") else 15)
        except (TypeError, ValueError):
            ln["vat_rate"] = 15.0
        try:
            ln["pieces_per_unit"] = float(ln.get("pieces_per_unit") or 1) or 1.0
        except (TypeError, ValueError):
            ln["pieces_per_unit"] = 1.0
        ln["barcode"] = "".join(ch for ch in str(ln.get("barcode") or "") if ch.isalnum())
        lines.append(ln)
    res["lines"] = lines
    return res
