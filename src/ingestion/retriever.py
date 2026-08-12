"""
Shared retrieval helper — both the team chatbot and the grading agent's rubric
lookups (if ever needed beyond the static rubric block) go through this.
"""

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from src.ingestion.build_knowledge_base import (
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
)


def load_retriever(k: int = 4):
    """
    Loads the persisted Chroma store and returns a retriever.
    Must be run after build_knowledge_base.py has created the store at least once.
    """
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )
    return vector_store.as_retriever(search_kwargs={"k": k})


if __name__ == "__main__":
    # Quick manual sanity check: run this file directly to test retrieval
    retriever = load_retriever()
    test_query = "How many members can be on a team?"
    results = retriever.invoke(test_query)
    print(f"Query: {test_query}\n")
    for i, doc in enumerate(results, 1):
        print(f"--- Result {i} (section: {doc.metadata['section']}) ---")
        print(doc.page_content[:300])
        print()
