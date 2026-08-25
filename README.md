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
Practice trials are a separate, simpler path: gather, then feedback. No score is ever produced, and no judge is involved at any point. This is a structurally different pipeline from official grading, not a variant of it, so a practice trial can never be mistaken for a real grade.

The chatbot is separate from all of this. It just answers rule questions from the competition's rules document, with no connection to grading.

## The three roles, step by step from the beginning

### Team, from the beginning

```
Opens the website
     v
Logs in with the team password
     v
Submits a repo link, the same single action every time
     v
The system checks how many times this team has already submitted
     v
Attempt 1 or 2: agent gathers evidence, writes feedback with no
score, team sees it right away, no judge involved. Team can edit
their repo and submit again.
     v
Attempt 3, the last one: agent gathers evidence, writes a scored
draft, checks its own evidence, lands in the judge queue as pending
review, team waits, sees nothing yet.
     v
Judge approves (can add bonus points), then separately releases.
     v
Team's report becomes visible only now.
     v
A fourth submission attempt is refused.
```

### Judge, from the beginning

```
Opens the website
     v
Logs in with the judge password
     v
Sees the queue of everything pending review
     v
Opens one team, sees the full scorecard, the evidence behind each
score, a confidence label per criterion, and any verification flags
     v
Writes a comment
     v
Approves
     v
Separately releases, possibly after approving several teams first
     v
Team can now see their result
```

A judge can also check a separate failures list, showing any submission that broke silently in the background.

### Chatbot, from the beginning

```
Anyone clicks the chat icon
     v
Types a question, sent with a thread id so the conversation is
remembered
     v
Backend searches the rules document for related content
     v
Each result gets a second check: does this actually answer the
question, not just sound related
     v
Only checked content is used to answer, following a strict rule
about official facts versus general explanation versus real
procedures that are never guessed at
     v
Answer appears, question and answer are logged
```

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

Each of the `src/` subfolders has its own README explaining what every file in it does read this one for the overall picture, then the folder-level ones when you're working on a specific piece.

Committed architecture diagrams can be `.excalidraw`, PNG, JPG/JPEG, WebP, or PDF. The existing parser reads Excalidraw JSON; a separate vision model contributes factual observations for raster images and the first five PDF pages. SVG files and live external Figma/Excalidraw links remain visible to judges for manual review.



## Running it, step by step

```bash
# 1. Install dependencies
poetry install

# 2. Set up secrets 
cp .env
# edit .env now

# 3. Build the chatbot's knowledge base
poetry run python -m src.ingestion.build_knowledge_base

# 4. Submit the same team 3 times in a row, to see all 3 attempts play out
# attempts 1 and 2 give automatic feedback, no score, no judge involved
poetry run python -m src.main submit --team "Test Team" --repo https://github.com/owner/repo
poetry run python -m src.main submit --team "Test Team" --repo https://github.com/owner/repo
# attempt 3 is the real, judge reviewed one
poetry run python -m src.main submit --team "Test Team" --repo https://github.com/owner/repo
poetry run python -m src.main review
poetry run python -m src.main approve --team "Test Team" --notes "..." --bonus 5
poetry run python -m src.main release --team "Test Team"
poetry run python -m src.main report --team "Test Team"

# 5. Try the chatbot
poetry run python -m src.main chat

# 6. Run the actual web API and website together
poetry run uvicorn src.api.main:app --reload

# 7. See the graph structure as an image, instead of only in text
poetry run python -m src.visualize_graphs
# saves logs/grading_graph.png, logs/practice_graph.png, logs/chatbot_graph.png
```


## Deploying it

See the Dockerfile at the project root. It packages everything, backend and website together, into one container that can run on Render, or any other Docker-capable host. The port is configurable via a `PORT` environment variable, so no code change is needed for a different host's requirements.
