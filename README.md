# padan

*Padan* (Indonesian): to match, to correspond. *Padanan* is a translator's word for an equivalent term.

padan reads a travel partner's booking API documentation and maps each of the partner's fields onto
one canonical booking schema: Viator's `booker.email` is the booking's `contact.email`, GetYourGuide's
`booking_status` is its `status` (after asking GetYourGuide what its codes mean). From those labels it
generates a readable partner client, in both directions, with no LLM.

Deterministic rules decide what they can; Claude sees only the fields the rules leave; and a field
whose meaning is critical and undocumented is **asked, never guessed**.

## Results

Measured on three partners the system had never seen, pre-registered before any of their specs was
opened, labelled by hand, sealed, and run once ([full report](docs/report.md)).

| | Dev (4 partners, used for tuning) | **Test (Viator, GetYourGuide, Musement)** |
| --- | --- | --- |
| Name matching (baseline) | 0.20 macro F1 | 0.09 |
| Rules alone | 0.60 | 0.22 |
| **Rules + Claude Opus 5.5** | **0.89**, 0 critical errors | **0.64**, 5 critical errors (0.72 and 4 after a declared labelling slip) |
| Cost of the Claude run | $0.67 | $1.40, about $0.004 per field |

- **Viator alone**, the one test spec whose answer key no AI tool ever touched: **0.74**.
- **Generated clients (M3):** Viator's create request, generated from the labels, is valid against
  Viator's own request schema, from the hand-labelled gold and from Claude's predictions alike. Every
  other failure is named: fields the partner needs that padan's schema does not hold, questions only a
  person can answer, and data the spec's examples do not contain.
- **Total spent on the Claude API for the whole project:** about $3.23.

## How it works

```
partner docs ─► extract ─► rules ─► Claude ─► labels ─► score against hand-labelled gold
 (OpenAPI,      fields +    lexicon,  only the    map / NONE /
  HTML+XML)     evidence    escalation fields the  ASK_PARTNER
                            policy     rules left
                                               └──► generate ─► client_<partner>.py ─► partner schema check
```

1. **Extract** (`fetch`, `bundle`, `extract`): partner specs fetched reproducibly (hash-locked; Redoc
   pages and split GitHub specs bundled), every in-scope field listed with its documentation.
2. **Rules** (`tokens`, `candidates`, `engine`, `enums`): a lexicon of partner vocabulary and an
   escalation policy. Free, deterministic and explainable (M1).
3. **Claude** (`llm`, `hybrid`): one call per field the rules leave blank, with a cached system prompt,
   structured output, and a disk cache so re-runs cost nothing (M2).
4. **Score** (`score`, `report`): mapping F1, escalation precision and recall, transform accuracy,
   and silent critical errors: a wrong value written into a critical field without a question.
5. **Generate** (`plan`, `generate`, `runtime`, `integration`): labels become plain Python that maps a
   partner response to a canonical booking and a booking to the partner's request; `derived` and `ask`
   labels become TODOs, never guesses (M3).

## Running it

```bash
uv sync
make check                       # ruff, mypy --strict, pytest
make fetch                       # download and hash-check the partner specs into data/raw/
make baselines rules             # dev predictions, free
make score PRED=data/predictions/rules_general
make hybrid MODEL=claude-opus-5-5 BASE=general   # needs ANTHROPIC_API_KEY in .env
make m3                          # generate every client and check it against the partners' schemas
```

The test set is gated: `make test-*` targets refuse to run unless every test label file is sealed and
unchanged (`make verify`), and the frozen Claude run refuses a second start.

## Repository

| Path | What |
| --- | --- |
| `src/padan/` | the pipeline (see How it works) |
| `data/manifest.yaml`, `data/specs.lock.json` | which specs, from where, and their hashes |
| `data/labels/` | dev gold; `test/` the sealed test gold; `test-corrected/` the sealed slip fix |
| `data/rules/lexicon.yaml` | the rules' vocabulary, each entry with the specs it was learnt from |
| `docs/report.md` | the results report |
| `docs/adr/ADR-001-scope-and-labels.md` | scope, label format, scoring and every amendment, incl. the test pre-registration (6) |
| `docs/milestones/` | M1 (rules) and M3 (generated clients) |
| `docs/journal.md`, `docs/metrics.md` | day-by-day decisions and numbers |

## Licence

MIT, covering this repository's code and labels. Third-party API specifications are fetched from their
sources and remain under their providers' terms; they are not redistributed here.
