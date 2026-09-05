# Enterprise AI Mentor

Enterprise AI Mentor is a Socratic onboarding and capability-development desk for fictional NovaTech Solutions employees. Its defining rule is simple: **the system knows when not to give the answer**. Direct code and SQL requests become guided questions and progressive hints instead of copy-paste output.

## What is implemented

- Password authentication with signed expiring bearer tokens
- Employee roles, departments, and clearance levels 1-5
- Admin-only document indexing and aggregate analytics
- Clearance-aware document retrieval before mentor context construction
- PDF extraction, chunking, Chroma/OpenAI RAG when `LLM_API_KEY` is configured
- Local keyword retrieval fallback when no LLM key is present
- Deterministic intent detection for SQL, code, debug, compliance, architecture, conceptual, and normal requests
- Five-level Socratic assistance with follow-up questions and challenges
- Compliance feedback for unsafe approaches such as plaintext password storage
- Per-employee interaction history, explainable skill scores, and next-practice recommendations
- Responsive employee mentor desk with source badges, hint control, profile signals, and admin upload

## Architecture

`frontend/src/App.jsx` calls the FastAPI API. The backend authenticates the employee first, then the mentor service detects intent, checks compliance, filters documents by `required_clearance <= employee.clearance_level`, ranks authorized content, records the interaction, and updates the skill signal. Only after that deterministic work can optional LangChain/Chroma/OpenAI retrieval be used. Restricted documents are never included in the returned sources or model context.

## Setup

### Docker

1. Copy `.env.example` to `.env` and set a long `JWT_SECRET`.
2. Optionally set `LLM_API_KEY` to enable OpenAI embeddings and generation. The core guided mentor works without it.
3. Start the stack:

```bash
docker compose up --build
```

Open `http://localhost:5173`. The API is at `http://localhost:8000`.

### Local development

Backend on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000` for local frontend development. PostgreSQL is provided by Docker; SQLite can be used for tests.

## Configuration

`DATABASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `CHROMA_PATH`, `JWT_SECRET`, `TOKEN_EXPIRE_MINUTES`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `MAX_UPLOAD_BYTES`, and `VITE_API_URL` are documented in `.env.example`. `.env` is ignored by Git. When both admin variables are set, startup creates one hashed bootstrap administrator; public signup can never elevate privileges or choose a clearance level.

## Tests

```powershell
$env:PYTHONPATH="backend"
.venv\Scripts\python.exe -m pytest backend\tests -q
```

The tests cover protected routes, invalid login, intent/gatekeeper behavior, compliance findings, interaction/skill progress, and clearance filtering. Build the frontend with `npm run build` from `frontend`.

## Demo flow

1. Sign up as an employee and ask: `Write SQL to find all active employees`. The mentor identifies `SQL_REQUEST`, asks targeted questions, and increases guidance only through the hint control.
2. Ask: `Give me Python code to reverse a linked list`. The first response asks about pointer state and edge cases rather than dumping code.
3. Create a clearance-1 user and add a clearance-4 document. The document is excluded before retrieval and never appears in sources.
4. Ask: `I will store user passwords directly in PostgreSQL`. The compliance panel flags the high-severity issue and explains hashing.
5. Send several SQL or debugging questions. The profile creates a lower SQL/Testing signal and recommends a guided practice challenge.

## API highlights

- `POST /api/signup`, `POST /api/login`, `GET /api/auth/me`
- `POST /api/mentor/chat`, `GET /api/mentor/history`, `GET /api/mentor/progress`
- `GET /api/documents`
- `POST /api/admin/documents`, `GET /api/admin/analytics`
- `GET /health`

## Limitations and future work

The local fallback uses explainable keyword retrieval rather than semantic embeddings, and the current schema bootstrap is intended for a fresh demo database. A production deployment should add migrations, refresh-token rotation, object storage, richer PDF parsing, and a proper vector database service.
