# pacs008-generator

CBPR+ pacs.008 Meldungsgenerator für den Vista Hackathon (Use Case A — SWIFT
Exceptions & Investigations). Erzeugt eine konfigurierbare Anzahl Meldungen,
davon ein konfigurierbarer Anteil mit zufälligen **Business-Fehlern** aus einem
erweiterbaren Fehlerkatalog.

**Design-Prinzip:** Alle Meldungen — auch die fehlerhaften — sind **XSD-valide**
gegen die offiziellen CBPR+ SR2025 Schemas (`schemas/`). Injizierte Fehler sind
Geschäftsfehler (IBAN-Prüfziffer, BIC↔IBAN-Mismatch, Beneficiary unvollständig, …),
wie sie in der Realität downstream Exceptions auslösen.
Jede erzeugte Meldung wird vor dem Output automatisch gegen das XSD geprüft.

## Quickstart

```bash
pip install -r requirements.txt

# 20 Meldungen, 30% fehlerhaft, reproduzierbar
python -m pacs008_generator --count 20 --error-rate 0.3 --seed 42

# oder absolut: genau 5 fehlerhafte von 20
python -m pacs008_generator --count 20 --faulty 5

# Fehlerkatalog anzeigen / nur bestimmte Fehler
python -m pacs008_generator --list-errors
python -m pacs008_generator --count 10 --errors IBAN_INVALID_CHECKSUM DUPLICATE_UETR
```

Output: `output/NNN_pacs008_{OK|FAULTY}.xml` + **`manifest.json`** (Ground
Truth: welche Datei welchen Fehler enthält). Alle Fehler sind aus der Meldung
bzw. dem Batch selbst erkennbar — keine simulierten Zusatzsysteme.

## Duplicate-Check-Free (Uniqueness-Garantien)

Der Generator erzeugt Meldungen, die gängige Duplikatsprüfungen sauber passieren:
UETR unique (UUID v4, batch-geprüft), MsgId/InstrId/EndToEndId run-scoped eindeutig
(Run-ID aus Zeitstempel; mit Seed deterministisch), keine fachlichen Duplikate
(Kombination Debtor-Konto/Creditor-Konto/Betrag/Währung/Valuta nie doppelt).
Self-Check über den ganzen Batch vor Output. Einzige gewollte Ausnahme: der
injizierte Fehler `DUPLICATE_UETR`.

## Demo-UI + API

```bash
uvicorn pacs008_generator.api:app --port 8080
# UI:      http://localhost:8080/
# Swagger: http://localhost:8080/docs
```

UI: Anzahl, Fehlerquote % oder absolute Anzahl, Seed, Fehlertypen-Auswahl →
Generieren → Ergebnistabelle (Datei/Status/Fehler/Detail), Klick auf Zeile zeigt
das XML, Button «Output-Ordner öffnen» öffnet `output/ui-runs/<run_id>/` im Finder.

Endpoints:
- `GET /errors` — Fehlerkatalog (für Checkbox-Liste im UI)
- `POST /generate` — `{"count": 20, "error_rate": 0.3, "faulty": null, "seed": 42, "error_codes": null, "include_xml": true, "write_files": true}`
  → Manifest inkl. XML, schreibt Dateien nach `output/ui-runs/<run_id>/`
- `POST /runs/{run_id}/open` — öffnet den Run-Ordner (lokale Demo)

## Struktur

```
pacs008_generator/
  datapool.py    Referenzdaten (Agents, Parteien, IBAN-Konstruktion mit Mod-97)
  builder.py     XML-Bau (AppHdr head.001.001.02 + Document pacs.008.001.08)
  errors.py      Fehler-Injektoren (arbeiten auf tx-Dict, vor XML-Bau)
  validator.py   XSD-Validierung (CBPR+ SR2025)
  generator.py   Batch-Orchestrierung + Manifest
  __main__.py    CLI
  api.py         FastAPI-Wrapper
error_catalog.yaml   Fehlerkatalog — neue Fehler hier + Injektor in errors.py
schemas/             Offizielle CBPR+ XSDs (MyStandards — nur interner Gebrauch!)
tests/               pytest-Suite
```

## Fehlerkatalog erweitern

1. Eintrag in `error_catalog.yaml` (code, title, category, severity, injector)
2. Injektor-Funktion in `errors.py` mit `@injector("name")` registrieren —
   sie mutiert das `tx`-Dict und gibt einen Detail-Text fürs Manifest zurück
3. `pytest` laufen lassen — `test_every_injector_stays_schema_valid` prüft
   automatisch jeden Katalog-Eintrag auf XSD-Konformität

## Tests

```bash
python -m pytest tests/ -v
```

Abgedeckt: XSD-Validität aller Outputs, Fehlerquote & Manifest-Konsistenz,
Seed-Reproduzierbarkeit, Fehlercode-Filter, jeder Injektor einzeln, Datei-/
Manifest-Output, Fehlerbehandlung.

## Hinweise

- Python ≥ 3.9, keine Netzwerkzugriffe zur Laufzeit (AWS-tauglich, air-gapped ok)
- `schemas/` unterliegt der MyStandards-Lizenz (Swift) — nur interner Gebrauch
- BizSvc `swift.cbprplus.03` (SR2025), Envelope/Transport-Header ist Sache des Senders
