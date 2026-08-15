from pathlib import Path
from typing import List

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.ai import ingest_document, answer_question
from app.models import DocumentRecord
from app.utils import ensure_upload_dir

UPLOAD_DIR = Path("./uploads")
ensure_upload_dir()


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text_chunks = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(chunk for chunk in text_chunks if chunk)


def save_uploaded_document(db: Session, filename: str, content: str) -> DocumentRecord:
    document = DocumentRecord(filename=filename, content=content)
    db.add(document)
    db.commit()
    db.refresh(document)
    ingest_document(filename, content)
    return document


def list_documents(db: Session) -> List[DocumentRecord]:
    return db.query(DocumentRecord).all()


def answer_with_rag(question: str) -> str:
    return answer_question(question)
