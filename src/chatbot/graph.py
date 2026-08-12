"""
The team chatbot, rebuilt as a small LangGraph graph so it gets real
short-term memory -- the ability to remember earlier questions in the
same conversation, not just answer each question in isolation.

Short-term vs long-term memory, briefly:
- Short-term (what this file adds): remembers the current conversation.
  Gone once the chat session ends. Good enough for "a team asks several
  related questions in one sitting."
- Long-term: would remember facts across different sessions/days. Not
  needed yet -- worth learning once short-term memory feels solid.

Flow per message: retrieve candidate chunks -> GRADE each one for actual
relevance to the question (not just topical similarity) -> answer using
only the chunks that passed grading. The grading step exists because
retrieval finding a chunk "similar" to a question isn't the same as that
chunk actually answering it -- a compound or oddly-phrased question can
retrieve related-but-unhelpful content otherwise.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
import re

import json

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

"""
Wires gather -> format -> verify into one runnable LangGraph flow.

This file is deliberately small: it doesn't contain any grading logic
itself (that's in nodes.py) -- it only describes the ORDER things happen
in. That separation is the LangGraph pattern: nodes do the work, the
graph decides the sequence.
"""

from langgraph.graph import StateGraph, END

from src.agent.state import GradingState
from src.agent.nodes import gather_node, format_node, verify_node


def build_grading_graph():
    graph = StateGraph(GradingState)

    graph.add_node("gather", gather_node)
    graph.add_node("format", format_node)
    graph.add_node("verify", verify_node)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "format")
    graph.add_edge("format", "verify")
    graph.add_edge("verify", END)

    return graph.compile()


def grade_repo(team_name: str, repo_url: str) -> dict:
    """
    The one function the rest of the project calls to grade a repo.
    Returns the final state, including final_scorecard.
    """
    app = build_grading_graph()
    initial_state: GradingState = {
        "team_name": team_name,
        "repo_url": repo_url,
        "file_tree": None,
        "readme_content": None,
        "raw_notes": None,
        "draft_scorecard": None,
        "final_scorecard": None,
        "verification_notes": None,
    }
    return app.invoke(initial_state)
def _grade_relevance(question: str, docs: list) -> list:
    if not docs:
        return []

    numbered = "\n\n".join(
        f"[{i}] Section: {d.metadata['section']}\n{d.page_content[:MAX_CHARS_PER_CHUNK]}"
        for i, d in enumerate(docs)
    )
    
    # We updated this prompt to be much more forgiving with synonyms, 
    # while still strictly filtering out off-topic sections.
    prompt = f"""Question: {question}

Below are numbered sections retrieved for this question. Your job is to filter out sections that are irrelevant.
- KEEP the section if it contains the direct answer, a partial answer, or is highly related to the user's intent.
- BE FORGIVING with synonyms (e.g., if they ask what it is "about", keep the "description" section).
- BE STRICT about categories (e.g., if they ask for "rules", KEEP sections about code originality and cheating, but DROP sections about "phases", "scoring", or "eligibility").

{numbered}

Return ONLY a JSON list of the indices (integers) to keep. Return [] if none help. Example: [0, 2]"""

    llm = get_llm(temperature=0.0) 
    response = llm.invoke(prompt)
    try:
        relevant_indices = json.loads(response.content)
        return [docs[i] for i in relevant_indices if isinstance(i, int) and 0 <= i < len(docs)]
    except (json.JSONDecodeError, TypeError):
        return docs
# def _grade_relevance(question: str, docs: list) -> list:
#     """
#     Retrieval finds chunks that are SIMILAR in meaning to the question --
#     that's not the same as chunks that actually ANSWER it. A compound or
#     oddly-phrased question can retrieve chunks that are topically related
#     but don't directly address what was asked. This asks the LLM to check
#     each retrieved chunk against the actual question before any of them
#     get used to answer -- filtering out anything that doesn't genuinely
#     help, instead of assuming "retrieved" means "relevant."
#     """
#     if not docs:
#         return []

#     numbered = "\n\n".join(
#         f"[{i}] Section: {d.metadata['section']}\n{d.page_content[:MAX_CHARS_PER_CHUNK]}"
#         for i, d in enumerate(docs)
#     )
#     prompt = f"""Question: {question}

# Below are numbered sections retrieved for this question. For EACH one,
# decide: does this section contain information that directly helps answer
# the question -- not just a related topic, but something that would
# actually appear in a correct answer?

# {numbered}

# Return ONLY a JSON list of the indices (integers) of sections that are
# genuinely relevant. Return an empty list [] if none of them actually
# answer the question. Example: [0, 2]"""

#     llm = get_llm(temperature=0.0)  # deterministic for a grading/filtering task
#     response = llm.invoke(prompt)
#     try:
#         relevant_indices = json.loads(response.content)
#         return [docs[i] for i in relevant_indices if isinstance(i, int) and 0 <= i < len(docs)]
#     except (json.JSONDecodeError, TypeError):
#         # If grading itself fails to parse, fail toward including everything
#         # retrieved rather than silently answering from nothing.
#         return docs


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
    relevant_docs = _grade_relevance(latest_question, docs)

    if relevant_docs:
        context = "\n\n".join(
            f"[{d.metadata['section']}]\n{d.page_content[:MAX_CHARS_PER_CHUNK]}" for d in relevant_docs
        )
    else:
        # Retrieval found chunks, but none of them actually answered the
        # question -- leave context empty rather than forcing the model to
        # work with topically-similar-but-unhelpful content. The system
        # prompt already knows what to do with empty context: say plainly
        # it isn't covered, don't guess.
        context = ""

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