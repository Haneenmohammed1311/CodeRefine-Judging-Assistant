"""
The team chatbot, rebuilt as a small LangGraph graph so it gets real
short-term memory -- the ability to remember earlier questions in the
same conversation, not just answer each question in isolation.

"""

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
import re

from src.chatbot.state import ChatState
from src.chatbot.prompts import CHATBOT_SYSTEM_PROMPT
from src.ingestion.retriever import load_retriever
from src.agent.llm import get_llm
from src.logging_utils import log_question

_retriever = None

# Defensive cap on how much of any ONE retrieved chunk gets used. This
# matters because the chunking step (build_knowledge_base.py) doesn't
# guarantee every section is small -- one section ("RESULTS - ANNOUNCEMENT")
# came out ~20x bigger than the others. Without this cap, that one chunk
# alone can push a request over Groq's per-minute token limit. The real
# fix is better chunking (splitting that section further); this is the
# safety net so a single bad chunk can never break the whole chatbot.
MAX_CHARS_PER_CHUNK = 800

# Layer 2 of the anti-speculation defense (layer 1 is the prompt itself).
# The prompt tells the model never to guess at THIS organization's actual
# procedures -- but a prompt instruction is not a guarantee the model
# follows it every time. This regex-based filter is a safety net that
# doesn't depend on the model's compliance at all: if a "General guidance"
# labeled section ALSO mentions procedural topics (registration, deadlines,
# contact methods), that whole section is stripped out programmatically,
# regardless of what the model decided to write.
_PROCEDURAL_KEYWORDS = [
    "regist", "sign up", "sign-up", "signup", "deadline", "apply",
    "application", "submit", "submission process", "contact form",
    "portal", "fee", "enroll", "how to join",
    # Arabic equivalents, since this chatbot has been tested bilingually
    "تسجيل", "التسجيل", "التقديم", "الاشتراك", "موعد نهائي",
]

_GENERAL_SECTION_PATTERN = re.compile(
    r"\*\*General (?:guidance|explanation)[^\n]*\*\*.*?(?=\n\*\*|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _strip_speculative_procedure_sections(answer: str) -> str:
    def maybe_strip(match):
        block = match.group(0)
        if any(keyword.lower() in block.lower() for keyword in _PROCEDURAL_KEYWORDS):
            return ""  # drop the whole speculative block
        return block  # genuine concept explanations pass through untouched

    return _GENERAL_SECTION_PATTERN.sub(maybe_strip, answer).strip()


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = load_retriever()
    return _retriever


def chat_node(state: ChatState) -> dict:
    """
    The only node in this graph. Runs once per message: retrieves relevant
    rules for the LATEST message, but sends the FULL conversation history
    to the LLM -- that combination is what lets it answer follow-ups
    correctly while still grounding answers in retrieved rules.
    """
    latest_question = state["messages"][-1].content

    retriever = _get_retriever()
    docs = retriever.invoke(latest_question)
    context = "\n\n".join(
        f"[{d.metadata['section']}]\n{d.page_content[:MAX_CHARS_PER_CHUNK]}" for d in docs
    )

    system_message = SystemMessage(content=CHATBOT_SYSTEM_PROMPT.format(context=context))
    llm = get_llm(temperature=0.2)

    # Full history + fresh system prompt each turn -- the system prompt is
    # rebuilt every time because the retrieved context changes per question.
    response = llm.invoke([system_message] + state["messages"])

    cleaned_content = _strip_speculative_procedure_sections(response.content)
    response.content = cleaned_content

    log_question(latest_question, cleaned_content)
    return {"messages": [response]}


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)
    # checkpointer=InMemorySaver() is the one line that turns this from a
    # stateless graph into one with short-term memory.
    return graph.compile(checkpointer=InMemorySaver())


_chat_app = None


def _get_chat_app():
    global _chat_app
    if _chat_app is None:
        _chat_app = build_chat_graph()
    return _chat_app


def ask(question: str, thread_id: str = "default-session") -> str:
    """
    thread_id groups messages into one conversation. Same thread_id across
    calls = the agent remembers earlier turns. A different thread_id would
    start a completely fresh conversation with no memory of the first.
    """
    app = _get_chat_app()
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke({"messages": [HumanMessage(content=question)]}, config=config)
    return result["messages"][-1].content
