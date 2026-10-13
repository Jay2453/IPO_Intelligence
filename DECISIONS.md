# IPO Intelligence — Architecture Decision Records (ADRs)

## ADR 001: Unified Relational Database with Multi-Dialect Support (PostgreSQL & SQLite)
- **Status**: Accepted
- **Context**: The primary production requirement specifies PostgreSQL for ACID compliance, relational integrity, foreign key cascades, and time-series querying. However, local developer setups and automated test runners (pytest, GitHub Actions) may not always have a running PostgreSQL daemon immediately reachable.
- **Decision**: Architect SQLAlchemy 2.0 models and Alembic migrations using portable standard SQL types (`String(36)` UUID representation, timezone-aware UTC timestamps, JSON/Text fallback). Set `DATABASE_URL` default to PostgreSQL, with zero-friction fallback to local SQLite for tests and local non-Docker development.
- **Consequences**: Fast test execution (in-memory SQLite in under 2 seconds for full test suite) and zero barriers to entry for initial developer setup, while retaining 100% compatibility with PostgreSQL via Docker Compose.

---

## ADR 002: Explicit `is_demo` Demarcation and Hardened Seed Isolation
- **Status**: Accepted
- **Context**: Financial products are vulnerable to reputation loss and regulatory non-compliance if mock or demo records are mistakenly represented as verified real market observations.
- **Decision**:
  1. Add an indexed boolean column `is_demo` directly to the `ipos` table.
  2. Implement an API route `/api/v1/seed/demo` that is explicitly disabled whenever `ENABLE_DEV_SEED != true` or `ENVIRONMENT == 'production'`.
  3. Every API response returns `is_demo: boolean`. The frontend UI strictly checks this flag and displays an unmissable amber `DEMO DATA` badge on every card, table row, and header.
- **Consequences**: No mock data can ever masquerade as real data.

---

## ADR 003: Append-Only Predictions with Model Versioning & Temporal Cutoffs
- **Status**: Accepted
- **Context**: In financial forecasting, model results must be strictly auditable to prevent hindsight bias, model tampering, or survivor bias.
- **Decision**: Predictions are stored in an append-only table `predictions`. A prediction is never updated in-place; when a new model or feature snapshot generates an updated estimate, a new prediction record is appended with a status of `ACTIVE`, and the previous record is marked `SUPERSEDED`. Every prediction links directly to a foreign key `model_version_id`.
- **Consequences**: Full historical audit trail; ability to measure model calibration across time horizons without losing earlier forecasts.

---

## ADR 004: Anti-Leakage Temporal Barrier for Future ML Training
- **Status**: Accepted
- **Context**: Common ML mistakes in financial modeling include using data that was not publicly known at the decision time (e.g., using final listing price, post-allotment subscription numbers, or revised financial figures to predict pre-issue outcomes).
- **Decision**: Architect point-in-time dataset generation enforcing a hard cutoff timestamp $T_{cutoff} \le T_{issue\_close}$. The feature extraction pipeline programmatically rejects any observation whose `observation_time` or `publication_timestamp` is greater than $T_{cutoff}$.
- **Consequences**: Model training and walk-forward backtests reflect true real-world operational reality without synthetic inflated accuracy.

---

## ADR 005: Honest Empty States & "Not Configured" Health Semantics
- **Status**: Accepted
- **Context**: Many dashboards display green "healthy" badges or synthetic numbers ("0.0%" or "N/A - Healthy") when an external pipeline or database is unconfigured.
- **Decision**: The system health endpoint `/api/v1/health` and `/api/v1/system/status` probe live dependencies (database connection ping, active ingestion logs). Any unverified or unconfigured source (e.g. SEBI Portal, NSE Feed) explicitly returns status `NOT_CONFIGURED` with an explanation. Unavailable financial metrics render an honest empty state ("Data not disclosed in DRHP" or "Pending RHP filing").
- **Consequences**: Complete transparency for the user and clear visibility into system boundaries.

---

## ADR 006: Physical Page Indexing and Extraction Provenance Standards
- **Status**: Accepted
- **Context**: In financial PDF filings (DRHP, RHP, Abridged Prospectus), discrepancies arose where:
  1. Record-level `extraction_method` defaulted to `PDFPLUMBER_TABLE` even when metrics were parsed via flowing text lines (`TEXT_LINE`).
  2. Observation-level `source_page` was overwritten by supplementary KPI pages (e.g., page 7) instead of the primary financial statement page (e.g., page 6).
  3. Printed footer page numbers differed from physical PDF page indices (e.g., physical page 6 having printed footer "5").
- **Decision**:
  1. Standardize `source_page` across all entities as the **1-based physical PDF page number** (`page_idx + 1`). Physical page indexing is deterministic and directly reproducible in PDF readers (Adobe Acrobat, Chrome PDF viewer) and automated tools (`pdfplumber`).
  2. Observation-level `source_page` strictly records the primary statement page where core financial statement metrics (Revenue, PAT, EBITDA, Net Worth) reside. Line items retain their individual extraction `source_page`, and `raw_data_provenance.source_pages` lists all contributing pages (e.g., `[6, 7]`).
  3. Record-level `extraction_method` dynamically derives from the actual extraction methods of contributing line items: `TEXT_LINE` when parsed via text lines, `PDFPLUMBER_TABLE` when parsed via ruled tables, or `HYBRID` when both contribute.
  4. Non-disclosed metrics in abridged filings (e.g., Total Assets / Total Liabilities not present in SEBI abridged formats) remain `None` and are not flagged as extraction failures.
  5. Re-extraction is strictly idempotent: existing observations are refreshed in-place, preventing duplicate rows and maintaining accurate extraction status (`PARTIAL` or `EXTRACTED`, never corrupted to `FAILED`).
- **Consequences**: Full transparency, reproducible provenance, and zero data duplication on repeated ingestion.

---

## ADR 007: SEBI Ingestion Optimization, Pipeline Telemetry, and Transient Resilience
- **Status**: Accepted
- **Context**: 
  1. SEBI sync jobs took 4–7 minutes because every sync streamed large PDF files (11–35 MB) across the network before computing SHA-256 hashes, even when the document was already stored.
  2. Documents classified as `ABRIDGED_PROSPECTUS` were omitted from automatic extraction triggers, leaving 16 matched real IPO prospectuses stranded in `PENDING`.
  3. System health telemetry omitted `PARTIAL` document extraction counts, creating a reporting discrepancy where stored documents did not sum to total filings.
  4. Transient network stream disconnects on large downloads caused entire ingestion jobs to be labeled `PARTIAL` without preserving actionable error details.
- **Decision**:
  1. **Fast URL Pre-check & Remote Metadata Probe**: Query stored documents by `file_url` prior to downloading full PDF payloads. Probe remote `Content-Length` via lightweight HTTP `HEAD` request; if size matches stored metadata, skip the multi-megabyte download. If remote size differs or `force_recheck=True` is provided, download and perform cryptographic SHA-256 validation.
  2. **Expanded Extraction Trigger**: Include `ABRIDGED_PROSPECTUS` in `doc_type` triggers alongside `DRHP`, `RHP`, `DRAFT_ABRIDGED_PROSPECTUS`, and `PROSPECTUS`.
  3. **Strict Reconciled Telemetry**: Expose `PARTIAL` counts across `get_document_status()` and frontend telemetry. Reconcile invariant: `total_documents == pending + extracted + partial + failed + unmatched`.
  4. **Status Definitions**:
     - `EXTRACTED`: All recognized fiscal periods in the document yielded usable statutory metrics.
     - `PARTIAL`: At least one fiscal period yielded usable metrics, while some periods contained omitted/null figures.
     - `PENDING`: Stored document matched to an IPO, awaiting on-demand or bounded extraction.
     - `UNMATCHED`: Stored document could not be matched with confidence to an active tracked IPO.
     - `FAILED`: Document was processed, but zero usable metrics could be extracted from any period, or an unrecoverable extraction error occurred.
  5. **Bounded Transient Retry & Concurrency Guard**: Implement 1 bounded retry for transient network disconnects (`httpx.RemoteProtocolError`, timeouts). Safely reject concurrent overlapping manual SEBI syncs via HTTP 409 Conflict. Sweep stranded `RUNNING` jobs older than 15 minutes.
  6. **Decoupled Pending Extraction Queue and PDF Payload Caching**: Stored documents awaiting extraction (`PENDING`) are processed through a bounded observable queue (`extract_pending_documents`) and dedicated endpoints (`POST /api/v1/sebi/extract-pending` and `POST /api/v1/documents/{id}/extract`), using local disk-backed PDF caching indexed by SHA-256 (`backend/data/pdf_cache/{sha256}.pdf`) to eliminate redundant HTTP downloads for stored files.
- **Consequences**: Sync duration drops from 300+ seconds to < 2 seconds for cached documents; zero redundant bandwidth usage; fully reconciled and honest telemetry reporting; clean extraction lifecycle for stored filings.

---

## ADR 008: Historical Ingestion Architecture & ISIN-First Entity Resolution
- **Status**: Accepted
- **Context**: 
  1. IPO coverage was concentrated in late 2026, with only 1 listing outcome recorded, which is insufficient for training predictive ML models.
  2. Expanding coverage back to 2015 requires ingesting historical exchange archives (NSE and BSE) and reconciling listing day price outcomes against official daily Bhavcopy files.
  3. Securities in Indian equity markets may have renamed symbols or different scrip codes across exchanges, creating false duplicates or accidental merges if matched merely by company names.
- **Decision**:
  1. **ISIN-First Resolution**: Use ISIN (`String(12)`, ISO 6166) as the primary immutable identifier for equity securities. Never merge records with differing valid ISINs, even if company names look similar. Fallback to `(exchange, symbol, listing_date +/- 7 days)` only when ISIN is absent on both records.
  2. **Concrete Bhavcopy Outcome Verifier**: Implement `BhavcopyOutcomeVerifier` implementing `IOutcomeVerifier`. Parses both modern (`sec_bhavdata_full.csv`) and legacy (`cm<date>bhav.csv`) NSE formats as well as BSE equity Bhavcopy (`EQ_ISIN_<date>.CSV`). Computes `listing_open_price_inr`, `listing_close_price_inr`, `listing_open_gain_pct`, `listing_gain_pct`. Caches files locally under `data/bhavcopy_cache/{exchange}/{year}/` with SHA-256 verification.
  3. **Historical Archive Parsers**: Implement `HistoricalArchiveParser` for NSE and BSE past issue archives (JSON and CSV formats) with flexible date parsing, number cleaning, and ISIN validation.
  4. **Strict Idempotency & In-Place Updates**: `HistoricalIngestionService` updates existing IPOs in-place without altering existing primary keys (`id`) or modifying child `financial_observations` and `documents`. Never overwrites existing verified outcomes (`bhavcopy_verified == True`). Supports dry-run simulation mode (`dry_run=True`).
  5. **Schema Migration**: Added `isin`, `bse_scrip_code` to `ipos` and `exchange`, `source_url`, `source_file_hash`, `raw_data_provenance` to `market_observations` via Alembic revision `d32f7e8afccc`.
- **Consequences**: Deterministic, lookahead-free historical outcomes verification; zero data corruption on existing records; transparent provenance for Day-1 prices; robust foundation for Phase 2 backfill.
