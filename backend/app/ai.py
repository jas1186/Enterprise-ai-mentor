from pathlib import Path
from typing import List

from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import CHROMA_PATH, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

CHROMA_COLLECTION_NAME = "enterprise_ai_mentor"

PROMPT_TEMPLATE = """Use the following company document context to answer the question.
If the answer is not contained in the context, reply exactly: "I could not find this information in the company documents."

{context}

Question: {question}
Answer:"""

QA_PROMPT = PromptTemplate(template=PROMPT_TEMPLATE, input_variables=["context", "question"])


def _require_api_key() -> str:
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is required in the environment to use the RAG pipeline.")
    return LLM_API_KEY


def get_embeddings() -> OpenAIEmbeddings:
    options = {"api_key": _require_api_key()}
    if LLM_BASE_URL:
        options["base_url"] = LLM_BASE_URL
    return OpenAIEmbeddings(**options)


def get_vector_store() -> Chroma:
    return Chroma(
        persist_directory=str(Path(CHROMA_PATH)),
        embedding_function=get_embeddings(),
        collection_name=CHROMA_COLLECTION_NAME,
    )


def ingest_document(document_id: int, filename: str, text: str, required_clearance: int, category: str, department: str | None = None) -> None:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)
    documents: List[Document] = [
        Document(page_content=chunk, metadata={"document_id": str(document_id), "source": filename, "filename": filename, "required_clearance": required_clearance, "category": category, "department": department or ""})
        for chunk in chunks
        if chunk.strip()
    ]

    if not documents:
        return

    store = get_vector_store()
    store.add_documents(documents)


def answer_authorized_question(question: str, clearance_level: int, department: str | None = None) -> tuple[str, list[dict[str, object]]]:
    store = get_vector_store()
    filters: dict[str, object] = {"required_clearance": {"$lte": clearance_level}}
    matches = store.similarity_search_with_score(question, k=4, filter=filters)
    if not matches:
        return "I could not find this information in the authorized company documents.", []
    context = "\n\n".join(document.page_content for document, _ in matches)
    options = {"api_key": _require_api_key(), "model": LLM_MODEL, "temperature": 0.0}
    if LLM_BASE_URL:
        options["base_url"] = LLM_BASE_URL
    llm = ChatOpenAI(**options)
    response = llm.invoke(PROMPT_TEMPLATE.format(context=context, question=question))
    answer = getattr(response, "content", str(response)).strip()
    sources = [document.metadata for document, _ in matches]
    return answer or "I could not find this information in the authorized company documents.", sources


def answer_question(question: str) -> str:
    store = get_vector_store()
    retriever = store.as_retriever(search_kwargs={"k": 4})
    options = {"api_key": _require_api_key(), "model": LLM_MODEL, "temperature": 0.0}
    if LLM_BASE_URL:
        options["base_url"] = LLM_BASE_URL
    llm = ChatOpenAI(**options)
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=False,
        chain_type_kwargs={"prompt": QA_PROMPT},
    )

    answer = qa.invoke({"query": question})
    if isinstance(answer, dict):
        answer = answer.get("result", "")

    if not answer or "could not find" in str(answer).lower():
        return "I could not find this information in the company documents."

    return str(answer).strip()
