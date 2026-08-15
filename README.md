# Enterprise AI Mentor MVP

## 1. Project architecture

This MVP combines a React + Tailwind frontend, a Python FastAPI backend, PostgreSQL for structured data, and a RAG pipeline powered by LangChain, OpenAI-compatible LLMs, and ChromaDB.

### High-level architecture
- Frontend: React.js with Tailwind CSS for login, chat UI, and admin upload panel.
- Backend: FastAPI for authentication, document management, chat endpoints, and API orchestration.
- Database: PostgreSQL stores employee accounts and uploaded document metadata.
- AI layer: LLM integration for question answering and LangChain + ChromaDB for retrieval.

### Suggested folder structure
```text
enterprise-ai-mentor/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── core/
│   │   ├── models/
│   │   ├── services/
│   │   ├── utils/
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── tailwind.config.js
├── database/
│   └── init.sql
├── docker-compose.yml
├── .env.example
└── README.md
```

## 2. Required dependencies

### Backend
- fastapi
- uvicorn
- python-dotenv
- sqlalchemy
- psycopg[binary]
- langchain
- langchain-community
- langchain-openai
- chromadb
- pypdf
- pytest

### Frontend
- react
- react-dom
- vite
- tailwindcss
- postcss
- autoprefixer

## 3. Step-by-step implementation plan

1. Create the workspace structure and initial documentation.
2. Build the React frontend shell with login, chat, and admin views.
3. Build the FastAPI backend with health checks and placeholder chat endpoints.
4. Set up PostgreSQL and create tables for employees and documents.
5. Integrate an LLM API and build the document ingestion flow.
6. Implement the RAG pipeline with LangChain and ChromaDB.
7. Add document upload and admin listing features.
8. Test the chat flow end to end and refine the UX.

## 4. Installation commands

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Database
```bash
docker compose up -d
```

## 5. Testing steps

- Run backend health check: `curl http://localhost:8000/health`
- Open the frontend at `http://localhost:5173`
- Upload a sample PDF via the admin panel
- Ask a question in the chat UI and verify that the answer comes from document context

## 6. Next implementation milestone

The next step is to wire the frontend to the backend, add authentication and document upload, and then connect the RAG workflow to the LLM.
