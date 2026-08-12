"""
The shared state that flows through every step of the grading agent
(gather -> format -> verify). Think of this as the agent's "memory" for
one grading run: each step reads from it and adds to it.
"""

from typing import TypedDict, Optional


class CriterionEvidence(TypedDict):
    """One piece of evidence the agent found while inspecting the repo."""
    id: int            # stable numeric id, used by format_node to cite this note
    file_path: str
    line_range: str  # e.g. "22-45"
    excerpt: str      # short excerpt supporting the observation
    observation: str  # what this evidence shows, in plain language


class CriterionScorecard(TypedDict):
    """The final, judge-facing result for a single rubric criterion."""
    criterion: str            # e.g. "Data Model"
    score_percent: int        # 0 to that criterion's weight_percent, see rubric.py
    justification: str        # short written reasoning
    evidence: list[CriterionEvidence]  # resolved by verify_node from cited evidence_ids
    confidence: str           # "high" | "medium" | "low" -- per-criterion, not global


class GradingState(TypedDict):
    """
    The full state object LangGraph passes between nodes for one team's
    grading run.
    """
    # --- input, set once at the start ---
    team_name: str
    repo_url: str

    # --- filled in by the "gather" step ---
    file_tree: Optional[list[str]]
    readme_content: Optional[str]
    raw_notes: Optional[list[CriterionEvidence]]  # ungraded observations, tied to files/lines

    # --- filled in by the "format" step ---
    draft_scorecard: Optional[list[CriterionScorecard]]

    # --- filled in by the "verify" step ---
    final_scorecard: Optional[list[CriterionScorecard]]
    verification_notes: Optional[str]  # any mismatches found and how they were handled
