<<<<<<< HEAD
# IPO Intelligence — Phase 1 Foundation & Architecture

> **Institutional-grade Indian Capital Markets Financial Intelligence & Predictive Platform**  
> Covering NSE & BSE Mainboard and SME IPOs with strict regulatory provenance, anti-leakage temporal barriers, and append-only model versioning.

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js 15 Client (App Router)           │
│  - Dark Institutional UI                                    │
│  - Dashboard, IPO Radar, Dossier Deep Dive                  │
│  - Methodology, System Health & Diagnostics                 │
└──────────────────────────────┬──────────────────────────────┘
                               │ JSON / HTTP (REST API v1)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend Service                  │
│  ├── API Routers (/api/v1/ipos, /health, /ingestion, etc.)  │
│  ├── Pydantic V2 Schemas & ORM Serialization                │
│  ├── Lifecycle Transition State Machine                     │
│  ├── Future Ingestion Pipeline Interfaces & Contracts       │
│  └── Machine Learning Anti-Leakage & Feature Pipeline       │
└──────────────────────────────┬──────────────────────────────┘
                               │ SQLAlchemy 2.0
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Relational Storage Engine                 │
│  ├── PostgreSQL 16 (Production Target via Docker Compose)   │
│  ├── SQLite (Out-of-the-Box Local Development & Fast Tests) │
│  └── Alembic Controlled Migrations                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites & Tooling

- **Python**: 3.11+ (tested on Python 3.13)
- **Node.js**: v20+ (tested on Node v24)
- **npm**: 10+
- **Docker & Docker Compose** (Optional for PostgreSQL local container)

---

## 3. Quick Start: Installation & Execution

### Step 3.1: Environment Configuration
Copy the sample environment file to `.env`:

```bash
# On Windows PowerShell
cp .env.example .env
```

Default `.env` configuration uses zero-barrier local SQLite storage:
```env
ENVIRONMENT=development
DATABASE_URL=sqlite:///./ipo_intelligence.db
ENABLE_DEV_SEED=true
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

*(To use PostgreSQL via Docker, simply set `DATABASE_URL=postgresql+psycopg://ipo_user:ipo_password@localhost:5432/ipo_intelligence`)*

---

### Step 3.2: Optional — Start PostgreSQL via Docker Compose

```bash
# Start PostgreSQL in background
docker compose up -d

# Verify container health
docker compose ps
```

---

### Step 3.3: Backend Setup & Database Migrations

1. Navigate to the `backend/` directory:
```bash
cd backend
```

2. Create and activate a Python virtual environment:
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

3. Install development and production dependencies:
```bash
pip install -r requirements-dev.txt
```

4. Apply Alembic database migrations:
```bash
alembic upgrade head
```

5. Seed the verified demonstration dataset (strictly flagged with `is_demo=True`):
```bash
python -c "from app.core.database import SessionLocal; from app.services.seed_service import seed_demo_dataset; db = SessionLocal(); print(seed_demo_dataset(db, force=True)); db.close()"
```

6. Launch the FastAPI backend server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend is now live at:
- API Root: `http://localhost:8000`
- Interactive OpenAPI Swagger Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/v1/health`
- IPOs List: `http://localhost:8000/api/v1/ipos`

---

### Step 3.4: Frontend Setup & Launch

1. In a new terminal, navigate to `frontend/`:
```bash
cd frontend
```

2. Install npm dependencies:
```bash
npm install
```

3. Start the Next.js development server:
```bash
npm run dev
```

The frontend application is now accessible at `http://localhost:3000`.

---

## 4. Running Automated Tests

### 4.1 Backend Pytest Suite
Run the 12 automated unit and integration tests (executes in < 0.5s with zero external dependencies):

```bash
cd backend
.\.venv\Scripts\python -m pytest
```

Test coverage includes:
- System health and live database connection probing (`test_health.py`)
- IPO querying, searching, filtering, and 404 validation (`test_ipos.py`)
- Statutory lifecycle state machine transition legalities (`test_lifecycle.py`)
- Safe dev-only demo seeding and production environment guards (`test_seed.py`)
- Machine learning temporal anti-leakage barriers and SHA-256 provenance checks (`test_leakage.py`)

### 4.2 Frontend Build & Typecheck
Verify TypeScript types and build the production bundle:

```bash
cd frontend
npm run build
```

---

## 5. API Reference (`/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Live database ping and service connectivity check |
| `GET` | `/api/v1/system/status` | Ingestion status, demo counts, and source integrations |
| `GET` | `/api/v1/ipos` | Searchable, sortable, filterable paginated list of IPOs |
| `GET` | `/api/v1/ipos/{id}` | Complete IPO dossier (events, documents, financials, predictions) |
| `GET` | `/api/v1/ipos/{id}/events` | Chronological regulatory milestones for an issue |
| `GET` | `/api/v1/ipos/{id}/documents`| Versioned documents with SHA-256 cryptographic hashes |
| `GET` | `/api/v1/ipos/{id}/predictions`| Append-only model assessment history |
| `GET` | `/api/v1/ingestion/jobs` | Historical audit log of ingestion, discovery, and sync jobs |
| `POST`| `/api/v1/seed/demo` | Dev-only seed trigger (strictly gated by `ENABLE_DEV_SEED=true`) |

---

## 6. Project Documentation & ADRs

- [PROJECT_SPEC.md](file:///e:/Studies/Wed%20Development%20Course/WEB%20DEV%20Projects/IPO/PROJECT_SPEC.md) — Domain specifications, principles, and regulatory state machine.
- [ARCHITECTURE.md](file:///e:/Studies/Wed%20Development%20Course/WEB%20DEV%20Projects/IPO/ARCHITECTURE.md) — System boundaries, module layouts, and data pipelines.
- [DATA_DICTIONARY.md](file:///e:/Studies/Wed%20Development%20Course/WEB%20DEV%20Projects/IPO/DATA_DICTIONARY.md) — Schema definitions for all 10 core entities.
- [DECISIONS.md](file:///e:/Studies/Wed%20Development%20Course/WEB%20DEV%20Projects/IPO/DECISIONS.md) — Architecture Decision Records (ADRs).
=======
# IPO_Intelligence
AI-powered Indian IPO analysis platform for automated IPO discovery, prospectus analysis, financial data extraction, listing performance verification, risk assessment, and historical return prediction using machine learning and leakage-resistant backtesting.
>>>>>>> bcee06e124d398bc86aa966fae348b0564ea1744
