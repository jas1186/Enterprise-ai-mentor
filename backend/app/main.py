from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Employee
from app.database import get_db, init_db
from app.services import answer_with_rag, extract_text_from_pdf, list_documents, save_uploaded_document

app = FastAPI(title="Enterprise AI Mentor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Initialize the database on startup."""
    init_db()


class SignupRequest(BaseModel):
    name: str
    email: str
    department: str
    role: str


class LoginRequest(BaseModel):
    email: str


class ChatRequest(BaseModel):
    question: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Enterprise AI Mentor backend is running"}


@app.post("/api/signup")
def signup(request: SignupRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    existing_employee = db.query(Employee).filter(
        Employee.email.ilike(request.email)
    ).first()
    
    if existing_employee:
        raise HTTPException(status_code=400, detail="Employee already exists")

    employee = Employee(
        name=request.name,
        email=request.email,
        department=request.department,
        role=request.role,
    )
    
    try:
        db.add(employee)
        db.commit()
        db.refresh(employee)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Employee already exists")
    
    return {"message": "Signup successful", "employee": employee.to_dict()}


@app.post("/api/login")
def login(request: LoginRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    employee = db.query(Employee).filter(
        Employee.email.ilike(request.email)
    ).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {"message": "Login successful", "employee": employee.to_dict()}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, str]:
    try:
        answer = answer_with_rag(request.question)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"answer": answer}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    upload_path = Path("./uploads") / file.filename
    with upload_path.open("wb") as target:
        content = await file.read()
        target.write(content)

    text = extract_text_from_pdf(str(upload_path))
    try:
        document = save_uploaded_document(db, file.filename, text)
    except ValueError as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc))
    return {"message": "Document uploaded", "document": document.to_dict()}


@app.get("/api/documents", response_model=List[dict[str, str]])
def get_documents(db: Session = Depends(get_db)) -> List[dict[str, str]]:
    documents = list_documents(db)
    return [{"filename": doc.filename, "content": doc.content[:200]} for doc in documents]
