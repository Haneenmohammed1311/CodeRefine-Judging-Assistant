# src/agent/

The grading agent itself. Reads a team's submission, produces a scorecard, and manages the review workflow before a judge releases anything.

## Files

**`rubric.py`** the five real judging criteria and their weights (15/20/20/25/20, plus a Bonus scored separately by the judge, not the agent). No functions, just data. The Bonus criteria are still unconfirmed with the organizers see the warning comment at the top before assuming what earns it.

**`llm.py`** creates the Groq client the agent uses to "think." One function, `get_llm()`, cached by temperature so repeated calls don't reconnect every time. Grading uses `temperature=0.0` (consistent, repeatable scoring); the chatbot uses a slightly higher one elsewhere.

**`state.py`**: defines the shape of data that flows through each pipeline. `GradingState` covers the official path: what's known at the start (team name, repo URL), what gather fills in (raw notes), what format fills in (draft scorecard), what verify fills in (final scorecard). `PracticeFeedbackState` is a separate, smaller shape for practice trials, with a `feedback` field and no score field at all. No logic in this file, just the data shapes.

**`nodes.py`** the actual grading logic, as three functions:
- `gather_node` reads the repo's README, Deep Dives file, BOTE file, and architecture diagram, and produces raw observations (no scoring). Includes prompt injection defenses, since this content is written by the team being graded and shouldn't be trusted as instructions.
- `format_node` turns those observations into a scored draft, citing evidence by ID rather than copied text (so verification doesn't break on paraphrasing).
- `verify_node` a plain code check (no LLM call) that confirms cited evidence actually exists, and flags any justification that looks like it invented a scoring threshold not in the rubric.
- `feedback_node`, the practice equivalent of format_node, but never produces a score, only improvement notes on what's missing or unclear. Practice path only.

**`graph.py`** wires the three functions above into an actual runnable sequence using LangGraph. `grade_repo(team_name, repo_url)` runs the official three step pipeline. `give_practice_feedback(team_name, repo_url)` runs the two step practice pipeline, gather then feedback, with no scoring node in the graph at all.

`review_queue.py`: tracks each team's official grading status (pending, then approved, then released) in a small SQLite database. Only used by the official path.

`practice_store.py`: tracks whether a practice trial is done and stores its feedback, in its own SQLite database, separate from review_queue.py. No approve or release states exist here, since practice feedback is visible to the team the moment it's ready.

**`report.py`** builds the actual text a team sees, but only once their result has been released. Pulls from the review queue, not from the agent directly.

## Nothing in this folder runs on its own

Everything here gets called from `src/main.py` or `src/api/main.py` there's no reason to run any of these files directly except `state.py`, `rubric.py`, and `llm.py`, which aren't runnable at all (they define things other files use).
