# padan: results report

**Question.** Given a travel partner's booking API documentation, can a pipeline of deterministic
rules plus Claude map the partner's fields onto one canonical booking schema well enough to build an
integration, and can it say when it does not know?

**Answer, in one line.** On three partners it had never seen, padan reaches **0.64 macro F1** (0.72
after a declared labelling slip; **0.74** on the one partner whose answer key no AI tool touched), for
about **$0.004 per field**, and its generated client produced a create request that the partner's own
schema accepts. It escalates too often on money, and makes **5 silent critical errors** in 368 fields.

## 1. The task

A partner field gets one label (ADR-001 §3): a **canonical target** (with `direct`, `transform` or
`derived`), `NONE` (nothing the schema holds), or `ASK_PARTNER` (probably a target, but the
documentation is not enough). Scope per spec: the booking create request(s) and the booking get
response. The canonical schema (v3.1) is a `Booking` with items, travellers, contact, prices,
cancellation terms and fulfilment (vouchers and tickets).

## 2. Data

| Role | Specs | Fields | Gold |
| --- | --- | --- | --- |
| **Dev** (rules written and tuned, prompt revised) | Headout, OCTO, Hotelbeds, HX (HTML + XML) | 239 entries | drafted by Claude, reviewed by me, with a blind sample (Amendment 4) |
| **Test** (Tier 1) | Viator, GetYourGuide, Musement | 368 | labelled by me from the canonical side; `NONE` filled by a script; sealed by hash |

Tier 2 (three more HTML partners) was **not attempted**: Amendment 6 allows it only before the Tier 1
run, and the days went to code generation (M3).

## 3. Method: how the test was protected

Written down **before any test spec was opened** (Amendment 6) and enforced in code:

- **Frozen system:** the general rules with the full dev lexicon, plus Claude Opus 5.5 at effort
  `medium` with prompt v2. Nothing changed after the test specs were seen.
- **Human-only gold:** no model draft (M2 is Claude, so a Claude draft would bend the answer key toward
  the system). The gold is labelled from the canonical side (for each target, which fields carry it),
  every other field is set to `NONE` by a script, and the `NONE` list is reviewed by hand.
- **Sealed:** the SHA-256 of every test label file is committed before any run; every run and score
  tool refuses to start unless the seal verifies (`make verify`), and the systems see only the
  extracted fields, never the gold.
- **One run.** Slip fixes after the run are allowed only for clear mistakes, each counted, in a
  separately sealed copy; the headline is reported before and after.

## 4. Results on dev (used for tuning; optimistic)

| System | Macro F1 | Critical errors |
| --- | --- | --- |
| name matching | 0.20 * | 4 * |
| rules, strict (leave-one-spec-out) | 0.40 | 3 * |
| rules, general | 0.60 | 0 * |
| **rules + Claude Opus 5.5, prompt v2** | **0.89** | **0** |

\* Measured on the M1 version of the dev gold (Day 9); the F1 of the rules is re-scored on the final
gold (Day 11).

## 5. Results on test (the headline)

| System (run once) | Macro F1 | Map P / R | Esc P / R | Transforms | Critical errors |
| --- | --- | --- | --- | --- | --- |
| all `NONE` | 0.00 | — / 0.00 | — / 0.00 | — | 0 |
| name matching | 0.09 | 0.37 / 0.05 | — / 0.00 | 0/1 | 4 |
| rules, strict | 0.15 | 0.60 / 0.09 | 0.03 / 0.04 | 0/1 | 1 |
| rules, general | 0.22 | 0.55 / 0.14 | 0.20 / 0.38 | 0/1 | 1 |
| **rules + Claude Opus 5.5 (frozen)** | **0.64** | **0.62 / 0.73** | **0.07 / 0.21** | **1/19** | **5** |

| Frozen system per spec | Before | After the slip fix |
| --- | --- | --- |
| **viator-partner** (gold with no model contact) | **0.74** | 0.74 |
| getyourguide-partner | 0.58 | 0.81 |
| musement-partner | 0.60 | 0.60 |
| **macro (critical errors)** | **0.64 (5)** | **0.72 (4)** |

**The slip.** I left GetYourGuide's create request almost all `NONE`, although my own gold maps the
same data in its GET response and I labelled Viator's create request field by field. Found by
comparing the gold with the system's output after the run; fixed by a script that copies my own frozen
response labels onto the matching request fields (34 picks, each reviewed by hand, all kept); counted
as 34 model-prompted changes; reported beside, never instead of, 0.64.

**Prediction made before the run:** 0.85 with 1 critical error. The gap to dev is the main finding.

## 6. Why test is lower than dev

- **Tuning.** The lexicon was learnt from the dev gold and prompt v2 fixed errors seen on dev. The
  rules fell from 0.60 to 0.22: their vocabulary does not travel well to new partners.
- **Conventions.** Where the gold and the system describe the same thing differently, both are
  defensible and the scorer counts a miss: one derived label over two fields against two separate
  maps; `construct(field_id=…)` against `direct` (transforms scored 1/19 mostly for this reason).
- **Escalation.** Claude asks about money far more than I did (14 unneeded asks on Musement, mostly
  its price and currency fields) and matched 2 of my 11 asks.
- **Real errors.** The five critical errors: GetYourGuide `booking_id` against `booking_hash` (two
  ID-like fields), `booking_status` mapped where I asked, a ticket called a voucher, the create request's
  date-time (my slip), and Musement's total taken from a different price group.

## 7. Generated clients (M3)

Labels → plain Python, both directions, no LLM ([M3 note](milestones/M3.md)). With one sample booking
and the specs' own examples:

- **Viator's generated create request is valid against Viator's request schema**, from my gold and
  from Claude's predictions alike.
- Everything else fails on named gaps, the same ones from either label source: fields the partner
  requires that padan's schema does not hold (Hotelbeds' holder address, Musement's quantity), TODOs a
  person must answer (OCTO's unit IDs, Headout's price), and data the example responses do not contain.
- Padan-owned fields (its own booking ID, the vertical, the lead traveller by a declared rule) and casts
  to the partner's types are filled by padan, with a note for every choice.

## 8. Cost

| | Value |
| --- | --- |
| Claude per field (Opus 5.5, cached prompt) | about $0.004 |
| Test run (340 fields asked) | $1.40, plus about $0.03 for an interrupted first start |
| **Whole project** (calibration, dev runs, test run) | **about $3.23**, of $20 budgeted |

## 9. Integrity notes

- **Model contact in the test gold**, disclosed when it happened: on GetYourGuide, a GPT revision of the
  sheet was seen and discarded before the `NONE` review (the frozen sheet is byte for byte my own
  earlier version); on Musement, GPT was used to format the sheet, with every decision mine. That is why
  Viator alone is reported.
- **A first, AI-assisted attempt at the slip fix** changed other labels and was discarded whole.
- **The paid run was started twice:** the first start was stopped after 34 seconds and its 6 replies
  were reused from the cache (same model, prompt and fields, so the same answers).
- **One labeller.** A second labeller's sample (13 Viator fields, Amendment 7) is drawn and ready;
  **inter-annotator agreement is not yet measured.**
- The partner specs are public and may be in Claude's training data.

## 10. Limitations and next steps

- Three test partners, all activities, all OpenAPI; one labeller.
- Field-by-field mapping: lists are aligned by a fixed rule, and multi-item bookings whose travellers
  differ per item are not modelled.
- M3 checks requests against schemas, not live partner servers.
- Next: the second labeller's agreement; a scoring rule that treats the convention differences in §6 as
  equivalent (reported separately, not as a new headline); casting and partner-only fields in the
  canonical schema; the HTML partners of Tier 2.
