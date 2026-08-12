"""
Diagnostic tool: shows exactly what the retriever returns for a given
question, without involving the LLM at all. Use this when the chatbot
gives a wrong or "I don't have that" answer, to check whether the problem
is retrieval (wrong chunks returned) or generation (right chunks returned,
but the LLM ignored or misused them).

Usage:
    poetry run python -m src.debug_retrieval "your question here"
"""

import sys
from src.ingestion.retriever import load_retriever


def main():
    if len(sys.argv) < 2:
        print('Usage: poetry run python -m src.debug_retrieval "your question"')
        return

    question = sys.argv[1]
    retriever = load_retriever(k=4)
    docs = retriever.invoke(question)

    print(f"Question: {question}\n")
    print(f"Retrieved {len(docs)} chunks:\n")
    for i, doc in enumerate(docs, 1):
        print(f"--- {i}. [{doc.metadata['section']}] ---")
        print(doc.page_content[:400])
        print()


if __name__ == "__main__":
    main()
