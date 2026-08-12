# Setup Guide — Full Run Order

This is the complete path from an empty terminal to a fully working system.
Steps are numbered in the order you need them the FIRST time. After that,
most steps only need re-running when their inputs change (noted below).

---

## Prerequisites (one-time, before anything else)
- [ ] Python 3.11+ installed and on PATH (`python --version` shows a version)
- [ ] Poetry installed: `pip install poetry`
- [ ] Groq API key — console.groq.com -> API Keys
- [ ] GitHub Personal Access Token — github.com -> Settings -> Developer
      settings -> Personal access tokens -> "repo" read scope
- [ ] (Optional) LangSmith API key — smith.langchain.com, for tracing/debugging

---

## Step 1 — Install dependencies
```bash
poetry install
```
Reads `pyproject.toml`, creates an isolated environment, installs every
library the project needs. Re-run this only if `pyproject.toml` changes
(e.g. a new dependency gets added later).

## Step 2 — Set up your secrets
```bash
cp .env.example .env
```
Then open `.env` and fill in real values (no quotes, no spaces around `=`):
```
GROQ_API_KEY=your_real_key
GITHUB_TOKEN=your_real_token
```
LangSmith variables are optional — leave them blank to skip tracing.
One-time, unless a key gets revoked/rotated.

## Step 3 — Build the knowledge base (powers the chatbot)
```bash
poetry run python -m src.ingestion.build_knowledge_base
```
Reads `data/rules.md`, cleans it, splits it into sections, embeds each
section with BGE-M3, saves to `data/chroma_db/`. First run downloads the
BGE-M3 model (~2GB, one-time). **Re-run this whenever `data/rules.md`
changes** — otherwise the chatbot answers from stale rules.

## Step 4 — Verify retrieval works (quick sanity check, optional)
```bash
poetry run python -m src.ingestion.retriever
```
Runs one hardcoded test question against the knowledge base and prints
what comes back. Not interactive — just proves Step 3 worked.

## Step 5 — Debug retrieval for a specific question (optional, as needed)
```bash
poetry run python -m src.debug_retrieval "your question here"
```
Shows exactly which chunks get retrieved for any question you give it, no
LLM involved — useful if the chatbot ever seems to be missing something
that should be in the rules doc.

---

## Running the chatbot (team support)
```bash
poetry run python -m src.main chat
```
Interactive — type questions, type `exit` to quit. Needs Steps 1-3 done
first. Remembers the whole conversation within one session (short-term
memory via LangGraph).

Quick non-interactive test of memory specifically:
```bash
poetry run python -m src.chatbot.chatbot
```

---

## Running the grading agent (one team at a time)
```bash
poetry run python -m src.main grade --team "Team Name" --repo https://github.com/owner/repo
```
Needs Steps 1-2 done (does NOT need the knowledge base — the grading
agent and the chatbot are independent of each other). Adds the result to
the review queue automatically.

## Running the grading agent (many teams at once, from a CSV)
```bash
poetry run python -m src.batch_grade submissions.csv
```
CSV format: a header row `team_name,repo_url`, then one row per team.
Grades each team with automatic pausing and retry-on-rate-limit between
teams. Prints a summary of any teams that failed and need manual
attention.

---

## The judge review workflow (after grading, before teams see anything)
```bash
poetry run python -m src.main approve --team "Team Name" --notes "..."
poetry run python -m src.main release --team "Team Name"
poetry run python -m src.main report --team "Team Name"                # what the team sees
```
Run in this order, per team: `grade` (or `batch_grade`) -> `review` ->
`approve` -> `release` -> `report`. A team's result is only visible via
`report` after it's been explicitly released.

---

## Running EVERYTHING together, from zero, first time ever
```bash
poetry install
cp .env.example .env
# [edit .env with real keys]
poetry run python -m src.ingestion.build_knowledge_base
poetry run python -m src.main grade --team "Test Team" --repo https://github.com/owner/repo
poetry run python -m src.main review
poetry run python -m src.main approve --team "Test Team" --notes "looks good"
poetry run python -m src.main release --team "Test Team"
poetry run python -m src.main report --team "Test Team"
poetry run python -m src.main chat
```

## What needs re-running vs. what's one-time

| Step | When to re-run |
|---|---|
| `poetry install` | Only if dependencies change |
| `.env` setup | Only if a key is revoked/rotated |
| `build_knowledge_base` | Whenever `data/rules.md` changes |
| `grade` / `batch_grade` | Once per team submission |
| `review` / `approve` / `release` / `report` | Once per team, in that order |
| `chat` | Any time — always available once Steps 1-3 are done |

---

## File-by-file reference

| File | Purpose | Run directly? |
|---|---|---|
| `src/ingestion/build_knowledge_base.py` | Builds the chatbot's knowledge base | Yes (Step 3) |
| `src/ingestion/retriever.py` | Manual retrieval test | Yes (Step 4) |
| `src/debug_retrieval.py` | Inspect retrieval for any question | Yes (Step 5) |
| `src/chatbot/chatbot.py` | Chatbot memory test | Yes (quick test) |
| `src/chatbot/graph.py`, `src/chatbot/state.py`, `src/chatbot/prompts.py` | Chatbot internals | No — used by `chatbot.py` |
| `src/agent/state.py` | Data shape the grading agent fills in | No — used by the graph |
| `src/agent/rubric.py` | The 5 real weighted criteria | No — used by the nodes |
| `src/agent/llm.py` | Groq client (cached) | No — used everywhere |
| `src/agent/nodes.py` | gather/format/verify logic | No — used by the graph |
| `src/agent/graph.py` | Wires the 3 nodes together | No — used by `main.py` |
| `src/agent/review_queue.py` | Pending/approved/released tracking | No — used by `main.py` |
| `src/agent/report.py` | Team-facing report generator | No — used by `main.py` |
| `src/tools/github_tool.py` | Repo file access | No — used by `nodes.py` |
| `src/tools/excalidraw_parser.py` | Parses diagram JSON | No — used by `nodes.py` |
| `src/logging_utils.py` | Audit log + question log | No — used by `main.py`/`chatbot.py` |
| `src/main.py` | Main entry point — most commands run through this | Yes — this is the one you use most |
| `src/batch_grade.py` | Grade many teams from a CSV | Yes |
| `src/*/__init__.py` | Mark folders as Python packages | Intentionally empty, never run |

## Common errors
- `ModuleNotFoundError` -> you ran `python` instead of `poetry run python`
- `EnvironmentError: GROQ_API_KEY is not set` / `GITHUB_TOKEN is not set` -> `.env` missing or not filled in
- `FileNotFoundError: data/rules.md` -> not running from the project's root folder
- `groq.APIStatusError` (rate limit) -> normal on the free tier under load; `batch_grade.py` retries automatically, single `grade` calls may need a short wait and retry