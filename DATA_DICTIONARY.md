# IPO Intelligence — Data Dictionary

This document details the relational entities, attributes, data types, constraints, and operational purposes across the 10 core tables in **IPO Intelligence**.

---

## 1. Table: `ipos`
The central registry entity representing an Indian Initial Public Offering.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | VARCHAR(36) | No | UUIDv4 | Primary key (UUID string) |
| `symbol` | VARCHAR(20) | Yes | NULL | NSE/BSE trading ticker symbol if assigned |
| `company_name` | VARCHAR(255) | No | - | Statutory legal name of the issuing company |
| `exchange` | VARCHAR(20) | No | - | Exchange listing venue: `NSE`, `BSE`, or `NSE_BSE` |
| `category` | VARCHAR(20) | No | `MAINBOARD` | Market tier: `MAINBOARD` or `SME` |
| `lifecycle_status` | VARCHAR(30) | No | `DISCOVERED` | State: `DISCOVERED`, `DOCUMENTS_PENDING`, `PRELIMINARY_ANALYSIS`, `PRICE_BAND_AVAILABLE`, `SUBSCRIPTION_OPEN`, `SUBSCRIPTION_CLOSED`, `FINAL_ANALYSIS`, `LISTED`, `OUTCOME_VERIFIED`, `WITHDRAWN`, `POSTPONED` |
| `min_price` | NUMERIC(12, 2) | Yes | NULL | Price band floor in Indian Rupees (INR) |
| `max_price` | NUMERIC(12, 2) | Yes | NULL | Price band cap in Indian Rupees (INR) |
| `lot_size` | INTEGER | Yes | NULL | Minimum number of shares per application lot |
| `issue_size_crores` | NUMERIC(14, 2) | Yes | NULL | Total issue size in ₹ Crores (1 Crore = 10 Million INR) |
| `fresh_issue_crores`| NUMERIC(14, 2) | Yes | NULL | Fresh capital raised by the company in ₹ Crores |
| `ofs_crores` | NUMERIC(14, 2) | Yes | NULL | Offer For Sale (secondary sale by existing promoters/PE) in ₹ Crores |
| `open_date` | DATE | Yes | NULL | Issue opening date for public bidding |
| `close_date` | DATE | Yes | NULL | Issue closing date for public bidding |
| `allotment_date` | DATE | Yes | NULL | Finalization of basis of allotment date |
| `refund_date` | DATE | Yes | NULL | Initiation of refunds / unblocking of ASBA funds |
| `credit_date` | DATE | Yes | NULL | Credit of equity shares to Demat accounts |
| `listing_date` | DATE | Yes | NULL | Date trading commences on the exchange |
| `face_value` | NUMERIC(8, 2) | Yes | NULL | Face value per share in INR (e.g. ₹1, ₹2, ₹10) |
| `lead_managers` | TEXT | Yes | NULL | Merchant bankers managing the book (comma-separated or JSON) |
| `registrar` | VARCHAR(255) | Yes | NULL | Registrar to the issue (e.g. Link Intime, KFintech) |
| `data_completeness_pct` | INTEGER | No | 0 | Automated calculation of available vs required data points (0 - 100) |
| `analysis_status` | VARCHAR(30) | No | `PENDING` | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED` |
| `is_demo` | BOOLEAN | No | FALSE | Explicit flag demarcating mock / sandbox data |
| `created_at` | TIMESTAMP (UTC)| No | utcnow() | Creation timestamp |
| `updated_at` | TIMESTAMP (UTC)| No | utcnow() | Last update timestamp |

---

## 2. Table: `ipo_events`
Chronological milestone log tracking state changes and announcements.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `ipo_id` | VARCHAR(36) | No | Foreign key referencing `ipos.id` (ON DELETE CASCADE) |
| `event_type` | VARCHAR(50) | No | e.g. `STATUS_CHANGED`, `RHP_FILED`, `PRICE_BAND_REVISED`, `SUBSCRIPTION_STARTED` |
| `from_status` | VARCHAR(30) | Yes | Previous lifecycle status |
| `to_status` | VARCHAR(30) | Yes | New lifecycle status |
| `headline` | VARCHAR(255) | No | Short title of event |
| `description` | TEXT | Yes | Detailed description or context |
| `event_timestamp`| TIMESTAMP (UTC)| No | Event occurrence timestamp |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 3. Table: `source_observations`
Auditable evidence store capturing raw data provenance.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `ipo_id` | VARCHAR(36) | Yes | Foreign key referencing `ipos.id` (Nullable if discovered before IPO created) |
| `source_name` | VARCHAR(100) | No | e.g. `SEBI_PUBLIC_FILINGS`, `NSE_ANNOUNCEMENT`, `BSE_CIRCULAR` |
| `canonical_url` | TEXT | No | Source URL where observation was captured |
| `content_hash_sha256`| VARCHAR(64) | No | SHA-256 hash of fetched response content |
| `publication_timestamp`| TIMESTAMP (UTC)| Yes | Timestamp claim made by original publisher |
| `retrieval_timestamp`| TIMESTAMP (UTC)| No | When IPO Intelligence crawler recorded the observation |
| `validation_status` | VARCHAR(30) | No | `VALID`, `UNVERIFIED`, `HASH_MISMATCH`, `REJECTED` |
| `raw_metadata` | JSON | Yes | Extracted HTTP headers, status code, extraction params |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 4. Table: `documents`
Version-controlled document filing registry (DRHP, RHP, Corrigenda).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `ipo_id` | VARCHAR(36) | No | Foreign key referencing `ipos.id` |
| `document_type` | VARCHAR(50) | No | `DRHP`, `RHP`, `PROSPECTUS`, `CORRIGENDUM`, `BASIS_OF_ALLOTMENT` |
| `version_number`| INTEGER | No | Version sequence number (1, 2, 3...) |
| `file_name` | VARCHAR(255) | No | Original file name |
| `file_url` | TEXT | No | Public / stored URL |
| `file_hash_sha256` | VARCHAR(64) | No | SHA-256 hash verifying document immutability |
| `file_size_bytes` | BIGINT | Yes | File size |
| `filing_date` | DATE | Yes | Official filing date |
| `is_current` | BOOLEAN | No | True if latest active document of this type |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 5. Table: `financial_observations`
Normalized historical financials across restated periods.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `ipo_id` | VARCHAR(36) | No | Foreign key referencing `ipos.id` |
| `fiscal_year` | VARCHAR(20) | No | Fiscal period (e.g. `FY24`, `FY23`, `FY22`, `H1FY25`) |
| `period_months` | INTEGER | No | Period duration in months (e.g. 12 or 6) |
| `revenue_crores`| NUMERIC(14, 2) | Yes | Total operating revenue in ₹ Crores |
| `ebitda_crores` | NUMERIC(14, 2) | Yes | Operating profit before interest, tax, D&A |
| `pat_crores` | NUMERIC(14, 2) | Yes | Profit After Tax (Net Income) in ₹ Crores |
| `total_assets_crores` | NUMERIC(14, 2) | Yes | Total Balance Sheet Assets in ₹ Crores |
| `net_worth_crores` | NUMERIC(14, 2) | Yes | Shareholders' equity (Net worth) in ₹ Crores |
| `total_debt_crores`| NUMERIC(14, 2) | Yes | Long-term and short-term debt in ₹ Crores |
| `roe_pct` | NUMERIC(6, 2) | Yes | Return on Equity (%) |
| `roce_pct` | NUMERIC(6, 2) | Yes | Return on Capital Employed (%) |
| `eps_inr` | NUMERIC(10, 2) | Yes | Diluted Earnings Per Share in INR |
| `nav_per_share_inr` | NUMERIC(10, 2) | Yes | Net Asset Value per share in INR |
| `source_document_id` | VARCHAR(36) | Yes | FK referencing `documents.id` |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 6. Table: `subscription_snapshots`
Time-series bidding demand captured across subscription window.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `ipo_id` | VARCHAR(36) | No | Foreign key referencing `ipos.id` |
| `snapshot_time` | TIMESTAMP (UTC)| No | Exact observation timestamp |
| `qib_subscription_times` | NUMERIC(10, 2) | Yes | Qualified Institutional Buyers subscription multiple |
| `nii_subscription_times` | NUMERIC(10, 2) | Yes | Non-Institutional Investors (HNI) multiple |
| `rii_subscription_times` | NUMERIC(10, 2) | Yes | Retail Individual Investors subscription multiple |
| `employee_subscription_times` | NUMERIC(10, 2) | Yes | Employee reservation quota multiple |
| `total_subscription_times` | NUMERIC(10, 2) | Yes | Cumulative overall subscription multiple |
| `total_shares_bid` | BIGINT | Yes | Total aggregate shares applied for |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 7. Table: `market_observations`
Sentiment indicators (GMP) and post-listing verification outcomes.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `ipo_id` | VARCHAR(36) | No | Foreign key referencing `ipos.id` |
| `observation_type` | VARCHAR(30) | No | `GMP_OBSERVATION` or `LISTING_OUTCOME` |
| `observation_time`| TIMESTAMP (UTC)| No | Observation timestamp |
| `gmp_inr` | NUMERIC(10, 2) | Yes | Grey Market Premium estimated premium per share in INR |
| `gmp_percent` | NUMERIC(6, 2) | Yes | Estimated percentage listing premium over issue cap |
| `final_issue_price_inr` | NUMERIC(12, 2) | Yes | Discovered issue price |
| `listing_open_price_inr`| NUMERIC(12, 2) | Yes | Actual open price on exchange day-1 |
| `listing_close_price_inr`| NUMERIC(12, 2)| Yes | Actual day-1 closing price |
| `listing_gain_pct`| NUMERIC(6, 2) | Yes | Actual day-1 listing percentage gain / loss |
| `bhavcopy_verified`| BOOLEAN | No | False until verified against official exchange Bhavcopy |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 8. Table: `model_versions`
Audit registry of Machine Learning models and heuristic scorecards.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `model_name` | VARCHAR(100) | No | e.g. `BASELINE_LOGISTIC_REGRESSOR`, `CATBOOST_LISTING_V1` |
| `version_tag` | VARCHAR(50) | No | Semantic version tag (e.g. `v0.1.0-alpha`) |
| `algorithm` | VARCHAR(100) | No | Algorithm family |
| `training_cutoff_date` | DATE | Yes | Strict date barrier preventing lookahead leakage |
| `validation_metrics` | JSON | Yes | Brier score, ROC-AUC, calibration error |
| `feature_manifest` | JSON | Yes | Ordered list of expected input feature names |
| `is_active` | BOOLEAN | No | True if active production model |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 9. Table: `predictions`
Append-only log of model assessments and probabilistic forecasts.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `ipo_id` | VARCHAR(36) | No | Foreign key referencing `ipos.id` |
| `model_version_id`| VARCHAR(36) | No | Foreign key referencing `model_versions.id` |
| `prediction_timestamp` | TIMESTAMP (UTC)| No | When inference was computed |
| `forecast_horizon` | VARCHAR(50) | No | Target: `LISTING_OPEN`, `LISTING_DAY_CLOSE`, `LONG_TERM_1Y` |
| `positive_return_prob` | NUMERIC(5, 4) | Yes | Probability of listing at or above issue price (0.0000 - 1.0000) |
| `predicted_return_pct` | NUMERIC(6, 2) | Yes | Point estimate expected return % (if regression model) |
| `risk_decile` | INTEGER | Yes | Risk decile 1 (lowest risk) to 10 (highest risk) |
| `feature_snapshot` | JSON | Yes | Frozen input vector at moment of prediction |
| `evidence_summary` | JSON | Yes | Feature importance or explanation weights |
| `prediction_status` | VARCHAR(30) | No | `ACTIVE`, `SUPERSEDED`, `RETIRED` |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |

---

## 10. Table: `ingestion_jobs`
Automated pipeline execution logs and audit records.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | No | Primary key |
| `job_type` | VARCHAR(50) | No | e.g. `DISCOVERY_POLL`, `DOCUMENT_SYNC`, `FINANCIAL_EXTRACTION` |
| `source_system` | VARCHAR(100) | No | e.g. `SEBI_PORTAL`, `NSE_FEED`, `BSE_FEED` |
| `status` | VARCHAR(30) | No | `RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED` |
| `started_at` | TIMESTAMP (UTC)| No | Ingestion start timestamp |
| `completed_at` | TIMESTAMP (UTC)| Yes | Ingestion end timestamp |
| `records_processed` | INTEGER | No | Count of records processed |
| `error_details` | TEXT | Yes | Stack trace or failure reason if failed |
| `created_at` | TIMESTAMP (UTC)| No | Record creation timestamp |
