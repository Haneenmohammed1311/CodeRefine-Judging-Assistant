# CodeRefine Judging Assistant

A grading assistant and support chatbot for CodeRefine's system-design track. Teams submit a GitHub repo, an agent drafts a scorecard against the real judging rubric, a judge reviews and approves it, and only then does the team see a result. A separate chatbot answers teams' questions about the rules.

Nothing here auto-publishes a score. The agent drafts, a human decides.

## How it fits together

```
Team submits repo link
        ↓
 Grading agent reads it (gather → format → verify)
        ↓
 Draft scorecard goes into the review queue
        ↓
 Judge reviews, approves (or edits), releases
        ↓
 Team sees the report
```

The chatbot is separate from all of this it just answers rule questions from the competition's rules document, with no connection to grading.

## Folder map

| Folder | What's in it |
|---|---|
| `src/agent/` | The grading agent itself rubric, LLM setup, the gather/format/verify pipeline, the review queue, report generation |
| `src/tools/` | Reading a team's GitHub repo and parsing the architecture diagram |
| `src/ingestion/` | Turns the rules document into a searchable knowledge base for the chatbot |
| `src/chatbot/` | The team support chatbot, with short-term conversation memory |
| `src/api/` | Turns everything above into a real web API  login, endpoints, rate limiting |
| `web/` | The website team portal, judge panel, chatbot widget |
| `data/` | The rules document (and the generated knowledge base, once built) |
| `logs/` | Audit log of every grading run, question log, review queue database |

Each of the `src/` subfolders has its own README explaining what every file in it does — read this one for the overall picture, then the folder-level ones when you're working on a specific piece.



## Running it, step by step

```bash
# 1. Install dependencies
poetry install

# 2. Set up secrets (see above)
cp .env
# edit .env now

# 3. Build the chatbot's knowledge base
poetry run python -m src.ingestion.build_knowledge_base

# 4. Try the grading agent on one team
poetry run python -m src.main grade --team "Test Team" --repo https://github.com/owner/repo
poetry run python -m src.main review
poetry run python -m src.main approve --team "Test Team" --notes "..."
poetry run python -m src.main release --team "Test Team"
poetry run python -m src.main report --team "Test Team"

# 5. Try the chatbot
poetry run python -m src.main chat

# 6. Run the actual web API + website together
poetry run uvicorn src.api.main:app --reload
# then open http://localhost:8000 in a browser
```

