import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://admin:admin123@localhost:5432/enterprise_ai_mentor")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
