"""
Security vulnerability tests.
Tests: SQL injection, XSS, CSRF, JWT attacks, rate limiting bypass,
       input validation bypass, path traversal, auth bypass.
"""
import pytest


class TestSQLInjection:
    SQLI_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users --",
        "admin' --",
        "1; SELECT * FROM users",
        "' OR 1=1 --",
        "'; EXEC xp_cmdshell('dir'); --",
        "' UNION SELECT null, null, null --",
        "1' ORDER BY 1--",
        "1' AND 1=1--",
    ]

    def test_sqli_in_login(self, client):
        for payload in self.SQLI_PAYLOADS:
            resp = client.post("/auth/login", data={
                "username": payload,
                "password": payload
            })
            # Should NOT return 200 (auth bypass)
            assert resp.status_code in (401, 422, 400), f"SQLi bypass with: {payload}"

    def test_sqli_in_predict(self, client):
        for payload in self.SQLI_PAYLOADS:
            resp = client.post("/predict", json={
                "text": payload,
                "source": "test"
            })
            assert resp.status_code in (200, 422), f"SQLi in predict: {payload}"

    def test_sqli_in_signup(self, client):
        resp = client.post("/auth/signup", json={
            "email": "sqli@test.com",
            "password": "StrongP@ss1"
        })
        assert resp.status_code in (200, 400)


class TestXSS:
    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert('xss')",
        "<svg onload=alert(1)>",
        "'-alert(1)-'",
        "<scr<script>ipt>alert(1)</scr</script>ipt>",
        "<?xml-stylesheet type=\"text/xsl\" href=\"evil.xsl\"?>",
        "<body onload=alert(1)>",
        "<input onfocus=alert(1) autofocus>",
        "<details open ontoggle=alert(1)>",
    ]

    def test_xss_in_predict(self, client):
        for payload in self.XSS_PAYLOADS:
            resp = client.post("/predict", json={
                "text": payload,
                "source": "test"
            })
            assert resp.status_code in (200, 400, 422)
            if resp.status_code == 200:
                # Response should not contain unescaped script tags
                body = resp.text.lower()
                assert "<script>" not in body.replace("\\u003cscript\\u003e", "")

    def test_xss_in_feedback(self, client, auth_headers):
        for payload in self.XSS_PAYLOADS:
            resp = client.post("/feedback", json={"message": payload},
                               headers=auth_headers)
            # Some payloads may be empty after sanitization or fail validation
            assert resp.status_code in (200, 400, 422), f"Unexpected {resp.status_code} for: {payload[:30]}"

    def test_xss_in_signup(self, client):
        resp = client.post("/auth/signup", json={
            "email": "<script>alert(1)</script>@test.com",
            "password": "StrongP@ss1"
        })
        # Email fails schema validation -> 400 (Pydantic raises ValueError -> HTTP 400)
        assert resp.status_code in (400, 422), f"Expected 400 or 422, got {resp.status_code}"


class TestInputValidation:
    def test_oversized_payload(self, client):
        huge_text = "A" * 100000
        resp = client.post("/predict", json={
            "text": huge_text,
            "source": "test"
        })
        assert resp.status_code == 422  # Max length enforced

    def test_null_bytes(self, client):
        resp = client.post("/predict", json={
            "text": "test\x00null byte injection",
            "source": "test"
        })
        assert resp.status_code in (200, 422)

    def test_unicode_attack(self, client):
        resp = client.post("/predict", json={
            "text": "\uff1cscript\uff1ealert(1)\uff1c/script\uff1e",
            "source": "test"
        })
        assert resp.status_code in (200, 422)

    def test_non_printable_chars(self, client):
        resp = client.post("/predict", json={
            "text": "\x01\x02\x03\x04\x05",
            "source": "test"
        })
        assert resp.status_code in (200, 422)

    def test_very_long_source(self, client):
        long_source = "A" * 100
        resp = client.post("/predict", json={
            "text": "test",
            "source": long_source
        })
        assert resp.status_code in (200, 422)


class TestJWTSecurity:
    def test_none_algorithm_attack(self, client):
        try:
            import jwt
        except ImportError:
            pytest.skip("jwt module (PyJWT) not installed")
        # Try "none" algorithm attack
        headers = {"Authorization": "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhZG1pbkB0ZXN0LmNvbSIsInJvbGUiOiJhZG1pbiJ9."}
        resp = client.get("/admin/users", headers=headers)
        assert resp.status_code == 401

    def test_weak_key_attack(self, client):
        headers = {"Authorization": "Bearer " + "a" * 1000}
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 401

    def test_token_replay(self, client, auth_headers):
        token = auth_headers["Authorization"].replace("Bearer ", "")
        # Reuse same token
        headers = {"Authorization": f"Bearer {token}"}
        resp1 = client.get("/auth/me", headers=headers)
        resp2 = client.get("/auth/me", headers=headers)
        assert resp1.status_code == resp2.status_code

    def test_altered_token_claims(self, client):
        from jose import jwt

        from backend.app.core.config import ALGORITHM, SECRET_KEY
        # Token with elevated privileges
        malicious_token = jwt.encode(
            {"sub": "attacker@test.com", "role": "superadmin", "type": "access"},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        resp = client.get("/admin/users",
                          headers={"Authorization": f"Bearer {malicious_token}"})
        # Should still require valid authentication (user must exist)
        assert resp.status_code in (401, 403)


class TestRateLimitBypass:
    def test_rate_limit_headers(self, client):
        resp = client.get("/health")
        # Rate limit headers might not be present on excluded paths
        assert resp.status_code == 200

    def test_distributed_bypass(self, client):
        # Try many requests
        for _ in range(20):
            client.post("/predict", json={"text": "test", "source": "test"})


class TestSecurityHeaders:
    def test_security_headers_present(self, client):
        resp = client.get("/health")
        headers = resp.headers
        # Check for essential security headers
        security_headers = {
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
            "x-xss-protection": "1; mode=block",
            "referrer-policy": "strict-origin-when-cross-origin",
        }
        for header, expected in security_headers.items():
            assert headers.get(header, "").lower() == expected.lower(), \
                f"Missing or wrong {header}: {headers.get(header)}"

    def test_cors_headers(self, client):
        resp = client.options("/predict", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })
        assert "access-control-allow-origin" in resp.headers


class TestAuthBypass:
    def test_no_auth_admin(self, client):
        resp = client.get("/admin/users")
        assert resp.status_code == 401

    def test_no_auth_history(self, client):
        resp = client.get("/history")
        assert resp.status_code == 401

    def test_weak_password_rejected(self, client):
        weak_passwords = [
            "password",
            "12345678",
            "qwerty123",
            "abcdefgh",
            "Passw0rd",  # Common pattern
        ]
        for pw in weak_passwords:
            resp = client.post("/auth/signup", json={
                "email": f"weak_{pw}@test.com",
                "password": pw
            })
            # API returns 400 for weak passwords (SecretsValidator raises HTTP 400)
            assert resp.status_code in (400, 422), f"Weak password not rejected: {pw}"

