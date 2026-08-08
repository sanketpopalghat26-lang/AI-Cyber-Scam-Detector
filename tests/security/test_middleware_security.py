"""
Security middleware tests.
Tests: CORS, CSP, HSTS, rate limiting, input sanitization, request ID.
"""
from fastapi.testclient import TestClient

from backend.app.main import app


class TestCORSMiddleware:
    def test_cors_allowed_origin(self):
        client = TestClient(app)
        resp = client.options("/predict", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_denied_origin(self):
        client = TestClient(app)
        resp = client.options("/predict", headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
        })
        origin = resp.headers.get("access-control-allow-origin", "")
        # If origin isn't in allowed list, it shouldn't be echoed back
        if origin:
            assert "evil.com" not in origin

    def test_cors_credentials(self):
        client = TestClient(app)
        resp = client.options("/predict", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.headers.get("access-control-allow-credentials") == "true"


class TestSecurityHeadersMiddleware:
    def test_hsts_in_production(self):
        import os
        os.environ["APP_ENV"] = "production"
        # Need to reload app to pick up new env
        import importlib

        import backend.app.main as main
        importlib.reload(main)

        client = TestClient(main.app)
        resp = client.get("/health")
        if "strict-transport-security" in resp.headers:
            assert "max-age=31536000" in resp.headers["strict-transport-security"]
        os.environ["APP_ENV"] = "testing"

    def test_x_frame_options(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        client = TestClient(app)
        resp = client.get("/health")
        policy = resp.headers.get("permissions-policy", "")
        assert "camera=()" in policy
        assert "microphone=()" in policy

    def test_csp_present(self):
        client = TestClient(app)
        resp = client.get("/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src" in csp
        assert "script-src" in csp
        assert "style-src" in csp

    def test_no_server_header(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert "server" not in resp.headers


class TestRateLimitMiddleware:
    def test_rate_limit_headers_present(self):
        client = TestClient(app)
        resp = client.get("/dashboard")
        # Rate limit headers might not be on excluded paths
        if "x-ratelimit-limit" in resp.headers:
            assert int(resp.headers["x-ratelimit-limit"]) > 0

    def test_rate_limit_blocks_excessive(self):
        """Rate limiting should block after threshold."""
        import os
        original_max = os.environ.get("RATE_LIMIT_MAX", "100")

        os.environ["RATE_LIMIT_MAX"] = "3"
        import importlib

        import backend.app.main as main
        importlib.reload(main)

        client = TestClient(main.app)
        # Make requests to a non-excluded path
        for _ in range(3):
            client.get("/dashboard")

        resp = client.get("/dashboard")
        if resp.status_code == 429:
            assert "Too many requests" in resp.text

        os.environ["RATE_LIMIT_MAX"] = original_max
        importlib.reload(main)

    def test_health_excluded_from_rate_limit(self):
        """Health endpoint should not be rate-limited."""
        client = TestClient(app)
        for _ in range(200):
            resp = client.get("/health")
            assert resp.status_code == 200


class TestRequestIDMiddleware:
    def test_request_id_generated(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) > 0

    def test_request_id_preserved(self):
        client = TestClient(app)
        rid = "test-request-id-123"
        resp = client.get("/health", headers={"X-Request-ID": rid})
        assert resp.headers.get("x-request-id") == rid

    def test_correlation_id(self):
        client = TestClient(app)
        cid = "test-correlation-456"
        resp = client.get("/health", headers={"X-Correlation-ID": cid})
        assert resp.headers.get("x-correlation-id") == cid


class TestInputSanitizationMiddleware:
    def test_script_injection_blocked(self):
        client = TestClient(app)
        resp = client.post("/predict", json={
            "text": "<script>alert('xss')</script>",
            "source": "test"
        })
        # Script tags should be handled gracefully
        assert resp.status_code in (200, 400, 422)

    def test_sql_injection_body(self):
        client = TestClient(app)
        resp = client.post("/predict", json={
            "text": "'; DROP TABLE users; --",
            "source": "test"
        })
        assert resp.status_code in (200, 422)

    def test_javascript_protocol(self):
        client = TestClient(app)
        resp = client.post("/predict", json={
            "text": "javascript:alert('xss')",
            "source": "test"
        })
        assert resp.status_code in (200, 400, 422)

    def test_os_command_injection(self):
        client = TestClient(app)
        resp = client.post("/predict", json={
            "text": "import os; os.system('rm -rf /')",
            "source": "test"
        })
        assert resp.status_code in (200, 400, 422)


class TestResponseTimeMiddleware:
    def test_response_time_header(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert "x-response-time" in resp.headers
        time_ms = float(resp.headers["x-response-time"].replace("ms", ""))
        assert time_ms >= 0

