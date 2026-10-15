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
