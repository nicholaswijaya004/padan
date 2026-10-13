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
