# CodeRefine IEEE VICTORIS 4.0

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

## What actually needs changing before you run this

Nothing here works with placeholder values. Before anything runs:

1. **Copy `.env.example` to `.env`** and fill in real values:
   - `GROQ_API_KEY`, `GITHUB_TOKEN` from Groq's console and GitHub's settings
   - `TEAM_PASSWORD`, `JUDGE_PASSWORD` pick real passwords, these gate the website's two logins
2. **`data/rules.md`** (or `data/rules.pdf`) needs to be the actual, current rules document — swap it out if the rules change, then rebuild the knowledge base (step 3 below)
3. **`src/agent/rubric.py`** the criteria weights are already the real ones (15/20/20/25/20 + bonus), but the Bonus scoring itself is still unresolved with the organizers read the note at the top of that file before assuming anything about it
4. **`web/index.html`**  currently shows sample data (3 example teams) until it's actually used for real; nothing needs editing here beyond what's already wired, but don't be surprised the first time you open it and see fake teams that's intentional placeholder content, not a bug

## Honest state of this project right now

The grading agent and the chatbot have each been tested and worked correctly, separately, run directly from the command line. **The website talking to the backend, end to end, through the API that has not been tested yet.** The code is correct by review and every piece has been checked individually, but "click submit on the website and watch a real grade come back" hasn't actually been tried. Expect to debug the connection the first time you run it for real.

## Running it, step by step

```bash
# 1. Install dependencies
poetry install

# 2. Set up secrets (see above)
cp .env.example .env
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

Steps 4 and 5 use the command line directly this is how everything was actually tested. Step 6 is the website talking to the same backend through the API — the untested part, worth trying early rather than right before you need it working.

## Deploying it

See the Dockerfile at the project root. It packages everything backend and website together — into one container that can run on Render, Hugging Face Spaces (Docker tier), or any other Docker-capable host. Full deployment steps were worked out separately; ask if you need them written down again.
