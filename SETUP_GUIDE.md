# Setup Guide, full run order

This is the complete path from an empty terminal to a fully working system. Steps are numbered in the order you need them the first time. After that, most steps only need re-running when their inputs change (noted below).

---

## Prerequisites (one-time, before anything else)
- [ ] Python 3.11+ installed and on PATH (`python --version` shows a version)
- [ ] Poetry installed: `pip install poetry`
- [ ] Groq API key, console.groq.com then API Keys
- [ ] GitHub Personal Access Token, github.com then Settings, Developer settings, Personal access tokens, "repo" read scope
- [ ] (Optional) LangSmith API key, smith.langchain.com, for tracing and debugging

---

## Step 1, install dependencies
```bash
poetry install
```
Reads `pyproject.toml`, creates an isolated environment, installs every library the project needs. Re-run this only if `pyproject.toml` changes.

## Step 2, set up your secrets
```bash
cp .env.example .env
```
Then open `.env` and fill in real values (no quotes, no spaces around `=`):
```
GROQ_API_KEY=your_real_key
GITHUB_TOKEN=your_real_token
TEAM_PASSWORD=a_real_password
JUDGE_PASSWORD=a_different_real_password
```
LangSmith variables are optional, leave them blank to skip tracing. One-time, unless a key gets revoked or rotated.

## Step 3, build the knowledge base (powers the chatbot)
```bash
poetry run python -m src.ingestion.build_knowledge_base
```
Reads `data/rules.md` (or `data/rules.pdf` if that exists instead), cleans it, splits it into sections, embeds each section with BGE-M3, saves to `data/chroma_db/`. First run downloads the BGE-M3 model (about 2GB, one time). Re-run this whenever the rules document changes, otherwise the chatbot answers from stale rules.

## Step 4, verify retrieval works (quick sanity check, optional)
```bash
poetry run python -m src.ingestion.retriever
```
Runs one hardcoded test question against the knowledge base and prints what comes back. Not interactive, just proves Step 3 worked.

## Step 5, debug retrieval for a specific question (optional, as needed)
```bash
poetry run python -m src.debug_retrieval "your question here"
```
Shows exactly which chunks get retrieved for any question you give it, no LLM involved, useful if the chatbot ever seems to be missing something that should be in the rules document.

---

## Running the chatbot (team support)
```bash
poetry run python -m src.main chat
```
Interactive, type questions, type `exit` to quit. Needs Steps 1 through 3 done first. Remembers the whole conversation within one session.

---

## Running the grading agent for one team, all 3 attempts

There is one submission command, `submit`. It automatically decides what happens based on how many times this team has already submitted, no separate command for practice versus official.

```bash
# attempt 1, automatic feedback, no score, no judge
poetry run python -m src.main submit --team "Team Name" --repo https://github.com/owner/repo

# attempt 2, same as attempt 1
poetry run python -m src.main submit --team "Team Name" --repo https://github.com/owner/repo

# attempt 3, the real one, goes to judge review
poetry run python -m src.main submit --team "Team Name" --repo https://github.com/owner/repo

# a 4th attempt for the same team is refused
```

## Running the grading agent for many teams at once, from a CSV

```bash
poetry run python -m src.batch_grade submissions.csv
```
CSV format: a header row `team_name,repo_url`, then one row per team. This bypasses the 3 attempt system entirely, meant for a final, forced grading pass, not the normal team-facing flow. Grades each team with automatic pausing and retry on rate limit between teams. Prints a summary of any teams that failed and need manual attention.

---

## The judge review workflow (after grading, before teams see anything)
```bash
poetry run python -m src.main review
poetry run python -m src.main approve --team "Team Name" --notes "..." --bonus 5
poetry run python -m src.main release --team "Team Name"
poetry run python -m src.main report --team "Team Name"
```
Run in this order, per team: `submit` (attempt 3) then `review` then `approve` then `release` then `report`. Bonus is 0 to 10, awarded only by a judge, never by the agent. A team's result is only visible via `report` after it has been explicitly released.

---

## Running the full web API and website together
```bash
poetry run uvicorn src.api.main:app --reload
```
Then open http://localhost:8000. One address serves both the website and every backend endpoint.

## Seeing the graph structure as an image
```bash
poetry run python -m src.visualize_graphs
```
Saves `logs/grading_graph.png`, `logs/practice_graph.png`, and `logs/chatbot_graph.png`.

---

## What needs re-running versus what is one-time

| Step | When to re-run |
|---|---|
| `poetry install` | Only if dependencies change |
| `.env` setup | Only if a key is revoked or rotated |
| `build_knowledge_base` | Whenever the rules document changes |
| `submit` | Once per team per attempt, up to 3 times |
| `batch_grade` | As needed for a bulk grading pass |
| `review`, `approve`, `release`, `report` | Once per team's final attempt, in that order |
| `chat` | Any time, always available once Steps 1 through 3 are done |

---

## File-by-file reference

For the full explanation of every file, see the README in each folder (`src/agent/README.md`, `src/api/README.md`, `src/chatbot/README.md`, `src/ingestion/README.md`, `src/tools/README.md`), plus `src/README.md` for the top level entry point files. `PROJECT_EXPLAINED.md` at the project root has the full narrative walkthrough, meant for explaining the whole system out loud.

## Common errors
- `ModuleNotFoundError`: you ran `python` instead of `poetry run python`
- `EnvironmentError: GROQ_API_KEY is not set` or similar: `.env` missing or not filled in
- `FileNotFoundError: data/rules.md`: not running from the project's root folder
- `groq.APIStatusError` (rate limit): normal on the free tier under load, `batch_grade.py` and the live API's job queue both retry automatically
- `400 Bad Request` on `/submit`: that team has already used all 3 attempts
