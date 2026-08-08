# Troubleshooting Guide

## Common Issues & Solutions

### Backend won't start

**Symptoms:**
- Container exits immediately
- `uvicorn` process crashes
- Port already in use

**Solutions:**

```bash
# 1. Check port availability
netstat -ano | findstr :8000

# 2. Check Python version
python --version  # Must be 3.11+

# 3. Verify dependencies
pip install -r backend/requirements.txt --force-reinstall

# 4. Check database connection
python -c "from sqlmodel import create_engine; engine = create_engine('sqlite:///dev.db'); engine.connect()"
```

---

### Database connection errors

**Symptoms:**
- `could not connect to server`
- `connection refused`
- `timeout expired`

**Solutions:**

```bash
# 1. Verify PostgreSQL is running
pg_isready -h localhost -p 5432

# 2. Check connection string
echo "DATABASE_URL should be: postgresql://user:password@host:5432/dbname"

# 3. Test connection
psql -h localhost -U scam_user -d scamdb -c "SELECT 1"

# 4. Check SSL requirements
psql "sslmode=require host=localhost dbname=scamdb user=scam_user"

# 5. Check connection pool
python -c "
from sqlalchemy import create_engine
e = create_engine('postgresql://scam_user:password@localhost:5432/scamdb', pool_size=5)
e.connect()
print('Connection successful')
"
```

---

### Model loading failures

**Symptoms:**
- Model loads as heuristic fallback
- `Could not load model` warning
- `joblib.load` exception

**Solutions:**

```bash
# 1. Check model file exists
ls -la model/best_model.joblib

# 2. Verify model file integrity
python -c "
import joblib
try:
    model = joblib.load('model/best_model.joblib')
    print(f'Model loaded: {type(model).__name__}')
except Exception as e:
    print(f'Model error: {e}')
"

# 3. Retrain if corrupted
cd model && python train_models.py

# 4. Check model path in environment
echo "MODEL_PATH=$MODEL_PATH"
```

---

### Redis connection failures

**Symptoms:**
- Cache operations slow
- Redis connection errors
- In-memory cache fallback active

**Solutions:**

```bash
# 1. Test Redis connectivity
redis-cli -h localhost -p 6379 ping

# 2. Check Redis auth
redis-cli -h localhost -p 6379 -a "$REDIS_PASSWORD" ping

# 3. Verify Redis URL format
# Correct: redis://:password@host:6379/0
# Correct: redis://host:6379/0 (no auth)

# 4. Check Redis resource usage
redis-cli INFO memory
redis-cli INFO stats
```

---

### Authentication failures

**Symptoms:**
- 401 Unauthorized
- Token validation errors
- Login fails

**Solutions:**

```bash
# 1. Check SECRET_KEY
echo "SECRET_KEY length: ${#SECRET_KEY}"
# Must be at least 32 characters in production

# 2. Verify token format
python -c "
from jose import jwt
jwt.decode('$TOKEN', '$SECRET_KEY', algorithms=['HS256'])
"

# 3. Check token expiration
python -c "
from datetime import datetime
import jwt
payload = jwt.decode('$TOKEN', '$SECRET_KEY', algorithms=['HS256'])
exp = datetime.fromtimestamp(payload['exp'])
print(f'Token expires: {exp}')
print(f'Is expired: {exp < datetime.now()}')
"

# 4. Force reset by revoking all tokens
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

---

### CORS errors

**Symptoms:**
- Browser console: CORS error
- Preflight requests failing
- `Access-Control-Allow-Origin` missing

**Solutions:**

```bash
# 1. Verify CORS_ORIGINS
echo "CORS_ORIGINS=$CORS_ORIGINS"

# 2. Check origin is included
# Must include EXACT origin (with protocol and port)
# Good: https://app.example.com
# Good: http://localhost:3000
# Bad: app.example.com (missing protocol)

# 3. Test CORS
curl -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS \
  -v http://localhost:8000/predict 2>&1 | grep -i "access-control"
```

---

### Rate limiting issues

**Symptoms:**
- 429 Too Many Requests
- Requests being throttled
- Retry-After headers

**Solutions:**

```bash
# 1. Check current rate limits
curl -I http://localhost:8000/health | grep -i rate

# 2. View rate limit headers
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1700000000

# 3. Increase limits (if needed)
export RATE_LIMIT_MAX=200
export RATE_LIMIT_WINDOW=60
```

---

### Monitoring not working

**Symptoms:**
- Prometheus targets down
- Grafana no data
- Metrics endpoint empty

**Solutions:**

```bash
# 1. Check metrics endpoint
curl http://localhost:8000/metrics

# 2. Verify Prometheus config
docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml

# 3. Check target discovery
curl http://localhost:9090/api/v1/targets

# 4. Restart monitoring stack
docker compose -f docker-compose.monitoring.yml restart
```

---

### Docker build failures

**Symptoms:**
- Build fails during pip install
- Package version conflicts
- Layer cache issues

**Solutions:**

```bash
# 1. Clear Docker cache
docker builder prune -af

# 2. Build with no cache
docker build --no-cache -t backend:test ./backend

# 3. Check pip versions
docker run --rm python:3.11-slim pip install -r backend/requirements.txt --dry-run

# 4. Debug build
DOCKER_BUILDKIT=0 docker build -t backend:debug ./backend
```

---

### Performance issues

**Symptoms:**
- Slow response times
- High CPU/memory usage
- Database query slowness

**Solutions:**

```bash
# 1. Profile slow requests
# Check logs for "Slow request detected"
docker compose logs backend | grep "Slow request"

# 2. Check database query performance
# Enable query logging
export DB_ECHO=true

# 3. Review connection pool
curl http://localhost:8000/system/config
# Check db_pool_size and db_max_overflow

# 4. Scale up
docker compose up -d --scale backend=5

# 5. Enable query caching
export ENABLE_CACHE=true

# 6. Check indexes
python -c "
from sqlmodel import SQLModel
# Verify indexes in models.py
"
```

---

### Getting Help

If issues persist:

1. **Check logs**: `docker compose logs backend --tail=200`
2. **Search docs**: See [docs/](docs/) directory
3. **Open issue**: GitHub Issues with logs
4. **Contact support**: See [README.md](../README.md)

