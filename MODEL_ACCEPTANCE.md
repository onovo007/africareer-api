# Model acceptance review — 28 September 2026

Decision: promote GPT-6 Sol for general guidance, résumé feedback, CVs and ordinary application documents. Use GPT-6 Astra (low reasoning) for explicitly doctoral application drafts and their factual review. The conversational assistant remains Sol, including doctoral questions; this release's Astra routing is confined to structured doctoral applications.

Compared 18 actual outputs across eight synthetic cases with identical prompts and retrieval disabled. Baselines: GPT-4o mini for advice, GPT-4.1-2025-04-14 for documents. All 18 passed the existing pipeline. This means schema and automated checks passed, not that every statement was independently verified. Three further candidate runs through the production LangChain library passed (21 completed runs total). No real applicant records used. This is a small editorial acceptance evaluation, not statistical proof of superiority or a full user pilot.

| Case | Baseline seconds | Sol seconds | Astra seconds |
|---|---:|---:|---:|
| Budget guidance | 6.53 | 7.85 | — |
| French guidance | 3.46 | 7.28 | — |
| Résumé feedback | 5.39 | 14.28 | — |
| Student CV | 6.59 | 18.71 | — |
| Professional CV | 5.22 | 13.34 | — |
| UCAS | 4.55 | 16.13 | — |
| PhD statement | 5.27 | 11.86 | 27.74 |
| PhD proposal | 6.40 | 27.85 | 101.61 |

Repeat runs: Sol student CV 7.90s, Sol UCAS 10.33s, Astra proposal 82.54s. Sol's first student CV and proposal needed one revision; both Astra proposals needed one revision. Repeated CV preserved all supplied proficiency qualifiers, student status, dates, 12 classmates and 300 records. Repeated UCAS answers were 409, 396 and 377 characters. Repeated Astra proposal was 392 words, preserved 1,200 records and MSc 2025, and explicitly separated proposed study design from completed work.

## Editorial findings

Sol's budget plan respected five hours weekly, zero budget and realistic internship preparation. Mini suggested unverified free platforms and used overconfident internship framing. Sol's résumé feedback recognized 8 clinics and 25 staff; mini incorrectly said metrics were absent. Sol distinguished activity counts from impact and kept keyword additions conditional on evidence. Both still need human review.

Sol's CVs were more factual and specific; the baseline added generic unsupported qualities. Sol's UCAS output retained supplied learning reflections; the baseline introduced unsupported retrospective reflections. Sol and Astra statements both preserved the core supplied facts. Astra did not show a decisive advantage on the short statement alone.

Astra's proposal supplied a concrete feasible design with appropriate limitations and ethics. The first used prospective qualitative interviews with training needs and voluntary participation; the repeat proposed existing-data analysis with a feasibility decision, missingness checks, conditional logistic regression and no causal claims. Sol's proposal was safer than baseline but deferred most design choices instead of proposing a usable design. Astra's proposal advantage supports the doctoral route, with longer wait time disclosed.

## Operational tradeoffs

General responses rose from roughly 3–7 seconds to 7–14 seconds in this sample. Doctoral proposals took 83–102 seconds. Academic request timeout is therefore extended to 260 seconds, with a visible waiting message. Doctoral generation permits two audited attempts, at most four provider calls with a 60-second timeout and no automatic transport retry per call. Validation failures remain closed; partial or truncated responses are not exported. Concurrent requests select clients independently. Environment variables allow rollback without source edits.

At published uncached short-context rates, approximate first-run model costs including audits were: résumé feedback mini $0.00049 versus Sol $0.01041; student CV 4.1 $0.01219 versus Sol $0.02565; PhD proposal 4.1 $0.01441, Sol $0.03394, Astra $0.29205. These are estimates using token counts, excluding cache adjustments and all other services. Billing is authoritative. The stronger models are materially more expensive, particularly Astra.

Sources: https://developers.openai.com/api/docs/models/gpt-6-sol and https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra . Model access was checked with the app's existing provider account. No embeddings, Pinecone index or job-search model changed.

Validation: 73 backend tests passed, including model parameter compatibility, rollback configuration, doctoral scope and truncated-response rejection. Frontend build and production smoke checks recorded after deployment below.

Remaining pilot checks: regional language coverage, multiple candidate backgrounds, retrieval-on citation support, peak concurrency, sustained latency/cost and real user preference. No numeric AI confidence percentage is inferred from this evaluation.
