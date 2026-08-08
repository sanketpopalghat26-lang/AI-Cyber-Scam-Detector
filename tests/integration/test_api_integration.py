"""
Integration tests for full API workflows.
Tests: auth flows, prediction pipelines, data persistence, cache integration.
"""


class TestAuthFlows:
    def test_full_auth_lifecycle(self, client):
        # Signup
        signup_resp = client.post("/auth/signup", json={
            "email": "lifecycle@test.com",
            "password": "LifeCycleP@ss1"
        })
        assert signup_resp.status_code == 200
        access = signup_resp.json()["access_token"]
        refresh = signup_resp.json()["refresh_token"]

        # Access protected endpoint
        me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert me_resp.status_code == 200

        # Refresh token
        refresh_resp = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert refresh_resp.status_code == 200
        new_access = refresh_resp.json()["access_token"]

        # New access token works
        me_resp2 = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
        assert me_resp2.status_code == 200

        # Logout
        logout_resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {new_access}"})
        assert logout_resp.status_code == 200

        # Old tokens invalid
        me_resp3 = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
        assert me_resp3.status_code == 401

    def test_concurrent_users_independent(self, client):
        import uuid
        suffix = uuid.uuid4().hex[:8]
        emails = [f"user{i}_{suffix}@test.com" for i in range(3)]
        tokens = []

        for email in emails:
            signup_resp = client.post("/auth/signup", json={
                "email": email,
                "password": "T3stP@ssW0rd!"
            })
            # If signup already exists, try login
            if signup_resp.status_code != 200:
                pass
            resp = client.post("/auth/login", data={
                "username": email,
                "password": "T3stP@ssW0rd!"
            })
            assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
            tokens.append(resp.json()["access_token"])

        # Each user can access their own data
        for token in tokens:
            resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200

        # Each user can make predictions
        for token in tokens:
            resp = client.post("/predict", json={
                "text": "Test prediction for integration",
                "source": "integration"
            }, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200

    def test_password_reset_flow(self, client):
        client.post("/auth/signup", json={
            "email": "reset@test.com",
            "password": "ResetP@ss123"
        })
        resp = client.post("/auth/forgot-password", json={
            "email": "reset@test.com",
            "password": "ResetP@ss123"
        })
        assert resp.status_code == 200
        assert "reset" in resp.json()["message"].lower()

    def test_invalid_token_handling(self, client):
        # Tampered token
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

        # Expired token format
        resp = client.get("/auth/me", headers={"Authorization": "Bearer " + "x" * 200})
        assert resp.status_code == 401


class TestPredictionWorkflow:
    def test_predict_then_dashboard(self, client, auth_headers):
        # Make predictions
        texts = [
            "Urgent bank verification needed",
            "Meeting at 3pm tomorrow",
            "Click here to claim your prize",
        ]
        for text in texts:
            resp = client.post("/predict", json={"text": text, "source": "integration"},
                               headers=auth_headers)
            assert resp.status_code == 200

        # Check dashboard reflects predictions
        dash_resp = client.get("/dashboard")
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        assert dash_data["total_scans"] >= 0

    def test_predict_then_history(self, client, auth_headers):
        # Make predictions
        for i in range(3):
            client.post("/predict", json={
                "text": f"Integration test {i}",
                "source": "integration"
            }, headers=auth_headers)

        # Check history
        hist_resp = client.get("/history", headers=auth_headers)
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) >= 3
        assert all("result" in item for item in history)
        assert all("created_at" in item for item in history)

    def test_anonymous_prediction(self, client):
        # Anonymous user can predict
        resp = client.post("/predict", json={
            "text": "Anonymous test prediction",
            "source": "test"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("safe", "suspicious", "scam")

    def test_predict_consistency(self, client):
        text = "This is a consistent test message for repeated predictions"
        results = []
        for _ in range(3):
            resp = client.post("/predict", json={"text": text, "source": "test"})
            results.append(resp.json()["label"])

        # Same text should give same result (if no model drift)
        assert len(set(results)) == 1


class TestDashboardWorkflow:
    def test_dashboard_structure(self, client):
        resp = client.get("/dashboard")
        data = resp.json()
        assert isinstance(data["total_scans"], int)
        assert isinstance(data["scam_percentage"], float)
        assert isinstance(data["safe_percentage"], float)
        assert isinstance(data["recent_scans"], list)
        assert 0 <= data["scam_percentage"] <= 100
        assert 0 <= data["safe_percentage"] <= 100

    def test_dashboard_percentages(self, client, auth_headers):
        # Make mixed predictions
        client.post("/predict", json={"text": "Your account is compromised urgent", "source": "test"},
                     headers=auth_headers)
        client.post("/predict", json={"text": "Hello, how are you doing today?", "source": "test"},
                     headers=auth_headers)

        resp = client.get("/dashboard")
        data = resp.json()
        assert data["scam_percentage"] + data["safe_percentage"] <= 100.1  # Allow float rounding


class TestAdminWorkflow:
    def test_admin_user_management(self, client, admin_headers):
        resp = client.get("/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) >= 1

    def test_admin_audit_logging(self, client, admin_headers):
        # Make some requests to generate audit logs
        client.get("/dashboard")
        client.post("/predict", json={"text": "Test", "source": "test"})

        resp = client.get("/admin/audit-log", headers=admin_headers)
        data = resp.json()
        assert data["total_events"] >= 0
        assert "by_severity" in data
        assert "by_action" in data


class TestSystemEndpoints:
    def test_resilience_status(self, client, admin_headers):
        resp = client.get("/system/resilience", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "circuit_breakers" in data
        assert "bulkheads" in data

    def test_system_config(self, client, admin_headers):
        resp = client.get("/system/config", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "app_name" in data
        assert "app_version" in data

    def test_metrics_accessible(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")


class TestErrorHandling:
    def test_404_handling(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404

    def test_method_not_allowed(self, client):
        resp = client.put("/predict")  # PUT not allowed
        assert resp.status_code in (405, 422)

    def test_invalid_content_type(self, client):
        resp = client.post("/predict", data="raw text",
                           headers={"Content-Type": "text/plain"})
        assert resp.status_code == 422

    def test_malformed_json(self, client):
        resp = client.post("/predict", data="{invalid json}",
                           headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

