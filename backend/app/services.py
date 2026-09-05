from pathlib import Path
from typing import Any, List
import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import JWT_SECRET, LLM_API_KEY, TOKEN_EXPIRE_MINUTES
from app.models import DocumentRecord, Employee, MentorshipInteraction, SkillProgress
from app.utils import ensure_upload_dir

UPLOAD_DIR = Path("./uploads")
ensure_upload_dir()


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text_chunks = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(chunk for chunk in text_chunks if chunk)


def save_uploaded_document(db: Session, filename: str, content: str, required_clearance: int = 1, category: str = "general", department: str | None = None) -> DocumentRecord:
    document = DocumentRecord(filename=filename, content=content, required_clearance=required_clearance, category=category, department=department)
    db.add(document)
    db.flush()
    if LLM_API_KEY:
        from app.ai import ingest_document
        try:
            ingest_document(document.id, filename, content, required_clearance, category, department)
        except Exception:
            db.rollback()
            raise
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session) -> List[DocumentRecord]:
    return db.query(DocumentRecord).all()


def answer_with_rag(question: str) -> str:
    from app.ai import answer_question

    return answer_question(question)


def hash_password(password: str) -> str:
    salt = hashlib.sha256(f"{JWT_SECRET}:{password}".encode()).hexdigest()[:32]
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
        return hmac.compare_digest(actual, expected)
    except ValueError:
        return False


def create_token(employee: Employee) -> str:
    payload = {"sub": employee.id, "exp": int((datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)).timestamp())}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_token(token: str) -> int:
    encoded, signature = token.split(".", 1)
    expected = hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid token")
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    if payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Token expired")
    return int(payload["sub"])


INTENT_PATTERNS = {
    "SQL_REQUEST": r"\b(sql|select|join|query|database)\b",
    "CODE_REQUEST": r"\b(write|give|generate|implement|code|function|reverse|python|javascript)\b",
    "DEBUG_REQUEST": r"\b(fix|debug|error|bug|broken|fails|exception)\b",
    "DIRECT_ANSWER_REQUEST": r"\b(just|complete|full|direct|answer|solution)\b",
    "COMPLIANCE_QUERY": r"\b(password|security|secure|compliance|standard|plaintext)\b",
    "DOCUMENTATION_QUERY": r"\b(document|documentation|handbook|guideline|policy|standard)\b",
    "LEARNING_QUERY": r"\b(learn|practice|training|improve|study)\b",
    "ARCHITECTURE_QUESTION": r"\b(architecture|design|service|api|system)\b",
    "CONCEPTUAL_QUESTION": r"\b(why|how does|explain|concept|difference)\b",
}


def detect_intent(query: str) -> str:
    for intent, pattern in INTENT_PATTERNS.items():
        if re.search(pattern, query.lower()):
            return intent
    return "NORMAL_CONVERSATION"


def topic_for_intent(intent: str) -> str:
    return {"SQL_REQUEST": "SQL", "CODE_REQUEST": "Python", "DEBUG_REQUEST": "Testing", "COMPLIANCE_QUERY": "Security", "ARCHITECTURE_QUESTION": "APIs"}.get(intent, "General")


def compliance_findings(query: str) -> list[dict[str, str]]:
    if re.search(r"(store|save|keep).{0,30}(password|credential).{0,20}(plain|direct|text)", query.lower()):
        return [{"issue": "Plaintext credential storage", "severity": "high", "principle": "Secure password handling", "guidance": "Use a slow one-way password hash and verify it during login."}]
    return []


def authorized_documents(db: Session, employee: Employee, query: str) -> list[DocumentRecord]:
    documents = db.query(DocumentRecord).filter(DocumentRecord.required_clearance <= employee.clearance_level).all()
    words = {word for word in re.findall(r"[a-zA-Z]{4,}", query.lower())}
    ranked = sorted(documents, key=lambda doc: sum(word in doc.content.lower() for word in words), reverse=True)
    return [doc for doc in ranked if not words or any(word in doc.content.lower() for word in words)][:4]


def mentor_response(db: Session, employee: Employee, query: str, hint_level: int = 1) -> dict[str, Any]:
    intent = detect_intent(query)
    topic = topic_for_intent(intent)
    findings = compliance_findings(query)
    documents = authorized_documents(db, employee, query)
    questions = {
        "SQL_REQUEST": ["Which table contains the records?", "Which column and value represent the state you need?", "What index would help if this table is large?"],
        "CODE_REQUEST": ["What is the expected input and output?", "Which state or pointer changes on each step?", "What edge case would you test first?"],
        "DEBUG_REQUEST": ["What behavior did you expect?", "What is the smallest failing test case?", "Which line first violates that expectation?"],
    }.get(intent, ["What have you tried so far?", "What constraint matters most here?"])
    levels = ["Let's reason through the problem before writing the final answer.", "Hint: identify the relevant concept and test it with a small example.", "Architecture hint: separate the decision into small, independently testable steps.", "Implementation guidance: write pseudocode first, then validate each branch with a test.", "Reference solutions are available after you show your attempt and explain the result."]
    message = levels[max(0, min(hint_level, 5) - 1)]
    if hint_level >= 5 and intent == "CODE_REQUEST" and "linked list" in query.lower():
        message = "Reference implementation after guided practice: set prev = None, walk current through the list, save current.next before redirecting it to prev, then advance both pointers and return prev."
    elif hint_level >= 5 and intent == "SQL_REQUEST":
        message = "Reference pattern: SELECT the needed columns FROM the identified table WHERE the status column equals the agreed active value; add an index on the filter column for a large table."
    if findings:
        message = "This approach raises a compliance concern. Think about why credentials must not be stored in plaintext."
    elif documents:
        message += f" I found {len(documents)} authorized source(s) to ground the next step."
    interaction = MentorshipInteraction(user_id=employee.id, query=query, intent=intent, hint_level=max(1, min(hint_level, 5)), topic=topic, compliance_issue=bool(findings), sources=",".join(doc.filename for doc in documents))
    db.add(interaction)
    skill = db.query(SkillProgress).filter(SkillProgress.user_id == employee.id, SkillProgress.skill == topic).first()
    if not skill:
        skill = SkillProgress(user_id=employee.id, skill=topic, score=50)
        db.add(skill)
    skill.score = max(0, min(100, skill.score - (5 if intent in {"SQL_REQUEST", "CODE_REQUEST", "DEBUG_REQUEST"} else 0) + (3 if hint_level >= 3 else 0)))
    db.commit()
    rag_answer = ""
    rag_sources = []
    if LLM_API_KEY and intent in {"DOCUMENTATION_QUERY", "CONCEPTUAL_QUESTION"}:
        try:
            from app.ai import answer_authorized_question
            rag_answer, rag_sources = answer_authorized_question(query, employee.clearance_level, employee.department)
        except Exception:
            rag_sources = []
    if rag_answer and "could not find" not in rag_answer.lower():
        message += f" Authorized guidance: {rag_answer}"
    source_names = {source.get("filename") or source.get("source") for source in rag_sources}
    sources = [doc.to_dict() | {"content": None} for doc in documents if not LLM_API_KEY or intent not in {"DOCUMENTATION_QUERY", "CONCEPTUAL_QUESTION"} or doc.filename in source_names]
    return {"mode": "guided", "hint_level": max(1, min(hint_level, 5)), "intent": intent, "message": message, "questions": questions[:max(1, min(hint_level, 3))], "sources": sources, "compliance": findings, "challenge": f"Explain your approach to the {topic} problem in two sentences."}


def get_recommendations(db: Session, employee: Employee) -> list[dict[str, Any]]:
    skills = db.query(SkillProgress).filter(SkillProgress.user_id == employee.id).order_by(SkillProgress.score).all()
    return [{"skill": skill.skill, "score": round(skill.score), "recommendation": f"Practice {skill.skill} with a small guided challenge."} for skill in skills[:3]]
