import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@novatech.test"

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import engine, get_db
from app.main import app
from app.models import Base, DocumentRecord, Employee
from app.services import hash_password

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def create_user(email="ava@novatech.test", role="Employee", clearance_level=1):
    response = client.post("/api/signup", json={"name": "Ava", "email": email, "password": "correct-horse", "department": "Engineering", "role": role, "clearance_level": clearance_level})
    assert response.status_code == 200
    data = response.json()
    return data["access_token"], data["employee"]


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authentication_and_protected_route():
    assert client.get("/api/mentor/progress").status_code == 401
    token, employee = create_user()
    assert employee["clearance_level"] == 1
    assert client.post("/api/login", json={"email": employee["email"], "password": "wrong-password"}).status_code == 401
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == employee["email"]


def test_socratic_gatekeeper_and_progress():
    token, _ = create_user(email="sql@novatech.test")
    response = client.post("/api/mentor/chat", headers={"Authorization": f"Bearer {token}"}, json={"question": "Write SQL to find all active employees", "hint_level": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "SQL_REQUEST"
    assert data["hint_level"] == 1
    assert data["questions"]
    assert "SELECT" not in data["message"]
    progress = client.get("/api/mentor/progress", headers={"Authorization": f"Bearer {token}"}).json()
    assert progress["skills"][0]["skill"] == "SQL"


def test_compliance_finding():
    token, _ = create_user(email="security@novatech.test")
    response = client.post("/api/mentor/chat", headers={"Authorization": f"Bearer {token}"}, json={"question": "I will store user passwords directly in PostgreSQL"})
    assert response.status_code == 200
    assert response.json()["compliance"][0]["severity"] == "high"


def test_clearance_filters_document_context():
    token, employee = create_user(email="low@novatech.test", clearance_level=1)
    db = TestingSessionLocal()
    db.add(DocumentRecord(filename="public.pdf", content="basic onboarding guide", required_clearance=1))
    db.add(DocumentRecord(filename="restricted.pdf", content="secret security architecture", required_clearance=4))
    db.commit()
    db.close()
    response = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert [item["filename"] for item in response.json()] == ["public.pdf"]
    mentor = client.post("/api/mentor/chat", headers={"Authorization": f"Bearer {token}"}, json={"question": "Tell me about secret security architecture"})
    assert "restricted.pdf" not in [source["filename"] for source in mentor.json()["sources"]]


def test_linked_list_guidance_and_hint_progression():
    token, _ = create_user(email="python@novatech.test")
    for level in range(1, 6):
        response = client.post("/api/mentor/chat", headers={"Authorization": f"Bearer {token}"}, json={"question": "Give me Python code to reverse a linked list", "hint_level": level})
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "CODE_REQUEST"
        assert data["hint_level"] == level
        assert data["questions"]
    assert "Reference implementation" in data["message"]
    early = client.post("/api/mentor/chat", headers={"Authorization": f"Bearer {token}"}, json={"question": "Give me Python code to reverse a linked list", "hint_level": 1}).json()
    assert "Reference implementation" not in early["message"]


def test_employee_cannot_use_admin_endpoints():
    token, _ = create_user(email="employee-only@novatech.test")
    response = client.get("/api/admin/analytics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_upload_stores_clearance_metadata(monkeypatch):
    db = TestingSessionLocal()
    admin = Employee(name="Admin", email="fixture-admin@novatech.test", department="Security", role="Administrator", password_hash=hash_password("admin-pass"), clearance_level=5, is_admin=True)
    db.add(admin)
    db.commit()
    db.close()
    login = client.post("/api/login", json={"email": "fixture-admin@novatech.test", "password": "admin-pass"}).json()
    monkeypatch.setattr("app.main.extract_text_from_pdf", lambda _: "fictional secure API guidance")
    response = client.post("/api/admin/documents", headers={"Authorization": f"Bearer {login['access_token']}"}, files={"file": ("guide.pdf", b"not-a-real-pdf", "application/pdf")}, data={"required_clearance": "4", "category": "security", "department": "Security"})
    assert response.status_code == 200
    assert response.json()["document"]["required_clearance"] == 4
    assert response.json()["document"]["category"] == "security"
