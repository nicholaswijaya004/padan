# Journal

What I learned and what cost me time, by day.

## Day 1 — Framing, Repo and Tooling

**Goal:** Understand what padan solves and why the rule engine comes first; stand up the repo with the
same merge discipline as a big-tech service repo.

### The problem, in one line

The output is not an adapter; it is an adapter plus a calibrated statement of which mappings can be trusted.
A wrong mapping (per-night `price` → `total_amount`) behaves like Loka's lost update: every request succeeds,
contract tests pass, and GBV is wrong.

### Why rules first is the design, not an optimisation

- It turns mapping into a cascade of classifiers that can abstain; quality depends on each stage knowing
  when it doesn't know.
- Rule errors are deterministic and fixable once; LLM errors are stochastic.
- A rule false positive never reaches the LLM and nobody looks at it again, so rules must be tuned for
  precision and abstain freely. Exact match is safe; fuzzy match is the danger.
- Open question to measure: removing easy fields also removes context the LLM uses on the hard ones.
- "~70% resolved by rules" is a hypothesis, not a fact.

### Repo rules (ruleset `main-protection`)

| Rule                                                              | Prevents                                           |
| ----------------------------------------------------------------- | -------------------------------------------------- |
| PR required, 0 approvals                                          | Direct pushes to `main`                            |
| Required checks `lint`, `typecheck`, `test` (GitHub Actions only) | Merging on red CI, or on a faked status            |
| Branch must be up to date                                         | Two green PRs combining into a red `main`          |
| Conversation resolution                                           | Merging with open review threads                   |
| Squash only, linear history                                       | Merge commits; one commit per PR, titled by the PR |
| No force push, no deletion, no bypass                             | Rewriting `main`, including by me as admin         |

### What cost me time

- **PR 1 was stuck forever.** It only contained `LICENSE`. Required checks only report if a workflow
  defines jobs with those names, so a PR without `ci.yml` waits on "Expected — waiting for status"
  indefinitely. Until CI exists, nothing can merge. Fixed by putting the licence, the skeleton and CI
  in one PR.
- **`brew install uv` started compiling LLVM and Rust.** No pre-built bottle for this Mac, so Homebrew
  fell back to building from source. Ctrl+C, cleaned up, used the standalone installer
  (`astral.sh/uv/install.sh`, read before running). Same applies if I set up the EliteBook.
- **`uv pip install` before `uv sync`** → "No virtual environment found". uv refuses to install into
  the global Python unless told `--system`, which is the point.

### uv experiments

| Experiment                                                         | Observed                       | Why                                                                                                                                     |
| ------------------------------------------------------------------ | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `uv pip install requests`, then `uv sync`                          | `requests` removed             | `uv sync` is exact: it uninstalls anything not in `uv.lock`                                                                             |
| Hand-edit `pyproject.toml` to add `httpx`, then `uv sync --locked` | Refused; needs `uv lock` first | Lock no longer matches `pyproject.toml`. In CI all three jobs fail at their shared `uv sync --locked` step, before ruff/mypy/pytest run |
| Delete `.venv`, then `uv run pytest`                               | `.venv` rebuilt, tests run     | Rebuilt **from `uv.lock`**, not resolved again, so identical versions                                                                   |

Answers were recorded after running. Next time the prediction goes in first.

### Understood

- uv = interpreter + virtualenv + resolver + lockfile + runner in one tool. `pyproject.toml` declares
  ranges; `uv.lock` pins exact versions and hashes for every platform.
- Python needs per-project environments because one interpreter has one `site-packages`; Go keeps every
  module version side by side, Java has a classpath per build.
- Committed lockfile + commit SHA in `metrics.md` = the environment behind every number is reproducible.
  A silent SDK or tokenizer bump could otherwise change F1 or cost with no code change.
- My prompt shows Python 3.9.7, which is the global interpreter, not padan's 3.12.
- Squash merges mean `git branch -d` refuses after merge; use `-D` once the PR is merged.
- Dependabot opened its first PR (`uv_build` range bump) within minutes of the skeleton landing.

### Still open from Day 1

- Direct-push test against the ruleset (prediction first).
- `python --version` vs `uv run python --version`.
- D1 vertical, D2 format scope, D3 label definition → ADR-001.
- Block 0: written answers to the five interview questions.
- LLM provider choice and the hard spend limit in its console, before any key exists.

### Tomorrow

Finish Day 1 Blocks 1–5: ADR-001, spec sourcing, canonical schema v0, label one spec end to end, timed.

## Day 1 (continued) — Dataset and Decisions

**Goal:** Fix scope, label format and scoring in ADR-001; build and verify the candidate spec list.

### The assumption that was wrong

I expected Royal Caribbean or Disney Cruise to publish an API. Neither does: Royal Caribbean's partner
access goes through the CruisingPower agent portal. After verification, cruise has only 2 public
families (HX/OpenTravel and Widgety). Same lesson as Loka, where "naive breaks, locking fixes it" turned
out wrong once measured: check the premise before building on it. Consequence: cruise is reported as a
case study, and activities carries the statistics.

### What cost me time

- PR 1 stuck forever: licence-only PR, required checks never reported (no `ci.yml` yet).
- `brew install uv` started compiling LLVM and Rust; switched to the standalone installer.
- The cloud environment's network policy blocked the doc sites during verification; had to widen
  network access before the check could run.

### Decisions

| Decision                                               | Why                                                                                                                                                                              |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 = activities, tours and cruise                 | Matches the phase 1 I proposed at Traveloka; flights and hotels later                                                                                                            |
| All formats, two-stage scoring                         | Partners without Swagger send PDF/HTML; scoring extraction and mapping separately keeps parsing errors out of mapping scores                                                     |
| Escalation (`ASK_PARTNER`) is a gold label             | From real integration work: when the docs are unclear, you ask the partner. A wrong cancellation mapping costs money; an escalation costs one email                              |
| Codegen without LLM                                    | Wiring is mechanical; LLM budget goes to mapping only                                                                                                                            |
| Exclude Bókun                                          | API terms clause 2.3.4 forbids "any similar benchmarking purposes"                                                                                                               |
| Target lowered from 20 to 12 specs                     | Only 12 of 25 candidates are verifiably public and usable; diversity is measured in families, not spec count. Expand later                                                       |
| Synthetic PDFs (Checkfront, Widgety printed from HTML) | No public PDF spec survived. Same content and labels as the HTML original, so HTML-vs-PDF extraction becomes a controlled comparison. Upper bound: real partner PDFs are messier |

### What I delegated, and what I decided

Claude found the candidate specs, ran the verification (headless browser, direct downloads), drafted
the ADR-001 text, the dry-run labels, and these docs. I made the scope and format decisions, the
escalation rule, the Bókun exclusion and the target size, and corrected the plan where it didn't match
how integrations actually work.

### Understood

- **The labels are the answer key, not the agent's output.** Same shape so they can be compared, but if
  the agent wrote them, its mistakes would become "correct" (like generating `expected` by running the
  code under test).
- **Precision / recall / F1.** Precision: when padan maps, how often it's right. Recall: of what it should
  map, how much it found. F1 is only high when both are. Target F1 alone misses the cents bug, so
  transform accuracy is a separate score.
- **Explicit `NONE`** is what makes false positives countable.
- **Generalisation.** In-domain (activities, cruise) vs held-out (hotels, never tuned on). If held-out
  F1 is close to in-domain F1, it generalises; like ICPC, solving the practice set doesn't prove you'll
  solve the regional. The held-out set works once: tune on it and it's leaked.
- Squash-merge ruleset + required checks: until `ci.yml` exists, nothing can merge.

### Plan change

Blocks 4 (canonical schema) and 5 (label one real spec, timed) moved to Day 2. Day 1 ran well over
its ~6.5 h plan on setup, and Block 5's output is a timing measurement, which would be distorted if
taken at the end of a long day.

### Still open

- LLM provider choice and the hard spend limit, before any API key exists.
- Direct-push test against the ruleset; `python --version` vs `uv run python --version`.
- 7 manifest entries still `unknown`; terms marked "Not checked" before publishing results.

### Tomorrow

Fetch script (direct download, multi-file `$ref`, spec embedded in HTML, HTML pages; hash each), then
canonical schema v0, then label one real spec, timed.

## Day 2 — Fetcher and Canonical Schema

**Goal:** Fetch specs reproducibly, then define the schema every partner field maps onto.

### What I built

- `padan.fetch` + `make fetch`: download → reject non-2xx → reject soft 404s → SHA-256 →
  compare with `data/specs.lock.json`. New specs are recorded, unchanged ones restored,
  changed ones reported and left untouched (exit code 1).
- `padan.schema`: canonical `Booking` = shared core + `ActivityDetails` / `CruiseDetails`
  extensions, with `source` and `critical` metadata on every field.

### Decisions

| Decision                                       | Why                                                                                    |
| ---------------------------------------------- | -------------------------------------------------------------------------------------- |
| Hashes in a separate lock file                 | Like `pyproject.toml` vs `uv.lock`: I edit the manifest, the script writes the lock    |
| Unknown formats fail closed                    | A guard that accepts what it can't check lets error pages through                      |
| Parse specs with `yaml.BaseLoader`             | Keeps every value as text: no dates, booleans or ints guessed from examples            |
| Label Headout first, not Hotelbeds             | Headout: 87% of fields described. Hotelbeds: 0%, so labels would be guesses from names |
| Schema option (b): core + extensions           | 17 of 25 concepts are shared; hotels can be added later as an extension                |
| J1 names: given / family (optional) / full     | Headout gives one NAME field; single-name travellers exist                             |
| J2 total price: Headout `bookingPrice`         | `price` is marked deprecated in its own description                                    |
| J3 `start_date` + optional `start_time`, local | Partners give dates, or local times without timezone                                   |
| J4 separate `contact` and `travellers`         | Hotelbeds' holder is a customer record, not necessarily a traveller                    |

### What cost me time

- Relearning Python syntax while building (imports, classes, exceptions, pytest).
- `uv add` for runtime libraries vs stub packages: mypy passed with stubs only,
  pytest failed because the library itself was missing.
- A test writing to a shared `/tmp` folder made correct code fail on the next run:
  the Loka stale-state lesson again. Always use `tmp_path`.
- Example code left at the top of a module runs on import, and made a real network call.
- Importing a library through my own module (`from padan.fetch import httpx`) caused a circular import.

### Understood

- **Validate at the boundary.** Once bad bytes pass `download` and `check_looks_like_spec`,
  every later step trusts them (the empty body hashes to a valid-looking `e3b0…`).
- **A test only proves the conditions it sets up.** `tmp_path` already exists, so a missing
  `mkdir` passes; `tmp_path / "raw"` matches reality.
- **"Must reject" tests can't catch a schema that rejects everything.** Only
  `test_minimal_activity_booking_is_valid` caught the missing defaults.
- **Floats can't be fixed later.** `0.1 + 0.2` stays `0.30000000000000004` as a Decimal, so
  partner JSON must be parsed with `json.loads(text, parse_float=Decimal)`.
- **Don't store what you can derive** (traveller count = number of travellers).
- **Each layer of `make check` catches a different class of mistake:** ruff (style, imports),
  mypy (types, None-safety), pytest (behaviour).

### Predictions

- Second `make fetch` would print `unchanged`: correct.
- First `make fetch` would "print the sha": wrong, it prints the outcome; the hash goes to the lock.
- Several predictions were made after running, or skipped. Tomorrow: write them first, every time.

### What I delegated, and what I decided

Claude wrote the concept table from the three specs, the schema skeleton and its fixes,
`main()`, and `test_schema.py`, and verified spec quality numbers. I wrote the fetch functions and
their tests with guidance, the validators, and made the decisions above (J1–J4, schema shape,
fail-closed, Headout first).

### Plan change

Block 3 (label Headout, timed) moved to Day 3 morning, so the timing is measured fresh.

## Day 3

### Block 1 — Label Headout (timed)

- Start: 16:08
- End: 17:08
- Labels: 45

### Day 3 (continued) — Review, schema v1, label validator

**Goal:** Compare my Headout labels with an independent draft, settle the disagreements, and make the
gold file trustworthy before anything is scored against it.

### The assumption that was wrong

I thought one careful labelling pass gave me a gold file. It didn't:

- The comparison with a sealed Claude draft changed **11 of 45** labels after I reviewed the
  disagreements (status mapping, unix timestamp, person type, voucher, price fields).
- The validator then found **23 of 45** labels (51%) with **format** errors that both my pass and the
  review missed: invented target names (`partner_item_id`, `is_primary`), `kind` and `transform` packed
  into one string, `ASK PARTNER` with a space, and the file name using `_` instead of the spec id.
- PR #11 merged that file into `main` unvalidated. Nothing checked it, so nothing stopped it.

Same lesson as Day 1: check the premise. Test data needs tests too.

### What cost me time

- Wrote the validator on a checkout without schema v1 (ADP-12 not merged yet), so a test failed for
  the wrong reason.
- Committed on `main` by accident, and `feat/ADP-13` already existed at an old commit. Fixed by moving
  branch pointers (`git branch -f`), no force-push.
- An untracked copy of the label file survived `git switch` and made `main` look broken. Git only
  touches tracked files when switching.

### Decisions

| Decision                                                                     | Why                                                                                                                                                             |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Label by hand, then compare with a sealed Claude draft                       | Gold labels must not come from the model family padan will use (same-family contamination). The sealed draft is only a second opinion, hashed before I labelled |
| Schema v1: `slot_id`, booking and traveller `custom_fields`                  | Headout has inventory slots and partner-defined questions at both levels; without them those fields become `NONE` and hide real integration data                |
| Tickets deferred (labels → `NONE`)                                           | One spec is not evidence; add when a second spec needs it                                                                                                       |
| `inputFields[].id` → `NONE`; the id lives in the path filter                 | `[id=EMAIL]` already says which field it is. Exception: `CUSTOM_*` ids are data and map to `custom_fields[].field_id`                                           |
| Request `count` → derived `count(travellers)`                                | Don't store what can be derived                                                                                                                                 |
| Product/variant `ASK_PARTNER` stays                                          | Not wrong to ask when the docs don't say whether two ids are the same                                                                                           |
| Valid targets are generated from the Pydantic schema                         | One source of truth: renaming a schema field makes every stale label fail CI                                                                                    |
| Lists (`travellers[]`) are valid targets, containers (`total_price`) are not | `count()` needs a list; a container target hides which leaf is meant                                                                                            |
| `source="ours"` fields are valid targets                                     | `partnerReferenceId` carries `our_booking_id` to the partner                                                                                                    |
| One source may feed several targets                                          | `startDateTime` → `start_date` and `start_time`; same source + same target is the real duplicate                                                                |
| Validator and label fixes in one PR                                          | `main` already had the invalid file; the validator alone would have turned `main` red                                                                           |

### What I delegated, and what I decided

Claude wrote the label scaffold, the sealed comparison draft, the schema v1 change, the validator and
its tests, and applied the mechanical label fixes. I wrote all 45 labels, adjudicated every
disagreement, and made the schema decisions. From now on Claude explains the concept and the decisions
first and only writes code or tests when I ask.

### Understood

- **Agreement is not accuracy.** 47% agreement with the draft says the task is ambiguous, not who is
  right. The review decides.
- **Validate the answer key.** A scorer is only as good as its gold set; a 100-line validator caught in
  under a second what two human passes missed.
- **Derive the vocabulary, don't copy it.** `VALID_TARGETS` comes from `Booking.model_fields`, so the
  schema and the labels can't drift silently.
- **Git:** untracked files follow you across branches; `git branch -f` can't move the branch you're on;
  a branch behind yours on the remote is a fast-forward push, no force needed.

### Plan change

Block 4 (re-plan labelling from the measured rate) moved to Day 4. The fetch blocks (more specs, GetYourGuide
multi-file `$ref`) moved after it. The review turned up schema gaps and invalid gold data; fixing those
was worth more than fetching specs I can't yet label correctly.

### Still open

- Judgement calls: label 31 (`variantInputFields[].name` → `custom_fields[].label`?), label 28 (per-traveller
  `CUSTOM_*` name → `travellers[].custom_fields[].label`?), request `PHONE` (`direct` or `to_e164`?).
- Transform names are free text; the scorer needs a fixed vocabulary.
- Interview question: what happens when `Traveller.is_lead` is renamed?
- A stash I haven't checked (`git stash list`).
- From Day 1: direct-push test, spend limit before an API key exists, 7 `unknown` manifest entries.

### Tomorrow

Block 4: re-plan from the measured rate. Decide scope per spec, a dev/test split inside the benchmark
(ADR-001 Amendment 2), whether the sealed-draft comparison stays for every spec, and which specs are
dev. Then fetch and label the next dev spec.

## Day 4 — Re-plan, dev/test split, schema v2, OCTO

**Goal:** Turn the measured labelling rate into a plan that fits M1, fetch the dev specs, and label the
next dev spec end to end.

### Block 5 — Review OCTO draft (timed)

- Start: 17:32
- End: 17:43
- Entries reviewed: 92

### The assumptions that were wrong

- **"The project takes about 12 days."** That was an estimate by analogy with Loka, made before anything
  was measured. Rate × volume says otherwise: about 500 fields at 2.5–3 min/field is 3–4 days of
  labelling alone. Re-estimated from components: about 22–25 working days left (about 28 with buffer),
  with a defensible stopping point at the end of M2 (around Day 18–20).
- **Widgety as a dev spec.** I picked it without reading its content: its public docs cover cruise
  _search_ only, not booking. HX, which documents storing and retrieving bookings, replaced it
  (Amendment 3).
- **Schema v0/v1 choices.** `voucher_url` sat inside `activity`, but cruise sends documents too, and
  a URL field cannot hold a QR code. `total_price` did not say _whose_ price. `status` merged "on
  hold" (expires unless we confirm) with "pending" (we confirmed, partner has not). Fixed in schema v2.

### What cost me time

- **What a PR contained versus what I thought it contained.** Three things reached `main` incomplete:
  ADP-19 had no tests for the `pages` method, the Amendment 3 roles stayed unapplied through three
  PRs, and ADR Amendment 1 (Day 1) never landed at all. A stale local copy of the ADR would also have
  deleted Amendments 1 and 4 if committed. `make check` was green every time, because it only proves
  that existing tests pass, not that the change is complete.
- **Snippet files saved into `tests/`.** pytest collects every `test_*.py`, so they ran as broken
  modules.
- Working on the wrong branch, and a branch created from a stale `main`.

**Habits from now on:** `git log --oneline origin/main..HEAD` and `git show --stat HEAD` before every
push; after every merge, `git switch main && git pull && make check`; compare the test count before
and after a PR.

### Decisions

| Decision                                                                                                                                                                                                                    | Why                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Label booking create and get only (D1)                                                                                                                                                                                      | The canonical schema is a booking; wider scope doubles labelling time and token cost                                   |
| Dev/test split inside the benchmark (Amendment 2)                                                                                                                                                                           | Reporting F1 on the specs the rules were written against is training-set accuracy                                      |
| A spec family never crosses roles; a test enforces it                                                                                                                                                                       | A same-family spec in test would score rules on conventions they were tuned on                                         |
| HX replaces Widgety in dev (Amendment 3)                                                                                                                                                                                    | Widgety has no public booking endpoints; HX does                                                                       |
| Dev labels model-drafted and reviewed; test labels human-only (Amendment 4)                                                                                                                                                 | Labelling cost; dev labels are only used for tuning, the headline number comes from test                               |
| Blind sample of 10 before each review                                                                                                                                                                                       | Measures anchoring instead of assuming it away                                                                         |
| Embedded catalogue objects out of scope (Amendment 4)                                                                                                                                                                       | OCTO repeats the full product inside a booking: 71 of 161 fields                                                       |
| Schema designed from dev specs, standards and non-benchmark OTAs only                                                                                                                                                       | Shaping the schema around test specs would make test mappings easier                                                   |
| OCTO pinned to a commit, not `main`                                                                                                                                                                                         | The content at that URL can never change; the lock only detects change                                                 |
| Accept the Headout upstream change after a diff                                                                                                                                                                             | One description changed, outside the labelled endpoints; a permanent "changed" warning would hide the next real one    |
| `fetch_file` refactor before `fetch_pages`                                                                                                                                                                                  | Existing tests passing unchanged proves the refactor changed no behaviour                                              |
| Schema v2: `fulfilment[]`, `on_hold` + `hold_expires_at`, gross `total_price` + `net_price`, split `contact`, `partner_confirmation_code`, `cancellable`, `end_time`, wider traveller types, `date_of_birth`, `nationality` | Each has evidence in a dev spec (Headout, OCTO, HX)                                                                    |
| `fulfilment[]`, not `documents[]`                                                                                                                                                                                           | In OpenTravel and HX, `Document` means a passport or ID                                                                |
| Headout prices → `ASK_PARTNER` (net or gross?)                                                                                                                                                                              | Under v2 the docs don't say which one `bookingPrice` is; guessing a critical money field is what escalation exists for |
| No `item_id` / `items[]` yet                                                                                                                                                                                                | `activity.option_id` covers "Disneyland 6h vs 12h"; multi-item bookings wait for evidence                              |
| Schema v2.1: `redeemed_at` on booking and fulfilment                                                                                                                                                                        | My proposal from support work: a refund dispute needs the redemption time in seconds, not a 10-minute log search       |
| `availabilityId` and `availability.id` both `direct`                                                                                                                                                                        | The docs say they hold the same value; `ASK_PARTNER` on clear docs lowers escalation precision                         |

### What I delegated, and what I decided

Claude drafted ADR Amendments 2–4 (and restored 1), wrote schema v2/v2.1, the `pages` fetch method and
its tests, the family test, the scaffolds, the OCTO draft and the re-labelled Headout file. I decided
the scope, the split, the labelling method (after asking whether an interviewer would see it as a
liability), the fulfilment design and the rejection of `item_id`, proposed the redemption time, and
reviewed every OCTO row. Three Headout label calls were applied on Claude's recommendation at my
request; they are recorded as Claude-decided (3 of 56).

### Understood

- **Leakage has levels:** test vs dev specs, spec families, and the sources the schema is designed from.
- **Anchoring is measurable:** 6/10 blind agreement against 1% of rows changed in review, at 7 s per row.
- **Docs drift and docs are wrong:** Headout changed in two days; OCTO's `deliveryValue` has the
  description of `deliveryFormat`.
- **A field's meaning can depend on another field:** `deliveryValue` is a URL or a QR code depending on
  `deliveryFormat`; Headout `inputFields[id=…]` is the same pattern.
- **YAML traps:** comments are invisible to the loader; PyYAML silently keeps the last of two duplicate
  keys.
- **Green CI is not "complete":** it cannot see a missing test or an unapplied decision.

### Plan change

Days 1–3 each pushed blocks forward; today's labelling (Block 5) fitted only because of Amendment 4.
Fetching test specs (GetYourGuide `$ref` bundling, Viator embedded spec) moves after M1: test specs are
not needed until the rule engine exists.

### Still open

- Interview question: what breaks when `Traveller.is_lead` is renamed, and why that is the outcome I want.
- The validator does not check field names inside a target filter (`travellers[is_lead=true]`).
- Coverage check: every scaffold field has at least one label.
- Label files should record the `spec_sha256` they were labelled against, so drift is caught by a test.
- A YAML loader that rejects duplicate keys, for the manifest and label files.
- Transform names are free text; the scorer needs a fixed vocabulary.
- The scaffold generator lives in Claude's scratch folder; it is Stage 1 extraction and belongs in the repo, with tests.
- OCTO gaps: no price in OCTO core, no lead-traveller flag. Headout: no price mapping until the partner answers.
- Later schema work: multi-item bookings, structured cancellation penalties, `HotelDetails` before M3.
- A second labeller on a 20% sample of one test spec before publishing results.
- Synthetic PDFs (Checkfront, Widgety) and their manifest entries.
- From Day 1: direct-push test, spend limit before an API key exists, `unknown` manifest entries, terms checks.

### Tomorrow

Move the scaffold generator into the repo as Stage 1 extraction (deterministic, tested). Then label the
remaining dev specs, Hotelbeds and HX, with the Amendment 4 method, timed with the blind sample. Then
the scorer.

## Day 5 — Stage 1 extraction, Hotelbeds, XML examples

**Goal:** Turn the scaffold script into tested pipeline code (Stage 1 extraction) and finish the dev
labels, so M1 needs only the scorer and the rule engine.

### The assumptions that were wrong

- **The project estimate, again.** The Day 1 "12 days" was copied from Loka, and Loka's own "12 days"
  was an undercount: half of Loka happened outside Claude Code and it took more than a month. Today's
  estimate (22–28 working days from Day 5) is built from components, but calibrated against my own
  history it is the optimistic end. Estimates for projects that depend on outside data are worth little
  before the first measurement.
- **Hotelbeds would have response examples instead of schemas.** It has neither: its booking responses
  are empty. Labels cover the booking request only.
- **Documentation examples are valid XML.** HX's create-response example is not: a `[..]` placeholder
  swallowed a closing tag, and a standard XML parser rejects it.

### What cost me time

- **ADP-25 merged with 2 of its 4 files** (no Hotelbeds labels, no new tests): the third incomplete PR
  in two days. Restored in ADP-26. ADP-26 was the first multi-commit PR checked file by file before merge.
- A `git switch main && git pull` that failed on local changes, while the next line still created the
  new branch from the old one.
- A second download with the same name saved as `… (1).yaml`, so a `cp` silently copied nothing.
- Python syntax after months of Java: `Node` vs `node`, a type written as a statement, indexing a list
  with a name.

### Decisions

| Decision                                                                                        | Why                                                                                                     |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Label scope (`scope`, `exclude`) lives in the manifest                                          | One source of truth for the extractor, the coverage check and the scorer                                |
| `extract()` is pure; `write_scaffold()` only renders                                            | Extraction is tested on data; rendering is a detail                                                     |
| Scaffolds are not committed (`data/scaffolds/` ignored)                                         | They are derived from the spec plus the code; two copies would drift                                    |
| Fixture tests in CI, plus regression tests against the gold files (skipped without `data/raw/`) | The regression proves the extractor reproduces every gold field and evidence string                     |
| Coverage counts a field split by filter as covered                                              | `inputFields[id=EMAIL].value` covers `inputFields[].value`; the check found that case on its first run  |
| Stage 1 on OpenAPI is not reported as a score                                                   | Its gold field list came from this extractor, so it would be 100% by construction                       |
| Evidence: description, else the field's example, else the operation's example body              | Hotelbeds has 0% descriptions; the example value (`ADULT`, `07198`) is the only evidence                |
| Hotelbeds: request only                                                                         | Its booking responses have no schema and no example                                                     |
| Multi-activity bookings: label the first (`activities[0]`), the rest is a gap                   | Precise with the existing path syntax; the `items[]` redesign needs its own block before test labelling |
| Hotelbeds hand-labelled (all 21), then adjudicated against a sealed draft                       | Stronger than a model draft; `preferedLanguage` escalated as `ASK_PARTNER`                              |
| HX scope includes the create response                                                           | The get-response example is mostly `[..]` placeholders                                                  |
| Tolerant XML parser with one repair rule: when an element closes, children left open close too  | Real docs are malformed; the rule is tested and its side effect recorded                                |
| Lists in XML only where the example repeats an element                                          | One example cannot tell more; the XSD would                                                             |

### What I delegated, and what I decided

I wrote the core of Stage 1: `resolve`, `properties` and `walk`, and `example_at`, with Claude's
guidance and corrections. Claude wrote `xml_leaves` at my request, the plumbing around the core,
the tolerant parser, all test files, the sealed Hotelbeds draft and the manifest changes. I labelled
all 21 Hotelbeds fields by hand and decided the 8 disagreements with the draft.

### Understood

- **Walking a schema:** `$ref` pointers, `allOf` composition, arrays, and a `seen` set per branch so a
  self-referencing schema expands once while two siblings pointing at the same schema both expand.
- **Test-first with a reference implementation:** the tests were proven achievable before I wrote a line.
- **Interview answer (`is_lead` rename):** valid targets are derived from the schema at import time, so
  a rename makes every stale gold label fail validation and CI blocks the PR; silently stale labels
  would corrupt F1. Known gap: names inside filters are not checked.
- **Evidence-poor specs make hand labels less reliable:** 38% of my Hotelbeds labels changed after
  comparison, against 24% on well-documented Headout.

### Still open

- HX labels (70 fields).
- `items[]` (multi-item bookings): design before any test spec is labelled; Hotelbeds is dev evidence.
- HX paths and lists come from one example; the OpenTravel XSD would give exact structure.
- Stage 1 for HTML needs an independent gold field list before any extraction score is reported.
- Log start and end times per block: today's were not recorded.
- Carried: filter-field validation, `spec_sha256` in label files, duplicate-key YAML loader, transform
  vocabulary, OCTO/Headout price gaps, second labeller, synthetic PDFs, Day 1 leftovers.

### Tomorrow

HX labels first (sealed draft, blind sample of 10, timed review), then the scorer: concept, decisions,
code. M1 (rule engine measured on dev) is then the rule engine itself.

## Day 6 — HX labels, the scorer, first baselines

**Goal:** Finish the dev gold set (HX), then build the scorer, so M1 needs only the rule engine.

### The assumptions that were wrong

- **"Name matching gets you a fair way."** Name-match maps 12 of about 115 gold pairs (macro F1 0.20).
  Partners and our schema rarely share a word (`ReservationID@ID`, `uuid` → `partner_booking_id`).
- **"A correct-looking match is a safe match."** Every one of name-match's 4 silent critical errors is
  a perfect name match on `status`: a raw partner code copied without `enum_map`, a ticket's status
  and a cabin's status written into the booking's status. High precision (0.78) did not mean safe.
- **"A dead schema target is harmless."** `cruise.voyage_id`, unused since the HX review, attracted a
  false positive from name-match on its first run.
- **"About 22 transform labels need rewriting."** Claude's estimate; it was 1. Once the rule became
  "the vocabulary applies to `kind: transform` only; `derived` keeps a free-text recipe", every other
  label already fitted.
- **"No other field holds an amount"** (my first view on HX #43). There are three, the one I wanted
  is labelled "Balance due", and `[..]` hides the other rows of an itemized invoice.

### What cost me time

- **Python syntax, again:** `&` used as "and" (in Python it is set intersection, and binds tighter
  than `==`); a loop variable used after the loop (Python keeps it, holding the last value, or never
  assigns it); passing a whole dict where one entry `d[key]` was needed.
- **"Either" vs "neither" written as code.** The first version skipped exactly the transform case that
  had to be scored. A truth table over the four kind combinations found it.
- **My blind-sample format:** 5 of 10 entries would have failed the validator (invented target names,
  two targets in one entry), because I labelled from memory instead of from `schema.py`.

### Decisions

| Decision                                                                                               | Why                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| HX `VoyageID` → `product_id`, not `cruise.voyage_id`                                                   | The schema already defines `product_id` as product _or sailing_; otherwise HX has no product key                                         |
| HX `PolicyInfo.Text` → `ASK_PARTNER` (`cancellation_policy`)                                           | My catch: the draft had no mapping for a critical field, and the docs say policy sections vary                                           |
| `ASK_PARTNER` when a meaning depends on an undocumented code                                           | My rule for status; applied consistently it also decided booking price (`PriceTypeCode`) and balance due date (`PaymentNumber`)          |
| No schema change for my Traveloka product/item model during labelling                                  | A label change fixed the urgent part; the rest belongs to the multi-item design                                                          |
| Canonical schema stores facts; composite IDs are views generated per consumer                          | `ANTHEM_OF_THE_SEAS_3D2N_SG-PENANG-SG` can be built from parts; parsing it back breaks                                                   |
| S1: gold `ASK_PARTNER` + predicted candidate = mapping FP, escalation FN, critical if the candidate is | Guessing where the docs do not support it is what escalation exists to prevent                                                           |
| S2: gold canonical + predicted `ASK_PARTNER` = FN and escalation FP, not critical                      | Asking costs a question, not a wrong value                                                                                               |
| S3: exact paths with filters; only `[0]` ≡ `[]`                                                        | The filter is the mapping logic                                                                                                          |
| S4: micro per spec, macro across specs as the headline, micro total too                                | OCTO's 92 entries must not drown Hotelbeds' 21                                                                                           |
| S5: fixed transform vocabulary (7 names) for `kind: transform`; `derived` scored on target only        | Transforms become comparable; `enum_map` ignores order but not values                                                                    |
| S6: `all_none` and `name_match` baselines before any rule                                              | Proves the scorer, and turns M1 into "rules vs name-match"                                                                               |
| S7: CLI table + JSON with a per-pair error list                                                        | The error list is the input for writing rules                                                                                            |
| Critical errors judged on the predicted target                                                         | Damage is decided by where a value is written; a missed critical field is visible, a wrong one is silent                                 |
| API credit moves to after M1 (about Day 9)                                                             | Nothing before M2 calls an LLM                                                                                                           |
| Multi-item bookings: `Booking.items[]` (option B), schema v3 on Day 7                                  | One root cause behind `activities[0]`, cabins, `option_id` in two places and the dead `voyage_id`; cheapest now (0 test labels, 0 rules) |

### What I delegated, and what I decided

I labelled the HX blind sample, made the review decisions (cancellation policy, `VoyageID`), kept
booking price as `ASK_PARTNER` after the evidence, and wrote `score_spec` (mapping, escalation,
transforms, critical errors) from a fill-in-the-blank skeleton. Claude drafted and sealed the HX
labels, wrote the HX coverage test, the transform vocabulary, the scorer's helpers and all its tests,
the baselines and the report, and found its own bug (F1 shown as undefined instead of 0). Scorer
decisions S1–S7 and option B were Claude's recommendations, accepted by me.

### Understood

- **Sets as an evaluation tool:** gold and prediction as sets of (field → target) pairs; TP = `g & p`,
  FP = `p - g`, FN = `g - p`. A wrong target is two errors: we wrote something wrong and missed the
  right thing.
- **Why F1 is not the headline** (answer written after the results, not before): F1 counts a missed
  middle name and a wrong booking status the same. Silent critical errors and escalation recall decide
  whether the system can run unattended.
- **The scorer compares transforms; it never runs them.** Running `date_part` belongs to codegen (M3);
  the vocabulary is the contract between labels, rules, the LLM and generated code.
- **Blind samples and reviews catch different things:** my 4 disagreements on mapped fields were all
  wrong, but my one note found a critical gap the draft missed.

### Still open

- Day 7: schema v3 (`items[]`, `option_id` moved, `voyage_id` and `fare_category_code` removed), ADR-001
  Amendment 5, mechanical relabel of the 4 dev files, baselines re-run.
- My M1 prediction (rule-engine F1 and critical errors on dev) before any rule exists.
- Validate `enum_map` values against the target's allowed values (`on-hold` would pass today).
- Measurement habits: block times and predictions were skipped again today.
- Missing final newline in `.gitignore` and `Makefile`.
- Carried: filter-field validation, `spec_sha256` in label files, duplicate-key YAML loader, OpenTravel
  XSD for HX structure, an independent gold for HTML Stage 1, second labeller, synthetic PDFs, Day 1
  leftovers.

### Tomorrow

Schema v3 with Amendment 5 and the relabel, re-run the baselines, then the rule engine design: rules
for mapping, transforms and escalation triggers, measured against name-match (macro F1 0.20, 4 critical
errors).

## Day 7 — Schema v3 (items[]), baselines re-measured, rule engine design

**Goal:** Schema v3 merged with the dev labels migrated, baselines re-measured on it, and the rule
engine designed, so rule code can start on Day 8.

### The assumptions that were wrong

- **"F1 goes up on v3"** (my prediction). The headline stayed at 0.20; only precision rose (0.78 →
  0.84). Removing a target can only remove false positives; it cannot create new matches, so recall
  could not move.
- **"2 critical errors on v3"** (my prediction). It stayed at 4: all four are on `status`, and v3 did
  not touch `status`. Before predicting a change's effect, list the errors the change touches.
- **"About 60 renames, 54 targets"** (Claude's estimates). It was 35 renames, and 55 targets: `items[]`
  itself became a target, like `travellers[]`.
- **"The ADR already says where the schema may be designed from."** It did not: the rule (dev specs,
  standards and non-benchmark OTAs, never test specs) was only in the Day 4 journal. Amendment 5 now
  records it.
- **"R1 (escalation) is a layer that runs first on its own."** My answer about HX cabin `Status`
  showed it cannot: "is it dangerous?" is a question about the candidate target, and candidates only
  exist after synonyms and context have run. R1 is a filter on candidates.

### What cost me time

- Not much: one PR, applied as a patch and merged unchanged. The merge was not reviewed with Claude
  before merging; the post-merge check found `main` identical to the tested patch.
- The co-author trailer: a squash merge replaces commit messages with the PR title, so a trailer in
  the commit is lost unless it is pasted into the squash message.

### Decisions

| Decision                                                                                                      | Why                                                                                                              |
| ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Schema v3: `Booking.items[]`, each with product, option, dates and exactly one of `activity` / `cruise`       | One root cause behind `activities[0]`, one cabin per booking, `option_id` in two places and the dead `voyage_id` |
| V1: no price per item                                                                                         | No dev label would use it; a field without evidence cannot be checked                                            |
| V2: travellers stay per booking                                                                               | 3 of 4 dev specs list travellers once per booking; Hotelbeds' per-activity paxes are a recorded limitation       |
| V3: `balance_due_date` moves to the booking                                                                   | Payment schedules belong to the booking; activities take deposits too                                            |
| V4: Hotelbeds `activities[0].*` → `activities[].*`                                                            | With `items[]` every activity maps; `[0]` meant "the rest is lost"                                               |
| HX `PricedCategoryCode` → `items[].option_id`                                                                 | The cabin category is the variant sold: my Traveloka "item = cabin type"                                         |
| Design-source rule written into the ADR (Amendment 5)                                                         | Schema design must never be shaped by test specs                                                                 |
| Schema and labels in one commit                                                                               | A schema-only commit would fail validation on every label file; every commit on `main` passes on its own         |
| Co-author trailer when Claude wrote most of a commit                                                          | Commit history should agree with the journal's delegation section                                                |
| E1: leave-one-spec-out on dev, plus a test that no rule contains a full partner path                          | A mock exam instead of the answer key: an honest estimate before the test set is touched                         |
| E2: ties → `ASK_PARTNER` if any candidate is critical, else `NONE`                                            | A 50/50 guess on a price is silently wrong half the time; a question costs one email                             |
| E3: rules as data (`data/rules/*.yaml`) plus a few Python matchers                                            | Countable, diffable and reviewable, like the label files                                                         |
| E4: match on tokens (`localDateTimeStart` → local, date, time, start), not whole names                        | The step that should beat name-match's exact equality                                                            |
| E5: every prediction records the rule that produced it, in a sidecar file                                     | Error analysis by rule, and explainability, without changing the label format                                    |
| Rule flow: noise → candidates (tokens, synonyms, context) → escalation filter → map + transform → else `NONE` | My correction to R1, from the cabin-status question                                                              |

### What I delegated, and what I decided

Claude wrote schema v3, the relabel script and its 35 renames, the test updates, Amendment 5 and the
rule engine design proposal (with the explanation by analogy I asked for). I decided V1–V4, E1–E5
(Claude's recommendations, accepted), confirmed the cabin-category judgement by merging, made both
baseline predictions before the run, and corrected the escalation layer's place in the design.

### Understood

- **Booking vs item:** a field belongs at the level where it varies. Status, contact and price exist
  once per booking; product, option and dates once per thing bought.
- **What a schema change can move:** removing a dead target raises precision only; recall needs new
  matches.
- **Leave-one-spec-out** is cross-validation for hand-written rules: rules learnt from a spec are
  switched off when scoring that spec.
- **Context decides meaning:** `status` at booking level is the booking's; under `unitItems[]` or
  `SelectedCabin` it is a ticket's or a cabin's. Three of name-match's four critical errors are this.
- **A patch carries no author:** whoever commits is the author; Claude appears only through a
  co-author trailer.

### Still open

- **My M1 prediction** (leave-one-spec-out macro F1 and critical errors), asked three times. It is the
  first item on Day 8, before any rule exists.
- Block times: none recorded again.
- The leave-one-spec-out question (Q2) I did not answer.
- Validate `enum_map` values against the target's allowed values.
- Later schema work: price per item (before test labelling, only with evidence), traveller–item link,
  structured cancellation penalties, `HotelDetails` before M3.
- Missing final newline in `.gitignore` and `Makefile`.
- Carried: filter-field validation, `spec_sha256` in label files, duplicate-key YAML loader, OpenTravel
  XSD for HX, an independent gold for HTML Stage 1, second labeller, synthetic PDFs, Day 1 leftovers.

### Tomorrow

M1 prediction first. Then the tokeniser (mine, fill-in-the-blank), the candidate finder with context,
the noise list and the escalation filter, and a first leave-one-spec-out run against name-match (macro
F1 0.20, 4 critical errors).

## Day 8 — Tokeniser, candidate finder, rule engine: M1 target met on dev

**Goal:** A first rule engine measured with leave-one-spec-out against name-match (macro F1 0.20, 4
critical errors).

### The assumptions that were wrong

- **"A lexicon learnt from dev labels generalises."** Drafted automatically from the 4 dev specs, it
  proposed the right target for 91% of gold pairs with all entries on, and 8% under leave-one-spec-out:
  only 3 of 79 entries were taught by more than one spec. Every partner names things its own way;
  rules learnt from one spec are memorised answers. Widening contexts (G1), the schema's own names (G2)
  and general synonyms (G3) raised it to 26% strict and 48% with synonyms.
- **"The nearest entity decides a field's context"** (Claude's recommendation C2). OCTO's
  `unitItems[].contact.firstName` and HX's `GuestDetail.ContactInfo...GivenName` are travellers, not
  the booking contact: a contact is read with its owner (`ticket contact`).
- **"A specific context can fall back to a general one."** A test caught it predicting the booker's
  name for a traveller once the specific entry was switched off. Context keys now match exactly.
- **"The draft script was correct."** It merged the same path from two endpoints into one entry with
  the target listed twice (21 entries). `decide()` read the repeated tuple as a second reading and
  returned `NONE` for sure mappings, e.g. Headout `productId`. Found while preparing this journal;
  fixed in ADP-36, and the validator now rejects repeated targets. Scores moved 0.40 → 0.41 (strict)
  and 0.60 → 0.61 (general).
- **My M1 prediction (0.45, 1 critical error)** sat between the two results: strict 0.41 / 3, with
  general synonyms 0.61 / 0. The best-calibrated prediction so far.

### What cost me time

- **The regex lookahead:** my first A was `[A-Z]+[a-z]+`, which eats the next word (`PNRNumber` →
  `pnrnumber`). `(?=...)` looks without consuming.
- **Commands on separate lines:** `make fmt` failed, but `git add` and `git commit` on the next lines
  still ran, so an untested commit with a lint error existed until I amended it. Chain with `&&`.
- **Label vs candidate in `decide()`:** I checked `candidate.target == 'ASK_PARTNER'`, but a candidate
  is a proposal with `targets` and an `escalate` flag; `ASK_PARTNER` exists only in labels. Also
  `candidate[0]` (indexing the object) instead of `candidate.targets[0]`, and a missing `s`.

### Decisions

| Decision | Why |
| --- | --- |
| M1 prediction written before any rule: 0.45, 1 critical error | Asked three times; the result is only meaningful against a guess made blind |
| Tokens: acronym-then-word, word, acronym, digits (`[A-Z]+(?=[A-Z][a-z])` first) | `PNRNumber` → `pnr, number`; order matters because the first fitting shape wins |
| C1: leaf words must equal an entry exactly | "Contains" would match `ID_Context` to the booking ID and `CabinCategoryStatusCode` to status |
| C2: context = entities in the parent path; dependents read with their owner; exact keys | The ticket holder is a traveller; the booking holder is the contact |
| C3: entries drafted from dev gold with `learnt_from`; entries are words, never paths | Makes leave-one-spec-out possible and memorised paths impossible |
| G1: a word applies in its parallel scope (contact ↔ traveller, voucher ↔ ticket, root ↔ item) | The source spec stays the same, so leave-one-spec-out stays honest |
| G2: the schema's own names (`learnt_from: schema`) | The knowledge name-match already uses; no leakage |
| G3: general synonyms reported separately (strict excludes them) | Written by Claude after reading dev specs, so not blind; the test set decides |
| `currency` / `amount` under a price proposes both gross and net | Two critical readings make `decide()` ask: it turned 3 silent wrong currencies into questions |
| `decide()`: none → `NONE`; learnt from `ASK_PARTNER` → ask; two readings → ask if critical else `NONE`; one → map; critical enum without a map → ask | The escalation policy in code (E2) |
| Repeated targets in a lexicon entry are invalid | One malformed entry silently turned correct mappings into `NONE` |

### What I delegated, and what I decided

I wrote the tokeniser (three of four blanks; the lookahead after Claude's explanation) and `decide()`
(seven blanks), made the M1 prediction, and decided C1–C3 and G1–G3 (Claude's recommendations,
accepted). Claude wrote the candidate finder, the lexicon draft and curation, the engine runner, all
tests, and found and fixed its own draft-script bug. I asked why I was not writing the candidate finder;
the answer (the design changed twice while being written, and time) led to me writing `decide()`.

### Understood

- **Memorising vs generalising, measured:** 91% with a spec's own entries, 8% without. Leave-one-spec-
  out is the only reason the 91% was not reported.
- **Context decides meaning:** OCTO's `contact.firstName` (booking holder → contact) and
  `unitItems[].contact.firstName` (ticket holder → traveller) share a leaf name.
- **An entry is general only when two partners taught it.**
- **Cross-spec generalisation can be wrong:** HX taught "price currency = gross"; Headout's docs do not
  say so. Without leave-one-spec-out, Headout's own entries would have hidden the 3 critical errors.
- **Safety by ambiguity:** proposing both readings for a critical field makes the system ask instead
  of guess.

### Still open

- **My G3 review** (keep / drop / add): G3 is the whole difference between 0.41 and 0.61.
- R4: build `enum_map` from documented values; until then `status` is asked (OCTO, Headout) and
  `traveller_type` mapped without a map (transforms 2/5).
- Keyed fields: Headout `inputFields[id=…].value` (11 gold pairs) carry their meaning in a filter the
  rules cannot see; derived labels (5) are not learnable.
- HX `Payment@Amount`, `PriceInfo@Amount`: asked, gold `NONE`.
- Local git name `nicholas.wijaya004`; block times not recorded.
- Carried from Day 7.

### Tomorrow

G3 review, then R4 (`enum_map` from evidence), a decision on keyed fields, a re-run, and M1 declared on
one page (strict and general numbers, the method, what is still wrong). Then the API credit for M2.

## Day 9 — G3 review, R4 enum maps, keyed fields, M1 declared

**Goal:** Declare M1: review the general synonyms, build enum maps from documented values (R4), decide
on keyed fields, and write the M1 page. M1 was planned for Day 9, Friday 23 October, on Day 4; it was
declared that day.

### The assumptions that were wrong

- **"R4 will raise F1"** (my prediction). Macro F1 stayed at 0.41 / 0.61. R4 fixes transforms, not
  targets, and mapping F1 counts targets only; the gain shows in the transforms column (2/5 → 4/5).
  The same lesson as Day 7: list the errors a change can touch before predicting its effect.
- **"R4 will map OCTO's `deliveryFormat`"** (Claude's expectation). Under leave-one-spec-out nothing
  proposes `fulfilment.format` for OCTO: only OCTO teaches the words "delivery format". R4 cannot give
  a table to a candidate that does not exist.
- **"A value name means the same thing everywhere."** Headout's `PENDING` is documented as "confirmed
  with supplier. Treat as confirmed". Mapping it to our `pending` by name would be a silent critical
  error. Status values are steps in each partner's own process, so `status` gets no table from names.
- **"Every synonym must be judged by reading it."** Benching one entry at a time (ablation) showed which
  of the 33 general entries earn their place, which one prevents 3 critical errors, and that 21 never
  fire on dev.

### What cost me time

- **Starting a branch before the PR it depends on was merged.** `git apply` refused the M1 patch
  (no `enums.py` on `main`), and the commit lines after it still ran. Check `origin/main` first, and
  chain the sequence with `&&`.
- **Python:** `any(allowed for ...)` is always true for a non-empty set (the check must be about each
  value: `value not in allowed`); f-strings put the variable inside the braces (`f"{code}={value}"`).
- **Regex capture groups:** `(...)` makes `findall` return only the code, not the backticks.

### Decisions

| Decision | Why |
| --- | --- |
| Keep the general synonyms that measurably help, and the gross/net currency and amount block | Ablation: 11 entries add true positives with no false positives; `net_price.currency` alone prevents 3 critical errors |
| Drop "state" (status), "expiry date" and "expiration date" (hold expiry) | Each sits next to a critical field and plausibly means something else (an address, a voucher or card expiry); none fired on dev |
| R4: enum maps by name for format and type enums; `status` stays `ASK_PARTNER` until M2 | Headout `PENDING` is a false friend; reading per-value descriptions is a language task |
| R4 builds a table only when every documented code matches | A partial table leaves a real value untranslated |
| R4 reads backticked capital codes in the evidence | That is how OCTO and Headout document values; schema-only `enum` lists are a recorded gap |
| K1: keyed fields (Headout `inputFields[id=…]`, 11 pairs) are a known gap | One dev example cannot be validated under leave-one-spec-out |
| M1 declared on one page (`docs/milestones/M1.md`) with strict 0.41 / 3 and general 0.61 / 0 | The range is the honest headline: strict is the floor, the general synonyms were not written blind |
| Explain the API to the funder as WhatsApp vs the WhatsApp Business API | My choice over a gym analogy: the same person-vs-system split and per-use billing, familiar to an Indonesian funder |
| API setup at $0 (workspace, $20 spend limit, key in `.env`); credit bought on Day 10 before the first call | No spend before M2's calibration run |

### What I delegated, and what I decided

I decided the G3 review, R1–R3 for R4 and K1 (Claude's recommendations, accepted), chose the funder
analogy, and wrote part of `enum_map_from()`: the lowercase value (B) and the logic of the all-or-
nothing check (C) and the output (D). Claude wrote the regex (A), the fix to C, the f-string syntax,
the ablation study, the engine integration and the `status` exclusion, all tests, the M1 page and the
funder note on the Claude API.

### Understood

- **Ablation:** remove one part, re-measure, and the difference is that part's contribution. Parts
  that change nothing on dev are untested, not useless.
- **Mapping F1 and transform accuracy measure different things:** a right target with a wrong table
  is a mapping true positive and a transform error.
- **False friends in enum values:** the same code can name different steps in different partners'
  processes.
- **A rule fitted to one example cannot be evaluated honestly** under leave-one-spec-out; recording
  the gap beats building something unmeasurable.
- **Subscription vs API:** a person using Claude's apps for a flat fee, vs software calling Claude with
  a key, billed per token from prepaid credit with a spend limit.

### Still open

- Block 5 (API setup at $0) confirmed done or not; credit bought on Day 10 before the calibration run.
- M2 design: prompt, the label schema for structured output, which fields go to Claude, cost logging,
  and how `status` values are read.
- Keyed fields, schema-only `enum` values, derived values, one-partner vocabulary: in the M1 page's
  gap table.
- A second labeller on a 20% sample before results are published.
- Block times: not recorded again.
- Carried from earlier days.

### Tomorrow

M2 begins: buy the credit (spend limit already set), load the key from `.env`, design the M2 call
(structured output, cached schema and rules, the same escalation policy), then a calibration run on one
dev partner to replace the cost estimate with measured numbers.
