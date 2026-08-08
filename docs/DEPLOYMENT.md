# Production Deployment Guide

## Prerequisites

- Docker Engine 24+ and Docker Compose v2+
- Domain name with DNS configured
- SSL certificates (Let's Encrypt / Cloudflare)
- PostgreSQL 15+ database
- Redis 7+ (optional, for caching)
- 2GB+ RAM, 2+ vCPUs

## Environment Variables

Copy `.env.example` to `.env` and configure all values:

```bash
cp .env.example .env
# Edit .env with production values
```

**Required secrets:**
```bash
# Generate strong secrets
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
REDIS_PASSWORD=$(openssl rand -hex 16)
GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 16)
```

## Docker Compose Deployment

### 1. Full Production Stack

```bash
# Deploy all services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### 2. With Monitoring Stack

```bash
# Deploy monitoring services
docker compose -f docker-compose.monitoring.yml up -d

# Access Grafana at http://localhost:3001
# Access Prometheus at http://localhost:9090
```

## Kubernetes Deployment

### 1. Create Namespace

```bash
kubectl create namespace scam-detector
```

### 2. Create Secrets

```bash
kubectl create secret generic backend-secrets \
  --namespace scam-detector \
  --from-literal=database-url="postgresql://..." \
  --from-literal=secret-key="your-secret-key" \
  --from-literal=redis-url="redis://..."
```

### 3. Deploy Services

```bash
# Deploy backend
kubectl apply -f deploy/k8s/backend-deployment.yaml

# Deploy frontend
kubectl apply -f deploy/k8s/frontend-deployment.yaml

# Check status
kubectl get pods -n scam-detector
kubectl get services -n scam-detector
```

### 4. Configure Ingress

```bash
# Install ingress controller (if not present)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

# Apply ingress rules
kubectl apply -f deploy/k8s/ingress.yaml
```

## AWS ECS Deployment

### 1. Create ECR Repositories

```bash
aws ecr create-repository --repository-name ai-scam-detector-backend
aws ecr create-repository --repository-name ai-scam-detector-frontend
```

### 2. Build and Push Images

```bash
# Build images
docker build -t backend:latest ./backend
docker build -t frontend:latest ./frontend

# Tag and push
docker tag backend:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/ai-scam-detector-backend:latest
docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/ai-scam-detector-backend:latest
```

### 3. Register Task Definition

```bash
aws ecs register-task-definition --cli-input-json file://deploy/ecs/task-definition.json
```

### 4. Create Service

```bash
aws ecs create-service \
  --cluster scam-detector \
  --service-name backend \
  --task-definition ai-scam-detector-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration ...
```

## Azure Container Apps

### 1. Create Azure Resources

```bash
az group create --name scam-detector --location eastus
az containerapp env create --name scam-detector-env --resource-group scam-detector
```

### 2. Deploy Backend

```bash
az containerapp create \
  --name ai-scam-detector-backend \
  --resource-group scam-detector \
  --environment scam-detector-env \
  --image ghcr.io/your-org/ai-scam-detector-backend:latest \
  --target-port 8000 \
  --ingress external
```

## Google Cloud Run

### 1. Build and Push

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/ai-scam-detector-backend ./backend
```

### 2. Deploy

```bash
gcloud run deploy ai-scam-detector-backend \
  --image gcr.io/PROJECT_ID/ai-scam-detector-backend \
  --platform managed \
  --region us-central1 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 2 \
  --max-instances 10 \
  --concurrency 80
```

## Health Checks

All deployment methods should use these health check endpoints:

| Endpoint | Purpose | Expected Status |
|----------|---------|-----------------|
| `/health` | Basic health | 200 OK |
| `/health/ready` | Readiness probe | 200 OK when ready, 503 otherwise |
| `/health/live` | Liveness probe | 200 OK |
| `/health/db` | Database check | 200 OK |

## Monitoring Setup

### Grafana

1. Access Grafana at `https://monitor.yourdomain.com:3001`
2. Login with admin credentials from `.env`
3. Add Prometheus data source: `http://prometheus:9090`
4. Import pre-configured dashboard from `monitoring/grafana/dashboards/`

### Prometheus

- Access Prometheus at `https://monitor.yourdomain.com:9090`
- Pre-configured targets: backend, node-exporter, cAdvisor
- Data retention: 30 days

### Logging

- Application logs in JSON format
- Aggregated via Loki + Promtail
- Viewable in Grafana Explore

## Scaling

### Vertical Scaling
- Increase worker count in Dockerfile CMD
- Increase memory/CPU limits in deployment configs

### Horizontal Scaling
- Docker: Increase replica count in compose files
- Kubernetes: HPA auto-scales based on CPU/memory
- Cloud: Configure auto-scaling rules

## Backup & Recovery

See [Disaster Recovery](DISASTER_RECOVERY.md) for comprehensive recovery procedures.

## Security Checklist

- [ ] SECRET_KEY generated with `openssl rand -hex 32`
- [ ] PostgreSQL password changed from default
- [ ] Redis password set and configured
- [ ] CORS_ORIGINS set to specific domains
- [ ] SSL certificates configured
- [ ] Rate limiting enabled
- [ ] Audit logging enabled
- [ ] Read-only filesystem enabled
- [ ] Non-root user configured
- [ ] Security headers verified
- [ ] Firewall rules configured
- [ ] Regular backup schedule configured
- [ ] Monitoring alerts configured

