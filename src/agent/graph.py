"""
Wires gather -> format -> verify into one runnable LangGraph flow.

It only describes the ORDER things happen in.
"""

from langgraph.graph import StateGraph, END
 
from src.agent.state import GradingState, PracticeFeedbackState
from src.agent.nodes import gather_node, format_node, verify_node, feedback_node
 

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
    Returns the final state, including final_scorecard. This is the
    OFFICIAL grading path always goes through judge review before a
    team sees anything (see src/agent/review_queue.py).
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


def build_practice_graph():
    """
    Deliberately only two steps gather, then feedback. There is no
    scoring node in this graph at all, not a format/verify pair with
    scoring "turned off" the graph structurally cannot produce a
    score, because no node here knows how to.
    """
    graph = StateGraph(PracticeFeedbackState)
 
    graph.add_node("gather", gather_node)
    graph.add_node("feedback", feedback_node)
 
    graph.set_entry_point("gather")
    graph.add_edge("gather", "feedback")
    graph.add_edge("feedback", END)
 
    return graph.compile()


def give_practice_feedback(team_name: str, repo_url: str) -> dict:
    """
    The practice-trial path. Returns feedback directly no review
    queue, no judge approval step, by design (this is what makes it a
    practice trial rather than an official grade). Teams see this
    immediately; nothing here is ever shown to a judge for approval.
    """
    app = build_practice_graph()
    initial_state: PracticeFeedbackState = {
        "team_name": team_name,
        "repo_url": repo_url,
        "raw_notes": None,
        "feedback": None,
    }
    return app.invoke(initial_state)

def submit_attempt(team_name: str, repo_url: str) -> dict:
    """
    The system decides automatically
    based on which attempt number this is for this team.

    Attempts 1 and 2: routes to the practice pipeline (feedback only, no
    score, no judge). Attempt 3: routes to the official pipeline (scored,
    goes to judge review). Attempt 4 and beyond: refused outright.

    Returns a dict with an "attempt_type" key ("practice" or "official")
    so the caller (the API layer) knows which store to save the result
    into, without needing its own copy of this counting logic.
    """
    from src.agent.attempt_tracker import (
        get_attempt_count,
        record_attempt,
        FINAL_ATTEMPT_NUMBER,
        MAX_ATTEMPTS,
        NoAttemptsRemainingError,
    )

    current_count = get_attempt_count(team_name)
    if current_count >= MAX_ATTEMPTS:
        raise NoAttemptsRemainingError(
            f"'{team_name}' has already used all {MAX_ATTEMPTS} submission attempts."
        )

    attempt_number = record_attempt(team_name)

    if attempt_number < FINAL_ATTEMPT_NUMBER:
        result = give_practice_feedback(team_name, repo_url)
        return {"attempt_type": "practice", "attempt_number": attempt_number, **result}
    else:
        result = grade_repo(team_name, repo_url)
        return {"attempt_type": "official", "attempt_number": attempt_number, **result}
