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
