"""Tests for investigation API endpoints."""


class TestInvestigationHealth:
    def test_health_endpoint(self, client):
        response = client.get("/api/investigation/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["module"] == "investigation"


class TestCreateCase:
    def test_create_case_without_auth(self, client):
        response = client.post(
            "/api/investigation/cases",
            json={"title": "Test case", "case_type": "phishing"},
        )
        assert response.status_code == 401

    def test_create_case_with_auth(self, client, auth_headers):
        response = client.post(
            "/api/investigation/cases",
            json={"title": "Phishing investigation", "case_type": "phishing", "priority": "high"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Phishing investigation"
        assert data["case_type"] == "phishing"
        assert data["priority"] == "high"
        assert data["status"] == "open"
        assert "id" in data

    def test_create_case_empty_title(self, client, auth_headers):
        response = client.post(
            "/api/investigation/cases",
            json={"title": "", "case_type": "phishing"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestListCases:
    def test_list_cases(self, client, auth_headers):
        response = client.get("/api/investigation/cases", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_list_cases_pagination(self, client, auth_headers):
        response = client.get(
            "/api/investigation/cases?page=1&page_size=5",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_list_cases_filter_by_status(self, client, auth_headers):
        response = client.get(
            "/api/investigation/cases?status=open",
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestGetCase:
    def test_get_nonexistent_case(self, client, auth_headers):
        response = client.get("/api/investigation/cases/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_case_success(self, client, auth_headers):
        # Create a case first
        create_resp = client.post(
            "/api/investigation/cases",
            json={"title": "Get test case", "case_type": "scam"},
            headers=auth_headers,
        )
        case_id = create_resp.json()["id"]

        response = client.get(f"/api/investigation/cases/{case_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Get test case"


class TestUpdateCase:
    def test_update_case_status(self, client, auth_headers):
        create_resp = client.post(
            "/api/investigation/cases",
            json={"title": "Update test", "case_type": "fraud"},
            headers=auth_headers,
        )
        case_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/investigation/cases/{case_id}",
            json={"status": "in_progress", "priority": "critical"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"
        assert data["priority"] == "critical"


class TestEvidence:
    def test_add_evidence(self, client, auth_headers):
        create_resp = client.post(
            "/api/investigation/cases",
            json={"title": "Evidence test", "case_type": "phishing"},
            headers=auth_headers,
        )
        case_id = create_resp.json()["id"]

        response = client.post(
            f"/api/investigation/cases/{case_id}/evidence",
            json={"evidence_type": "email", "title": "Phishing email", "content": "Full email"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["evidence_type"] == "email"
        assert data["title"] == "Phishing email"


class TestNotes:
    def test_add_note(self, client, auth_headers):
        create_resp = client.post(
            "/api/investigation/cases",
            json={"title": "Note test", "case_type": "other"},
            headers=auth_headers,
        )
        case_id = create_resp.json()["id"]

        response = client.post(
            f"/api/investigation/cases/{case_id}/notes",
            json={"content": "Important finding"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Important finding"


class TestStats:
    def test_investigation_stats(self, client, auth_headers):
        response = client.get("/api/investigation/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_cases" in data
        assert "open_cases" in data
        assert "critical_cases" in data


class TestDeleteCase:
    def test_delete_case(self, client, auth_headers):
        create_resp = client.post(
            "/api/investigation/cases",
            json={"title": "Delete test", "case_type": "other"},
            headers=auth_headers,
        )
        case_id = create_resp.json()["id"]

        response = client.delete(f"/api/investigation/cases/{case_id}", headers=auth_headers)
        assert response.status_code == 204

