# Task quality and contract decision — 2026-09-10

Canonical task SHA256: `8b251ad606c231b843c3af74d31ebbd9a09d31112e017d89cd0c2e9f03cbc115`.
18 tasks / 18 verifiers / 18 non-answer-leaking rubrics, IDs 0–17.
UI observations below come from the frozen `playwright-189ebc6-final-20260910`
runs, not a claim about an independently exploring model. The final shipment
and pickup bundles supersede those two runs only, without changing contracts.

## Per-task matrix

Actions include homepage start, menu clicks, done and persistence reload; they
are reproducible recorded counts, not a difficulty score. Target positions are
one-based. Generated quotes and authenticated terminal records are not search
previews: facts belong on those pages; a hidden requirement to open a nonexistent
detail would be inappropriate. No answer-key field is present in task/rubric.

| Task | Recorded path / actions | Candidates and target order | Leakage / reasoning / permitted alternatives |
|---|---|---|---|
| 0 | Tracking → result → detail; 8 | Exact identifier, 1 result; 5 timeline events | Lookup deliberately exact; latest cause/location requires detail. Homepage or tracking form may initiate the same request. |
| 1 | Multi-track → compare → delivered detail; 8 | 3 requested records; delivered record 1st | Status alone visible, signature absent from cards. Needs both status selection and signature detail; equivalent comma/newline inputs valid. |
| 2 | Support `tracking` → exception article; 8 | 18 guides across categories; target 18th | No requested event fields/status mapping in preview. Near-misses: weather, address-hold, proof-of-delivery guides. Task strengthened from topic-chip extraction. |
| 3 | Quote form → compare; 10 | 5 generated services, cheapest 4th | No quote before submit; min price comparison. State abbreviations/names normalize, valid prose accepted. |
| 4 | Quote form → compare + subtract; 10 | 5 services; fastest 1st, cheapest 4th | Not solvable from fastest card alone; correct pair and difference required. |
| 5 | Alice login → shipments → invoices; 12 | 15 shipment rows; Dallas delivery last; 15 invoices | Reverse Dallas-origin delivery is a near-miss. Requires cross-page code join. Either order of the two history pages is allowed after authentication. |
| 6 | Bob login → claims; 10 | 3 claims, matching status 1st | Terminal authenticated cards intentionally show identifiers. Simple status lookup, not high difficulty; wrong statuses are distractors. No nonexistent claim detail requirement. |
| 7 | Carol login → pickups; 8 | 2 pickups; ready-for-driver 2nd | Simple authenticated row selection; full time window + code required. Alternate equivalent time punctuation accepted. |
| 8 | David login → full history; 10 | 15 rows; matches 1st, 6th, 11th | Exhaustive set/filter, destination not origin. Dashboard only shows recent subset. Extra/mispaired results rejected; order of output irrelevant. |
| 9 | Locations `Ship Center` → Dallas; 8 | 11 counters; target 9th | Detail-only freight cutoff; service/type near-misses across cities. Broad named query is exercised. |
| 10 | Locations → Miami; 6 | 15 locations; target 6th | International-document note absent from listing. Simple detail lookup; no hidden requirement to use a particular query. |
| 11 | Global `delay` → weather guide → track → detail; 12 | 2 relevant guides; weather 2nd; 5 timeline events | Search has only 2 results: below the generic six-distractor heuristic. Retained for cross-page timestamp/ETA interpretation, not search difficulty. No date commitment in prompt/card. Strengthened from boilerplate extraction. |
| 12 | Alice login → shipment details → service → review → confirmation; 22 | 5 service choices; requested 2Day 3rd | Deep constrained stateful flow; exact fields and generated tracking are not supplied by a result card. Optional handoff choice remains allowed by the task contract. |
| 13 | Alice login → pickup location → earliest slot → account; 14 | 15 locations; Seattle 14th alphabetically; 3 dated slots, earliest 1st | Earliest order is deliberately visible, not hidden difficulty. Must create one correct pickup and bind generated confirmation to DB. Keeping preselected correct values is a legitimate alternative. |
| 14 | Global `Ship Center` → Seattle; 7 | 8 locations, target 1st | Search preview omits hours, detail required. Short lookup and first-target risk explicitly retained as lower-difficulty coverage. |
| 15 | David login → claims; 10 | 3 claims, requested type 3rd | Two missing-package near-misses. Terminal claim cards intentionally contain the two identifiers. |
| 16 | Tracking → detail → final event; 8 | Exact identifier, 1 result; 5 timeline events | Delivered badge is visible, final handoff location must be read from detail; reject contradictory moving/delivered answer. |
| 17 | Quote form → compare maximum; 10 | 5 services, most expensive 5th | Exact quote request and max service/price, not first-card selection. |

## Set decision and honest limits

Accept 18 without filler. They cover lookup, comparison, cross-page joining,
exhaustive filtering and two exact persistent workflows. Tasks 2/11 received
substantive repairs; task 10 now makes its locations navigation explicit;
3/17 lose test-oriented wording. Task/rubric/verifier semantics remain aligned.

The collection is mixed-difficulty, not 18 hard tasks. Tasks 6/7/10/14 are
simple authenticated/detail lookups; task 11 has only two search candidates;
task 14's target is first. These are explicit quality limitations, not disguised
as six-result/full-match or frontier-difficulty passes. The guided runs establish
solvability only. No empirical claim that a frontier model is challenged has
been established; an independent exploration study would be needed for that.
The six-result heuristic is applied to broad catalog search (2/9/14), not
exact-ID, generated quotes or authenticated terminal account records. Task 11
is retained on the strength of its multi-page reasoning rather than its search.

## Contract / scorer checks

The fresh 174-case matrix covers each actual run, valid prose, wrong/empty
answer, no-op, answer-only shortcut, foreign origin, wrong local port; plus
required-account omission, state mismatch, unrelated database change, and the
new 2/11 field/ETA negatives. Existing unit tests exercise equivalent hour
formats, wrong-task replay, negation/reversal, exact relationship/set binding,
signed quote submission and legal ordering/parameter choices. Legitimate
alternatives above are contract/static reviews plus applicable fixtures, not
18 additional independently recorded alternative-path runs.

## Facts and provenance

All task-answer facts are explicitly synthetic benchmark state, not asserted
as real current FedEx rates, tracking, locations or carrier policy. Source
authenticity for those facts is N/A with this disclosure. Original homepage
media/fonts have source URLs and hashes in the committed asset manifest.
Homepage visual reference was obtained from normal Chrome, not an access-error
page. Local detail templates were inspected for readability/population, not
claimed to exactly replicate real authenticated FedEx account pages.
