# Enterprise Architecture

## System Overview

The AI Cyber Scam Detector follows **Clean Architecture** principles with strict separation of concerns, dependency injection, and enterprise-grade patterns throughout.

## Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│                      Presentation Layer                       │
│  React Frontend  │  Browser Extension  │  REST API Clients   │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    API Gateway (Nginx)                        │
│  HTTPS │ Rate Limiting │ Security Headers │ Gzip/Brotli     │
│  Caching │ WebSocket Proxy │ Request Routing                  │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Application Layer (FastAPI)                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                 Enterprise Middleware Stack           │    │
│  │  CORS │ Security Headers │ Rate Limit │ Audit        │    │
│  │  Request ID │ Structured Logging │ Metrics           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │
│  │ Auth Module │  │ Prediction  │  │ Admin Dashboard   │   │
│  │ JWT/RBAC    │  │ Engine      │  │ Analytics/Reports │   │
│  └─────────────┘  └─────────────┘  └───────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Resilience & Reliability                 │    │
│  │  Circuit Breaker │ Retry Policy │ Bulkhead Isolation│    │
│  │  Fallback Handler │ Idempotency │ Graceful Shutdown  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                     Data Layer                                │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │
│  │ PostgreSQL  │  │   Redis     │  │  ML Model (joblib)│   │
│  │ Primary DB  │  │ Cache/Queue │  │  Inference Engine │   │
│  └─────────────┘  └─────────────┘  └───────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Enterprise Middleware Stack (Order Matters)

| Order | Middleware | Purpose |
|-------|-----------|---------|
| 1 | CORS Middleware | Cross-origin resource sharing |
| 2 | Security Headers | CSP, HSTS, XSS, clickjacking |
| 3 | Request ID | Unique tracing ID per request |
| 4 | Rate Limiting | Per-IP request throttling |
| 5 | Request Timing | Duration tracking, slow request detection |
| 6 | Input Sanitization | Injection attack prevention |
| 7 | Audit Middleware | Security event logging |
| 8 | Structured Logging | JSON log format |
| 9 | Prometheus Metrics | HTTP, business, and system metrics |

### 2. Security Architecture

```
Authentication Flow:
┌─────────┐     ┌──────────┐     ┌───────────┐
│ Client  │────▶│ /login   │────▶│ Issue JWT │
│         │     │          │     │ Pair      │
│         │◀────│ Tokens   │◀────│ Access +  │
│         │     │          │     │ Refresh   │
└─────────┘     └──────────┘     └───────────┘

Token Refresh Flow:
┌─────────┐     ┌──────────┐     ┌───────────┐
│ Client  │────▶│ /refresh │────▶│ Rotate    │
│         │     │          │     │ Token     │
│         │◀────│ New Pair │◀────│ Pair      │
└─────────┘     └──────────┘     └───────────┘
```

### 3. Observability Stack

```
Application Metrics → Prometheus → Grafana Dashboards
Application Logs    → Loki       → Grafana Explore
Application Traces  → OpenTelemetry → Jaeger
System Metrics      → Node Exporter → Prometheus
Container Metrics   → cAdvisor → Prometheus
```

## Data Flow

### Prediction Flow

1. **Input**: User submits text via API, UI, or browser extension
2. **Validation**: Input sanitization, length checks, rate limiting
3. **Cache Check**: Redis cache lookup for repeated predictions
4. **Inference**: ML model prediction with circuit breaker protection
5. **Explanation**: AI explanation generation (keywords, risk, advice)
6. **Persistence**: Optional storage for authenticated users
7. **Audit**: Security audit log entry
8. **Response**: Prediction with explanation

### Authentication Flow

1. **Signup**: Email validation → Password strength check → User creation → Token pair issuance
2. **Login**: Credential verification → Token pair issuance → Audit log
3. **Token Refresh**: Refresh token validation → Old token revocation → New token pair issuance
4. **Logout**: All user tokens revoked → Session terminated

## Resilience Patterns

### Circuit Breaker States
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: After N failures, requests are rejected immediately
- **HALF_OPEN**: After timeout, allow test request to check recovery

### Retry Policy
- Exponential backoff with jitter
- Configurable max retries (default: 3)
- Configurable timeout per attempt

### Bulkhead Isolation
- Separate thread pools for different services
- Limits concurrent calls to prevent resource exhaustion
- Queuing mechanism for excess requests

## Database Schema

See [ER Diagram](ER.md) for complete database schema.

## Security Architecture

See [Security Guide](SECURITY.md) for complete security architecture.

