# ============================================================
# DayBill ERP - Wathq lookup (Saudi Commercial Registration)
# ------------------------------------------------------------
# Looks up a company by its Commercial Registration (CR) number via
# the Wathq API (Ministry of Commerce). Requires the user's own Wathq
# beneficiary API key (paid, registered service).
#
# Settings keys (config/app_settings.json):
#   wathq_enabled  : bool
#   wathq_api_key  : your beneficiary apiKey
#   wathq_base_url : default https://api.wathq.sa
#   wathq_endpoint : default /commercial-registration/fullinfo/{cr}
#                    (older accounts: /commercialregistration/info/{cr})
#
# NOTE: Wathq does CR-number lookup, not VAT-number lookup. There is
# no public VAT→company API, so auto-fill works from the CR number.
# ============================================================

import sys, os, json, urllib.request, urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import settings as cfg

DEFAULT_BASE = "https://api.wathq.sa"
DEFAULT_ENDPOINT = "/commercial-registration/fullinfo/{cr}"


def enabled():
    return bool(cfg.get("wathq_enabled", False)) and bool(cfg.get("wathq_api_key", ""))


def _first(d, *keys):
    """Return the first present, non-empty value among nested keys."""
    for k in keys:
        cur = d
        ok = True
        for part in k.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, "", []):
            return cur
    return ""


def lookup_cr(cr_number):
    """
    Returns (data_dict, error_str). On success error_str is None.
    data_dict keys: name_ar, name_en, cr_number, status, city_ar,
    city_en, district_ar, street_ar, building_number, postal_code.
    """
    cr = "".join(ch for ch in str(cr_number or "") if ch.isdigit())
    if not cr:
        return None, "Enter a CR number first."
    api_key = cfg.get("wathq_api_key", "")
    if not api_key:
        return None, ("No Wathq API key set. Add it in System → Integrations "
                      "(Wathq).")
    base = (cfg.get("wathq_base_url", DEFAULT_BASE) or DEFAULT_BASE).rstrip("/")
    endpoint = cfg.get("wathq_endpoint", DEFAULT_ENDPOINT) or DEFAULT_ENDPOINT
    url = base + endpoint.replace("{cr}", cr)

    req = urllib.request.Request(url, headers={
        "apiKey": api_key,
        "Accept": "application/json",
        "User-Agent": "DayBillERP/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, "Wathq rejected the API key (401/403). Check the key."
        if e.code == 404:
            return None, "CR number not found in Wathq."
        if e.code == 429:
            return None, "Wathq rate limit reached. Try again shortly."
        return None, f"Wathq error HTTP {e.code}."
    except urllib.error.URLError as e:
        return None, f"Network error reaching Wathq: {e.reason}"
    except Exception as e:
        return None, f"Wathq lookup failed: {str(e)[:120]}"

    try:
        j = json.loads(raw)
    except Exception:
        return None, "Wathq returned an unreadable response."

    # Response shapes differ across Wathq versions; map defensively.
    data = {
        "name_ar": _first(j, "crName", "name", "businessName", "entityName"),
        "name_en": _first(j, "crNameEn", "nameEn", "englishName"),
        "cr_number": _first(j, "crNumber", "crEntityNumber", "registrationNumber") or cr,
        "status": _first(j, "status.name", "status", "crStatus.name", "crStatus"),
        "building_number": _first(j, "address.buildingNumber",
                                  "nationalAddress.buildingNumber", "buildingNumber"),
        "street_ar": _first(j, "address.street", "nationalAddress.street", "street"),
        "district_ar": _first(j, "address.district", "nationalAddress.district",
                              "district"),
        "city_ar": _first(j, "address.city", "nationalAddress.city", "city"),
        "city_en": _first(j, "address.cityEn", "nationalAddress.cityEn"),
        "postal_code": _first(j, "address.postalCode", "nationalAddress.postalCode",
                              "postalCode", "zipCode"),
    }
    data["_raw"] = j
    return data, None


def fill_party_fields(fields, cr_number, on_status=None):
    """
    Look up cr_number and populate a form's `fields` dict of StringVars.
    `fields` uses the customer/supplier key names. Name keys are resolved
    for whichever party type is present. Returns (ok, message).
    """
    data, err = lookup_cr(cr_number)
    if err:
        return False, err

    def setf(key, val):
        if val and key in fields and not fields[key].get().strip():
            fields[key].set(str(val))

    def setf_force(key, val):
        if val and key in fields:
            fields[key].set(str(val))

    # name (AR is what Wathq returns; EN if available)
    name_ar_key = "customer_name_ar" if "customer_name_ar" in fields else "supplier_name_ar"
    name_en_key = "customer_name_en" if "customer_name_en" in fields else "supplier_name_en"
    setf_force(name_ar_key, data.get("name_ar"))
    if data.get("name_en"):
        setf(name_en_key, data.get("name_en"))
    elif data.get("name_ar") and name_en_key in fields and not fields[name_en_key].get().strip():
        # no English from Wathq — leave EN for the user, but don't block save
        pass

    setf_force("cr_number", data.get("cr_number"))
    setf("building_number", data.get("building_number"))
    setf("street_name_ar", data.get("street_ar"))
    setf("district_ar", data.get("district_ar"))
    setf("city_ar", data.get("city_ar"))
    setf("city_en", data.get("city_en"))
    setf("postal_code", data.get("postal_code"))

    name = data.get("name_ar") or data.get("name_en") or data.get("cr_number")
    msg = f"Loaded: {name}"
    if data.get("status"):
        msg += f"  ({data['status']})"
    return True, msg
