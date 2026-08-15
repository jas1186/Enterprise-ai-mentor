from pathlib import Path
from typing import List

from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import CHROMA_PATH, LLM_API_KEY, LLM_MODEL

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
    return OpenAIEmbeddings(api_key=_require_api_key())


def get_vector_store() -> Chroma:
    return Chroma(
        persist_directory=str(Path(CHROMA_PATH)),
        embedding_function=get_embeddings(),
        collection_name=CHROMA_COLLECTION_NAME,
    )


def ingest_document(filename: str, text: str) -> None:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)
    documents: List[Document] = [
        Document(page_content=chunk, metadata={"source": filename})
        for chunk in chunks
        if chunk.strip()
    ]

    if not documents:
        return

    store = get_vector_store()
    store.add_documents(documents)
    if hasattr(store, "persist"):
        store.persist()


def answer_question(question: str) -> str:
    store = get_vector_store()
    retriever = store.as_retriever(search_kwargs={"k": 4})
    llm = ChatOpenAI(api_key=_require_api_key(), model=LLM_MODEL, temperature=0.0)
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
