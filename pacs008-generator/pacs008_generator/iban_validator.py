"""Weltweiter IBAN-Validator (ISO 13616 / ISO 7064 Mod-97).

Prueft eine IBAN in 5 Stufen und liefert strukturierte Fehlercodes, die zu
error_catalog.yaml / agent_error_knowledge.yaml passen:

  IBAN_COUNTRY_UNKNOWN     Laendercode nicht im IBAN-Register
  IBAN_INVALID_FORMAT      unzulaessige Zeichen / Aufbau
  IBAN_WRONG_LENGTH        Laenge passt nicht zur Soll-Laenge des Landes
  IBAN_INVALID_CHECKDIGITS Pruefziffern 00/01/99 sind per Standard unzulaessig
  IBAN_INVALID_CHECKSUM    Mod-97-Pruefung fehlgeschlagen

CLI:  python3 -m pacs008_generator.iban_validator CH9300762011623852957 DE44...
"""
import re
import sys

# ISO 13616 IBAN-Register: Laendercode -> IBAN-Gesamtlaenge (Stand 2026)
IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16,
    "BG": 22, "BH": 22, "BI": 27, "BR": 29, "BY": 28, "CH": 21, "CR": 22,
    "CY": 28, "CZ": 24, "DE": 22, "DJ": 27, "DK": 18, "DO": 28, "EE": 20,
    "EG": 29, "ES": 24, "FI": 18, "FK": 18, "FO": 18, "FR": 27, "GB": 22,
    "GE": 22, "GI": 23, "GL": 18, "GR": 27, "GT": 28, "HN": 28, "HR": 21,
    "HU": 28, "IE": 22, "IL": 23, "IQ": 23, "IS": 26, "IT": 27, "JO": 30,
    "KW": 30, "KZ": 20, "LB": 28, "LC": 32, "LI": 21, "LT": 20, "LU": 20,
    "LV": 21, "LY": 25, "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MN": 20,
    "MR": 27, "MT": 31, "MU": 30, "NI": 28, "NL": 18, "NO": 15, "OM": 23,
    "PK": 24, "PL": 28, "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22,
    "RU": 33, "SA": 24, "SC": 31, "SD": 18, "SE": 24, "SI": 19, "SK": 24,
    "SM": 27, "SO": 23, "ST": 25, "SV": 28, "TL": 23, "TN": 24, "TR": 26,
    "UA": 29, "VA": 22, "VG": 24, "XK": 20, "YE": 30,
}

_STRUCT_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$")


def _mod97(iban):
    s = iban[4:] + iban[:4]
    total = 0
    for c in s:
        total = (total * (10 if c.isdigit() else 100) + int(c, 36)) % 97
    return total


def validate_iban(iban):
    """Validiert eine IBAN. Rueckgabe:
    {"iban", "normalized", "country", "valid", "errors": [{code, detail}]}
    Leerzeichen werden toleriert (Papierformat), Kleinbuchstaben normalisiert."""
    raw = iban or ""
    norm = re.sub(r"[\s\-]", "", str(raw)).upper()
    res = {"iban": raw, "normalized": norm, "country": norm[:2] or None,
           "valid": False, "errors": []}

    def err(code, detail):
        res["errors"].append({"code": code, "detail": detail})

    if not _STRUCT_RE.match(norm):
        err("IBAN_INVALID_FORMAT",
            "Aufbau muss sein: 2 Buchstaben Laendercode + 2 Ziffern Pruefziffer "
            "+ max. 30 alphanumerische Zeichen (gefunden: '%s')" % norm[:40])
        return res  # weitere Pruefungen sinnlos

    ctry = norm[:2]
    expected = IBAN_LENGTHS.get(ctry)
    if expected is None:
        err("IBAN_COUNTRY_UNKNOWN",
            "Laendercode '%s' ist nicht im ISO-13616-IBAN-Register" % ctry)
        return res

    if len(norm) != expected:
        err("IBAN_WRONG_LENGTH",
            "%s-IBAN muss %d Zeichen haben, gefunden: %d"
            % (ctry, expected, len(norm)))

    if norm[2:4] in ("00", "01", "99"):
        err("IBAN_INVALID_CHECKDIGITS",
            "Pruefziffern '%s' sind per ISO 7064 unzulaessig" % norm[2:4])

    if _mod97(norm) != 1:
        err("IBAN_INVALID_CHECKSUM",
            "Mod-97-Pruefung fehlgeschlagen (Rest %d statt 1) - "
            "Tippfehler oder verfaelschte IBAN" % _mod97(norm))

    res["valid"] = not res["errors"]
    return res


def is_valid(iban):
    return validate_iban(iban)["valid"]


def main(argv):
    if not argv:
        print("Aufruf: python3 -m pacs008_generator.iban_validator <IBAN> [<IBAN> ...]")
        return 1
    rc = 0
    for iban in argv:
        r = validate_iban(iban)
        if r["valid"]:
            print("OK    %s (%s)" % (r["normalized"], r["country"]))
        else:
            rc = 1
            print("FAIL  %s" % r["normalized"])
            for e in r["errors"]:
                print("      %-24s %s" % (e["code"], e["detail"]))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
