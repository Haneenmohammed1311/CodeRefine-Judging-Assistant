# src/api/

Turns everything else in this project into a real website-callable API. No grading or judging logic lives here every endpoint just calls a function that already exists elsewhere and already worked from the command line.

## Files

**`auth.py`** real login, not a static key sitting in a file. A team or judge posts a password; if it's correct, they get back a random session token valid for 4 hours. That token is what gets used for further requests the password itself is never stored anywhere the website's code can see it. Two roles, checked separately: `require_team_session` and `require_judge_session`.

**`main.py`** the actual API. Worth knowing what each endpoint maps to:

| Endpoint | Calls | Who can use it |
|---|---|---|
| POST /login/team, POST /login/judge | auth.py | anyone with the right password |
| POST /submissions | agent/graph.py's grade_repo | logged in team |
| POST /practice | agent/graph.py's give_practice_feedback | logged in team, no judge involved |
| GET /practice/{team} | agent/practice_store.py | anyone, no login needed |
| GET /submission/{team} | agent/review_queue.py's get | logged in judge, full data, any status |
| GET /report/{team} | agent/report.py | anyone, but only returns anything once released |
| GET /queue | agent/review_queue.py's list_pending | logged in judge |
| POST /approve, POST /release | agent/review_queue.py | logged in judge |
| POST /chat | chatbot/chatbot.py | anyone |
| GET / | serves web/index.html | anyone, this is what makes one URL work for both the website and the API |

Grading runs in the background (`BackgroundTasks`) so `/submissions` responds instantly instead of making a team wait for the whole grading run to finish. Rate limiting (`slowapi`) is applied to login, submission, and chat endpoints specifically, to slow down password-guessing and spam.

## Running it

```bash
poetry run uvicorn src.api.main:app --reload
```

