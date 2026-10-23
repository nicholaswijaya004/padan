# Metrics

Measurements recorded as the project is built. Each entry states what was run,
what was observed, and what it showed.

## Day 1

**Goal:** Build the candidate dataset and fix the label format before any pipeline code.

### Spec sourcing (2026-10-13)

Candidates found by web search, verified logged out by headless browser and direct download.

| Outcome            | Count    | Detail                                                                                                                 |
| ------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------- |
| Candidates checked | 25       | 18 activities, 6 cruise, 1 hotel (held out)                                                                            |
| Usable             | 12 (48%) | 10 activities across 9 families, 2 cruise across 2 families                                                            |
| Unknown            | 7        | Reference not reachable or not yet checked                                                                             |
| Rejected           | 6        | No public docs (Tiqets, Traveltek, Royal Caribbean, Scenic); docs removed (Holibob); terms forbid benchmarking (Bókun) |

| Format of usable specs                   | Count                                     |
| ---------------------------------------- | ----------------------------------------- |
| OpenAPI (direct, multi-file or embedded) | 6                                         |
| HTML                                     | 6                                         |
| PDF                                      | 0 public; 2 synthetic (printed from HTML) |

Explicit permissive licences: 3 (GetYourGuide Apache-2.0, Musement Apache-2.0, Viator CC BY 4.0).

### Label format dry run

10 labels on a made-up API exposed 4 gaps in the format, all fixed before real labelling (ADR-001).

**Not measured:** labelling time per field. The dry-run labels were not written by me, so the first
timing comes from the first real spec (Day 2).

**Caveat:** Spec availability was checked on one day; public docs move and disappear (Holibob's site
was already gone).

## Day 2

**Goal:** Reproducible spec fetching, and a canonical schema to label against.

### Spec fetching

| Spec                 | Bytes                      | SHA-256 (prefix) | Verified                                                            |
| -------------------- | -------------------------- | ---------------- | ------------------------------------------------------------------- |
| hotelbeds-activities | 47,469                     | `a5e3a44e…`      | identical hash from two independent downloads on different machines |
| headout-partner      | see `data/specs.lock.json` |                  | `new`, then `unchanged` on re-run                                   |

### Spec quality (direct-download OpenAPI specs)

| Spec                 | Operations | Fields | Fields with description | Responses with schema |
| -------------------- | ---------- | ------ | ----------------------- | --------------------- |
| Hotelbeds Activities | 13         | 179    | 0 (0%)                  | 0                     |
| Headout              | 20         | 516    | 453 (87%)               | 19                    |
| Musement             | 106        | 724    | 554 (76%)               | 129                   |

Hotelbeds' "OpenAPI" is a converted Postman collection: no descriptions, no response schemas.
Headout chosen as first labelling spec; Hotelbeds kept as the evidence-poor specimen.

### Bugs found by real data (not by synthetic tests)

| Bug                                                     | Found by                                     | Impact if missed                          |
| ------------------------------------------------------- | -------------------------------------------- | ----------------------------------------- |
| Unquoted `yes`/`no` in manifest → booleans (15 values)  | Pydantic `Literal` test on the real manifest | `make fetch` would silently fetch 0 specs |
| Hotelbeds example `2016-04-31` crashed `yaml.safe_load` | first real `make fetch`                      | a valid spec rejected                     |
| Example `zipCode: 07198` → int `7198` under `safe_load` | spec inspection                              | leading zeros lost in extracted values    |

### Tests

46 passing (fetcher, manifest validation, canonical schema).

**Not measured:** time per block (not recorded, start tracking on Day 3); labelling time per
field (Block 3 moved to Day 3).

## Day 3

**Goal:** Label the first real spec by hand, timed, and measure how reliable that label set is.

### Headout labelling (2026-10-15)

| Measure                                             | Value                                                                                |
| --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Fields labelled (booking create + get)              | 45                                                                                   |
| Time (judgement only, with scaffold)                | 60 min → **1.33 min/field**                                                          |
| Same target as the sealed Claude draft              | 21/45 (47%)                                                                          |
| Same concept, different name                        | 7                                                                                    |
| Both flagged a schema gap                           | 3                                                                                    |
| Real disagreements                                  | 14                                                                                   |
| Labels changed after review                         | **11/45 (24%)**                                                                      |
| Labels with format errors (caught by the validator) | **23/45 (51%)**, plus the file name                                                  |
| Final gold set                                      | 54 entries: 38 canonical, 15 `NONE`, 1 `ASK_PARTNER`                                 |
| Schema gaps found                                   | 3 added (slot, booking custom fields, traveller custom fields), 1 deferred (tickets) |
| Tests                                               | 67                                                                                   |

**What it showed:** a single labelling pass is not a gold set. Review changed a quarter of the labels
and the validator found format errors in half. Both steps stay in the process.

**Not measured:** time for the comparison, adjudication and fixes. Tomorrow's plan assumes the full
cost is about twice the judgement time (2.5–3 min/field); time the next spec end to end to check.

**Caveats:** one spec, one labeller. Agreement is with a model draft, not with a second human, so it
measures ambiguity, not accuracy. Headout is well documented (87% descriptions); a weakly documented
spec will be slower.

## Day 4

**Goal:** Re-plan from the measured labelling rate, fetch the dev specs, and label the next dev spec.

### Plan re-estimate (2026-10-16)

| Measure                                      | Value                                         |
| -------------------------------------------- | --------------------------------------------- |
| Day 1 estimate (by analogy with Loka)        | 12 days                                       |
| Re-estimate (rate × volume, plus 30% buffer) | 22–25 working days left, about 28 with buffer |
| Defensible stopping point                    | end of M2, around Day 18–20                   |
| Labelling left before the split              | about 25–35 h                                 |
| Labelling left after Amendments 2 and 4      | about 10–14 h                                 |

### Dataset

| Measure             | Value                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------- |
| Roles               | dev 4 specs (headout, octo-core, hotelbeds-activities, hx-swota), test 8, held-out 0 usable |
| Dev specs fetched   | 4/4 (OCTO pinned to commit; HX as 2 pages)                                                  |
| Widgety             | plain download blocked (Cloudflare challenge, HTTP 403); Zendesk Help Center API works      |
| Spec drift          | Headout: 1 description changed in 2 days (voucher schema), outside the labelled endpoints   |
| OCTO booking fields | 161, of which 71 embedded catalogue fields excluded → 90 in scope                           |
| OCTO doc defects    | 2 fields with no description; 1 copy-paste description (`deliveryValue`)                    |

### Schema

| Measure                       | Value                   |
| ----------------------------- | ----------------------- |
| Valid targets                 | 40 (v1) → **56** (v2.1) |
| Headout labels revised for v2 | 9, all accepted by me   |

### OCTO labelling (dev: model-drafted, human-reviewed, Amendment 4)

| Measure                                      | Value                                                                        |
| -------------------------------------------- | ---------------------------------------------------------------------------- |
| Entries                                      | 92 (90 fields + 2 date/time splits): 46 canonical, 46 `NONE`                 |
| Blind sample agreement with the sealed draft | 6/10 (2 of the 4 differences were schema proposals, not label errors)        |
| Review time                                  | 11 min → **about 7 s/entry** (Headout by hand: 80 s/field, about 11× slower) |
| Rows changed by the review                   | 4/92 (4%), all through a schema gap found during review (redemption time)    |
| Blind sample time                            | not measured                                                                 |

**What it showed:** reviewing a draft is about 11× faster than writing labels, but the gap between
blind agreement (60%) and review changes (4%) points to anchoring. Dev labels are now cheap, with a
known weakness; the headline number stays on human-only test labels.

### Gold set

| Spec            | Entries | Canonical | `NONE` | `ASK_PARTNER` |
| --------------- | ------- | --------- | ------ | ------------- |
| headout-partner | 56      | 39        | 12     | 5             |
| octo-core       | 92      | 46        | 46     | 0             |

### Process

| Measure                            | Value                                                                                             |
| ---------------------------------- | ------------------------------------------------------------------------------------------------- |
| PRs merged                         | 9 (ADP-14 to ADP-22)                                                                              |
| Incomplete changes found on `main` | 3: `pages` tests missing, Amendment 3 roles unapplied through 3 PRs, ADR Amendment 1 never landed |
| Near-miss                          | a stale local ADR would have deleted 2 amendments                                                 |
| Tests                              | 77 → **88**                                                                                       |

**Caveats:** one labeller; one reviewed dev spec so far, so the 7 s/entry and anchoring numbers come
from a single spec. OCTO is well documented and likely in training data, so the draft may be better
here than on Hotelbeds or HX.

## Day 5

**Goal:** Stage 1 extraction as tested code; dev labels for Hotelbeds; extraction from XML examples.

### Stage 1 extraction (2026-10-19)

| Spec                 | Source of fields                           | Fields in scope                                     | Matches gold labels                  |
| -------------------- | ------------------------------------------ | --------------------------------------------------- | ------------------------------------ |
| headout-partner      | OpenAPI schemas                            | 45                                                  | yes: every field and evidence string |
| octo-core            | OpenAPI schemas (inline)                   | 90 (161 before catalogue exclusion)                 | yes                                  |
| hotelbeds-activities | OpenAPI request schema + operation example | 21                                                  | yes                                  |
| hx-swota             | XML examples in 2 HTML pages               | 70 (request 7, create response 50, get response 13) | labels tomorrow                      |

### Spec quality found by extraction

| Measure                                                  | Value                                                              |
| -------------------------------------------------------- | ------------------------------------------------------------------ |
| Hotelbeds booking operations with a documented response  | 0 of 10 (no schema, no example)                                    |
| Hotelbeds fields whose evidence is only an example value | 21/21                                                              |
| HX in-scope XML examples that are not well-formed        | 1 of 3 (`OTA_CruiseBookRS`)                                        |
| HX get-response fields hidden behind `[..]` placeholders | most of the message (13 fields shown vs 50 in the create response) |

### Hotelbeds labelling (dev, hand-labelled, adjudicated against a sealed draft)

| Measure                           | Value                                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Entries                           | 21: 13 canonical, 7 `NONE`, 1 `ASK_PARTNER`                                                                    |
| Agreement with the sealed draft   | 13/21 (62%); blind-sample subset 6/10                                                                          |
| Labels changed after adjudication | 8/21 (38%): 2 slips (surname → given name), 2 joined names despite a separate surname field, 4 judgement calls |
| Time                              | not measured                                                                                                   |

**What it showed:** on an evidence-poor spec, hand labels without a second opinion change much more
(38%) than on a well-documented one (Headout, 24%).

### Gold set so far (dev)

| Spec                 | Entries | Canonical | `NONE` | `ASK_PARTNER` | Method            |
| -------------------- | ------- | --------- | ------ | ------------- | ----------------- |
| headout-partner      | 56      | 39        | 12     | 5             | hand, reviewed    |
| octo-core            | 92      | 46        | 46     | 0             | drafted, reviewed |
| hotelbeds-activities | 21      | 13        | 7      | 1             | hand, adjudicated |
| hx-swota             | —       | —         | —      | —             | tomorrow          |

### Process

| Measure           | Value                                        |
| ----------------- | -------------------------------------------- |
| PRs merged        | 3 (ADP-24 to ADP-26)                         |
| Incomplete merges | 1 (ADP-25: 2 of 4 files; restored in ADP-26) |
| Tests             | 88 → **129**                                 |
| Block times       | not measured                                 |

**Caveats:** HX field paths come from single examples (lists only detected where repeated, one
repaired structure). Stage 1 extraction is not independently scored for OpenAPI.

## Day 6

**Goal:** Dev gold set complete (HX); scorer and baselines.

### HX labelling (dev: model-drafted, human-reviewed, Amendment 4)

| Measure                                      | Value                                                                                  |
| -------------------------------------------- | -------------------------------------------------------------------------------------- |
| Entries                                      | 70: 17 canonical, 5 `ASK_PARTNER`, 48 `NONE`                                           |
| Blind sample agreement with the sealed draft | **4/10** (all 4 on `NONE`); OCTO 6/10, Hotelbeds 6/10                                  |
| Blind disagreements resolved to the draft    | 6/6                                                                                    |
| Blind entries that would fail the validator  | 5/10                                                                                   |
| Draft rows changed by the review             | 4/71: 3 by me (`VoyageID` ×2, `PolicyInfo.Text`), 1 by Claude (`DueDate` split merged) |
| Critical gap found in review                 | 1: `cancellation_policy` unmapped in the draft                                         |
| Time                                         | not measured                                                                           |

**What it showed:** blind agreement was lowest on the spec with no descriptions, and the review still
found a critical gap the draft missed. `ASK_PARTNER` share is highest here (5/70) because HX meanings
depend on undocumented codes.

### Gold set (dev, complete)

| Spec                 | Entries | Canonical | `NONE`  | `ASK_PARTNER` | Method            |
| -------------------- | ------- | --------- | ------- | ------------- | ----------------- |
| headout-partner      | 56      | 39        | 12      | 5             | hand, reviewed    |
| octo-core            | 92      | 46        | 46      | 0             | drafted, reviewed |
| hotelbeds-activities | 21      | 13        | 7       | 1             | hand, adjudicated |
| hx-swota             | 70      | 17        | 48      | 5             | drafted, reviewed |
| **total**            | **239** | **115**   | **113** | **11**        |                   |

### Baselines (dev, schema v2.1)

| Baseline   | Map P | Map R | Map F1 (macro) | Map F1 (micro) | Esc R | Transforms | Critical errors |
| ---------- | ----- | ----- | -------------- | -------------- | ----- | ---------- | --------------- |
| all_none   | —     | 0.00  | 0.00           | 0.00           | 0.00  | —          | 0               |
| name_match | 0.78  | 0.12  | **0.20**       | 0.18           | 0.00  | 0/2        | **4**           |

| name_match per spec  | Map F1 | Critical errors                                                 |
| -------------------- | ------ | --------------------------------------------------------------- |
| headout-partner      | 0.10   | 1 (`status` without `enum_map`)                                 |
| hotelbeds-activities | 0.38   | 0                                                               |
| hx-swota             | 0.10   | 1 (cabin `Status` → booking `status`)                           |
| octo-core            | 0.23   | 2 (`status` without `enum_map`; ticket status → booking status) |

**M1 target (set before any rule exists):** macro F1 above 0.20, fewer than 4 critical errors (goal 0),
escalation recall above 0.

### Process

| Measure                                       | Value                                          |
| --------------------------------------------- | ---------------------------------------------- |
| PRs merged                                    | 2 (ADP-28, ADP-29)                             |
| Incomplete merges                             | 0 (both checked file by file before merge)     |
| Tests                                         | 129 → **175**                                  |
| Transform labels rewritten for the vocabulary | 1 (estimate was 22)                            |
| Scorer bugs found after the first real run    | 1 (Claude's helper: F1 undefined instead of 0) |
| Block times / predictions                     | not measured / not made                        |

**Caveats:** baselines are scored on dev only, against single-labeller gold; the baseline field list
comes from the gold files (equal to Stage 1's by the coverage test). Scores will shift on Day 7 when
schema v3 renames item-level targets.

## Day 7

**Goal:** Schema v3 and migrated labels; baselines re-measured; rule engine designed.

### Schema v3

| Measure                                                 | Value                                                                                  |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Valid targets                                           | 56 (v2.1) → **55** (v3): `voyage_id` and `fare_category_code` removed, `items[]` added |
| Label targets / candidates renamed                      | 35 (32 targets + 3 candidates), 1 of them a judgement call                             |
| Hotelbeds source paths `activities[0]` → `activities[]` | 9                                                                                      |
| v2.1 targets left in label files                        | 0 (the validator rejects them)                                                         |

### Baselines on v3 (dev)

| name_match          | v2.1 | v3                      |
| ------------------- | ---- | ----------------------- |
| Macro precision     | 0.78 | **0.84**                |
| Macro recall        | 0.12 | 0.12                    |
| Macro F1 (headline) | 0.20 | **0.20**                |
| Micro F1            | 0.18 | 0.19                    |
| HX precision        | 0.25 | 0.50                    |
| Critical errors     | 4    | **4** (all on `status`) |

`all_none` is unchanged (F1 0.00, 0 critical errors). Rule-engine results will be compared with the v3
row only.

### Predictions (made before the run)

| Prediction                    | Result                                               | Right?              |
| ----------------------------- | ---------------------------------------------------- | ------------------- |
| name_match F1 goes up on v3   | macro unchanged (0.20); micro +0.01; precision +0.06 | no, on the headline |
| name_match critical errors: 2 | 4                                                    | no                  |

**What it showed:** the first day with predictions written before the results. Both were wrong for
the same reason: the change only touched one false positive, and none of the critical errors.

### Process

| Measure          | Value                                   |
| ---------------- | --------------------------------------- |
| PRs merged       | 1 (ADP-31), plus a Dependabot ruff bump |
| Tests            | 175 → **179**                           |
| Post-merge check | `main` identical to the tested patch    |
| Block times      | not measured                            |
| M1 prediction    | not yet made                            |

**Caveats:** dev baselines only. The rule engine design (E1–E5) is not yet measured.

## Day 8

**Goal:** First rule engine, measured with leave-one-spec-out (LOSO) on dev.

### Candidate recall (share of gold pairs whose target is proposed at all; the engine's ceiling)

| Lexicon | Entries | All entries on | LOSO strict | LOSO + general synonyms |
| --- | --- | --- | --- | --- |
| Drafted from dev gold | 79 | 91% | 8% | — |
| + G1 contexts, G2 schema names, G3 synonyms | 190 | 93% | 26% | 48% |

Drafted entries taught by more than one spec: 4 of 78 (booking `id`, `productId`, `status`, `surname`).

### Rule engine (dev, LOSO, schema v3)

| | Macro P | Macro R | Macro F1 | Micro F1 | Esc P / R (micro) | Transforms | Critical errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| name_match | 0.84 | 0.12 | 0.20 | 0.19 | — / 0.00 | 0/2 | 4 |
| **rules strict** | 0.84 | 0.27 | **0.41** | 0.34 | 0.33 / 0.27 | 0/0 | **3** |
| **rules + general** | 0.96 | 0.45 | **0.61** | 0.58 | 0.42 / 0.45 | 2/5 | **0** |

| Macro F1 per spec | strict | + general |
| --- | --- | --- |
| headout-partner | 0.13 | 0.39 |
| hotelbeds-activities | 0.56 | 0.70 |
| hx-swota | 0.58 | 0.69 |
| octo-core | 0.36 | 0.65 |

**M1 target** (Day 6): macro F1 above 0.20, fewer than 4 critical errors, escalation recall above 0. Met
by both variants. Strict's 3 critical errors are all Headout currency fields mapped to gross by a rule
HX taught; general synonyms make them questions instead.

### Predictions

| Prediction | Result | Right? |
| --- | --- | --- |
| LOSO macro F1 0.45 | strict 0.41, general 0.61 | between the two: close |
| 1 critical error | strict 3, general 0 | between the two |

### Process

| Measure | Value |
| --- | --- |
| PRs merged | 3 (ADP-33 tokeniser, ADP-34 candidate finder, ADP-35 rule engine); ADP-36 fix open |
| Tests | 179 → **226** |
| Bugs found by tests while writing | 1 (context fallback predicted the booker's name for a traveller) |
| Bugs found after merge | 1 (repeated targets in 21 drafted entries; macro F1 0.40 → 0.41 strict, 0.60 → 0.61 general once fixed) |
| Untested commit | 1 (lint error; amended before push) |
| Block times | not measured |

**Caveats:** dev only, single-labeller gold. The general synonyms were written by someone who had read
the dev specs, so the 0.61 is optimistic; 0.41 is the floor. The test set has not been touched.

## Day 9

**Goal:** M1 declared.

### G3 review (ablation: each general entry removed in turn, leave-one-spec-out)

| Group | Entries | Effect when removed |
| --- | --- | --- |
| Helpers | 11 | −0.008 to −0.034 macro F1 each; 0 false positives |
| Safety (`net_price.currency`) | 1 | +3 critical errors, +3 false positives |
| No effect on dev | 21 | none (untested, not useless) |
| Dropped after review | 3 words | none on dev ("state", "expiry date", "expiration date") |

### R4 (enum maps from documented values)

| | Before | After |
| --- | --- | --- |
| Macro F1, strict / general | 0.41 / 0.61 | 0.41 / 0.61 |
| Transforms right, general | 2/5 | **4/5** |
| Critical errors, strict / general | 3 / 0 | 3 / 0 |
| `status` | asked | asked (lifecycle enum; Headout `PENDING` = confirmed) |

### M1 (declared 2026-10-23, Day 9, as planned)

| | Macro F1 | Micro F1 | Esc P / R | Transforms | Critical errors |
| --- | --- | --- | --- | --- | --- |
| name_match | 0.20 | 0.19 | — / 0.00 | 0/2 | 4 |
| **rules, strict** | **0.41** | 0.34 | 0.33 / 0.27 | — | **3** |
| **rules, general** | **0.61** | 0.58 | 0.42 / 0.45 | 4/5 | **0** |

Target (Day 6): macro F1 above 0.20, fewer than 4 critical errors, escalation recall above 0. Met.

### Predictions

| Prediction | Result | Right? |
| --- | --- | --- |
| R4 raises macro F1 | unchanged; transforms 2/5 → 4/5 | no |

### Process

| Measure | Value |
| --- | --- |
| PRs merged | 3 (ADP-38 G3 review, ADP-39 R4, ADP-40 M1 page) |
| Tests | 226 → **234** |
| Failed attempts | 1 (M1 branch created before ADP-39 was merged; nothing committed) |
| Funder material | 1 page: Claude API vs subscription, integration code, cost estimate |
| API spend | $0 |
| Block times | not measured |

**Caveats:** dev only, single-labeller gold, general synonyms not written blind. The test set is
untouched.
