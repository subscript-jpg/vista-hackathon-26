import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pacs008_generator.iban_validator import IBAN_LENGTHS, is_valid, validate_iban

VALID = [
    "CH9300762011623852957", "DE89370400440532013000", "GB29NWBK60161331926819",
    "FR1420041010050500013M02606", "NL91ABNA0417164300", "BE68539007547034",
    "IT60X0542811101000000123456", "ES9121000418450200051332",
    "AT611904300234573201", "PL61109010140000071219812874",
    "SA0380000000608010167519", "BR1800360305000010009795493C1",
    "AE070331234567890123456", "TR330006100519786457841326",
    "NO9386011117947", "MT84MALT011000012345MTLCAST001S",
]


def test_valid_ibans_worldwide():
    for iban in VALID:
        r = validate_iban(iban)
        assert r["valid"], (iban, r["errors"])


def test_paper_format_normalized():
    assert is_valid("CH93 0076 2011 6238 5295 7")
    assert is_valid("de89 3704 0044 0532 0130 00")


def test_invalid_checksum():
    r = validate_iban("CH9400762011623852957")
    assert not r["valid"]
    assert any(e["code"] == "IBAN_INVALID_CHECKSUM" for e in r["errors"])


def test_wrong_length():
    r = validate_iban("DE8937040044053201300")  # 21 statt 22
    assert any(e["code"] == "IBAN_WRONG_LENGTH" for e in r["errors"])


def test_unknown_country():
    r = validate_iban("ZZ68539007547034")
    assert any(e["code"] == "IBAN_COUNTRY_UNKNOWN" for e in r["errors"])


def test_bad_format():
    r = validate_iban("DE89-!!37")
    assert any(e["code"] == "IBAN_INVALID_FORMAT" for e in r["errors"])


def test_invalid_check_digits_rule():
    r = validate_iban("DE00370400440532013000")
    assert any(e["code"] == "IBAN_INVALID_CHECKDIGITS" for e in r["errors"])


def test_generator_errors_are_detected():
    """Die vom Generator injizierten IBAN-Fehler muessen erkannt werden."""
    from pacs008_generator.generator import generate_batch
    for code in ("IBAN_INVALID_CHECKSUM", "IBAN_WRONG_LENGTH"):
        m = generate_batch(count=6, error_rate=1.0, error_codes=[code],
                           seed=5, write_files=False)
        for msg in m["messages"]:
            bad_iban = msg["xml"].split("<pacs:CdtrAcct>")[1].split(
                "<pacs:IBAN>")[1].split("<")[0]
            r = validate_iban(bad_iban)
            assert not r["valid"], (code, bad_iban)
            assert any(e["code"] == code for e in r["errors"]), (code, r["errors"])


def test_registry_plausible():
    assert len(IBAN_LENGTHS) >= 85
    assert all(15 <= n <= 34 for n in IBAN_LENGTHS.values())
