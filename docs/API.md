# API Reference

## AI Cyber Scam Detector — Enterprise Edition v2.0.0

Interactive API documentation (Swagger UI) is available at `/docs` when the application runs in non-production environments (`APP_ENV != production`). The OpenAPI schema is served at `/openapi.json`.

**Base URL**: `https://<host>/api` (production) or `http://localhost:8000` (dev)

---

## Authentication

All protected endpoints require a Bearer access token:

```http
Authorization: Bearer <access_token>
```

Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 1440 min / 24h). Refresh tokens are valid for `REFRESH_TOKEN_EXPIRE_DAYS` (default 30d) and are single-use (rotation enforced).

### POST /auth/signup

Register a new user.

**Request**
```json
{
  "email": "user@example.com",
  "password": "Str0ng!Passw0rd"
}
```

**Response 201**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### POST /auth/login

Authenticate with OAuth2 password form (`application/x-www-form-urlencoded`).

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | User email |
| `password` | string | User password |

**Response 200**: Same token shape as signup.

### POST /auth/refresh

Rotate a refresh token into a new token pair.

**Request**
```json
{ "refresh_token": "<refresh_jwt>" }
```

**Response 200**: New `access_token`, `refresh_token`, `token_type`, `expires_in`.

### POST /auth/logout
*Requires auth.* Revokes all tokens for the current user.

### POST /auth/forgot-password

Request password reset for an email address. Always returns a generic message.

**Request**
```json
{ "email": "user@example.com", "password": "UnusedButValid!" }
```

**Response 200**
```json
{ "message": "If that email exists, a reset link has been sent." }
```

### GET /auth/me
*Requires auth.* Returns current user profile:
```json
{
  "id": 1,
  "email": "user@example.com",
  "is_admin": false,
  "created_at": "2024-01-15T12:00:00+00:00"
}
```

---

## Scam Detection

### POST /predict

Analyze text for scam content. Returns a prediction label, confidence score, and a detailed explanation.

**Request**
```json
{
  "text": "Urgent: verify your bank account now or it will be suspended",
  "source": "sms"
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `text` | string | 1–10,000 chars, non-empty |
| `source` | string (optional) | max 50 chars, default `generic` |

**Response 200**
```json
{
  "label": "scam",
  "confidence": 0.85,
  "explanation": {
    "keywords": ["urgent", "verify", "bank", "account"],
    "reason": "The message contains high-risk urgency and impersonation patterns commonly used in scams.",
    "risk_level": "High",
    "safety_advice": "Do not click links, share credentials, or respond to the sender.",
    "simple_explanation": "This looks like a scam because it pressures you to act fast and may try to steal your password or money.",
    "source": "sms",
    "confidence": 0.85
  }
}
```

`label` ∈ `safe | suspicious | scam`. Responses are cached in Redis for `CACHE_PREDICTION_TTL` (default 600s) keyed by normalized text.

### GET /dashboard

Public dashboard statistics (aggregate of the 20 most recent scans).

**Response 200**
```json
{
  "total_scans": 20,
  "scam_percentage": 45.0,
  "safe_percentage": 55.0,
  "recent_scans": [
    {
      "id": 1,
      "input_text": "Urgent: verify your bank account...",
      "result": "scam",
      "confidence": 0.85,
      "created_at": "2024-01-15T12:00:00+00:00"
    }
  ]
}
```

### GET /history
*Requires auth.* Returns the authenticated user's 50 most recent scans.

### GET /reports/{scan_id}
*Requires auth, ownership.* Returns a detailed report for the user's own scan.

### POST /feedback
*Requires auth.* Submit user feedback.

**Request**
```json
{ "message": "The explanation was very helpful." }
```

---

## Admin Endpoints
*Requires admin role.*

### GET /admin/users

List all users:
```json
[
  { "id": 1, "email": "user@example.com", "is_admin": false }
]
```

### GET /admin/audit-log?days=7

Security summary of audit events for the last N days:
```json
{
  "total_events": 100,
  "by_severity": { "info": 90, "warning": 10 },
  "by_action": { "auth.login": 50 },
  "failed_actions": [],
  "unique_actor_count": 5
}
```

---

## System Endpoints

### GET /health

Basic health + model status:
```json
{
  "status": "ok",
  "model_status": "loaded",
  "timestamp": "2024-01-15T12:00:00+00:00"
}
```

### GET /health/live

Liveness probe — returns 200 with `{"status": "alive"}` when the process is running.

### GET /health/ready

Readiness probe — verifies database and cache connectivity. Returns 200 `{"status": "ready"}` or 503 `{"status": "not_ready"}`.

### GET /health/db

Database-specific health check.

### GET /metrics

Prometheus metrics endpoint (text/plain exposition format).

### GET /system/resilience
*Requires admin.* Status of circuit breakers, bulkheads, and idempotency store.

### GET /system/config
*Requires admin.* Non-secret system configuration.

---

## Error Responses

All errors use RFC 7807-style JSON:

```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning |
|--------|---------|
| 400 | Validation/sanitization failure |
| 401 | Missing/invalid credentials |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 429 | Rate limit exceeded (includes `Retry-After`) |
| 500 | Internal server error |

---

## Rate Limiting

Per-IP limits are enforced by the gateway and middleware:
- Default: `RATE_LIMIT_MAX` (100) requests per `RATE_LIMIT_WINDOW` (60s).
- Excluded paths: `/health`, `/metrics`.
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.

---

## Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Client-generated or server-issued request ID (echoed back) |
| `X-Correlation-ID` | Correlation ID for tracing across services |
| `X-Response-Time` | Request duration in ms |

---

## Example Usage

### curl

```bash
# Health check
curl -s http://localhost:8000/health

# Prediction
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"text":"Urgent verify your bank account now","source":"sms"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=user@example.com&password=Str0ng!Passw0rd'

# Authenticated request
curl http://localhost:8000/history \
  -H 'Authorization: Bearer <access_token>'
```

### Python (httpx)

```python
import httpx

client = httpx.Client(base_url="http://localhost:8000")
resp = client.post("/predict", json={"text": "urgent verify your bank", "source": "sms"})
print(resp.json())
