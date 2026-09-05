# =============================================================================
# Stage 1: Builder — Install dependencies and build static assets
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /build

# Copy dependency files first for layer caching
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --omit=optional

# Copy source and build
COPY . .
RUN npm run build

# =============================================================================
# Stage 2: Runtime — Serve static files via Nginx
# =============================================================================
FROM nginx:1.31-alpine AS runtime

# Security: non-root user
RUN adduser -D -g '' -u 1001 appuser

# Copy built assets
COPY --from=builder /build/dist /usr/share/nginx/html

# Security: remove default nginx configs
RUN rm -f /etc/nginx/conf.d/default.conf.bak \
    && rm -f /etc/nginx/conf.d/examples* \
    && chown -R appuser:appuser /usr/share/nginx/html \
    && chown -R appuser:appuser /var/cache/nginx \
    && touch /var/run/nginx.pid \
    && chown -R appuser:appuser /var/run/nginx.pid

USER appuser

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]

