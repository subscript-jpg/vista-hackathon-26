# pacs.008 Error List — Use Case A (SWIFT Exceptions & Investigations)

Error catalog for the pacs.008 CBPR+ test-message generator and the AI analysis
agent. **Design principle:** every injected message remains XSD-valid (CBPR+
SR2025); all errors are *business* errors and are detectable **without any
external or simulated systems** — either from the message itself, from the
batch, or via a short static lookup table (ISO standards). Ground truth for
benchmarking the agent is delivered in `manifest.json` per generated batch.

| # | Code | Error | Detection (no external system) | Severity | Investigation type |
|---|------|-------|--------------------------------|----------|--------------------|
| 1 | `IBAN_INVALID_CHECKSUM` | Creditor IBAN has an invalid check digit | ISO 7064 mod-97 calculation on the IBAN itself | high | UTAP (Unable to Apply) |
| 2 | `IBAN_WRONG_LENGTH` | IBAN length does not match the country | Static ISO 13616 length table (89 countries, included in `iban_validator.py`) | high | UTAP |
| 3 | `BIC_IBAN_COUNTRY_MISMATCH` | Creditor agent BIC country ≠ creditor IBAN country | Compare BIC positions 5–6 with IBAN positions 1–2 (two fields of the same message) | high | UTAP / routing clarification |
| 4 | `BIC_INVALID_COUNTRY` | BIC carries a non-existent country code (e.g. `ZAPHZZ22XXX` → "ZZ") | BIC positions 5–6 against the static ISO 3166 country list | high | Routing / possible return |
| 5 | `BENEFICIARY_NAME_INCOMPLETE` | Creditor name is a fragment/initial (e.g. "P.") | Structural heuristic (length, single initial, placeholder) or LLM plausibility judgement — no reference data | medium | UTAP (strongest demo case) |
| 6 | `ADDRESS_INCOMPLETE` | Creditor postal address contains only the country — no town/street | Structural check on the message (CBPR+ expects at least town + country) | medium | RQFI (compliance) / UTAP |
| 7 | `XCHG_RATE_INCONSISTENT` | InstdAmt × XchgRate deviates strongly from IntrBkSttlmAmt | Pure arithmetic across three fields of the same message (internal consistency, not market-rate validation) | medium | Clarification with instructing agent |
| 8 | `DUPLICATE_UETR` | Two files **within the same batch** carry the same UETR | Batch-level check: the "history" is the set of delivered messages itself — nothing is pre-seeded | high | Duplicate clarification / recall (camt.056) |

## Notes for reviewers

- **Deliberately out of scope:** sanctions/watchlist hits and closed beneficiary
  accounts were removed — they are not detectable by the sender without
  simulated external systems (screening engine, beneficiary bank account data).
- **`DUPLICATE_UETR`** requires the agent to process the batch as a whole (or
  keep a processing history). If the agent strictly analyses one message in
  isolation, this error type should be deselected (possible per run via UI /
  `error_codes`).
- Each generated batch ships a `manifest.json` (which file carries which error,
  incl. detail text) — use it to benchmark agent detection precision/recall.
- Full detection rules per error (fields/XPath, algorithm, suggested action,
  auto-repairability): `agent_error_knowledge.yaml`. Generator side:
  `error_catalog.yaml`. Both are code-synchronised (same 8 codes, tested).
