import os
from pathlib import Path
from typing import List

from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.embeddings import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.docstore.document import Document

from app.core.config import CHROMA_PATH, LLM_API_KEY, LLM_MODEL

if not LLM_API_KEY:
    raise ValueError("LLM_API_KEY is required in the environment to use the RAG pipeline.")

CHROMA_COLLECTION_NAME = "enterprise_ai_mentor"

PROMPT_TEMPLATE = """Use the following company document context to answer the question.
If the answer is not contained in the context, reply exactly: "I could not find this information in the company documents."

{context}

Question: {question}
Answer:"""

QA_PROMPT = PromptTemplate(template=PROMPT_TEMPLATE, input_variables=["context", "question"])


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(openai_api_key=LLM_API_KEY)


def get_vector_store() -> Chroma:
    return Chroma(
        persist_directory=Path(CHROMA_PATH),
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
    store.persist()


def answer_question(question: str) -> str:
    store = get_vector_store()
    retriever = store.as_retriever(search_kwargs={"k": 4})
    llm = ChatOpenAI(openai_api_key=LLM_API_KEY, model_name=LLM_MODEL, temperature=0.0)
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=False,
        chain_type_kwargs={"prompt": QA_PROMPT},
    )

    answer = qa.run(question)
    if not answer or "could not find" in answer.lower():
        return "I could not find this information in the company documents."

    return answer.strip()
