"""Business-error injectors. Each injector mutates the tx dict BEFORE the XML is
built, so the output stays XSD-valid. Returns a human-readable detail string."""
import os
import yaml

from . import datapool

_REGISTRY = {}


def injector(name):
    def deco(fn):
        _REGISTRY[name] = fn
        return fn
    return deco


def load_catalog(path=None):
    path = path or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "error_catalog.yaml")
    with open(path, encoding="utf-8") as f:
        cat = yaml.safe_load(f)["errors"]
    for e in cat:
        if e["injector"] not in _REGISTRY:
            raise ValueError("Unknown injector: %s" % e["injector"])
    return cat


def apply_error(entry, tx, ctx, rng):
    """ctx: {'used_uetrs': [...]} shared batch state."""
    return _REGISTRY[entry["injector"]](tx, ctx, rng)


@injector("iban_invalid_checksum")
def _iban_checksum(tx, ctx, rng):
    p = tx["cdtr"]
    if not p.get("iban"):
        p.update(datapool.make_party(rng, "DE"))
    iban = p["iban"]
    bad = (int(iban[2:4]) % 97) + 2  # guaranteed different, keeps 2 digits
    p["iban"] = iban[:2] + "%02d" % (bad if bad != int(iban[2:4]) else bad + 1) + iban[4:]
    return "CdtrAcct IBAN %s hat ungueltige Pruefziffer (war %s)" % (p["iban"], iban)


@injector("iban_wrong_length")
def _iban_length(tx, ctx, rng):
    p = tx["cdtr"]
    if not p.get("iban"):
        p.update(datapool.make_party(rng, "FR"))
    iban = p["iban"]
    p["iban"] = iban[:-2]
    return "CdtrAcct IBAN %s ist 2 Zeichen zu kurz fuer %s" % (p["iban"], iban[:2])


@injector("bic_iban_country_mismatch")
def _bic_iban_mm(tx, ctx, rng):
    p = tx["cdtr"]
    if not p.get("iban"):
        p.update(datapool.make_party(rng, "NL"))
    iban_ctry = p["iban"][:2]
    others = [a for a in datapool.AGENTS if a["ctry"] != iban_ctry]
    tx["cdtr_agt_bic"] = rng.choice(others)["bic"]
    return "CdtrAgt %s (Land %s) passt nicht zur IBAN %s (Land %s)" % (
        tx["cdtr_agt_bic"], tx["cdtr_agt_bic"][4:6], p["iban"], iban_ctry)


@injector("bic_invalid_country")
def _bic_invalid_country(tx, ctx, rng):
    fake = rng.choice(["ZAPHZZ22XXX", "QUUXXX33XXX", "NOBKQQ2LXXX"])
    tx["cdtr_agt_bic"] = fake
    return ("CdtrAgt BIC %s traegt ungueltigen Laendercode '%s' (kein ISO-3166)"
            % (fake, fake[4:6]))


@injector("beneficiary_name_incomplete")
def _benef_name(tx, ctx, rng):
    full = tx["cdtr"]["nm"]
    tx["cdtr"]["nm"] = full.split()[0][:1] + "."
    return "Cdtr Name '%s' unvollstaendig (vollstaendig: '%s')" % (tx["cdtr"]["nm"], full)


@injector("address_incomplete")
def _addr_incomplete(tx, ctx, rng):
    p = tx["cdtr"]
    p["strt"] = p["bldgnb"] = p["pstcd"] = p["twn"] = None
    return "Cdtr Adresse nur mit Land %s, Strasse/Ort fehlen" % p["ctry"]


@injector("duplicate_uetr")
def _dup_uetr(tx, ctx, rng):
    if ctx["used_uetrs"]:
        tx["uetr"] = rng.choice(ctx["used_uetrs"])
        return "UETR %s bereits im Batch verwendet (Duplikat)" % tx["uetr"]
    return None  # no earlier UETR -> injection not possible, message stays clean


@injector("xchg_rate_inconsistent")
def _fx_inconsistent(tx, ctx, rng):
    tx["instd_ccy"] = "USD" if tx["ccy"] != "USD" else "GBP"
    tx["instd_amt"] = tx["amt"]
    tx["xchg_rate"] = "0.5"  # implies settlement ~= half of instructed -> inconsistent
    return ("InstdAmt %s %s * XchgRate 0.5 != IntrBkSttlmAmt %s %s"
            % (tx["instd_amt"], tx["instd_ccy"], tx["amt"], tx["ccy"]))
