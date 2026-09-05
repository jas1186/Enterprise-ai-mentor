from pathlib import Path
from typing import Annotated, List

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import ADMIN_EMAIL, ADMIN_PASSWORD, MAX_UPLOAD_BYTES
from app.database import SessionLocal, get_db, init_db
from app.models import Employee, MentorshipInteraction, SkillProgress
from app.services import (
    create_token,
    decode_token,
    extract_text_from_pdf,
    get_recommendations,
    hash_password,
    list_documents,
    mentor_response,
    save_uploaded_document,
    verify_password,
)

app = FastAPI(title="Enterprise AI Mentor API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        db = SessionLocal()
        try:
            if not db.query(Employee).filter(Employee.email == ADMIN_EMAIL.strip().lower()).first():
                db.add(Employee(name="NovaTech Admin", email=ADMIN_EMAIL.strip().lower(), department="Security", role="Administrator", password_hash=hash_password(ADMIN_PASSWORD), clearance_level=5, is_admin=True))
                db.commit()
        finally:
            db.close()


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    department: str = Field(min_length=2, max_length=255)
    role: str = Field(min_length=2, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    hint_level: int = Field(default=1, ge=1, le=5)


def current_employee(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Employee:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        employee_id = decode_token(authorization.split(" ", 1)[1])
    except (ValueError, KeyError, IndexError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return employee


def admin_employee(employee: Employee = Depends(current_employee)) -> Employee:
    if not employee.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return employee


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Enterprise AI Mentor backend is running"}


@app.post("/api/signup")
def signup(request: SignupRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    email = request.email.strip().lower()
    if db.query(Employee).filter(Employee.email == email).first():
        raise HTTPException(status_code=400, detail="Employee already exists")
    employee = Employee(
        name=request.name.strip(), email=email, department=request.department.strip(), role=request.role.strip(),
        password_hash=hash_password(request.password), clearance_level=1, is_admin=False,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return {"message": "Signup successful", "employee": employee.to_dict(), "access_token": create_token(employee)}


@app.post("/api/login")
def login(request: LoginRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    employee = db.query(Employee).filter(Employee.email == request.email.strip().lower()).first()
    if not employee or not verify_password(request.password, employee.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"message": "Login successful", "employee": employee.to_dict(), "access_token": create_token(employee)}


@app.get("/api/auth/me")
def me(employee: Employee = Depends(current_employee)) -> dict[str, object]:
    return employee.to_dict()


@app.post("/api/mentor/chat")
@app.post("/api/chat")
def chat(request: ChatRequest, employee: Employee = Depends(current_employee), db: Session = Depends(get_db)) -> dict[str, object]:
    return mentor_response(db, employee, request.question, request.hint_level)


@app.get("/api/mentor/progress")
def progress(employee: Employee = Depends(current_employee), db: Session = Depends(get_db)) -> dict[str, object]:
    skills = db.query(SkillProgress).filter(SkillProgress.user_id == employee.id).order_by(SkillProgress.score).all()
    return {"skills": [{"skill": item.skill, "score": round(item.score)} for item in skills], "recommendations": get_recommendations(db, employee)}


@app.get("/api/mentor/history")
def history(employee: Employee = Depends(current_employee), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    interactions = db.query(MentorshipInteraction).filter(MentorshipInteraction.user_id == employee.id).order_by(MentorshipInteraction.created_at.desc()).limit(20).all()
    return [{"query": item.query, "intent": item.intent, "hint_level": item.hint_level, "topic": item.topic, "created_at": item.created_at.isoformat()} for item in interactions]


@app.post("/api/admin/documents")
@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), required_clearance: int = Form(1), category: str = Form("general"), department: str = Form(""), _: Employee = Depends(admin_employee), db: Session = Depends(get_db)) -> dict[str, object]:
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    if not 1 <= required_clearance <= 5:
        raise HTTPException(status_code=422, detail="Required clearance must be between 1 and 5")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit")
    safe_name = Path(file.filename).name
    upload_path = Path("./uploads") / safe_name
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(content)
    try:
        text = extract_text_from_pdf(str(upload_path))
        if not text.strip():
            raise HTTPException(status_code=400, detail="The PDF contains no readable text")
        document = save_uploaded_document(db, safe_name, text, required_clearance=required_clearance, category=category.strip()[:100] or "general", department=department.strip()[:255] or None)
    except HTTPException:
        upload_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not process document: {exc}")
    return {"message": "Document uploaded", "document": document.to_dict()}


@app.get("/api/documents", response_model=List[dict[str, object]])
def get_documents(employee: Employee = Depends(current_employee), db: Session = Depends(get_db)) -> List[dict[str, object]]:
    return [{**doc.to_dict(), "content": None} for doc in list_documents(db) if doc.required_clearance <= employee.clearance_level]


@app.get("/api/admin/analytics")
def analytics(_: Employee = Depends(admin_employee), db: Session = Depends(get_db)) -> dict[str, object]:
    interactions = db.query(MentorshipInteraction).all()
    topics: dict[str, int] = {}
    intents: dict[str, int] = {}
    for item in interactions:
        topics[item.topic] = topics.get(item.topic, 0) + 1
        intents[item.intent] = intents.get(item.intent, 0) + 1
    return {"employee_count": db.query(Employee).count(), "interaction_count": len(interactions), "topics": topics, "intents": intents, "average_hint_level": round(sum(item.hint_level for item in interactions) / len(interactions), 2) if interactions else 0}
