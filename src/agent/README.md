# src/agent/

The grading agent and the practice feedback path. Reads a team's submission and produces either automatic feedback (attempts 1 and 2, no score, no judge) or an official scorecard with judge review (attempt 3, the final one). Also manages the review workflow before a judge releases anything.

## Files

`rubric.py`: the five real judging criteria and their weights (15/20/20/25/20, plus a Bonus scored separately by the judge, not the agent). No functions, just data. The Bonus criteria are still unconfirmed with the organizers, see the warning comment at the top before assuming what earns it.

`llm.py`: creates the Groq clients. `get_llm()` remains the text client for grading, feedback, and chat. `get_vision_llm()` is a separate Qwen vision client used only to make factual observations about committed image/PDF diagrams. Both use the existing `GROQ_API_KEY`; neither vision nor text scoring automatically publishes a result.

`state.py`: defines the shape of data that flows through each pipeline. `GradingState` covers the official path: what's known at the start (team name, repo URL), what gather fills in (raw notes), what format fills in (draft scorecard), what verify fills in (final scorecard). `PracticeFeedbackState` is a separate, smaller shape for practice attempts, with a `feedback` field and no score field at all. No logic in this file, just the data shapes.

`nodes.py`: the actual reasoning logic, as four functions:
- `gather_node`, reads the repo's README, Deep Dives file, BOTE file, and architecture diagram, and produces raw observations (no scoring). Committed PNG/JPG/WebP diagrams and the first five PDF pages add factual vision evidence; the existing Excalidraw parser remains the path for `.excalidraw` files. Includes prompt injection defenses, since this content is written by the team being graded and shouldn't be trusted as instructions. Shared by both the practice and official paths.
- `format_node`, turns those observations into a scored draft, citing evidence by ID rather than copied text so verification doesn't break on paraphrasing. Official path only.
- `verify_node`, a plain code check (no LLM call) that confirms cited evidence actually exists, and flags any justification that looks like it invented a scoring threshold not in the rubric. Official path only.
- `feedback_node`, the practice equivalent of format_node, but never produces a score, only improvement notes on what's missing or unclear. Practice path only.

`graph.py`: wires the functions above into runnable sequences using LangGraph. `grade_repo()` runs the official three step pipeline. `give_practice_feedback()` runs the two step practice pipeline. `submit_attempt(team_name, repo_url)` is the one function everything else actually calls: it checks how many times this team has submitted (via `attempt_tracker.py`) and automatically routes to `give_practice_feedback` for attempts 1 and 2, or `grade_repo` for attempt 3, no separate choice needed from the team.

`attempt_tracker.py`: tracks how many times each team has submitted, in a small SQLite database. This is what `submit_attempt` checks before deciding which pipeline to run. A team gets exactly 3 attempts; a 4th is refused with `NoAttemptsRemainingError`.

`review_queue.py`: tracks each team's official grading status (pending, then approved, then released) in a small SQLite database. Only used by the official path. Also protects against two different teams accidentally sharing the same team name: if a name already has an approved or released result, a new submission under that same name is refused rather than silently overwriting it. Also stores `bonus_percent` (0 to 10), the one place Bonus points ever get recorded, always set by a judge during approval, never by the agent.

`practice_store.py`: tracks a team's practice feedback (attempts 1 and 2), in its own SQLite database, separate from review_queue.py. No approve or release states exist here, since practice feedback is visible to the team the moment it's ready.

`report.py`: builds the actual text a team sees for an official grade, but only once their result has been released. Includes the base score plus any Bonus in the total. Pulls from review_queue.py, not from the agent directly.

## Nothing in this folder runs on its own

Everything here gets called from src/main.py or src/api/main.py. There's no reason to run any of these files directly, except state.py, rubric.py, and llm.py, which aren't runnable at all since they define things other files use.
