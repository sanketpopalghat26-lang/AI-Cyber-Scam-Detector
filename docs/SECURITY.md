# Enterprise Security Guide

## Security Architecture

### Defense in Depth

The platform implements multiple layers of security:

```
Layer 1: Network Security
  - HTTPS/TLS 1.2+
  - DDoS protection
  - Firewall rules

Layer 2: Reverse Proxy (Nginx)
  - Rate limiting
  - Security headers
  - Request size limits

Layer 3: Application Security
  - JWT authentication
  - RBAC authorization
  - Input sanitization
  - CSRF protection

Layer 4: Data Security
  - Database encryption
  - Secrets management
  - Audit logging

Layer 5: Infrastructure Security
  - Read-only filesystem
  - Non-root user
  - No new privileges
  - Container scanning
```

## Authentication & Authorization

### JWT Token Management

```python
# Token structure
{
    "sub": "user@example.com",    # Subject (user email)
    "exp": 1700000000,            # Expiration timestamp
    "iat": 1699913600,            # Issued at timestamp
    "jti": "uuid-v4",             # Unique token ID
    "type": "access",             # Token type (access/refresh)
    "role": "admin",              # User role
    "scopes": ["predict", "view_history"]  # Permissions
}
```

### Token Lifetimes
- Access Token: 24 hours (configurable)
- Refresh Token: 30 days (configurable)
- Token rotation on every refresh
- Immediate revocation on logout

### RBAC Roles

| Role | Permissions |
|------|-------------|
| **viewer** | Read-only access to predictions |
| **user** | Make predictions, view history |
| **analyst** | Generate reports, export data |
| **admin** | Manage users, view audit logs |
| **superadmin** | System configuration, all permissions |

## Password Policy

```python
MIN_LENGTH = 12
REQUIREMENTS:
  ✓ Minimum 12 characters
  ✓ At least 1 uppercase letter
  ✓ At least 1 lowercase letter
  ✓ At least 1 digit
  ✓ At least 1 special character
  ✗ No common patterns (password, 12345, etc.)
  ✗ No repeated characters (3+ times)
```

## API Security

### Rate Limiting

| Endpoint | Rate | Burst |
|----------|------|-------|
| `/predict` | 10 req/s | 20 |
| `/auth/*` | 5 req/s | 10 |
| `/api/*` | 30 req/s | 50 |
| `/health` | No limit | - |

### Security Headers

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; ...
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-site
```

### CORS Configuration

```python
CORS_ORIGINS = [
    "https://app.yourdomain.com",
    "https://admin.yourdomain.com",
]
# Wildcard is PROHIBITED in production
```

## Input Validation & Sanitization

### Prevention Measures

- **SQL Injection**: SQLModel parameterized queries
- **XSS**: HTML encoding, CSP headers
- **Command Injection**: No shell execution, validated inputs
- **Path Traversal**: Path validation, read-only filesystem
- **Null Bytes**: Removed from all inputs
- **Mass Assignment**: Explicit field definitions

### Dangerous Patterns Blocked

```
<script>            # XSS
javascript:         # XSS
onerror=            # XSS
onload=             # XSS
eval(               # Code execution
exec(               # Code execution
system(              # Command injection
import os           # Module injection
subprocess          # Command injection
__import__          # Module injection
```

## Secrets Management

### Validated on Startup

1. **SECRET_KEY**: Minimum 32 chars, not a default value
2. **DATABASE_URL**: Must be set in production
3. **REDIS_PASSWORD**: Warning if not set
4. **Password Strength**: Validated on user creation

### Production Requirements

```bash
# Generate secrets
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
REDIS_PASSWORD=$(openssl rand -hex 16)
```

## Audit Logging

### Logged Events

```json
{
    "timestamp": "2024-01-01T00:00:00Z",
    "action": "auth.login",
    "actor": "user@example.com",
    "resource": "user",
    "result": "success",
    "ip_address": "192.168.1.1",
    "correlation_id": "uuid-v4",
    "details": {"method": "password"}
}
```

### Audit Log Retention
- Storage: JSONL files rotated daily
- Retention: 90 days (configurable)
- Compression: gzip after rotation
- Access: Admin only via API

## Container Security

### Docker Security Measures

```dockerfile
# Non-root user
USER appuser

# Read-only filesystem
read_only: true

# No new privileges
security_opt:
  - no-new-privileges:true

# Drop all capabilities
capabilities:
  drop:
    - ALL

# Resource limits
deploy:
  resources:
    limits:
      cpus: '1'
      memory: 1G
```

## Incident Response

See [Runbook](RUNBOOK.md) for detailed incident response procedures.

## Compliance

### Data Protection
- All data encrypted in transit (TLS 1.2+)
- Audit logs for all security events
- Configurable data retention periods

### Security Scanning
- Daily container vulnerability scanning (Trivy)
- Weekly dependency auditing (pip-audit, safety)
- Secrets detection (GitLeaks)
- Automated security testing in CI/CD

