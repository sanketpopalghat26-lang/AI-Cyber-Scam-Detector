# Production Certification Re-Audit — Task Tracker

## Approved Plan

- [x] **Phase 1 — Repository Discovery** (architecture map, evidence gathering)
- [x] **Plan approved** by user

## Fixes (in approved order)

- [ ] **A** — Fix backend Dockerfile: `COPY core/ ./core/` → remove broken line (core lives at `app/core/`)
- [ ] **B** — Make `models/exports/best_model.pkl` the authoritative model artifact; fix model path resolution
- [ ] **C** — Initialize test database in `tests/conftest.py` (call `init_db()`)
- [ ] **D** — Re-run complete backend test suite (non-`-x`)
- [ ] **E** — Validate Docker build, Docker Compose, deployment manifests
- [ ] **F** — Run quality gates: ruff, black, isort, mypy, bandit
- [ ] **G** — Generate certification reports

## Regression Tests

- [ ] Add test for Dockerfile correctness (referenced paths exist)
- [ ] Add test for model path resolution to real artifact
- [ ] Add test for conftest DB initialization

## Reports

- [ ] `ENTERPRISE_CERTIFICATION_GAP_ANALYSIS.md`
- [ ] `FINAL_PRODUCTION_CERTIFICATION_REPORT.md`
