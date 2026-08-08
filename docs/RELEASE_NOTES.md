# Release Notes — v2.0.0

## AI Cyber Scam Detector — Enterprise Edition

**Release Date**: See git tag `v2.0.0`
**Status**: Production-ready

---

## Overview

This release marks the enterprise production stabilization of the AI Cyber Scam Detector platform. It delivers a hardened, cloud-ready, fully validated system suitable for Fortune 500 deployments.

---

## New in v2.0.0

### Enterprise Security
- JWT access + refresh tokens with rotation and revocation
- RBAC with 5-role hierarchy (viewer → superadmin)
- Comprehensive middleware stack (CORS, security headers, rate limiting, audit, input sanitization)
- Immutable audit trail with daily rotation
- Secret validation on startup (blocks insecure defaults in production)
- Strict input validation and sanitization (SQL injection, XSS, SSRF guards)

### Reliability & Resilience
- Circuit breaker (3 states), retry with exponential backoff + jitter, bulkhead isolation
- Fallback handlers and idempotency key store
- Graceful shutdown with in-flight request draining
- Model loading retry with heuristic fallback

### Observability
- Prometheus metrics (HTTP, prediction, auth, DB, cache, system)
- Grafana dashboard provisioning
- Structured JSON logging
- OpenTelemetry tracing (optional)
- Health, readiness, liveness, and DB probes
- Loki log aggregation

### Performance
- Database connection pooling with `pool_pre_ping` and recycling
- Redis cache-aside with in-memory fallback
- Gzip/Brotli compression at the Nginx gateway
- Async inference isolated behind bulkhead
- Optimized multi-stage Docker images

### Machine Learning Pipeline (`enterprise_pipeline/`)
- Dataset engine with validation, deduplication, class balancing
- Feature engineering
- AutoML training
- Model evaluation and registry
- Experiment tracking
- Continuous training orchestration

### Advanced Modules
- **Threat Intelligence Center** — provider-based threat intel enrichment
- **AI Explainability Center** — SHAP/LIME-style explanations
- **Fraud Investigation Dashboard** — investigation workflows

### Deployment & Cloud
- Helm chart, Kubernetes manifests (HPA, PDB, VPA, network policies, Kyverno)
- Terraform (AWS ECS, Azure Container Apps, GCP Cloud Run, K8s)
- Docker Compose (dev, prod, monitoring)
- AWS ECS, Azure, GCP, Render, Railway configurations

### CI/CD
- GitHub Actions CI (lint, security, tests, Docker build)
- CD pipeline (SBOM, cosign, multi-arch images, Helm deploy)
- Weekly container & dependency scanning

---

## Validation Highlights

- **515 tests passing**, 1 environment-dependent skip
- Unit, integration, e2e, security, concurrency, chaos, load, and enterprise lifecycle suites green
- Zero lint, format, import, or type errors
- Zero deprecated API usages, invalid escape sequences, or TODO/FIXME placeholders
- All deployment YAML validated
- App starts with zero syntax warnings

---

## Breaking Changes

- `POST /auth/login` now uses OAuth2 password form (`username`/`password`), consistent with OAuth2PasswordRequestForm.
- Token responses now include `refresh_token` and `expires_in` fields.
- `backend/app/db.py` and `backend/app/security.py` are now re-exports of `backend/app/core/*`; imports remain backward-compatible.

---

## Upgrade Notes

1. Set `APP_ENV=production` and provide strong `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL` in production.
2. Run database migrations (`alembic upgrade head`).
3. Mount the trained model artifact at `MODEL_PATH`.
4. Review `CORS_ORIGINS` for your production domains.

---

## Known Limitations

- In-memory token blacklist/rate-limit stores are suitable for single-instance or shared-cache deployments; production is recommended to back these with Redis for multi-replica consistency.
- The heuristic fallback model is used when the ML artifact is absent; it is a safety net, not a substitute for a trained model.

---

## Documentation

- [Architecture](architecture.md)
- [API](API.md)
- [Deployment](DEPLOYMENT.md)
- [Security](SECURITY.md)
- [Operations](OPS.md)
- [Developer](DEVELOPER.md)
- [Performance Report](PERFORMANCE_REPORT.md)
- [Validation Report](VALIDATION_REPORT.md)
- [Runbook](RUNBOOK.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Disaster Recovery](DISASTER_RECOVERY.md)
