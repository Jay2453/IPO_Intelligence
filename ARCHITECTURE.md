# IPO Intelligence — System Architecture

## 1. Architectural Topology

The IPO Intelligence platform is designed as a decoupled, layered full-stack application optimized for data integrity, auditable provenance, and future autonomous pipeline execution.

```
┌─────────────────────────────────────────────────────────────┐
│                   Next.js 15 Client (App Router)            │
│  - Dark Institutional UI                                    │
│  - IPO Radar & Interactive Table                            │
│  - IPO Deep Dive (Financials, Valuation, Subscriptions)     │
│  - Methodology & Disclosure Pages                           │
│  - System Health & Source Lineage Monitor                   │
└──────────────────────────────┬──────────────────────────────┘
                               │ JSON / HTTP (REST API v1)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend Service                  │
│  ├── API Routers (/api/v1/ipos, /health, /ingestion, etc.)  │
│  ├── Pydantic V2 Serialization & Validation Schemas         │
│  ├── Domain & Lifecycle Services                            │
│  ├── Future Pipeline Interfaces (Ingestion, Extraction)     │
│  └── Future ML Modular Stubs & Leakage Protections          │
└──────────────────────────────┬──────────────────────────────┘
                               │ SQLAlchemy 2.0 (Async/Sync)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Relational Storage Engine                 │
│  ├── PostgreSQL (Production / Docker Compose Target)        │
│  ├── SQLite (Seamless Local Dev / Automated CI Fallback)    │
│  └── Alembic Controlled Migrations                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Layout

```
IPO/
├── backend/
│   ├── alembic/                      # Database schema migrations
│   │   ├── versions/                 # Version migration scripts
│   │   └── env.py                    # Alembic execution environment
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── health.py     # System health and connectivity checks
│   │   │       │   ├── ipos.py       # IPO listing, filtering, and detail APIs
│   │   │       │   ├── ingestion.py  # Ingestion audit and job history
│   │   │       │   ├── system.py     # Source integration status
│   │   │       │   └── seed.py       # Dev-only demo data population
│   │   │       └── router.py         # Consolidated API v1 router
│   │   ├── core/
│   │   │   ├── config.py             # Typed settings using Pydantic Settings
│   │   │   └── database.py           # Engine, SessionFactory, Base declarative
│   │   ├── models/                   # 10 Core SQLAlchemy Entities
│   │   │   ├── base.py               # TimeStampedBase and UUID PK mixins
│   │   │   ├── ipo.py                # Primary IPO entity
│   │   │   ├── events.py             # IPOEvent milestone entity
│   │   │   ├── sources.py            # SourceObservation provenance entity
│   │   │   ├── documents.py          # Document revision entity
│   │   │   ├── financials.py         # FinancialObservation normalized metrics
│   │   │   ├── subscriptions.py      # SubscriptionSnapshot category demands
│   │   │   ├── market.py             # MarketObservation & listing outcomes
│   │   │   ├── predictions.py        # Append-only Prediction entity
│   │   │   ├── ingestion.py          # IngestionJob audit trail entity
│   │   │   └── ml_model.py           # ModelVersion registry entity
│   │   ├── schemas/                  # Pydantic validation schemas
│   │   │   ├── common.py             # Pagination and API envelope schemas
│   │   │   ├── ipo.py                # IPO request and response schemas
│   │   │   ├── events.py             # Event schemas
│   │   │   ├── documents.py          # Document schemas
│   │   │   ├── financials.py         # Financial observation schemas
│   │   │   ├── subscriptions.py      # Subscription snapshot schemas
│   │   │   ├── predictions.py        # Prediction schemas
│   │   │   ├── ingestion.py          # Ingestion job schemas
│   │   │   └── system.py             # Health and system status schemas
│   │   ├── services/
│   │   │   ├── ipo_service.py        # Business logic for query & aggregation
│   │   │   ├── lifecycle_service.py  # State transition validation logic
│   │   │   ├── health_service.py     # Live dependency verification
│   │   │   └── seed_service.py       # Controlled demo seed data generator
│   │   ├── pipeline/                 # Future Autonomous Ingestion Subsystem
│   │   │   ├── interfaces.py         # Ingestion abstract protocols
│   │   │   ├── discovery.py          # Circulars & Exchange notice scanner
│   │   │   ├── document_fetcher.py   # Rate-limited document retriever
│   │   │   ├── extraction.py         # OCR / PDF / XBRL extractor interface
│   │   │   ├── validation.py         # Provenance verification & hash validator
│   │   │   └── outcome_verifier.py   # Post-listing Bhavcopy reconciler
│   │   ├── ml/                       # Future Machine Learning Subsystem
│   │   │   ├── dataset.py            # Point-in-time training set generator
│   │   │   ├── features.py           # Feature engineering pipeline
│   │   │   ├── models.py             # Baseline & ensemble estimators
│   │   │   ├── validation.py         # Walk-forward chronological backtesting
│   │   │   └── leakage_protection.py # Strict timestamp temporal cutoff checks
│   │   └── main.py                   # FastAPI application factory & middleware
│   ├── tests/                        # Comprehensive pytest suite
│   │   ├── conftest.py               # Fixtures, test DB session, client
│   │   ├── test_health.py            # Health and status tests
│   │   ├── test_ipos.py              # IPO query, filter, sort & detail tests
│   │   ├── test_lifecycle.py         # State machine transition rules tests
│   │   └── test_seed.py              # Dev seed isolation & integrity tests
│   ├── alembic.ini                   # Alembic configuration
│   ├── requirements.txt              # Production Python dependencies
│   ├── requirements-dev.txt          # Development & test tools (pytest, ruff)
│   └── pytest.ini                    # Pytest configuration
├── frontend/                         # Next.js 15 client
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx            # Global dark theme layout & font
│   │   │   ├── page.tsx              # Executive Dashboard
│   │   │   ├── radar/
│   │   │   │   └── page.tsx          # IPO Radar (Search, Filter, Sort)
│   │   │   ├── ipo/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx      # Comprehensive IPO Detail Page
│   │   │   ├── methodology/
│   │   │   │   └── page.tsx          # Research Principles & Disclosure
│   │   │   └── health/
│   │   │       └── page.tsx          # System Health & Ingestion Status
│   │   ├── components/               # Accessible, modular UI components
│   │   │   ├── Navbar.tsx
│   │   │   ├── DemoBadge.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   └── ...
│   │   └── lib/
│   │       ├── api.ts                # Typed client fetching utility
│   │       └── types.ts              # Mirror TypeScript interfaces
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── postcss.config.mjs
├── docker-compose.yml                # Local PostgreSQL service
├── .env.example                      # Documented configuration defaults
├── PROJECT_SPEC.md                   # Product specification & lifecycle
├── ARCHITECTURE.md                   # This document
├── DATA_DICTIONARY.md                # Exhaustive schema definitions
├── DECISIONS.md                      # Architecture Decision Records (ADR)
└── README.md                         # Quickstart & operational manual
```

---

## 3. Database Layer Design

The system relies on 10 relational entities linked through strict foreign keys, cascade protections, and indexes. 

- **Primary Keys**: UUID v4 strings (stored as CHAR(36) or native UUID) for deterministic, collision-free distributed references.
- **Timestamps**: All timestamps are timezone-aware UTC (`TIMESTAMP WITH TIME ZONE` in Postgres, standard ISO8601 strings in SQLite).
- **Audit Trails**: Created at and updated at timestamps are populated on all core tables.
- **Null Safety**: Unknown or unavailable data fields are stored as `NULL` and rendered honestly without placeholder distortion.

---

## 4. Future Ingestion Pipeline Architecture

The future ingestion subsystem (in `app/pipeline/`) establishes concrete contracts for asynchronous batch jobs:
1. **Discovery Stage**: Checks permitted public portals (SEBI filings search, NSE/BSE public announcement feeds) without bypassing robots.txt or terms of service.
2. **Document Fetcher**: Downloads PDFs with SHA-256 fingerprinting to guarantee data provenance.
3. **Structured Extractor**: Translates financial tables into structured JSON schemas.
4. **Provenance Validator**: Confirms document integrity before saving.
5. **Outcome Verifier**: Post-listing reconciliation engine that ingests official exchange bhavcopy files on Day 1 to record true opening and closing prices.

---

## 5. Future Machine Learning Pipeline Architecture

The machine learning framework (in `app/ml/`) enforces strict temporal guarantees:
1. **Point-in-Time Dataset Generation**: Ensures feature vectors only see observations stamped prior to the prediction horizon time $T_{cutoff}$.
2. **Leakage Protection Protocol**: Programmatic asserts ensure that post-listing metrics ($P_{listing}$, $Return_{day1}$, subscription allotment ratios) never leak into pre-bid or pre-listing inference.
3. **Calibration & Ranking**: Evaluates models using Brier Score and Expected Calibration Error (ECE) rather than raw accuracy.
4. **Model Registry**: Models are never transient; every inference is tagged with an immutable `model_version` UUID.
