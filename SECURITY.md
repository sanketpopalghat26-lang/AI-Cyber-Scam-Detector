# Security Policy

## Reporting a Vulnerability

We take the security of **AI Cyber Scam Detector** seriously. If you believe you
have found a security vulnerability, please report it to us as soon as possible.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@example.com**

You should receive a response within 48 hours. If you do not, please follow up.

### When reporting, please include:

- A description of the vulnerability
- The affected component(s) and version(s)
- Steps to reproduce the issue
- Any proof-of-concept or exploit code (if available)
- Your contact information (optional)

## Supported Versions

We follow a continuous delivery model. Only the latest release on the `main`
branch is actively supported with security patches.

## Security Disclosure Policy

We follow coordinated disclosure:

1. Reporter confirms the vulnerability and provides details.
2. Our security team triages and determines severity.
3. A fix is developed and tested.
4. A patch is released and announced.
5. Details are published after users have had time to update.

## Security Best Practices (for Operators)

- **Always** set a strong `SECRET_KEY` via environment variable — never use the default.
- **Never** run the application in `production` with SQLite — use PostgreSQL.
- Set `APP_ENV=production` in all production deployments.
- Use TLS/HTTPS everywhere (see `nginx/nginx.conf` and Helm TLS config).
- Restrict `CORS_ORIGINS` to known, trusted origins.
- Rotate secrets regularly (use HashiCorp Vault, AWS Secrets Manager, or KMS).
- Enable database backups and test restore procedures (see `deploy/k8s/backup-cronjob.yaml`).
- Keep dependencies updated (see `SECURITY.md` and Dependabot config).
- Run the automated security scans in CI (Bandit, pip-audit, Safety, Trivy, gitleaks, CodeQL).

## Security Features Implemented

| Feature | Location |
|---------|----------|
| JWT access + refresh tokens with rotation | `backend/app/core/security.py` |
| RBAC permissions | `backend/app/core/security.py` |
| Password hashing (bcrypt) | `backend/app/core/security.py` |
| Security headers (CSP, HSTS, etc.) | `backend/app/core/middleware.py` |
| CORS hardening | `backend/app/core/middleware.py` |
| Rate limiting (per-IP, per-endpoint) | `nginx/nginx.conf` + middleware |
| Input sanitization | `backend/app/core/middleware.py` |
| Audit logging | `backend/app/core/audit.py` |
| Secret validation on startup | `backend/app/core/secrets.py` |
| Rootless container (non-root user) | `backend/Dockerfile` |
| Read-only root filesystem | `deploy/k8s/backend-deployment.yaml` |
| Network policies | `deploy/k8s/network-policy.yaml` |
| Pod security context | `deploy/k8s/backend-deployment.yaml` |
| SBOM generation + signing | `.github/workflows/cd.yml` |
| Dependency scanning (pip-audit, Safety) | `.github/workflows/security-scan.yml` |
| Container scanning (Trivy) | `.github/workflows/security-scan.yml` |
| Secret scanning (gitleaks) | `.github/workflows/security-scan.yml` |
| Static analysis (CodeQL) | `.github/workflows/codeql.yml` |

## Compliance

The platform is designed to support readiness for:
- OWASP Top 10 / MASVS
- NIST Cybersecurity Framework
- CIS Benchmarks
- SOC 2 / ISO 27001 / GDPR / PCI-DSS

See `docs/SECURITY.md` for the full security architecture.
