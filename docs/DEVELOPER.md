# Developer Guide

## AI Cyber Scam Detector — Enterprise Edition v2.0.0

This guide covers the local development workflow, repository structure, coding standards, and contribution process for the enterprise platform.

---

## 1. Repository Structure

```
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── main.py          # Application factory & route definitions
│   │   ├── models.py        # SQLModel ORM entities
│   │   ├── schemas.py       # Pydantic request/response validation
│   │   ├── core/            # Enterprise core modules
│   │   │   ├── config.py    # Centralized configuration
│   │   │   ├── security.py  # JWT, RBAC, password hashing
│   │   │   ├── middleware.py# Enterprise middleware stack
│   │   │   ├── resilience.py# Circuit breaker, retry, bulkhead
│   │   │   ├── cache.py     # Redis + in-memory cache-aside
│   │   │   ├── observability.py # Prometheus, tracing, health
│   │   │   ├── audit.py     # Immutable audit trail
│   │   │   ├── lifecycle.py # Graceful startup/shutdown
│   │   │   ├── secrets.py   # Secret validation
│   │   │   └── db.py        # Connection pooling & sessions
│   │   ├── investigation/   # Fraud investigation module
│   │   ├── threat_intelligence/ # Threat intel providers
│   │   └── explainability/  # AI explainability module
│   ├── alembic/             # Database migrations
│   └── requirements.txt     # Pinned production dependencies
├── enterprise_pipeline/     # ML training pipeline
│   ├── dataset_engine/      # Dataset loading, validation, balancing
│   ├── feature_engineering/ # Feature extraction
│   ├── automl/              # Auto-trainer
│   ├── evaluation/          # Model evaluation
│   ├── experiment_tracking/ # MLflow/file-based tracking
│   ├── model_registry/      # Model versioning
│   ├── continuous_training/ # Retraining orchestration
│   └── application/         # Training service entry point
├── frontend/                # React (Vite) + Tailwind UI
├── extension/               # Browser extension (Chrome/Edge)
├── deploy/                  # k8s, helm, terraform, ecs, azure, gcp
├── monitoring/              # Prometheus, Grafana, Loki/Promtail
├── tests/                   # Unit, integration, e2e, security, perf
└── scripts/                 # Validation & release tooling
```

---

## 2. Local Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (optional, for services)
- PostgreSQL 15 (optional; SQLite is the dev default)

### Backend

```bash
# Create and activate a virtual environment
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
pip install -r tests/requirements-dev.txt 2>/dev/null || \
  pip install pytest pytest-cov pytest-asyncio httpx ruff mypy black isort bandit

# Run the development server
uvicorn backend.app.main:app --reload --port 8000
```

### Environment Variables

Copy the reference values from `backend/app/core/config.py`. Critical development defaults:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./dev.db` | Database connection |
| `SECRET_KEY` | dev-only | JWT signing key |
| `MODEL_PATH` | `/app/model/best_model.joblib` | ML model artifact |
| `REDIS_URL` | empty | Redis for caching (optional in dev) |
| `APP_ENV` | `development` | Runtime environment |

### Frontend

```bash
cd frontend
npm install
npm run dev   # Vite dev server on :5173
```

---

## 3. Coding Standards

The project enforces the following via `pyproject.toml` and CI:

- **Ruff** — linting (E, W, F, I, N, UP, S, B, A, C4, DTZ, T10, SIM, TID)
- **Black** — formatting (line length 100)
- **isort** — import ordering (black profile)
- **mypy** — static type checking
- **Bandit** — security scanning

### Conventions

1. **Type hints** are mandatory on all public functions.
2. **Docstrings** are required for all modules and public classes.
3. **Naming**: `snake_case` for functions/variables, `PascalCase` for classes.
4. **Imports**: stdlib → third-party → local, each group alphabetized.
5. **No `TODO`/`FIXME`/`XXX`/`HACK`** placeholders are permitted in source.
6. **No deprecated APIs**: `datetime.utcnow()` → `datetime.now(UTC)`; pandas `select_dtypes(include=["object"])` → `include=["object", "string"]`.
7. **Raw strings** (`r"..."`) for all regex patterns to avoid escape-sequence warnings.

### Running Quality Gates Locally

```bash
# Lint
ruff check backend/ enterprise_pipeline/ scripts/
# Format check
black --check backend/ enterprise_pipeline/ scripts/
# Import order
isort --check-only --diff backend/ enterprise_pipeline/ scripts/
# Type check
mypy backend/ enterprise_pipeline/
# Security
bandit -r backend/ enterprise_pipeline/
# Release quality gates
python scripts/release_checks.py
# YAML validation
python scripts/validate_yaml.py
```

---

## 4. Testing

The suite is organized by concern:

| Directory | Focus | Markers |
|-----------|-------|---------|
| `tests/unit/` | Pure unit tests (API, cache, DB, resilience, security, secrets, token store, dataset engine) | `unit` |
| `tests/integration/` | API & database integration | `integration` |
| `tests/e2e/` | End-to-end flows | `e2e` |
| `tests/security/` | Security & middleware verification | `security` |
| `tests/concurrency/` | Async/concurrency correctness | `integration` |
| `tests/chaos/` | Resilience & chaos engineering | `integration` |
| `tests/performance/` | Load testing | `slow` |
| `tests/enterprise/` | Lifecycle/enterprise behaviors | `integration` |
| `tests/threat_intelligence/` | Threat intel module | `unit` |
| `tests/explainability/` | Explainability module | `unit` |
| `tests/investigation/` | Investigation module | `unit` |

Run commands:

```bash
# Full suite
python -m pytest tests/ -q

# Fast subset (unit only)
python -m pytest tests/unit -q

# With coverage
python -m pytest tests/ -q --cov=backend --cov=enterprise_pipeline --cov-report=term-missing

# Security tests only
python -m pytest tests/security -q

# Load/performance tests (slow)
python -m pytest tests/performance -q -m slow
```

---

## 5. Adding a New Endpoint

1. Add request/response schemas in `backend/app/schemas.py`.
2. Add the route in `backend/app/main.py` (or a feature router).
3. Register enterprise middleware requirements (rate limit, auth, audit).
4. Add tests under `tests/unit/` and `tests/integration/`.
5. Run `python scripts/release_checks.py` and the full test suite.
6. Update `docs/API.md` with the new endpoint.

---

## 6. Database Migrations

The project uses Alembic. Migrations live in `backend/alembic/versions/`.

```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Validate migrations with `python scripts/validate_migrations.py`.

---

## 7. Contribution Flow

1. Create a feature branch from `main`.
2. Implement changes following the coding standards.
3. Add tests covering new behavior.
4. Run all quality gates (lint, format, type, security, release checks).
5. Open a PR against `main`. CI runs lint, security, tests, and Docker builds.
6. Merge after all checks pass and at least one review approval.

---

## 8. Troubleshooting Development

| Issue | Resolution |
|-------|-----------|
| `MODEL_PATH` not found | Copy/point to a trained model, or allow heuristic fallback in dev |
| Redis unavailable | The cache gracefully falls back to in-memory |
| `Python was not found` on Windows | Activate the venv: `.\.venv\Scripts\activate` then use `python` |
| OpenTelemetry import error | Optional; install `opentelemetry-*` packages if tracing is needed |
| Port 8000 in use | Change with `--port`, or set `PORT` env var |
