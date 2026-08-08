# Incident Response Runbook

## Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| **SEV-1** | Complete service outage | 15 minutes |
| **SEV-2** | Partial degradation | 1 hour |
| **SEV-3** | Minor issues, no impact | 4 hours |
| **SEV-4** | Informational | Next business day |

---

## Incident: Service Down

### Symptoms
- Health check returns 503
- All requests timeout
- Frontend returns 502 Bad Gateway

### Immediate Actions

```bash
# 1. Check all services
docker compose -f docker-compose.prod.yml ps

# 2. Check recent logs
docker compose logs --tail=200 backend

# 3. Check resource usage
docker stats --no-stream

# 4. Restart service if needed
docker compose restart backend

# 5. Scale up if under load
docker compose up -d --scale backend=5
```

### Escalation
If still down after 5 minutes:
1. Notify on-call engineer
2. Check cloud provider status
3. Initiate disaster recovery if needed

---

## Incident: Database Connection Failure

### Symptoms
- `/health/db` returns unhealthy
- Queries timeout
- Application errors: `could not connect to server`

### Immediate Actions

```bash
# 1. Check DB container
docker compose logs db --tail=50

# 2. Check DB connectivity
pg_isready -h localhost -U scam_user

# 3. Restart DB if needed
docker compose restart db

# 4. Check disk space
docker exec -it $(docker compose ps -q db) df -h
```

### Root Causes
- PostgreSQL service crashed
- Disk full
- Connection pool exhausted
- Network issue

---

## Incident: High Error Rate

### Symptoms
- Error rate > 5%
- 500 errors in logs
- Alert from monitoring

### Investigation

```bash
# 1. Check recent errors
docker compose logs backend | grep ERROR | tail -50

# 2. Check model status
curl http://localhost:8000/health

# 3. Check rate limiting
docker compose logs nginx | grep "429"

# 4. Check slow queries
docker compose logs backend | grep "Slow request"
```

### Resolution
- Check ML model file integrity
- Restart backend service
- Rollback recent changes
- Increase resources if under load

---

## Incident: Security Breach

### Symptoms
- Suspicious login attempts
- Unexpected data access
- Audit log anomalies
- IDS/IPS alerts

### Immediate Actions

```bash
# 1. Audit current sessions
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"

# 2. Check audit logs
cat logs/audit/audit-$(date +%Y-%m-%d).jsonl | \
  jq 'select(.result == "failure")'

# 3. Revoke all tokens
# (via admin API)
curl http://localhost:8000/admin/audit-log?days=1

# 4. Rotate secrets
export SECRET_KEY=$(openssl rand -hex 32)
docker compose restart backend
```

### Post-Incident
1. Rotate ALL secrets
2. Review access logs
3. Update firewall rules
4. Conduct security review

---

## Incident: ML Model Degradation

### Symptoms
- Low confidence predictions
- Increased false positives
- Model drift detected

### Investigation

```bash
# 1. Check model metrics
curl http://localhost:8000/metrics | grep model_

# 2. Check prediction latency
docker compose logs backend | grep "prediction_duration"

# 3. Validate model file
python -c "
import joblib
model = joblib.load('model/best_model.joblib')
print('Model loaded successfully')
print(f'Classes: {model.classes_}')
"
```

### Resolution
- Fallback to heuristic model automatically
- Retrain with recent data
- Rollback to previous model version

---

## Incident Response Communication

### Internal Notification
```yaml
channel: #incidents
message: |
  🚨 INCIDENT: [SEVERITY] - [TITLE]
  Description: [description]
  Status: Investigating
  Responder: @oncall
  Started: [timestamp]
```

### Status Update Template

```yaml
status: |
  Update [N]:
  - Action: [what was done]
  - Result: [outcome]
  - Next: [next step]
```

---

## Post-Mortem Template

```yaml
title: "[DATE] - [INCIDENT TITLE]"
severity: SEV-1/2/3/4
duration: "Start → End"
summary: |
  Brief description of what happened
root_cause: |
  Technical root cause
impact: |
  Users affected: X
  Data loss: Yes/No
  Downtime: X minutes
actions_taken:
  - action: "Immediate fix applied"
    timestamp: "YYYY-MM-DD HH:MM UTC"
preventive_measures:
  - "Add monitoring for X"
  - "Update documentation for Y"
  owner: "Team Name"
```

---

## On-Call Rotation

### Handover Checklist

1. Review active incidents
2. Check monitoring dashboards
3. Verify backup completion
4. Update runbook if needed
5. Confirm escalation contacts

### Escalation Contacts

| Role | Contact | SLA |
|------|---------|-----|
| **Primary On-Call** | engineer@example.com | 15 min |
| **Secondary** | senior@example.com | 30 min |
| **Engineering Manager** | manager@example.com | 1 hour |
| **VP Engineering** | vp@example.com | 2 hours |

