# Operations Manual

## Daily Operations

### 1. System Health Check

```bash
# Check all services
docker compose -f docker-compose.prod.yml ps

# Check health endpoints
curl -f http://localhost:8000/health
curl -f http://localhost:8000/health/ready
curl -f http://localhost:8000/health/live

# Check database
curl -f http://localhost:8000/health/db
```

### 2. Monitoring Dashboard

Access Grafana at `https://monitor.yourdomain.com:3001`

**Key Metrics to Monitor:**
- Prediction latency (p95 < 500ms)
- Error rate (< 1%)
- Active users
- Cache hit ratio (> 80%)
- Database connection pool utilization
- CPU/Memory usage

### 3. Log Review

```bash
# View application logs
docker compose logs -f backend --tail=100

# View audit log
cat logs/audit/audit-$(date +%Y-%m-%d).jsonl | jq .

# Check error log
docker compose logs backend 2>&1 | grep ERROR
```

---

## Alerting Configuration

### Prometheus Alert Rules

Create `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: ai-scam-detector
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High request latency"

      - alert: ModelUnavailable
        expr: model_inference_time_seconds_count == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Model inference unavailable"

      - alert: DatabaseDown
        expr: pg_up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Database connection lost"
```

---

## Backup Procedures

### Database Backup

```bash
# Manual backup
pg_dump -h localhost -U scam_user scamdb > backup_$(date +%Y%m%d).sql

# Automated daily backup (add to crontab)
0 2 * * * pg_dump -h localhost -U scam_user scamdb | gzip > /backups/scamdb_$(date +\%Y\%m\%d).sql.gz
```

### Configuration Backup

```bash
# Backup .env and configs
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env nginx/ monitoring/
```

---

## Scaling Operations

### Vertical Scaling

```yaml
# Increase backend workers
deploy:
  resources:
    limits:
      cpus: '2'    # Increase from 1
      memory: 2G   # Increase from 1G
```

### Horizontal Scaling

```bash
# Docker Compose
docker compose -f docker-compose.prod.yml up -d --scale backend=5

# Kubernetes
kubectl scale deployment scam-detector-backend --replicas=5
```

---

## Maintenance Windows

### Update Procedure

1. **Pre-maintenance**: 
   - Set maintenance page in nginx
   - Notify users
   - Take DB snapshot

2. **During maintenance**:
   - Pull latest images
   - Apply updates
   - Run migrations

3. **Post-maintenance**:
   - Verify health endpoints
   - Run smoke tests
   - Remove maintenance page

### Zero-Downtime Deploy

```bash
# Rolling update
docker compose -f docker-compose.prod.yml up -d --no-deps --build backend
```

