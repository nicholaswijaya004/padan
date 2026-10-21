# ADR-001: Scope, label format and scoring

**Status:** Accepted
**Date:** 2026-10-13
**Evidence:** `data/labels/dry_run.yaml` (format rehearsal on a made-up API). Nothing has been measured
yet; every number in this ADR is a hypothesis.

## Context

padan takes a travel partner's API documentation and produces a field mapping onto a canonical booking
schema, a generated client, and a validation suite.

A partner integration has two parts:

- **Wiring**: turning requests and responses into objects. Mechanical.
- **Mapping**: deciding what each partner field means and what we can construct from it. Judgement.

Mapping is where the expensive errors are, and they fail silently. A per-night price mapped as the
total, or cents read as euros, still produces successful requests and passing contract tests. Only the
money is wrong. So padan's output is not only an adapter: it is an adapter plus a calibrated statement of
which mappings can be trusted. When the documentation does not support a confident answer, the correct
behaviour is to escalate to the partner, as engineers do today.

This ADR fixes what padan is evaluated on before any pipeline code exists, so that no reported number can
be shaped by choosing the scoring after seeing the results.

## Decision

### 1. Scope

- **Phase 1 verticals: activities/tours and cruise.** This matches phase 1 of the original proposal.
- **Flights and hotels are out of phase 1.** Hotels return later as a **held-out generalisation test**:
  3–4 hotel specs are labelled, and the pipeline runs on them with no rule tuned for them.
- **Public specifications only.** No Traveloka partner documentation, in any form.
- **Diversity is counted by spec family.** Specs implementing the same standard (e.g. OCTO) count as one
  family. The manifest records `spec_family`, and results are reported per family and per vertical.
- Public cruise specs are scarce (expected 3–5). Cruise results are reported as case studies, not
  statistics.

### 2. Input formats and two stages

- OpenAPI, XSD (OpenTravel), HTML and PDF are all in scope, because partners without machine-readable
  specs send documents.
- **Stage 1, extraction:** document → list of fields (path, type, description text).
- **Stage 2, mapping:** field list → canonical schema.
- The stages are scored separately:
  - extraction precision/recall, per format;
  - mapping scored against the **gold field list**, so a parsing failure never counts as a mapping error;
  - end-to-end scores reported alongside both.
- Build order: structured formats (OpenAPI, XSD) first and deterministic; HTML and PDF after.

### 3. Label format

One label per partner field, stored as YAML in `data/labels/`.

| Key         | Required               | Meaning                                                                                                                             |
| ----------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `source`    | always                 | `endpoint`, `direction` (request/response), `paths`                                                                                 |
| `target`    | always                 | a canonical field, `NONE` (no counterpart) or `ASK_PARTNER` (docs too unclear)                                                      |
| `kind`      | canonical targets only | `direct`, `transform` or `derived`                                                                                                  |
| `transform` | transform/derived only | named function; may take other fields as inputs, e.g. `minor_units_to_decimal(currencyCode)`, `add_days(stay.checkIn, stay.nights)` |
| `evidence`  | always                 | the sentence from the documentation that justifies the label                                                                        |
| `candidate` | `ASK_PARTNER` only     | the canonical field suspected                                                                                                       |
| `question`  | `ASK_PARTNER` only     | the exact question to send the partner                                                                                              |

**Path syntax:** dotted names; `[n]` for a list position; `[field=value]` for a filter, e.g.
`guests[isLead=true].firstName`. If the documentation does not say how to select an item, the label is
`ASK_PARTNER`.

### 4. Scoring

- **Target F1** on (partner field → target) pairs. `NONE` and `ASK_PARTNER` are explicit labels, never
  the absence of one.
- **Transform accuracy**, measured on fields whose target is correct.
- **Escalation precision and recall** on `ASK_PARTNER`.
- Many-to-one sources (first + last name) are separate labels with separate credit.
- Canonical fields we generate ourselves (e.g. `our_booking_id`) are never labelled. Canonical fields
  marked as partner-sourced and required, but filled by no partner field, are reported as **integration
  gaps**. This needs a `source: ours | partner` tag on each canonical field.

### 5. Escalation policy

The two kinds of error do not cost the same. Wrongly mapping a cancellation or price field costs money
and trust; wrongly escalating costs one email to the partner. Thresholds are therefore **per field
criticality**:

- money and policy fields (price, tax, cancellation, refund) escalate unless confidence is high;
- display-only fields tolerate a guess.

The actual thresholds are set later, from labelled data, in their own ADR.

### 6. Code generation

Wiring is mechanical, so the client is generated from templates, deterministically, **with no LLM**. LLM
spend goes only to mapping and to HTML/PDF extraction.

### 7. Gold set integrity

- Labels are written by hand, by me, before the pipeline is run on that spec.
- No LLM-drafted labels: anchoring would leak the model's errors into the answer key and inflate its score.
- A subset is re-labelled blind later to measure my own consistency. Score differences smaller than my
  self-disagreement are reported as noise.

## Rejected alternatives

| Alternative                      | Rejected because                                                                                                                                     |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| All verticals in phase 1         | The canonical schema and labelling cost explode; the generalisation claim is better tested by holding out a vertical                                 |
| OpenAPI only                     | Partners without specs send PDF/HTML. The real concern (parsing errors polluting mapping scores) is solved by scoring the two stages separately      |
| Score target selection only      | A mapping to the right field without the cents conversion would count as correct: the most dangerous error class would be invisible to the benchmark |
| Treat unlabelled as "no mapping" | A pipeline that maps every field would never be penalised for false positives                                                                        |
| One global confidence threshold  | Ignores that a wrong cancellation mapping costs far more than an unnecessary escalation                                                              |
| LLM-generated client code        | Wiring is mechanical; spending budget and adding nondeterminism there buys nothing                                                                   |

## Consequences

- Labelling covers both the field list (for extraction) and the mapping, so it costs more than mapping
  labels alone. Block 5's timing on the first real spec decides whether 20 specs is realistic.
- HTML/PDF extraction will consume LLM budget, and must fit within the project's USD 40–80 total.
- Results are reported in many slices (vertical, family, format, stage) with small n each, so counts are
  reported alongside percentages.

## Open questions

- LLM provider, and the hard spend limit in its console.
- Canonical schema v0 (Block 4): one shared core plus vertical extensions for cruise and activities?
- Whether the transform vocabulary is a closed list.
- Single-name travellers: the canonical schema cannot assume a last name exists.

## Amendment 1 — 2026-10-13: dataset size, PDF, Bókun

Verification of 25 candidate specs (`data/manifest.yaml`) left 12 usable: 10 activities specs across
9 families, and 2 cruise specs across 2 families. Accordingly:

- **Target lowered from 20 specs to the 12 verified ones**, to be expanded later. Results are reported
  per spec family, so the family count, not the spec count, is the honest measure of diversity.
- **No public PDF spec survived verification.** PDF is evaluated with synthetic variants: two HTML specs
  (Checkfront v3, Widgety) printed to PDF. They share their originals' labels, are not counted as extra
  specs, and are reported as an HTML-vs-PDF extraction comparison on identical content. Printed PDFs are
  cleaner than real partner PDFs, so these results are an upper bound.
- **Bókun excluded:** its API Terms (clause 2.3.4) forbid use "for any similar benchmarking purposes".
- **Cruise is reported as a case study** (2 families), not as statistics.

_Restored 2026-10-16: drafted and agreed on Day 1, but missing from the merged ADR._

## Amendment 2 — 2026-10-16: dev/test split

Day 3 measured labelling at 1.33 min/field for judgement alone; with review, adjudication and validator
fixes the full cost is estimated at about twice that. Labelling all 12 specs before building rules would
take 3–4 working days, and every rule written while reading those labels would then be scored on them.
That is training-set accuracy, the same leakage the hotel held-out set exists to prevent, one level down.
Accordingly:

- **The benchmark is split into `dev` and `test`.** `role` in `data/manifest.yaml` is now
  `dev | test | held_out` (replacing `benchmark`).
  - **dev:** rules are written and tuned while reading these labels.
  - **test:** labels are not opened until measurement. No rule is changed because of a test result.
  - **held_out:** unchanged (hotels, never tuned on).
- **The split**, chosen for diversity so rules do not fit one documentation style:

  | Role | Specs                                                                                                                            | Why                                                                     |
  | ---- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
  | dev  | headout-partner                                                                                                                  | Well documented (87% field descriptions); already labelled              |
  | dev  | octo-core                                                                                                                        | An open standard; conventions shared by its implementations             |
  | dev  | hotelbeds-activities                                                                                                             | Weakly documented (0% descriptions, no response schemas): the hard case |
  | dev  | widgety-cruise-v2                                                                                                                | Cruise, HTML format                                                     |
  | test | viator-partner, getyourguide-partner, musement-partner, rezdy-agent, rezdy-connect, checkfront-v3, fareharbor-external, hx-swota | 8 specs, 7 families, both verticals, OpenAPI, HTML and PDF              |

- **A `spec_family` never appears in more than one role.** A spec sharing a family with a dev spec would
  test the rules on conventions they were tuned on. So synthetic PDF twins, once created, take their original's role,
  `octo-zaui` is dev if it becomes usable, and `hotelbeds-hotels` is no longer usable as held-out
  (hotelbeds family is dev). Held-out hotel specs must come from families not in dev. A test over the
  manifest enforces this rule.
- **Order of work:** dev specs are labelled before M1; test specs after rule engine v1. Labelling test
  specs after the rules exist also prevents labelling them towards the rules.
- **Reporting:** the headline is F1 on **test**. Dev F1 is reported beside it; the gap between them is
  overfitting, made visible. Cruise has one family in each role and stays a case study.
- **Labelling scope per spec: booking create and booking get only.** The canonical schema is a booking;
  cancellation and availability need their own schemas and are out of phase 1.
- **The sealed-draft comparison continues for every spec.** It changed 11 of 45 Headout labels (24%).
  Re-checked after 3 specs: below about 10% changes, it continues for dev specs only.

## Amendment 3 — 2026-10-16: HX replaces Widgety in dev

Widgety's public documentation (Cruises API v2, "Fields Explained") covers only content requests
(cruise search, fare sets, port visits); its booking endpoints need a test key. Under Amendment 2's
booking-only scope it cannot teach the rules anything about cruise bookings. HX SWOTA documents
storing and retrieving bookings publicly (OpenTravel messages).

- `hx-swota` moves to dev, with `opentravel-cruise-xsd` (same family).
- `widgety-cruise-v2` moves to test. It has no booking endpoints, so it is labelled on all documented
  fields; most are expected to be `NONE`, which measures over-mapping on a content API.
- HX labelling scope: "Storing a Booking" and "Retrieving Bookings".
- HX partner terms restrict copying the API or API data (cl. 2.6): raw HX pages are never committed,
  only their hashes.

## Amendment 4 — 2026-10-16: labelling method by role, catalogue objects out of scope

Day 3 measured hand-labelling at 1.33 min/field for judgement alone, with review changing 24% of labels
and the validator finding format errors in 51%. At that cost the remaining 11 specs (about 900 fields
before scoping) would take 25–35 hours of labelling. The cost of protecting a label set should follow
what the labels are used for. Accordingly, §7 ("gold labels written by hand") now applies by role:

- **Dev labels: model-drafted, human-reviewed.** Claude drafts every entry for a dev spec; the labeller
  reviews and corrects each one. Dev labels are only used to write and tune rules; no reported headline
  number comes from them. To measure anchoring (accepting a wrong draft because it is already written),
  each dev spec starts with a **blind sample**: 10 entries chosen by a fixed random seed, labelled by hand
  before the draft is seen. Reported per spec: blind-sample agreement with the draft, and the share of
  draft entries the review changed. `headout-partner` stays hand-labelled (Day 3).
- **Test labels: human-only, labelled from the canonical side.** For each canonical field the labeller
  finds the partner field(s) that carry it, or records `ASK_PARTNER`. Every partner field not chosen is
  set to `NONE` mechanically by a script, with no model, and the labeller then reviews that `NONE` list.
  The label file format is unchanged, so the validator and the scorer are unchanged. The sealed-draft
  comparison (Amendment 2) continues for test specs and catches mappings the labeller missed.
- **Embedded catalogue objects are out of scope.** When a booking response repeats catalogue definitions
  (e.g. OCTO's `product.*`, `option.*`, `unitItems[].unit.*`), those fields are not labelled; their
  identifiers at booking level (e.g. `productId`, `optionId`, `unitItems[].unitId`) are. The rule
  applies to every spec, so the extraction and mapping stages are scored on the same scoped field list.
- **Known limitation: one labeller.** There is no second human annotator, so inter-annotator agreement is
  not measured; the sealed model draft is a second opinion, not a second human. Before results are
  published, a second person labels a 20% sample of one test spec.

## Amendment 5 — 2026-10-21: schema v3, a booking holds items

Schema v2.1 assumed a booking contains exactly one thing. Dev labelling and the first baseline run
(Day 6) showed four symptoms of that one assumption:

- Hotelbeds books several `activities[]` in one booking; only `activities[0]` could be labelled.
- A cruise booking can hold several cabins; `cruise.cabin_number` held one.
- "Which variant was bought" lived in two places: `activity.option_id`, and
  `cruise.fare_category_code` (a misnomer: OpenTravel's `PricedCategoryCode` is a cabin category).
- `cruise.voyage_id` duplicated `product_id` ("product (or sailing) identifier") and, unused after
  the HX review, drew a false positive from the name-match baseline on its first run.

The labeller's industry experience (Traveloka: a product ID plus an item ID per booked line) points to
the same model. This amendment also records the rule the schema has followed since Day 4: **the schema
is designed only from dev specs, published standards (OpenTravel, OCTO) and OTAs outside the benchmark
(Traveloka), never from test specs**, so test mappings are not made easier by design.

**Decision: schema v3.** Fields move to the level where they vary.

- `Booking` keeps everything that exists once per booking: identifiers, status and hold, `booked_at`,
  `redeemed_at`, `contact`, `travellers[]`, `total_price`, `net_price`, `cancellable`,
  `cancellation_policy`, `fulfilment[]`, `custom_fields[]`, and `balance_due_date` (moved up from
  `cruise.*`: payment schedules belong to the booking, and activities take deposits too).
- New `items[]` (at least one): `product_id`, `product_name`, `option_id`, `option_name`, start and end
  date and time, and exactly one of `activity` (`slot_id`, `service_language`) or `cruise`
  (`cabin_number`, `deck`). A single-item partner maps to `items[]` as a list of one.
- Removed: `cruise.voyage_id` (now `items[].product_id`) and `cruise.fare_category_code` (now
  `items[].option_id`). Valid targets: 56 → 55 (`items[]` itself becomes a target, like `travellers[]`).
- Not added: a price per item. No dev label would use it, and a field without evidence cannot be
  checked. It may be added before test labelling if evidence appears, never after.
- Canonical fields store facts, not composite keys. Identifiers such as Traveloka's
  `SHIP_3D2N_SG-PENANG-SG` are views built from the parts by the consumer (generated code), because
  building a key from parts always works and parsing one back does not.

**Migration.** The four dev label files were migrated by a mechanical rename (35 targets and
`ASK_PARTNER` candidates; one judgement, HX `PricedCategoryCode` → `items[].option_id`, decided in
review), and Hotelbeds source paths `activities[0].*` became `activities[].*`. The validator rejects
every v2.1 target, so no stale label can survive. No test label existed, so the change costs nothing in
evaluation integrity; baselines are re-measured on v3 and v2.1 numbers are not compared with later ones.

**Known limitation: travellers are per booking.** Which traveller takes part in which item is not
modelled. It loses information for one dev spec (Hotelbeds `activities[].paxes[]`); the other three list
travellers once per booking.
