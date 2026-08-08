# Enterprise Transformation TODO — Phase 6/8 + Guardrails

## Phase 6: Enterprise Notification Center
- [ ] Create `backend/app/notifications/config.py`
- [ ] Create `backend/app/notifications/models.py` (Notification, NotificationPreference, NotificationChannel)
- [ ] Create `backend/app/notifications/schemas.py`
- [ ] Create `backend/app/notifications/service.py` (in-app, email, websocket, retry queue, history)
- [ ] Create `backend/app/notifications/router.py` (`/api/notifications`)
- [ ] Create `backend/app/notifications/__init__.py`
- [ ] Create Alembic migration `0004_notifications.py`
- [ ] Tests: `tests/notifications/` (models, service, api)

## Phase 8: Executive Dashboard
- [ ] Create `backend/app/executive/config.py`
- [ ] Create `backend/app/executive/service.py` (threat analytics, trends, AI metrics, guardrail metrics, system health, security events)
- [ ] Create `backend/app/executive/schemas.py`
- [ ] Create `backend/app/executive/router.py` (`/api/executive`)
- [ ] Create `backend/app/executive/__init__.py`
- [ ] Tests: `tests/executive/` (service, api)

## AI Guardrails Integration (Centralized)
- [ ] Create `backend/app/core/ai_guardrail_service.py` (inject/jailbreak/PII/toxicity/sanitize/confidence/risk/audit + Prometheus)
- [ ] Add guardrail Prometheus metrics to `observability.py`
- [ ] Create `backend/app/core/guardrail_middleware.py` (centralized pipeline middleware)
- [ ] Register guardrail middleware + routers in `main.py`
- [ ] Update `alembic/env.py` to import new models

## Testing & Validation
- [ ] Unit / integration / API / security / regression tests
- [ ] Run Ruff, Black, isort, Bandit, Pytest, Coverage
- [ ] Verify all tests pass, target >= 90% coverage

## Documentation
- [ ] ENTERPRISE_GAP_ANALYSIS.md
- [ ] AI_GUARDRAILS.md
- [ ] EXECUTIVE_DASHBOARD.md
- [ ] NOTIFICATION_CENTER.md
- [ ] SECURITY_AUDIT.md
- [ ] PERFORMANCE_REPORT.md
- [ ] RELEASE_READINESS.md
- [ ] CHANGELOG.md
