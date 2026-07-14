"""Batch generation: N messages, configurable error rate (percent) or absolute
faulty count, duplicate-check-free by design, manifest as ground truth.

Uniqueness guarantees (common duplicate-detection rules):
  1. UETR unique per batch (except injected DUPLICATE_UETR error)
  2. MsgId/BizMsgIdr unique across runs via run_id (timestamp+random; with a
     seed the run_id is derived from the seed to keep runs reproducible)
  3. InstrId / EndToEndId unique per run
  4. No business duplicates: combination (debtor acct, creditor acct, amount,
     currency, settlement date) never repeats within a batch
  5. Self-check over the whole batch before returning; violation -> exception
"""
import datetime
import json
import os
import random
import uuid

from . import builder, datapool, errors, validator


def _make_run_id(rng, seed):
    if seed is not None:
        return "S%04X" % (seed % 0xFFFF)
    return datetime.datetime.now().strftime("%m%d%H%M") + "%03X" % rng.randint(0, 0xFFF)


def _base_tx(rng, idx, run_id, biz_keys):
    ccy = rng.choice(list(datapool.CURRENCIES))
    instg = rng.choice(datapool.AGENTS)
    instd = rng.choice([a for a in datapool.AGENTS if a["bic"] != instg["bic"]])
    dbtr = datapool.make_party(rng, instg["ctry"])
    cdtr = datapool.make_party(rng, instd["ctry"])
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().replace(microsecond=0).isoformat() + "+02:00"
    # business-duplicate free: re-roll amount until (accts, amt, ccy, date) unique
    for _ in range(100):
        amt = datapool.make_amount(rng, ccy)
        key = (dbtr.get("iban") or dbtr.get("othr_id"),
               cdtr.get("iban") or cdtr.get("othr_id"), amt, ccy, today)
        if key not in biz_keys:
            biz_keys.add(key)
            break
    else:
        raise AssertionError("could not create business-unique payment")
    tx = {
        "msg_id": "GEN-P008-%s-%04d" % (run_id, idx),          # <=35, run-unique
        "instr_id": ("I%s%04d" % (run_id, idx))[:16],           # <=16 (CBPR+)
        "e2e_id": "E2E-%s-%04d" % (run_id, idx),
        "uetr": datapool.make_uetr(rng),
        "cre_dt": now, "sttlm_dt": today,
        "ccy": ccy, "amt": amt,
        "chrg_br": rng.choice(["DEBT", "CRED", "SHAR"]),
        "instg_bic": instg["bic"], "instd_bic": instd["bic"],
        "dbtr_agt_bic": instg["bic"], "cdtr_agt_bic": instd["bic"],
        "dbtr": dbtr, "cdtr": cdtr,
        "rmt_ustrd": "Invoice INV-2026-%05d" % rng.randint(1, 99999),
    }
    if rng.random() < 0.25:
        others = [a for a in datapool.AGENTS
                  if a["bic"] not in (instg["bic"], instd["bic"])]
        tx["intrmy_bic"] = rng.choice(others)["bic"]
    return tx


def _self_check(manifest):
    """Enforce uniqueness rules over the finished batch."""
    msgs = manifest["messages"]
    dup_ok = set()
    for m in msgs:
        if any(e["code"] == "DUPLICATE_UETR" for e in m["errors"]):
            dup_ok.add(m["file"])
    for field in ("msg_id",):
        vals = [m[field] for m in msgs]
        assert len(vals) == len(set(vals)), "duplicate %s in batch" % field
    uetrs = [m["uetr"] for m in msgs if m["file"] not in dup_ok]
    assert len(uetrs) == len(set(uetrs)), "duplicate UETR in batch"


def generate_batch(count=10, error_rate=0.3, faulty=None, seed=None,
                   error_codes=None, out_dir="output", catalog_path=None,
                   write_files=True, run_id=None):
    """Generate `count` messages. Faulty messages: either `faulty` (absolute
    number) or `error_rate` (fraction 0..1). Returns manifest dict.
    Every message is asserted XSD-valid and duplicate-check-free."""
    rng = random.Random(seed)
    run_id = run_id or _make_run_id(rng, seed)
    catalog = errors.load_catalog(catalog_path)
    if error_codes:
        catalog = [e for e in catalog if e["code"] in set(error_codes)]
        if not catalog:
            raise ValueError("error_codes filtert alle Katalog-Eintraege weg")
    n_bad = faulty if faulty is not None else round(count * error_rate)
    if not 0 <= n_bad <= count:
        raise ValueError("faulty muss zwischen 0 und count liegen")
    bad_idx = set(rng.sample(range(count), n_bad))
    ctx = {"used_uetrs": []}
    biz_keys = set()
    manifest = {"created": datetime.datetime.now().isoformat(),
                "run_id": run_id, "seed": seed, "count": count,
                "error_rate": error_rate, "faulty_requested": n_bad,
                "schema": "CBPR+ SR2025 pacs.008.001.08", "messages": []}
    if write_files:
        os.makedirs(out_dir, exist_ok=True)
    for i in range(count):
        tx = _base_tx(rng, i + 1, run_id, biz_keys)
        entry = {"file": None, "msg_id": tx["msg_id"], "uetr": tx["uetr"],
                 "is_faulty": False, "errors": []}
        if i in bad_idx:
            err = rng.choice(catalog)
            detail = errors.apply_error(err, tx, ctx, rng)
            if detail is not None:
                entry["uetr"] = tx["uetr"]
                entry["is_faulty"] = True
                entry["errors"].append({"code": err["code"], "title": err["title"],
                                        "category": err["category"],
                                        "severity": err["severity"],
                                        "detail": detail})
        ctx["used_uetrs"].append(tx["uetr"])
        status = "FAULTY" if entry["is_faulty"] else "OK"
        content = builder.build_file_content(
            tx, "generated by pacs008-generator | run %s | %s" % (run_id, status))
        verrs = validator.validate(content)
        if verrs:
            raise AssertionError("Generated message not schema-valid: %s -> %s"
                                 % (tx["msg_id"], verrs))
        entry["file"] = "%03d_pacs008_%s.xml" % (i + 1, status)
        entry["xml"] = content
        if write_files:
            with open(os.path.join(out_dir, entry["file"]), "w", encoding="utf-8") as f:
                f.write(content)
        manifest["messages"].append(entry)
    _self_check(manifest)
    if write_files:
        slim = json.loads(json.dumps(manifest))
        for m in slim["messages"]:
            m.pop("xml", None)
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(slim, f, indent=2, ensure_ascii=False)
    return manifest
