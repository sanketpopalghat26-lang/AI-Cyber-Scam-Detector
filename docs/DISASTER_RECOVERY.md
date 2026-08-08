# Disaster Recovery Plan

## Recovery Objectives

| Metric | Target | Maximum |
|--------|--------|---------|
| **RTO** (Recovery Time Objective) | 1 hour | 4 hours |
| **RPO** (Recovery Point Objective) | 15 minutes | 1 hour |
| **Data Loss** | 0 (committed transactions) | 15 minutes |

---

## Failure Scenarios

### Scenario 1: Single Service Failure

**Impact**: One service crashes but others remain operational.

**Recovery**:
```bash
# 1. Restart failed service
docker compose restart backend

# 2. Verify health
curl -f http://localhost:8000/health

# 3. Check logs for root cause
docker compose logs --tail=50 backend
```

**RTO**: 5 minutes
**RPO**: 0 data loss

---

### Scenario 2: Database Corruption

**Impact**: Data integrity compromised, queries failing.

**Recovery**:
```bash
# 1. Stop all affected services
docker compose stop backend

# 2. Take corrupted DB snapshot (for forensics)
pg_dump -h localhost -U scam_user scamdb > corrupted_snapshot_$(date +%Y%m%d).sql

# 3. Restore from latest backup
psql -h localhost -U scam_user -d scamdb < latest_backup.sql

# 4. Verify restore
python -c "
from sqlmodel import Session, select
from backend.app.models import User, Scan
# Verify data integrity
"

# 5. Restart services
docker compose start backend
```

**RTO**: 30 minutes
**RPO**: Based on backup frequency

---

### Scenario 3: Complete Infrastructure Failure

**Impact**: All services down, full recovery needed.

**Recovery**:
```bash
# 1. Provision new infrastructure
# Cloud: Use IaC (Terraform/Pulumi)
# Docker: Use docker-compose.prod.yml
# K8s: Use deploy/k8s/

# 2. Restore database
# From latest backup stored in S3/Blob Storage
aws s3 cp s3://backups/scamdb/latest.sql.gz .
gunzip latest.sql.gz
psql -h new-db-host -U scam_user -d scamdb < latest.sql

# 3. Deploy services
docker compose -f docker-compose.prod.yml up -d

# 4. Verify all health endpoints
for endpoint in health health/ready health/live health/db; do
    curl -f "http://localhost:8000/$endpoint" || exit 1
done

# 5. Run smoke tests
python -m pytest tests/test_predict.py -v

# 6. Verify monitoring
curl http://localhost:9090/api/v1/targets
curl http://localhost:3001/api/health
```

**RTO**: 2-4 hours
**RPO**: 15 minutes (with streaming replication)

---

### Scenario 4: Security Breach

**Impact**: Unauthorized access, potential data compromise.

**Recovery**:
```bash
# 1. Isolate affected services
docker compose stop backend nginx

# 2. Revoke all auth tokens
# Delete all JWT blacklist entries

# 3. Rotate ALL secrets
export SECRET_KEY=$(openssl rand -hex 32)
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
export REDIS_PASSWORD=$(openssl rand -hex 16)

# 4. Restore from clean backup
# Use backup taken BEFORE breach

# 5. Deploy fresh instances
docker compose -f docker-compose.prod.yml up -d

# 6. Force password reset for all users
# (via admin API)

# 7. Enable enhanced auditing
export AUDIT_RETENTION_DAYS=365
```

**RTO**: 4 hours
**RPO**: Based on backup frequency (may lose data between breach discovery and backup)

---

### Scenario 5: Data Center Failure (Cloud)

**Impact**: Complete loss of cloud region/availability zone.

**Recovery**:
```bash
# 1. Activate cross-region deployment
# Deploy to secondary region using same configs
gcloud config set project secondary-project
gcloud run deploy ai-scam-detector-backend \
  --region us-west1

# 2. Promote database replica
# Promote read replica in secondary region

# 3. Update DNS
# Change DNS records to point to secondary region
# TTL should be 60 seconds for quick failover

# 4. Verify deployment
curl -f https://secondary-backend.example.com/health

# 5. Enable monitoring
# Re-deploy monitoring stack in secondary region
docker compose -f docker-compose.monitoring.yml up -d
```

**RTO**: 1 hour
**RPO**: < 1 minute (with synchronous replication)

---

## Recovery Scripts

### Automated Recovery Script

Save as `scripts/recover.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Disaster Recovery Script ==="
echo "Starting recovery at $(date)"

# Configuration
BACKUP_BUCKET="s3://backups/scamdb"
COMPOSE_FILE="docker-compose.prod.yml"

# 1. Restore Database
echo "Restoring database..."
aws s3 cp "${BACKUP_BUCKET}/latest.sql.gz" /tmp/db_restore.sql.gz
gunzip -f /tmp/db_restore.sql.gz
psql -h "${DB_HOST}" -U "${DB_USER}" -d "${DB_NAME}" < /tmp/db_restore.sql
echo "Database restored successfully"

# 2. Deploy Services
echo "Deploying services..."
docker compose -f "${COMPOSE_FILE}" up -d

# 3. Wait for readiness
echo "Waiting for services..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend is ready"
        break
    fi
    sleep 2
done

# 4. Run Smoke Tests
echo "Running smoke tests..."
python -m pytest tests/test_predict.py -v --tb=short

# 5. Verify Monitoring
echo "Verifying monitoring..."
curl -f http://localhost:9090/api/v1/targets || echo "Warning: Prometheus not available"

echo "=== Recovery completed at $(date) ==="
```

---

## Backup Strategy

### Database Backups

| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| Full | Daily | 30 days | S3/Blob |
| WAL | Continuous | 7 days | Same region |
| Pre-deployment | On deploy | 7 days | Same region |

### Backup Verification

```bash
# Monthly restore test
scripts/test_restore.sh:
1. Restore latest backup to test database
2. Run data integrity checks
3. Verify all tables have expected data
4. Run API smoke tests
5. Report results
```

---

## Disaster Recovery Team

| Role | Contact | Responsibility |
|------|---------|---------------|
| **Incident Commander** | oncall@example.com | Overall coordination |
| **Database Admin** | dba@example.com | DB recovery |
| **DevOps Engineer** | devops@example.com | Infrastructure |
| **Security Engineer** | security@example.com | Security incidents |
| **Engineering Lead** | eng-lead@example.com | Code fixes |

---

## Post-Incident Review

After every disaster recovery event:

1. **Root Cause Analysis** within 48 hours
2. **Timeline Reconstruction** with all actions taken
3. **Gap Analysis**: What worked, what didn't
4. **Improvement Plan**: Specific actions with owners
5. **Runbook Updates**: Incorporate learnings
6. **Drill Schedule**: Quarterly DR drills

