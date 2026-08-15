import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_signup_and_login_flow():
    signup_response = client.post(
        '/api/signup',
        json={
            'name': 'Ava',
            'email': 'ava@company.com',
            'department': 'HR',
            'role': 'Manager',
        },
    )
    assert signup_response.status_code == 200

    login_response = client.post('/api/login', json={'email': 'ava@company.com'})
    assert login_response.status_code == 200
    assert login_response.json()['employee']['email'] == 'ava@company.com'

