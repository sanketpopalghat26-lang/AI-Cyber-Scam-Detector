"""
End-to-end tests for complete user workflows.
Tests: full user journeys, cross-component integration.
"""
from fastapi.testclient import TestClient

from backend.app.main import app


class TestUserJourney:
    def test_complete_user_flow(self):
        """Complete user journey: signup -> predict -> history -> report -> logout."""
        client = TestClient(app)

        # 1. Signup
        signup_resp = client.post("/auth/signup", json={
            "email": "journey@test.com",
            "password": "JourneyP@ss1"
        })
        assert signup_resp.status_code == 200
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Check profile
        me_resp = client.get("/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "journey@test.com"

        # 3. Make predictions
        predict_resp = client.post("/predict", json={
            "text": "Urgent: Your account has been compromised",
            "source": "e2e"
        }, headers=headers)
        assert predict_resp.status_code == 200
        scan_id = predict_resp.json().get("scan_id")

        # 4. View dashboard
        dash_resp = client.get("/dashboard")
        assert dash_resp.status_code == 200

        # 5. View history
        history_resp = client.get("/history", headers=headers)
        assert history_resp.status_code == 200
        assert len(history_resp.json()) >= 1

        # 6. Submit feedback
        feedback_resp = client.post("/feedback", json={
            "message": "Great tool, very useful!"
        }, headers=headers)
        assert feedback_resp.status_code == 200

        # 7. Logout
        logout_resp = client.post("/auth/logout", headers=headers)
        assert logout_resp.status_code == 200

        # 8. Verify token invalidated
        me_resp2 = client.get("/auth/me", headers=headers)
        assert me_resp2.status_code == 401

    def test_anonymous_user_flow(self):
        """Anonymous user flow: predict -> dashboard."""
        client = TestClient(app)

        # 1. Predict without auth
        predict_resp = client.post("/predict", json={
            "text": "Free money! Click here to claim your prize!",
            "source": "e2e"
        })
        assert predict_resp.status_code == 200
        data = predict_resp.json()
        assert "label" in data
        assert "explanation" in data

        # 2. Dashboard works
        dash_resp = client.get("/dashboard")
        assert dash_resp.status_code == 200

    def test_admin_flow(self):
        """Admin flow: login -> manage users -> audit log."""
        client = TestClient(app)

        import uuid
        suffix = uuid.uuid4().hex[:8]
        admin_email = f"admin_e2e_{suffix}@test.com"

        # Create and promote admin
        signup_resp = client.post("/auth/signup", json={
            "email": admin_email,
            "password": "Xyz9#K2m!QpR"
        })
        assert signup_resp.status_code == 200, f"Signup failed: {signup_resp.text}"
        login_resp = client.post("/auth/login", data={
            "username": admin_email,
            "password": "Xyz9#K2m!QpR"
        })
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Promote to admin via DB
        from sqlmodel import Session, text

        from backend.app.core.db import engine
        with Session(engine) as session:
            session.exec(text(f"UPDATE users SET is_admin = 1 WHERE email = '{admin_email}'"))
            session.commit()

        # View users
        users_resp = client.get("/admin/users", headers=headers)
        assert users_resp.status_code == 200

        # View audit log
        audit_resp = client.get("/admin/audit-log", headers=headers)
        assert audit_resp.status_code == 200

        # View resilience
        resilience_resp = client.get("/system/resilience", headers=headers)
        assert resilience_resp.status_code == 200

    def test_error_scenarios(self):
        """Test error handling scenarios."""
        client = TestClient(app)

        # 1. Invalid endpoint
        assert client.get("/invalid").status_code == 404

        # 2. Invalid method
        assert client.put("/health").status_code in (405, 422)

        # 3. Unauthorized access
        assert client.get("/admin/users").status_code == 401

        # 4. Invalid input
        assert client.post("/predict", json={"text": ""}).status_code == 422

        # 5. Invalid auth
        assert client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


class TestPredictionAccuracy:
    def test_scam_detection(self):
        """Verify scam detection catches high-risk messages."""
        client = TestClient(app)
        scam_messages = [
            "Urgent: Your bank account has been compromised. Click here to secure it.",
            "You have won $1,000,000! Claim your prize now by providing your bank details.",
            "Your Netflix account is suspended. Verify your payment immediately.",
            "IRS notification: You owe back taxes. Pay now to avoid arrest.",
            "Congrats! You've been selected for a free iPhone. Click here to claim.",
        ]
        for msg in scam_messages:
            resp = client.post("/predict", json={"text": msg, "source": "e2e"})
            assert resp.status_code == 200
            data = resp.json()
            # Should flag as scam or suspicious
            assert data["label"] in ("scam", "suspicious"), f"Missed scam: {msg[:50]}"

    def test_safe_detection(self):
        """Verify normal messages are not flagged as scams."""
        client = TestClient(app)
        safe_messages = [
            "Hey, are we still meeting for lunch tomorrow?",
            "The project deadline has been extended to next Friday.",
            "Please find attached the quarterly report for review.",
            "Reminder: Team standup at 10 AM tomorrow morning.",
            "Thanks for your help with the presentation yesterday.",
        ]
        for msg in safe_messages:
            resp = client.post("/predict", json={"text": msg, "source": "e2e"})
            assert resp.status_code == 200
            data = resp.json()
            # Should be safe
            assert data["label"] in ("safe", "suspicious"), f"False positive: {msg[:50]}"


class TestAPIContract:
    """Test API contract compliance."""

    def test_health_contract(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "model_status" in body
        assert "timestamp" in body

    def test_predict_contract(self):
        client = TestClient(app)
        resp = client.post("/predict", json={
            "text": "Test message for API contract",
            "source": "contract_test"
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "label" in body
        assert "confidence" in body
        assert "explanation" in body
        assert isinstance(body["label"], str)
        assert isinstance(body["confidence"], (int, float))
        assert isinstance(body["explanation"], dict)

    def test_predict_explanation_contract(self):
        client = TestClient(app)
        resp = client.post("/predict", json={
            "text": "Test message for explanation contract",
            "source": "contract_test"
        })
        body = resp.json()
        expl = body["explanation"]
        assert "keywords" in expl
        assert "reason" in expl
        assert "risk_level" in expl
        assert "safety_advice" in expl
        assert "simple_explanation" in expl
        assert "source" in expl
        assert "confidence" in expl

    def test_auth_signup_contract(self):
        client = TestClient(app)
        resp = client.post("/auth/signup", json={
            "email": "contract@test.com",
            "password": "ContractP@ss1"
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert "token_type" in body
        assert "expires_in" in body
        assert body["token_type"] == "bearer"

    def test_auth_login_contract(self):
        client = TestClient(app)
        client.post("/auth/signup", json={
            "email": "contract_login@test.com",
            "password": "ContractP@ss1"
        })
        resp = client.post("/auth/login", data={
            "username": "contract_login@test.com",
            "password": "ContractP@ss1"
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert "expires_in" in body

    def test_error_contract(self):
        client = TestClient(app)
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        body = resp.json()
        assert "detail" in body

