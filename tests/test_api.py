import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# ── Make app/ importable ──────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

# ── Set env vars BEFORE importing app ────────────────────
os.environ.setdefault("DB_HOST",          "localhost")
os.environ.setdefault("DB_PORT",          "3306")
os.environ.setdefault("DB_NAME",          "patientdb")
os.environ.setdefault("DB_USER",          "patientuser")
os.environ.setdefault("DB_PASSWORD",      "patientpass")
os.environ.setdefault("AES_SECRET_KEY",   "MySuperSecretKey1234567890123456")
os.environ.setdefault("KEYCLOAK_URL",     "http://localhost:8080")
os.environ.setdefault("KEYCLOAK_REALM",   "patient-realm")
os.environ.setdefault("KEYCLOAK_CLIENT_ID", "patient-client")


# ── Fake JWT claims for each role ─────────────────────────
EDITOR_CLAIMS = {
    "sub": "editor-user-001",
    "preferred_username": "lab_editor",
    "realm_access": {"roles": ["editor"]},
}

VIEWER_CLAIMS = {
    "sub": "viewer-user-002",
    "preferred_username": "lab_viewer",
    "realm_access": {"roles": ["viewer"]},
}


# ── Pytest Fixture: Flask test client ─────────────────────
@pytest.fixture
def client():
    """
    Create a Flask test client using SQLite in-memory DB
    so tests never need a real MySQL or Keycloak connection.
    """
    with patch("database.db") as mock_db:
        from main import app
        app.config["TESTING"]                  = True
        app.config["SQLALCHEMY_DATABASE_URI"]  = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        with app.test_client() as client:
            yield client


# ═══════════════════════════════════════════════════════════
# TEST 1 — Health Check (public, no auth)
# ═══════════════════════════════════════════════════════════
def test_health_check(client):
    """GET /health should return 200 with no token."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    print("✅ TEST 1 PASSED: Health check works")


# ═══════════════════════════════════════════════════════════
# TEST 2 — POST /patient (editor role → should succeed 201)
# ═══════════════════════════════════════════════════════════
@patch("auth.decode_token", return_value=EDITOR_CLAIMS)
@patch("models.db.session")
def test_create_patient_as_editor(mock_session, mock_decode, client):
    """Editor POSTing a patient should return 201."""

    # Mock the patient save
    mock_patient        = MagicMock()
    mock_patient.id     = 1
    mock_session.add    = MagicMock()
    mock_session.commit = MagicMock()

    with patch("main.Patient") as MockPatient:
        instance = MockPatient.return_value
        instance.id = 1
        instance.set_data = MagicMock()

        response = client.post(
            "/patient",
            json={
                "name":      "John Doe",
                "age":       "35",
                "diagnosis": "Hypertension"
            },
            headers={"Authorization": "Bearer fake-editor-token"}
        )

    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data
    assert data["message"] == "Patient created successfully"
    print("✅ TEST 2 PASSED: Editor can create patient")


# ═══════════════════════════════════════════════════════════
# TEST 3 — POST /patient (viewer role → should fail 403)
# ═══════════════════════════════════════════════════════════
@patch("auth.decode_token", return_value=VIEWER_CLAIMS)
def test_create_patient_as_viewer(mock_decode, client):
    """Viewer POSTing a patient should be rejected with 403."""
    response = client.post(
        "/patient",
        json={
            "name":      "Jane Doe",
            "age":       "28",
            "diagnosis": "Diabetes"
        },
        headers={"Authorization": "Bearer fake-viewer-token"}
    )
    assert response.status_code == 403
    data = response.get_json()
    assert data["error"] == "Access denied"
    assert "viewer" in data["your_roles"]
    print("✅ TEST 3 PASSED: Viewer cannot create patient (403)")


# ═══════════════════════════════════════════════════════════
# TEST 4 — GET /patient/<id> (viewer role → should succeed)
# ═══════════════════════════════════════════════════════════
@patch("auth.decode_token", return_value=VIEWER_CLAIMS)
@patch("models.Patient.query")
def test_get_patient_as_viewer(mock_query, mock_decode, client):
    """Viewer GETting a single patient should return 200."""
    mock_patient = MagicMock()
    mock_patient.get_data.return_value = {
        "id":        1,
        "name":      "John Doe",
        "age":       "35",
        "diagnosis": "Hypertension"
    }
    mock_query.get.return_value = mock_patient

    response = client.get(
        "/patient/1",
        headers={"Authorization": "Bearer fake-viewer-token"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"]      == "John Doe"
    assert data["diagnosis"] == "Hypertension"
    print("✅ TEST 4 PASSED: Viewer can read single patient")


# ═══════════════════════════════════════════════════════════
# TEST 5 — GET /patients (editor role → should succeed)
# ═══════════════════════════════════════════════════════════
@patch("auth.decode_token", return_value=EDITOR_CLAIMS)
@patch("models.Patient.query")
def test_get_all_patients_as_editor(mock_query, mock_decode, client):
    """Editor GETting all patients should return a list."""
    mock_p1 = MagicMock()
    mock_p1.get_data.return_value = {
        "id": 1, "name": "John Doe",
        "age": "35", "diagnosis": "Hypertension"
    }
    mock_p2 = MagicMock()
    mock_p2.get_data.return_value = {
        "id": 2, "name": "Jane Doe",
        "age": "28", "diagnosis": "Diabetes"
    }
    mock_query.all.return_value = [mock_p1, mock_p2]

    response = client.get(
        "/patients",
        headers={"Authorization": "Bearer fake-editor-token"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "John Doe"
    assert data[1]["name"] == "Jane Doe"
    print("✅ TEST 5 PASSED: Editor can retrieve all patients")


# ═══════════════════════════════════════════════════════════
# TEST 6 — POST /patient with missing fields → 400
# ═══════════════════════════════════════════════════════════
@patch("auth.decode_token", return_value=EDITOR_CLAIMS)
def test_create_patient_missing_fields(mock_decode, client):
    """POST with incomplete data should return 400."""
    response = client.post(
        "/patient",
        json={"name": "Incomplete Patient"},   # missing age & diagnosis
        headers={"Authorization": "Bearer fake-editor-token"}
    )
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    print("✅ TEST 6 PASSED: Missing fields returns 400")


# ═══════════════════════════════════════════════════════════
# TEST 7 — No token → 401
# ═══════════════════════════════════════════════════════════
def test_no_token_returns_401(client):
    """Calling protected endpoint with no token should return 401."""
    response = client.get("/patients")
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "Missing token"
    print("✅ TEST 7 PASSED: No token returns 401")