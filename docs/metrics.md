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
