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
