# ============================================================
# DayBill ERP - ZATCA Phase 2 (Integration) core
# ------------------------------------------------------------
# Pure functions, no database:
#   • make_csr()        key pair + CSR exactly like the ZATCA SDK makes it
#   • build_xml()       UBL 2.1 invoice / credit note (ZATCA KSA profile)
#   • invoice_hash()    SHA-256 of the canonical invoice (C14N) without
#                       UBLExtensions, cac:Signature and the QR reference
#   • sign_xml()        simplified (B2C) invoices: ECDSA secp256k1 signature,
#                       XAdES signed properties, Phase 2 QR (tags 1-9)
#   • api_*()           Fatoora API (compliance CSID, compliance checks,
#                       production CSID, reporting, clearance)
# Checked against ZATCA SDK 238-R3.4.8 outputs (hash, signed properties,
# QR) and its business rules (see tests).
# ============================================================

import base64
import hashlib
import json
import re
import uuid as _uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

GENESIS_PIH = ("NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRk"
               "NGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ==")

ENV_URLS = {
    "sandbox":    "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal",
    "simulation": "https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation",
    "production": "https://gw-fatoora.zatca.gov.sa/e-invoicing/core",
}
ENV_NAMES = {"sandbox": "Sandbox (test only)", "simulation": "Simulation (test with your VAT no.)",
             "production": "Production (real invoices)"}
TEMPLATE_NAME = {"sandbox": "TSTZATCA-Code-Signing",
                 "simulation": "PREZATCA-Code-Signing",
                 "production": "ZATCA-Code-Signing"}
SANDBOX_OTP = "123345"            # the developer portal accepts this OTP

NS_INV = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"

TYPE_INVOICE, TYPE_DEBIT, TYPE_CREDIT = "388", "383", "381"
SUB_STANDARD, SUB_SIMPLIFIED = "0100000", "0200000"

# zero-rated / exempt / out-of-scope reasons (VATEX codes)
VATEX = {
    "Z": ("VATEX-SA-36", "Qualifying medicines and medical equipment"),
    "E": ("VATEX-SA-29", "Financial services mentioned in Article 29 of the VAT Regulations"),
    "O": ("VATEX-SA-OOS", "Not subject to VAT"),
}
VATEX_CHOICES = [
    ("VATEX-SA-32", "Export of goods"),
    ("VATEX-SA-33", "Export of services"),
    ("VATEX-SA-34-1", "International transport of goods"),
    ("VATEX-SA-35", "Medicines and medical equipment"),
    ("VATEX-SA-36", "Qualifying medicines and medical equipment"),
    ("VATEX-SA-EDU", "Private education to citizen"),
    ("VATEX-SA-HEA", "Private healthcare to citizen"),
    ("VATEX-SA-29", "Financial services (Article 29)"),
    ("VATEX-SA-30", "Real estate transactions (Article 30)"),
    ("VATEX-SA-OOS", "Not subject to VAT"),
]


# ── small helpers ─────────────────────────────────────────────
def D(v):
    try:
        return Decimal(str(v if v not in (None, "") else 0))
    except Exception:
        return Decimal("0")


def r2(v):
    return D(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def m2(v):
    """Amount text with 2 decimals."""
    return "%s" % r2(v)


def num(v, places=6):
    """Quantity / price text: up to `places` decimals, no trailing zeros."""
    q = D(v).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    s = format(q.normalize(), "f")
    return s if s not in ("-0", "") else "0"


def esc(v):
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def digits(v):
    return "".join(ch for ch in str(v or "") if ch.isdigit())


# ============================================================
# CSR — like the SDK: C/OU/O/CN subject, template name (UTF8String)
# and the EGS details in the Subject Alternative Name.
# ============================================================
def make_csr(info, env="sandbox"):
    """info: common_name, serial ('1-..|2-..|3-..'), vat, org_unit, org_name,
    invoice_type ('1100'), location, industry.  → (private_key_pem, csr_b64)"""
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ObjectIdentifier
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256K1())
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "SA"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, info["org_unit"][:64]),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, info["org_name"][:64]),
        x509.NameAttribute(NameOID.COMMON_NAME, info["common_name"][:64]),
    ])
    tpl = TEMPLATE_NAME.get(env, TEMPLATE_NAME["sandbox"]).encode("ascii")
    tpl_der = bytes([0x0C, len(tpl)]) + tpl                       # UTF8String
    san = x509.SubjectAlternativeName([x509.DirectoryName(x509.Name([
        x509.NameAttribute(ObjectIdentifier("2.5.4.4"), info["serial"]),
        x509.NameAttribute(ObjectIdentifier("0.9.2342.19200300.100.1.1"), info["vat"]),
        x509.NameAttribute(ObjectIdentifier("2.5.4.12"), info.get("invoice_type", "1100")),
        x509.NameAttribute(ObjectIdentifier("2.5.4.26"), info["location"][:100]),
        x509.NameAttribute(ObjectIdentifier("2.5.4.15"), info["industry"][:100]),
    ]))])
    csr = (x509.CertificateSigningRequestBuilder().subject_name(subject)
           .add_extension(x509.UnrecognizedExtension(
               ObjectIdentifier("1.3.6.1.4.1.311.20.2"), tpl_der), critical=False)
           .add_extension(san, critical=False)
           .sign(key, hashes.SHA256()))
    key_pem = key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.TraditionalOpenSSL,
                                serialization.NoEncryption()).decode()
    csr_pem = csr.public_bytes(serialization.Encoding.PEM)
    return key_pem, base64.b64encode(csr_pem).decode()


# ============================================================
# UBL 2.1 XML
# ============================================================
def _party_address(a, ind):
    p = " " * ind
    out = [p + "<cac:PostalAddress>"]
    for tag, key in (("StreetName", "street"), ("AdditionalStreetName", "street2"),
                     ("BuildingNumber", "building"), ("PlotIdentification", "plot"),
                     ("CitySubdivisionName", "district"), ("CityName", "city"),
                     ("PostalZone", "postal"), ("CountrySubentity", "region")):
        if a.get(key):
            out.append(p + "  <cbc:%s>%s</cbc:%s>" % (tag, esc(a[key]), tag))
    out.append(p + "  <cac:Country>")
    out.append(p + "    <cbc:IdentificationCode>%s</cbc:IdentificationCode>"
               % esc(a.get("country") or "SA"))
    out.append(p + "  </cac:Country>")
    out.append(p + "</cac:PostalAddress>")
    return out


def _tax_cat(tag, code, rate, ind, reason=None):
    p = " " * ind
    out = [p + "<cac:%s>" % tag,
           p + '  <cbc:ID schemeID="UN/ECE 5305" schemeAgencyID="6">%s</cbc:ID>' % code,
           p + "  <cbc:Percent>%s</cbc:Percent>" % num(rate, 2)]
    if reason:
        out.append(p + "  <cbc:TaxExemptionReasonCode>%s</cbc:TaxExemptionReasonCode>" % esc(reason[0]))
        out.append(p + "  <cbc:TaxExemptionReason>%s</cbc:TaxExemptionReason>" % esc(reason[1]))
    out += [p + "  <cac:TaxScheme>",
            p + '    <cbc:ID schemeID="UN/ECE 5153" schemeAgencyID="6">VAT</cbc:ID>',
            p + "  </cac:TaxScheme>",
            p + "</cac:%s>" % tag]
    return out


def compute(doc):
    """Line + document amounts the ZATCA way (2-decimal rounding, VAT per
    category). Fills doc['_calc'] and returns it."""
    lines = []
    cats = {}
    for i, ln in enumerate(doc["lines"], 1):
        qty = D(ln["qty"])
        rate = D(ln.get("vat_rate", 15))
        code = (ln.get("vat_code") or "S").upper()
        if code == "S" and rate == 0:
            code = "Z"
        if code != "S":
            rate = D(0)
        net = r2(ln["net_amount"])                          # BT-131 (after discount)
        disc = r2(ln.get("discount") or 0)                  # discount (excl. VAT)
        q6 = Decimal("0.000001")
        price = (net / qty).quantize(q6, ROUND_HALF_UP) if qty else D(0)       # BT-146 net price
        unit_disc = (disc / qty).quantize(q6, ROUND_HALF_UP) if qty else D(0)  # BT-147
        base = price + unit_disc                                               # BT-148 gross price
        tax = r2(net * rate / 100)
        lines.append({"id": i, "name": ln["name"], "qty": qty, "unit": ln.get("unit_code") or "PCE",
                      "net": net, "disc": disc, "price": price, "unit_disc": unit_disc,
                      "base": base, "rate": rate, "code": code,
                      "tax": tax, "reason": ln.get("vatex")})
        c = cats.setdefault((code, rate), {"taxable": D(0), "reason": None})
        c["taxable"] += net
        if code != "S":
            c["reason"] = c["reason"] or ln.get("vatex") or VATEX.get(code)
    subtotals = []
    tax_total = D(0)
    for (code, rate), c in sorted(cats.items()):
        t = r2(c["taxable"] * rate / 100)
        tax_total += t
        subtotals.append({"code": code, "rate": rate, "taxable": r2(c["taxable"]), "tax": t,
                          "reason": c["reason"]})
    line_ext = sum((l["net"] for l in lines), D(0))
    incl = line_ext + tax_total
    rounding = D(0)
    want = doc.get("total")
    if want is not None:
        diff = r2(want) - incl
        if abs(diff) <= D("0.99"):                          # DayBill rounding / cents
            rounding = diff
    calc = {"lines": lines, "subtotals": subtotals, "line_ext": r2(line_ext),
            "tax": r2(tax_total), "incl": r2(incl), "rounding": r2(rounding),
            "payable": r2(incl + rounding)}
    doc["_calc"] = calc
    return calc


def build_xml(doc):
    """doc: number, uuid, issue_date 'YYYY-MM-DD', issue_time 'HH:MM:SS',
    type_code 388/381/383, subtype 0100000/0200000, icv, pih, currency,
    seller{name, vat, crn, street, building, district, city, postal},
    buyer{name, vat, street, building, district, city, postal, country} or {},
    payment_code, billing_ref, reason, delivery_date, lines[{name, qty,
    unit_code, net_amount, discount, vat_code, vat_rate, vatex}], total.
    → unsigned XML text (no UBLExtensions / QR / signature)."""
    c = compute(doc)
    cur = doc.get("currency") or "SAR"
    s, b = doc["seller"], doc.get("buyer") or {}
    X = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<Invoice xmlns="%s" xmlns:cac="%s" xmlns:cbc="%s" xmlns:ext="%s">'
         % (NS_INV, NS_CAC, NS_CBC, NS_EXT),
         "  <cbc:ProfileID>reporting:1.0</cbc:ProfileID>",
         "  <cbc:ID>%s</cbc:ID>" % esc(doc["number"]),
         "  <cbc:UUID>%s</cbc:UUID>" % esc(doc["uuid"]),
         "  <cbc:IssueDate>%s</cbc:IssueDate>" % doc["issue_date"],
         "  <cbc:IssueTime>%s</cbc:IssueTime>" % doc["issue_time"],
         '  <cbc:InvoiceTypeCode name="%s">%s</cbc:InvoiceTypeCode>' % (doc["subtype"], doc["type_code"]),
         "  <cbc:DocumentCurrencyCode>%s</cbc:DocumentCurrencyCode>" % cur,
         "  <cbc:TaxCurrencyCode>SAR</cbc:TaxCurrencyCode>"]
    if doc["type_code"] in (TYPE_CREDIT, TYPE_DEBIT):
        X += ["  <cac:BillingReference>",
              "    <cac:InvoiceDocumentReference>",
              "      <cbc:ID>%s</cbc:ID>" % esc(doc.get("billing_ref") or "Not specified"),
              "    </cac:InvoiceDocumentReference>",
              "  </cac:BillingReference>"]
    X += ["  <cac:AdditionalDocumentReference>",
          "    <cbc:ID>ICV</cbc:ID>",
          "    <cbc:UUID>%d</cbc:UUID>" % int(doc["icv"]),
          "  </cac:AdditionalDocumentReference>",
          "  <cac:AdditionalDocumentReference>",
          "    <cbc:ID>PIH</cbc:ID>",
          "    <cac:Attachment>",
          '      <cbc:EmbeddedDocumentBinaryObject mimeCode="text/plain">%s</cbc:EmbeddedDocumentBinaryObject>'
          % doc.get("pih", GENESIS_PIH),
          "    </cac:Attachment>",
          "  </cac:AdditionalDocumentReference>",
          "  <cac:AccountingSupplierParty>",
          "    <cac:Party>",
          "      <cac:PartyIdentification>",
          '        <cbc:ID schemeID="%s">%s</cbc:ID>' % (esc(s.get("id_scheme") or "CRN"), esc(s["crn"])),
          "      </cac:PartyIdentification>"]
    X += _party_address(s, 6)
    X += ["      <cac:PartyTaxScheme>",
          "        <cbc:CompanyID>%s</cbc:CompanyID>" % esc(s["vat"]),
          "        <cac:TaxScheme>",
          '          <cbc:ID schemeID="UN/ECE 5153" schemeAgencyID="6">VAT</cbc:ID>',
          "        </cac:TaxScheme>",
          "      </cac:PartyTaxScheme>",
          "      <cac:PartyLegalEntity>",
          "        <cbc:RegistrationName>%s</cbc:RegistrationName>" % esc(s["name"]),
          "      </cac:PartyLegalEntity>",
          "    </cac:Party>",
          "  </cac:AccountingSupplierParty>",
          "  <cac:AccountingCustomerParty>"]
    if b and (b.get("name") or b.get("vat")):
        X.append("    <cac:Party>")
        if b.get("id") and not b.get("vat"):
            X += ["      <cac:PartyIdentification>",
                  '        <cbc:ID schemeID="%s">%s</cbc:ID>' % (esc(b.get("id_scheme") or "CRN"), esc(b["id"])),
                  "      </cac:PartyIdentification>"]
        if b.get("street") or b.get("city") or b.get("vat"):
            X += _party_address(b, 6)
        if b.get("vat"):
            X += ["      <cac:PartyTaxScheme>",
                  "        <cbc:CompanyID>%s</cbc:CompanyID>" % esc(b["vat"]),
                  "        <cac:TaxScheme>",
                  '          <cbc:ID schemeID="UN/ECE 5153" schemeAgencyID="6">VAT</cbc:ID>',
                  "        </cac:TaxScheme>",
                  "      </cac:PartyTaxScheme>"]
        if b.get("name"):
            X += ["      <cac:PartyLegalEntity>",
                  "        <cbc:RegistrationName>%s</cbc:RegistrationName>" % esc(b["name"]),
                  "      </cac:PartyLegalEntity>"]
        X.append("    </cac:Party>")
    else:
        X.append("    <cac:Party/>")
    X.append("  </cac:AccountingCustomerParty>")
    if doc.get("delivery_date"):
        X += ["  <cac:Delivery>",
              "    <cbc:ActualDeliveryDate>%s</cbc:ActualDeliveryDate>" % doc["delivery_date"],
              "  </cac:Delivery>"]
    # one PaymentMeans per way the bill was paid (v6.0: cash + card = 10 + 48)
    codes = [c for c in (doc.get("payment_codes") or []) if c] or [doc.get("payment_code") or "10"]
    for n_pm, code in enumerate(codes):
        X += ["  <cac:PaymentMeans>",
              "    <cbc:PaymentMeansCode>%s</cbc:PaymentMeansCode>" % esc(code)]
        if doc["type_code"] in (TYPE_CREDIT, TYPE_DEBIT) and n_pm == 0:
            X.append("    <cbc:InstructionNote>%s</cbc:InstructionNote>"
                     % esc(doc.get("reason") or "Goods returned"))
        X.append("  </cac:PaymentMeans>")
    X += ["  <cac:TaxTotal>",
          '    <cbc:TaxAmount currencyID="SAR">%s</cbc:TaxAmount>' % m2(c["tax"]),
          "  </cac:TaxTotal>",
          "  <cac:TaxTotal>",
          '    <cbc:TaxAmount currencyID="%s">%s</cbc:TaxAmount>' % (cur, m2(c["tax"]))]
    for st in c["subtotals"]:
        X += ["    <cac:TaxSubtotal>",
              '      <cbc:TaxableAmount currencyID="%s">%s</cbc:TaxableAmount>' % (cur, m2(st["taxable"])),
              '      <cbc:TaxAmount currencyID="%s">%s</cbc:TaxAmount>' % (cur, m2(st["tax"]))]
        X += _tax_cat("TaxCategory", st["code"], st["rate"], 6,
                      st["reason"] if st["code"] != "S" else None)
        X.append("    </cac:TaxSubtotal>")
    X += ["  </cac:TaxTotal>",
          "  <cac:LegalMonetaryTotal>",
          '    <cbc:LineExtensionAmount currencyID="%s">%s</cbc:LineExtensionAmount>' % (cur, m2(c["line_ext"])),
          '    <cbc:TaxExclusiveAmount currencyID="%s">%s</cbc:TaxExclusiveAmount>' % (cur, m2(c["line_ext"])),
          '    <cbc:TaxInclusiveAmount currencyID="%s">%s</cbc:TaxInclusiveAmount>' % (cur, m2(c["incl"])),
          '    <cbc:AllowanceTotalAmount currencyID="%s">0.00</cbc:AllowanceTotalAmount>' % cur,
          '    <cbc:PrepaidAmount currencyID="%s">0.00</cbc:PrepaidAmount>' % cur]
    if c["rounding"]:
        X.append('    <cbc:PayableRoundingAmount currencyID="%s">%s</cbc:PayableRoundingAmount>'
                 % (cur, m2(c["rounding"])))
    X += ['    <cbc:PayableAmount currencyID="%s">%s</cbc:PayableAmount>' % (cur, m2(c["payable"])),
          "  </cac:LegalMonetaryTotal>"]
    for l in c["lines"]:
        X += ["  <cac:InvoiceLine>",
              "    <cbc:ID>%d</cbc:ID>" % l["id"],
              '    <cbc:InvoicedQuantity unitCode="%s">%s</cbc:InvoicedQuantity>' % (esc(l["unit"]), num(l["qty"], 6)),
              '    <cbc:LineExtensionAmount currencyID="%s">%s</cbc:LineExtensionAmount>' % (cur, m2(l["net"])),
              "    <cac:TaxTotal>",
              '      <cbc:TaxAmount currencyID="%s">%s</cbc:TaxAmount>' % (cur, m2(l["tax"])),
              '      <cbc:RoundingAmount currencyID="%s">%s</cbc:RoundingAmount>' % (cur, m2(l["net"] + l["tax"])),
              "    </cac:TaxTotal>",
              "    <cac:Item>",
              "      <cbc:Name>%s</cbc:Name>" % esc(l["name"] or "Item")]
        X += _tax_cat("ClassifiedTaxCategory", l["code"], l["rate"], 6)
        X += ["    </cac:Item>",
              "    <cac:Price>",
              '      <cbc:PriceAmount currencyID="%s">%s</cbc:PriceAmount>' % (cur, num(l["price"], 6))]
        if l["disc"]:
            X += ["      <cac:AllowanceCharge>",
                  "        <cbc:ChargeIndicator>false</cbc:ChargeIndicator>",
                  "        <cbc:AllowanceChargeReason>discount</cbc:AllowanceChargeReason>",
                  '        <cbc:Amount currencyID="%s">%s</cbc:Amount>' % (cur, num(l["unit_disc"], 6)),
                  '        <cbc:BaseAmount currencyID="%s">%s</cbc:BaseAmount>' % (cur, num(l["base"], 6)),
                  "      </cac:AllowanceCharge>"]
        X += ["    </cac:Price>",
              "  </cac:InvoiceLine>"]
    X.append("</Invoice>")
    return "\n".join(X)


# ============================================================
# hash  (what the SDK hashes: C14N without ext / signature / QR)
# ============================================================
def _parse(xml):
    from lxml import etree
    data = xml.encode("utf-8") if isinstance(xml, str) else xml
    return etree.fromstring(data, etree.XMLParser(remove_blank_text=False,
                                                  resolve_entities=False, no_network=True))


def canonical(xml):
    """C14N bytes of the invoice without UBLExtensions, cac:Signature and
    the QR AdditionalDocumentReference (the parts signing adds)."""
    from lxml import etree
    root = _parse(xml)
    gone = (root.xpath("//*[local-name()='UBLExtensions']")
            + root.xpath("//*[local-name()='Invoice']//*[local-name()='Signature']")
            + root.xpath("//*[local-name()='AdditionalDocumentReference']"
                         "[*[local-name()='ID' and normalize-space(text())='QR']]"))
    for el in gone:
        p = el.getparent()
        if p is None:
            continue
        if el.tail:                       # keep the text after it
            prev = el.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + el.tail
            else:
                p.text = (p.text or "") + el.tail
        p.remove(el)
    return etree.tostring(root, method="c14n", with_comments=False)


def invoice_hash(xml):
    return base64.b64encode(hashlib.sha256(canonical(xml)).digest()).decode()


# ============================================================
# certificate helpers
# ============================================================
def cert_b64_from_token(token):
    """binarySecurityToken → the certificate's base64 text (MIIC…)."""
    t = str(token or "").strip()
    try:
        inner = base64.b64decode(t).decode("ascii").strip()
        if inner.startswith("MII"):
            return inner
    except Exception:
        pass
    return t


def load_cert(cert_b64):
    from cryptography import x509
    return x509.load_der_x509_certificate(base64.b64decode(cert_b64))


def cert_digest(cert_b64):
    """base64( hex( sha256( cert base64 text ) ) ) — the SDK's CertDigest."""
    return base64.b64encode(hashlib.sha256(cert_b64.encode()).hexdigest().encode()).decode()


def issuer_name(cert):
    """'CN=…, DC=extgazt, DC=gov, DC=local' like the SDK."""
    parts = []
    for rdn in reversed(cert.issuer.rdns):
        for a in rdn:
            key = {"2.5.4.3": "CN", "0.9.2342.19200300.100.1.25": "DC", "2.5.4.10": "O",
                   "2.5.4.11": "OU", "2.5.4.6": "C", "2.5.4.7": "L"}.get(a.oid.dotted_string,
                                                                      a.oid.dotted_string)
            parts.append("%s=%s" % (key, a.value))
    return ", ".join(parts)


def cert_expiry(cert_b64):
    try:
        c = load_cert(cert_b64)
        try:
            return c.not_valid_after_utc.replace(tzinfo=None)
        except AttributeError:
            return c.not_valid_after
    except Exception:
        return None


# ============================================================
# signing (simplified invoices / notes)
# ============================================================
SIGNED_PROPS = (
    '<xades:SignedProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" Id="xadesSignedProperties">\n'
    '                                    <xades:SignedSignatureProperties>\n'
    '                                        <xades:SigningTime>{time}</xades:SigningTime>\n'
    '                                        <xades:SigningCertificate>\n'
    '                                            <xades:Cert>\n'
    '                                                <xades:CertDigest>\n'
    '                                                    <ds:DigestMethod xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>\n'
    '                                                    <ds:DigestValue xmlns:ds="http://www.w3.org/2000/09/xmldsig#">{digest}</ds:DigestValue>\n'
    '                                                </xades:CertDigest>\n'
    '                                                <xades:IssuerSerial>\n'
    '                                                    <ds:X509IssuerName xmlns:ds="http://www.w3.org/2000/09/xmldsig#">{issuer}</ds:X509IssuerName>\n'
    '                                                    <ds:X509SerialNumber xmlns:ds="http://www.w3.org/2000/09/xmldsig#">{serial}</ds:X509SerialNumber>\n'
    '                                                </xades:IssuerSerial>\n'
    '                                            </xades:Cert>\n'
    '                                        </xades:SigningCertificate>\n'
    '                                    </xades:SignedSignatureProperties>\n'
    '                                </xades:SignedProperties>')

UBL_EXT = """<ext:UBLExtensions>
    <ext:UBLExtension>
        <ext:ExtensionURI>urn:oasis:names:specification:ubl:dsig:enveloped:xades</ext:ExtensionURI>
        <ext:ExtensionContent>
            <sig:UBLDocumentSignatures xmlns:sig="urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2" xmlns:sac="urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2" xmlns:sbc="urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2">
                <sac:SignatureInformation>
                    <cbc:ID>urn:oasis:names:specification:ubl:signature:1</cbc:ID>
                    <sbc:ReferencedSignatureID>urn:oasis:names:specification:ubl:signature:Invoice</sbc:ReferencedSignatureID>
                    <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Id="signature">
                        <ds:SignedInfo>
                            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2006/12/xml-c14n11"/>
                            <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256"/>
                            <ds:Reference Id="invoiceSignedData" URI="">
                                <ds:Transforms>
                                    <ds:Transform Algorithm="http://www.w3.org/TR/1999/REC-xpath-19991116">
                                        <ds:XPath>not(//ancestor-or-self::ext:UBLExtensions)</ds:XPath>
                                    </ds:Transform>
                                    <ds:Transform Algorithm="http://www.w3.org/TR/1999/REC-xpath-19991116">
                                        <ds:XPath>not(//ancestor-or-self::cac:Signature)</ds:XPath>
                                    </ds:Transform>
                                    <ds:Transform Algorithm="http://www.w3.org/TR/1999/REC-xpath-19991116">
                                        <ds:XPath>not(//ancestor-or-self::cac:AdditionalDocumentReference[cbc:ID='QR'])</ds:XPath>
                                    </ds:Transform>
                                    <ds:Transform Algorithm="http://www.w3.org/2006/12/xml-c14n11"/>
                                </ds:Transforms>
                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                                <ds:DigestValue>{invoice_hash}</ds:DigestValue>
                            </ds:Reference>
                            <ds:Reference Type="http://www.w3.org/2000/09/xmldsig#SignatureProperties" URI="#xadesSignedProperties">
                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                                <ds:DigestValue>{props_hash}</ds:DigestValue>
                            </ds:Reference>
                        </ds:SignedInfo>
                        <ds:SignatureValue>{signature}</ds:SignatureValue>
                        <ds:KeyInfo>
                            <ds:X509Data>
                                <ds:X509Certificate>{cert}</ds:X509Certificate>
                            </ds:X509Data>
                        </ds:KeyInfo>
                        <ds:Object>
                            <xades:QualifyingProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" Target="signature">
                                <xades:SignedProperties Id="xadesSignedProperties">
                                    <xades:SignedSignatureProperties>
                                        <xades:SigningTime>{time}</xades:SigningTime>
                                        <xades:SigningCertificate>
                                            <xades:Cert>
                                                <xades:CertDigest>
                                                    <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                                                    <ds:DigestValue>{digest}</ds:DigestValue>
                                                </xades:CertDigest>
                                                <xades:IssuerSerial>
                                                    <ds:X509IssuerName>{issuer}</ds:X509IssuerName>
                                                    <ds:X509SerialNumber>{serial}</ds:X509SerialNumber>
                                                </xades:IssuerSerial>
                                            </xades:Cert>
                                        </xades:SigningCertificate>
                                    </xades:SignedSignatureProperties>
                                </xades:SignedProperties>
                            </xades:QualifyingProperties>
                        </ds:Object>
                    </ds:Signature>
                </sac:SignatureInformation>
            </sig:UBLDocumentSignatures>
        </ext:ExtensionContent>
    </ext:UBLExtension>
</ext:UBLExtensions>"""

QR_AND_SIGNATURE = """<cac:AdditionalDocumentReference>
        <cbc:ID>QR</cbc:ID>
        <cac:Attachment>
            <cbc:EmbeddedDocumentBinaryObject mimeCode="text/plain">{qr}</cbc:EmbeddedDocumentBinaryObject>
        </cac:Attachment>
</cac:AdditionalDocumentReference><cac:Signature>
      <cbc:ID>urn:oasis:names:specification:ubl:signature:Invoice</cbc:ID>
      <cbc:SignatureMethod>urn:oasis:names:specification:ubl:dsig:enveloped:xades</cbc:SignatureMethod>
</cac:Signature>"""


def signed_props_hash(time, digest, issuer, serial):
    s = SIGNED_PROPS.format(time=time, digest=digest, issuer=esc(issuer), serial=serial)
    return base64.b64encode(hashlib.sha256(s.encode()).hexdigest().encode()).decode()


def ecdsa_sign(hash_b64, private_key_pem):
    """ECDSA-SHA256 over the invoice hash bytes (what the SDK signs)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    sig = key.sign(base64.b64decode(hash_b64), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(sig).decode()


def tlv(tag, value):
    v = value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
    if len(v) > 255:
        raise ValueError("QR tag %d is longer than 255 bytes" % tag)
    return bytes([tag, len(v)]) + bytes(v)


def _values(xml):
    r = _parse(xml)
    ns = {"cac": NS_CAC, "cbc": NS_CBC}
    g = lambda p: (r.xpath(p, namespaces=ns) or [""])[0]
    return {
        "seller": g("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName/text()"),
        "vat": g("cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID/text()"),
        "time": g("cbc:IssueDate/text()") + "T" + g("cbc:IssueTime/text()"),
        # the SDK checks QR tag 4 against BT-115 PayableAmount
        "total": g("cac:LegalMonetaryTotal/cbc:PayableAmount/text()"),
        "tax": g("cac:TaxTotal[1]/cbc:TaxAmount/text()"),
        "subtype": g("cbc:InvoiceTypeCode/@name"),
    }


def phase2_qr(xml, inv_hash, signature_b64, cert):
    """Tags 1-9: seller, VAT no, time, total, VAT, hash, signature,
    public key, the CA's signature on the certificate."""
    from cryptography.hazmat.primitives import serialization
    v = _values(xml)
    pub = cert.public_key().public_bytes(serialization.Encoding.DER,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)
    data = (tlv(1, v["seller"]) + tlv(2, v["vat"]) + tlv(3, v["time"]) + tlv(4, v["total"])
            + tlv(5, v["tax"]) + tlv(6, inv_hash) + tlv(7, signature_b64) + tlv(8, pub)
            + tlv(9, cert.signature))
    return base64.b64encode(data).decode()


def sign_xml(xml, cert_b64, private_key_pem, signing_time=None):
    """Sign a simplified invoice / note. → {xml, hash, qr, signature}"""
    canon = canonical(xml)
    h = base64.b64encode(hashlib.sha256(canon).digest()).decode()
    sig = ecdsa_sign(h, private_key_pem)
    cert = load_cert(cert_b64)
    t = signing_time or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    digest = cert_digest(cert_b64)
    issuer = issuer_name(cert)
    serial = str(cert.serial_number)
    props = signed_props_hash(t, digest, issuer, serial)
    qr = phase2_qr(xml, h, sig, cert)
    body = canon.decode("utf-8")
    ext = UBL_EXT.format(invoice_hash=h, props_hash=props, signature=sig, cert=cert_b64,
                         time=t, digest=digest, issuer=esc(issuer), serial=serial)
    first = body.index(">") + 1
    body = body[:first] + ext + body[first:]
    pos = body.index("<cac:AccountingSupplierParty>")
    body = body[:pos] + QR_AND_SIGNATURE.format(qr=qr) + body[pos:]
    return {"xml": '<?xml version="1.0" encoding="UTF-8"?>\n' + body, "hash": h, "qr": qr,
            "signature": sig, "signing_time": t}


def unsigned_payload(xml):
    """Standard (B2B) invoices go to clearance unsigned: canonical XML."""
    canon = canonical(xml)
    return {"xml": '<?xml version="1.0" encoding="UTF-8"?>\n' + canon.decode("utf-8"),
            "hash": base64.b64encode(hashlib.sha256(canon).digest()).decode(), "qr": "",
            "signature": ""}


def qr_from_xml(xml):
    """The QR text inside an invoice (e.g. ZATCA's cleared invoice)."""
    try:
        r = _parse(xml)
        v = r.xpath("//cac:AdditionalDocumentReference[cbc:ID='QR']/cac:Attachment/"
                    "cbc:EmbeddedDocumentBinaryObject/text()", namespaces={"cac": NS_CAC, "cbc": NS_CBC})
        return v[0].strip() if v else ""
    except Exception:
        return ""


def is_simplified(xml):
    return _values(xml)["subtype"].startswith("02")


# ============================================================
# Fatoora API
# ============================================================
BASE_OVERRIDE = {"url": None}           # tests point this at a local server


def base_url(env):
    return BASE_OVERRIDE["url"] or ENV_URLS.get(env, ENV_URLS["sandbox"])


class ApiError(Exception):
    def __init__(self, message, status=0, data=None):
        super().__init__(message)
        self.status = status
        self.data = data or {}


def _ssl():
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_post(url, body, headers, timeout=40, method="POST"):
    """→ (status, data dict). Network problems raise ApiError(status 0)."""
    import urllib.request, urllib.error
    h = {"Accept": "application/json", "Accept-Language": "en", "Accept-Version": "V2",
         "Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=h,
                                 method=method)
    try:
        ctx = _ssl() if url.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:
        raise ApiError(_net_text(e), 0)
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {"message": raw[:500]}
    if not isinstance(data, dict):
        data = {"data": data}
    return status, data


def _net_text(e):
    t = str(getattr(e, "reason", e))
    low = t.lower()
    if "getaddrinfo" in low or "name or service" in low or "nodename" in low:
        return "No internet / ZATCA server name not found (%s)" % t
    if "timed out" in low:
        return "ZATCA did not answer in time (internet slow or ZATCA busy)"
    if "certificate" in low:
        return "Secure connection problem (%s) — check the PC date & time" % t
    return "Connection problem: %s" % t


def _basic(token, secret):
    return "Basic " + base64.b64encode(("%s:%s" % (token, secret)).encode()).decode()


def messages(data):
    """(errors[], warnings[]) as plain text from any ZATCA answer."""
    errs, warns = [], []
    vr = data.get("validationResults") or {}
    for e in vr.get("errorMessages") or []:
        errs.append("%s: %s" % (e.get("code", ""), e.get("message", "")))
    for w in vr.get("warningMessages") or []:
        warns.append("%s: %s" % (w.get("code", ""), w.get("message", "")))
    for e in data.get("errors") or []:
        errs.append(e if isinstance(e, str) else "%s: %s" % (e.get("code", ""), e.get("message", e)))
    if data.get("message") and not errs and data.get("code"):
        errs.append("%s: %s" % (data.get("code"), data.get("message")))
    return errs, warns


def api_compliance_csid(env, csr_b64, otp):
    st, d = http_post(base_url(env) + "/compliance", {"csr": csr_b64}, {"OTP": str(otp).strip()})
    if st == 200 and d.get("binarySecurityToken"):
        return d
    errs, _w = messages(d)
    msg = "; ".join(errs) or d.get("message") or "HTTP %s" % st
    if st in (400, 401) and ("otp" in msg.lower() or st == 401):
        msg = "The OTP was not accepted (wrong or older than 1 hour). " + msg
    raise ApiError(msg, st, d)


def api_compliance_check(env, token, secret, payload):
    st, d = http_post(base_url(env) + "/compliance/invoices", payload,
                      {"Authorization": _basic(token, secret)})
    return st, d


def api_production_csid(env, token, secret, request_id):
    st, d = http_post(base_url(env) + "/production/csids",
                      {"compliance_request_id": str(request_id)},
                      {"Authorization": _basic(token, secret)})
    if st == 200 and d.get("binarySecurityToken"):
        return d
    errs, _w = messages(d)
    raise ApiError("; ".join(errs) or d.get("message") or "HTTP %s" % st, st, d)


def api_report(env, token, secret, payload):
    return http_post(base_url(env) + "/invoices/reporting/single", payload,
                     {"Authorization": _basic(token, secret), "Clearance-Status": "0"})


def api_clear(env, token, secret, payload):
    return http_post(base_url(env) + "/invoices/clearance/single", payload,
                     {"Authorization": _basic(token, secret), "Clearance-Status": "1"})


def payload(signed, uuid):
    return {"invoiceHash": signed["hash"], "uuid": uuid,
            "invoice": base64.b64encode(signed["xml"].encode("utf-8")).decode()}


def new_uuid():
    return str(_uuid.uuid4())
