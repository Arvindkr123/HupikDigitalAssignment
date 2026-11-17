# Harbourline Physio — SEO and automation assignment

This project folder contains the work for the four assignment parts. The clinic, addresses, phone numbers, and `.example` domain in the brief are fictional.

## Status at hand-in

- **Part A — WordPress:** child theme, native Location fields, idempotent seed data for both locations, FAQs, and generated JSON-LD are provided. The local WordPress render, screenshots, Rich Results Test, and mobile Lighthouse before/after still need to be done in LocalWP/Chrome.
- **Part B — Search analysis:** runnable code, cleaned CSV input, ranked opportunities, page-conflict report, and owner summary are included.
- **Part C — Scanner:** CLI, four JSON scan results, approval CSV, and drafts for approved URLs are included. PageSpeed Insights returned HTTP 429 after retries for the public URLs; those fields are marked unavailable. The Harbourline result is a static HTML fixture, not a WordPress-rendered page.
- **Part D — Thinking questions:** answered below.

## Run it

From the assignment folder in PowerShell:

```powershell
python analysis\analyze.py
python -m unittest discover -s analysis -v
python -m pip install -r scanner\requirements.txt
python -m unittest discover -s scanner -v
python scanner\scan.py https://www.sydneyphysio.com.au/
python scanner\draft.py
```

The analysis script reads `analysis/gsc_export.csv` and regenerates `opportunities.csv`, `page_conflicts.csv`, and `summary.md`. The scanner writes JSON under `scanner/results/`; it makes no LLM calls. Only `yes` rows in `scanner/approvals.csv` get a draft in `scanner/outbox/`.

For Part A, install LocalWP and WordPress, activate Twenty Twenty-Five, copy `wordpress/harbourline-child` into `wp-content/themes/`, and follow [wordpress/README.md](./wordpress/README.md). Run its WP-CLI seed command to create both locations. Do not treat `wordpress/chatswood-preview.html` as a WordPress render; it is only a scanner fixture until the local site is tested.

## Part B — Data decisions

The supplied file is an `.xlsx` workbook although the brief calls it a CSV. Its worksheet is `gsc_export.csv`; it has been exported to `analysis/gsc_export.csv`, preserving empty cells. The input has 224 query rows plus one `Grand total` row.

| Finding | Rows affected | Treatment |
|---|---:|---|
| Grand total is mixed into the query rows and has no page | 1 | Excluded from query analysis. Its 4,014 clicks and 86,114 impressions match the uncleaned detail-row sums exactly. |
| Exact duplicate query/page/metric rows | 5 | Removed so repeated export rows do not inflate results. Together they account for 6 clicks and 2,244 impressions. |
| Same query/page appears again with different metrics | 4 query-page groups | Aggregated: clicks and impressions are summed; average position is impression-weighted; CTR is recalculated. |
| Page URL has an HTTP/non-`www` variant | 1 row | Normalized to the same HTTPS page as the rest of the site. |
| Page URL contains UTM tracking parameters | 1 row | Tracking parameters are removed before grouping so a tagged URL is not treated as a different page. |
| Query capitalization differs (`Physio Chatswood`) | 1 row | Case-folded for grouping and branded classification; the original query text is retained for display. |
| Blank clicks and blank CTR | 6 source rows (4 distinct rows after exact de-duplication) | Missing clicks are assumed to be zero because impressions are present; CTR is derived from clicks/impressions. |
| Blank average position | 1 distinct row | Keep its clicks/impressions, but do not use it in ranking or quick-win selection. |
| Average position of zero | 1 row | Treat as invalid/missing for ranking, not as a real position. |
| CTR over 100% | 1 row | Retain it: 673 clicks / 633 impressions is 106.32%, which can occur when a result gets multiple clicks per impression. It is not a negative or impossible metric. |
| Missing numeric values otherwise, negative metrics, or numeric CTR mismatches | 0 | No other cases found. |

The phrase “near me” is repeated in one query across 3 source rows. It is preserved verbatim as search data rather than rewritten; exact duplicate and page-overlap handling still applies.

After cleaning, there are 215 query/page combinations, 4,008 clicks, and 83,870 impressions. The click change from the source total is entirely due to removing the exact duplicates.

“Branded” matches Harbourline name forms including `Harbourline`, `Harbor line`, and `Harbourlines`. The branded share is **1,545 / 4,008 = 38.55% of clicks**.

Quick wins are non-branded queries with at least 100 impressions and an average position greater than 3 and no worse than 20. Job/course intent and clearly out-of-area states are excluded. For positions 4–10, the benchmark CTR is 12%; for positions 11–20 it is 5%. The score is `impressions × max(benchmark CTR − actual CTR, 0) × relevance multiplier`: 1.2 for an offered service or a named clinic suburb, 0.8 for another location signal, 0.5 for informational searches, and 1.0 otherwise. It is an opportunity estimate, not a forecast. This produces 25 ranked queries. The 37-query overlap report recommends a page based on explicit suburb/service/booking intent first, then current ranking where intent is unclear; review those recommendations against real catchment and conversion data.

## Part A — WordPress implementation notes

The child theme uses native post meta instead of ACF. The CPT editor stores each location detail once; both the visible template and JSON-LD read those same values. FAQs are displayed in the HTML and repeated in generated `FAQPage` data. The business uses the Schema.org `MedicalBusiness` type with the `Physiotherapy` medical-specialty value, address, phone, and opening-hours specifications. No geo coordinates were invented.

On a real client site, I would first verify the sample addresses and booking workflow, use the client's approved wording and coordinates, then test the rendered page, schema, and accessibility with their content and brand assets. Google may not show FAQ rich results for a commercial clinic even when the JSON-LD parses.

## Part C — Scan targets and limitations

The three public targets are [Sydney Physiotherapy](https://www.sydneyphysio.com.au/), [City Physio & Pilates](https://cityphysio.com.au/), and [Sydney Allied Health's Balmain physiotherapy page](https://www.sydneyalliedhealth.com.au/balmain-physiotherapy). The fourth result scans the local static Harbourline fixture. The three live PageSpeed requests returned HTTP 429, so the JSON correctly marks the score and LCP unavailable; this is not represented as a successful performance test. Two example email drafts were generated because their URLs are approved; the other URLs are marked `no`.

The scanner makes no LLM calls, so its current drafting cost is $0. Its public fetcher only follows public HTTP(S) hosts and limits redirects and downloaded HTML. A hosted version would still need an egress-controlled worker, rate limits, caching, and a queue.

## Part D — Thinking questions

### Your score

The score could over-prioritize “physio near me”: its large impression count may include searchers outside Chatswood and Parramatta or people who will not become patients. I would split it by location and device, then use call, booking, and direction-request data to estimate useful demand. I would also lower the score for queries that do not match the clinic’s service area.

### Mixed signals

1. More searchers may call from the map listing without visiting the site. Check Business Profile calls/directions and compare them with Search Console clicks by query and suburb.
2. Website analytics may be undercounting visits after a tag or consent change while the profile calls are real. Compare Search Console clicks with GA4 organic sessions, consent rates, and tag diagnostics.
3. Search demand or ranking may have shifted toward local/map results, especially on mobile. Compare impressions, average position, device, and suburb in Search Console with profile views/calls and call logs over the same dates.

### Scale

The first bottleneck is likely PageSpeed quota/latency, followed by slow or oversized target pages. I would queue scans, cache results, cap per-user frequency, limit concurrency and response size, and run fetches in an isolated worker with strict outbound-network rules. At 1,000 scans/day, assume 30,000 scans/month, 2,000 input tokens and 500 output tokens per scan, and model rates of $2/M input and $8/M output tokens: $0.008 per scan, or **about $240/month**, excluding retries, tax, and hosting.

### Two more days

I would build focused sports-injury and back/neck landing pages linked from the two location pages, then instrument calls and bookings by landing page. That follows the data’s service-query demand and page overlap, and gives the clinic a way to judge whether more visibility is bringing in patients.

## Time log and AI use

Approximate AI-assisted implementation effort in this workspace (not a substitute for your own end-to-end time log):

| Part | Approx. effort | Status |
|---|---:|---|
| A | 45 minutes | Theme and seed data written; LocalWP/Chrome validation remains. |
| B | 45 minutes | CSV cleanup, analysis, outputs, and focused tests. |
| C | 60 minutes | Scanner, approval gate, live scans, and tests; PageSpeed was rate-limited. |
| D | 20 minutes | Drafted and checked the written answers and assumptions. |

AI was used to inspect the brief and workbook, implement the analysis/scanner/theme scaffolding, and draft the written explanations. I checked the data totals against the supplied grand total, reviewed the scan JSON and generated emails, and added tests for data cleaning, raw HTML extraction, and the approval gate. I did not fabricate Lighthouse scores or claim the local WordPress checks passed. Before submitting, replace the time estimates with your actual time, perform the remaining browser checks, and update this note to match your own review.

## Submission

This workspace was not a Git repository and no GitHub username or remote was supplied. Create/share the GitHub repository and add the assignment commits under your account before emailing the repository link.
