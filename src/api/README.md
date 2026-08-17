# src/api/

Turns everything else in this project into a real website callable API. No grading or judging logic lives here. Every endpoint just calls a function that already exists elsewhere and already worked from the command line.

## Files

`auth.py`: real login, not a static key sitting in a file. A team or judge posts a password, and if it's correct, they get back a random session token valid for 4 hours. That token is what gets used for further requests. The password itself is never stored anywhere the website's code can see it. Two roles, checked separately: `require_team_session` and `require_judge_session`.

`job_queue.py`: a single background worker thread that runs submission jobs strictly one at a time, in the order they arrived. Without this, several teams submitting close together could have their grading run concurrently, which risks exceeding the AI provider's per minute usage limit. A submission is still accepted instantly either way, this only controls the order and pace the actual work happens in. Any job that fails gets written to `logs/submission_failures.jsonl`, not just printed to the console, so a failure is not lost.

`main.py`: the actual API. Worth knowing what each endpoint maps to:

| Endpoint | Calls | Who can use it |
|---|---|---|
| POST /login/team, POST /login/judge | auth.py | anyone with the right password |
| POST /submit | agent/graph.py's submit_attempt, via the job queue | logged in team, this is the ONE submission endpoint, it routes automatically to practice feedback or official grading depending on attempt number |
| GET /attempts/{team} | agent/attempt_tracker.py | anyone, how many of the 3 attempts a team has used |
| GET /practice/{team} | agent/practice_store.py | anyone, no login needed |
| GET /submission/{team} | agent/review_queue.py's get | logged in judge, full data, any status |
| GET /report/{team} | agent/report.py | anyone, but only returns anything once released, includes any bonus in the total |
| GET /queue | agent/review_queue.py's list_pending | logged in judge |
| GET /failures | job_queue.py's failure log | logged in judge, shows any submission that failed silently in the background |
| POST /approve | agent/review_queue.py, now also accepts bonus_percent | logged in judge |
| POST /release | agent/review_queue.py | logged in judge |
| POST /chat | chatbot/chatbot.py | anyone |
| GET / | serves web/index.html | anyone, this is what makes one URL work for both the website and the API |

There used to be two separate submission endpoints, one for practice and one for official grading, requiring a team to choose between two buttons. This was replaced with the single /submit endpoint above, the system now decides automatically based on attempt count, see src/agent/graph.py's `submit_attempt`.

Rate limiting (slowapi) is applied to login, submission, and chat endpoints specifically, to slow down password guessing and spam.

## Running it

```bash
poetry run uvicorn src.api.main:app --reload
```
