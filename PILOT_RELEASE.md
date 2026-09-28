# Pilot API remediation — 28 September 2026

The release adds checked CV previews and exports, scoped academic formats, reviewed source notes, conservative search filtering and confirmed feedback persistence. Read the acceptance evidence before inviting users; automated model review is not factual certification.

## Validation

Run `python -m unittest discover -s tests -v` from this directory after installing `requirements.txt` with Python 3.12. These regression tests use mocked providers; live synthetic outputs require separate inspection. CI runs the same suite.

The ordinary guidance model remains GPT-4o mini. Documents and their factual review use the pinned `gpt-4.1-2025-04-14` JSON model because live testing exposed contradictory factual-review failures with the older model. `DOCUMENT_MODEL` allows an intentional server-side override. Re-run acceptance tests after any model change. Document generation can make up to three draft/review attempts and therefore costs more than one chat response.

## Configuration and rollout

Preserve existing server secrets. `FRONTEND_ORIGIN` must include each actual frontend origin. CORS is not authentication. Do not embed provider or admin secrets in frontend variables. Public launch needs durable cohort authentication and shared quotas; the current limiter is per-instance and requires trusted host proxy configuration.

Apply `migrations/001_pilot_feedback.sql` before enabling feedback. It adds a separate table with RLS and server-role access. A successful feedback response requires read-back of the stored payload. Retrying the same request ID does not create a duplicate. The migration and a synthetic duplicate check were performed in the existing Supabase project during remediation. Exclude synthetic test rows from pilot outcome analysis.

`/health` reports configuration presence and release identity, not full provider connectivity. Deploy the complete Dockerfile file list before the matching frontend; CV preview routes are `/cv/draft` and `/cv/document`.

## Evidence limits

The public library contains dated, reviewed short paraphrases from primary pages, with scope, limitations and note hashes. It is not a complete full-text corpus. Similarity scores and model self-assessments are not confidence probabilities. The evidence panel shows what references were supplied and explicitly says individual claims are not independently verified.

The existing Pinecone index has 2,017 records. Sampled legacy AfDB chunks lacked official URL, page and provenance metadata. Do not bulk-mark them verified. Only records with reviewed primary-source metadata pass the existing strict retrieval gate. No legacy records were deleted or rewritten.

Academic presets apply only to the stated application routes; applicants must confirm current requirements and authorship rules. CV exports preserve supplied numbers and language labels through deterministic checks; wording, completeness and user edits still need personal review. No employer ATS certification is claimed.

Price-filtered courses come from a small dated catalogue. Free learning access and free certificates are distinct. Jobs require matching structured posting metadata; unavailable metadata can yield no results. Opportunity discovery uses conservative search-text matching and does not confirm eligibility, funding or deadlines.
