# src/, top level files

These are the entry points that tie the subfolders together. Everything they call is explained in that subfolder's own README (agent/, api/, chatbot/, ingestion/, tools/).

`main.py`: the command line entry point. The `submit` command is the one a team actually uses, it routes automatically to practice feedback or official grading depending on how many times that team has already submitted, see agent/attempt_tracker.py. Every command (submit, review, approve, release, report, chat) is a thin wrapper that calls into agent/ or chatbot/ and prints the result. This is how everything got tested before the API existed.

`visualize_graphs.py`: generates actual PNG image files of the LangGraph graphs in this project (the official grading graph, the practice feedback graph, the chatbot graph), instead of only seeing the flow described in text. Uses LangGraph's built in `draw_mermaid_png()`, which needs internet access but no local install. Saves images into logs/.

`batch_grade.py`: grades many teams at once from a CSV file (team_name,repo_url per row), instead of running submit by hand for each one. This deliberately bypasses the attempt tracking system entirely, meant for a final, forced grading pass rather than the normal team-facing flow. Includes automatic retry with backoff if Groq's rate limit gets hit mid run, and prints a summary of any team that still failed and needs manual attention.

`debug_retrieval.py`: a small diagnostic tool. Shows exactly which knowledge base chunks get retrieved for a given question, with no LLM involved. Useful when the chatbot seems to be missing something that should be in the rules document, since this tells you whether it's a retrieval problem or something else.

`logging_utils.py`: writes append only logs. Every official grading run ever performed (logs/scorecards.jsonl, for dispute resolution, never edited after writing), every practice trial's feedback (logs/practice_feedback.jsonl, kept separate since practice trials never carry a score), and every chatbot question asked (logs/questions.jsonl). Separate from agent/review_queue.py and agent/practice_store.py, which track current status and do get edited as a submission moves through review.
