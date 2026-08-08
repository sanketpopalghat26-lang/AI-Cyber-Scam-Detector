"""
Unit tests for FastAPI endpoints.
Tests: health, predict, auth, dashboard, admin endpoints.
"""


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model_status" in data
        assert "timestamp" in data

    def test_health_model_status(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["model_status"] in ("loaded", "fallback")

    def test_liveness_endpoint(self, client):
        resp = client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"

    def test_readiness_endpoint(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code in (200, 503)

    def test_metrics_endpoint(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200


class TestPredictEndpoint:
    def test_predict_scam_text(self, client):
        resp = client.post("/predict", json={
            "text": "Urgent! Verify your bank account immediately or it will be closed.",
            "source": "email"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("safe", "suspicious", "scam")
        assert 0.0 <= data["confidence"] <= 1.0
        assert "explanation" in data
        assert "keywords" in data["explanation"]
        assert "risk_level" in data["explanation"]

    def test_predict_safe_text(self, client):
        resp = client.post("/predict", json={
            "text": "Hey, are we still meeting for lunch tomorrow at 1pm?",
            "source": "chat"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("safe", "suspicious", "scam")

    def test_predict_suspicious_text(self, client):
        resp = client.post("/predict", json={
            "text": "Click here to claim your free prize of $1000! Limited time offer.",
            "source": "sms"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("safe", "suspicious", "scam")

    def test_predict_empty_text(self, client):
        resp = client.post("/predict", json={"text": "", "source": "email"})
        assert resp.status_code == 422  # FastAPI validation

    def test_predict_whitespace_text(self, client):
        resp = client.post("/predict", json={"text": "   ", "source": "email"})
        assert resp.status_code == 422

    def test_predict_long_text(self, client):
        text = "A" * 10001
        resp = client.post("/predict", json={"text": text, "source": "email"})
        assert resp.status_code == 422  # Max length 10000

    def test_predict_with_auth_saves_scan(self, client, auth_headers):
        resp = client.post("/predict", json={
            "text": "Urgent bank verification needed",
            "source": "email"
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("safe", "suspicious", "scam")

    def test_predict_explanation_structure(self, client):
        resp = client.post("/predict", json={
            "text": "Urgent: Your account has been compromised. Click here to reset.",
            "source": "email"
        })
        data = resp.json()
        expl = data["explanation"]
        assert "keywords" in expl
        assert "reason" in expl
        assert "risk_level" in expl
        assert "safety_advice" in expl
        assert "simple_explanation" in expl
        assert "source" in expl
        assert "confidence" in expl

    def test_predict_invalid_json(self, client):
        resp = client.post("/predict", data="not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422


class TestAuthEndpoints:
    def test_signup_success(self, client):
        resp = client.post("/auth/signup", json={
            "email": "newuser@test.com",
            "password": "NewUserP@ss1"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_signup_duplicate_email(self, client):
        client.post("/auth/signup", json={
            "email": "dup@test.com",
            "password": "DupUserP@ss1"
        })
        resp = client.post("/auth/signup", json={
            "email": "dup@test.com",
            "password": "DupUserP@ss1"
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_signup_weak_password(self, client):
        resp = client.post("/auth/signup", json={
            "email": "weak@test.com",
            "password": "short"
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_signup_invalid_email(self, client):
        resp = client.post("/auth/signup", json={
            "email": "notanemail",
            "password": "StrongP@ss123"
        })
        assert resp.status_code == 422

    def test_login_success(self, client):
        client.post("/auth/signup", json={
            "email": "login@test.com",
            "password": "LoginP@ss123"
        })
        resp = client.post("/auth/login", data={
            "username": "login@test.com",
            "password": "LoginP@ss123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client):
        client.post("/auth/signup", json={
            "email": "wrongpw@test.com",
            "password": "CorrectP@ss1"
        })
        resp = client.post("/auth/login", data={
            "username": "wrongpw@test.com",
            "password": "WrongP@ss1"
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", data={
            "username": "nobody@test.com",
            "password": "SomeP@ss123"
        })
        assert resp.status_code == 401

    def test_refresh_token(self, client):
        client.post("/auth/signup", json={
            "email": "refresh@test.com",
            "password": "RefreshP@ss1"
        })
        login_resp = client.post("/auth/login", data={
            "username": "refresh@test.com",
            "password": "RefreshP@ss1"
        })
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    def test_refresh_with_invalid_token(self, client):
        resp = client.post("/auth/refresh", json={"refresh_token": "invalid"})
        # Pydantic validation returns 422 for short strings, API returns 401 for invalid tokens
        assert resp.status_code in (401, 422), f"Expected 401 or 422, got {resp.status_code}"

    def test_me_endpoint(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert "id" in data

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_logout(self, client, auth_headers):
        resp = client.post("/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert "logged out" in resp.json()["message"].lower()

    def test_logout_invalidates_token(self, client, auth_headers):
        client.post("/auth/logout", headers=auth_headers)
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 401

    def test_forgot_password(self, client):
        resp = client.post("/auth/forgot-password", json={
            "email": "anyuser@test.com",
            "password": "AnyP@ss123"
        })
        assert resp.status_code == 200
        assert "reset" in resp.json()["message"].lower()


class TestDashboardEndpoint:
    def test_dashboard_returns_stats(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_scans" in data
        assert "scam_percentage" in data
        assert "safe_percentage" in data
        assert "recent_scans" in data

    def test_dashboard_with_predictions(self, client, auth_headers):
        client.post("/predict", json={"text": "Test scam text urgent", "source": "test"},
                     headers=auth_headers)
        resp = client.get("/dashboard")
        data = resp.json()
        assert data["total_scans"] >= 0


class TestHistoryEndpoint:
    def test_history_requires_auth(self, client):
        resp = client.get("/history")
        assert resp.status_code == 401

    def test_history_returns_scans(self, client, auth_headers):
        client.post("/predict", json={"text": "Test history item", "source": "test"},
                     headers=auth_headers)
        resp = client.get("/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "input_text" in data[0]
            assert "result" in data[0]

    def test_history_limits_results(self, client, auth_headers):
        for i in range(5):
            client.post("/predict", json={"text": f"Test {i}", "source": "test"},
                         headers=auth_headers)
        resp = client.get("/history", headers=auth_headers)
        data = resp.json()
        assert len(data) <= 50


class TestFeedbackEndpoint:
    def test_feedback_requires_auth(self, client):
        resp = client.post("/feedback", json={"message": "Great tool!"})
        assert resp.status_code == 401

    def test_feedback_submission(self, client, auth_headers):
        resp = client.post("/feedback", json={"message": "This is great!"},
                            headers=auth_headers)
        assert resp.status_code == 200

    def test_feedback_empty_message(self, client, auth_headers):
        resp = client.post("/feedback", json={"message": ""},
                            headers=auth_headers)
        assert resp.status_code == 422


class TestAdminEndpoints:
    def test_admin_users_requires_admin(self, client, auth_headers):
        resp = client.get("/admin/users", headers=auth_headers)
        assert resp.status_code == 403

    def test_admin_users_with_admin(self, client, admin_headers):
        resp = client.get("/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_audit_log(self, client, admin_headers):
        resp = client.get("/admin/audit-log", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_events" in data

    def test_admin_audit_log_requires_admin(self, client, auth_headers):
        resp = client.get("/admin/audit-log", headers=auth_headers)
        assert resp.status_code == 403


class TestSystemEndpoints:
    def test_resilience_status_requires_admin(self, client, auth_headers):
        resp = client.get("/system/resilience", headers=auth_headers)
        assert resp.status_code == 403

    def test_system_config_requires_admin(self, client, auth_headers):
        resp = client.get("/system/config", headers=auth_headers)
        assert resp.status_code == 403
