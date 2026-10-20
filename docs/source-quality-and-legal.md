# Source quality, compliance, and production boundary

The sample inputs are fictional. `example.org` / `example.com` URLs are documentation placeholders, not scraped registries. This project makes **no real network requests** and does not validate a property title, lien, reserve price, auction outcome, court filing, parcel ID, or legal encumbrance.

## What is actually implemented

- Offline CSV/JSON/illustrative HTML-card parsers and source-specific mapping.
- Normalization for select European number, date, country and language patterns.
- Deterministic property keys based on source-provided country + cadastral reference.
- Source observation timestamps, source IDs and original source URLs kept with output.
- Data-quality quarantine, cross-source conflict reporting and deterministic precedence.
- SQLite current-snapshot table plus curated JSONL text for downstream RAG experiments.
- Tested reruns; no extraction of restricted, personal or password-protected information.

## Production requirements not implemented

1. Confirm each official source's terms of use, licensing, robots policies, access permissions, privacy/retention constraints, and appropriate lawful legal basis before collecting data.
2. Build *source-specific adapters* with robust pagination, dynamic HTML parsing, localized encodings, retry/backoff, rate-limit handling, CAPTCHA **non-circumvention**, structured logs, and monitoring. This project does not circumvent any site restrictions.
3. Handle genuinely multilingual documents (PDF text, scanned image OCR, entity extraction, natural-language disambiguation), with language-specific tests and human review.
4. Replace this simplistic cadastral key with verified identifiers and country-specific registry matching. Conflicting prices may reflect amended auctions or different legal rights, not a bad source.
5. Maintain versioned history / bitemporal validity instead of only current snapshot. Persist conflicts and rejects to monitored storage.
6. Confirm auction price currency and conversion. Demo examples accept only EUR; currency is not inferred from mixed-country production listings.
7. RAG: supply embeddings, vector store, retrieval quality tests, redaction, hallucination checks, and citation correctness before suggesting downstream legal-investment use.
8. Add infrastructure for AWS or other approved platform, secrets, IAM, deployment, alerting, recovery, and a controlled change process.

## Suggested initial freelance scope

Take one officially permitted public source, define an extraction contract and provenance requirements, build a controlled incremental ingestion path and quality dashboard, and demonstrate how bad/conflicting data is flagged before downstream AI processing.
