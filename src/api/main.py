"""
The API layer wraps everything already built in main.py, review_queue.py,
report.py, and chatbot.py as real HTTP endpoints a website can call.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.api.auth import (
    require_team_session,
    require_judge_session,
    create_session,
    check_login_password,
)

app = FastAPI(title="CodeRefine API")

# Rate limiting: caps how many requests one visitor can make per minute,
# regardless of whether they have a valid session or not. This matters
# even with proper login it stops someone from hammering /login trying
# to guess the password, or spamming /submit.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5500")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def serve_website():
    """Serves the website itself at the root address one Space, one URL for both."""
    return FileResponse("web/index.html")


class SubmissionRequest(BaseModel):
    team_name: str
    repo_url: str


class ApproveRequest(BaseModel):
    team_name: str
    notes: str = ""
    bonus_percent: int = 0


class ReleaseRequest(BaseModel):
    team_name: str


class ChatRequest(BaseModel):
    question: str
    thread_id: str = "web-session"


class LoginRequest(BaseModel):
    password: str


def _run_submission_job(team_name: str, repo_url: str) -> None:
    """
    The one job function behind every submission, whichever attempt
    number it turns out to be. submit_attempt() (src/agent/graph.py)
    decides automatically whether this becomes a practice run or the
    real, judge-reviewed grading run this function just saves the
    result to the right place afterward.
    """
    from src.agent.graph import submit_attempt
    from src.logging_utils import log_scorecard, log_practice_feedback
    from src.agent.review_queue import add_pending
    from src.agent.practice_store import complete_practice

    result = submit_attempt(team_name=team_name, repo_url=repo_url)

    if result["attempt_type"] == "practice":
        log_practice_feedback(team_name=team_name, repo_url=repo_url, feedback=result["feedback"])
        complete_practice(team_name, repo_url, result["feedback"])
    else:
        log_scorecard(
            team_name=team_name, repo_url=repo_url,
            final_scorecard=result["final_scorecard"],
            verification_notes=result["verification_notes"],
        )
        add_pending(
            team_name=team_name, repo_url=repo_url,
            final_scorecard=result["final_scorecard"],
            verification_notes=result["verification_notes"],
        )


@app.post("/login/team")
@limiter.limit("5/minute")  # slows down anyone trying to guess the password
def login_team(request: Request, req: LoginRequest):
    if not check_login_password(req.password, "team"):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"session_token": create_session("team")}


@app.post("/login/judge")
@limiter.limit("5/minute")
def login_judge(request: Request, req: LoginRequest):
    if not check_login_password(req.password, "judge"):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"session_token": create_session("judge")}


@app.post("/submit", dependencies=[Depends(require_team_session)])
@limiter.limit("10/minute")
def submit(request: Request, req: SubmissionRequest):
    """
    The one submission endpoint. A team always calls this, whichever
    attempt it is. The system checks how many times this team has
    submitted before (src/agent/attempt_tracker.py) and automatically
    routes attempts 1 and 2 to practice feedback (no score, no judge)
    and attempt 3 to the real, judge-reviewed grading run. A team never
    picks which one happens.
    """
    from src.agent.attempt_tracker import get_attempt_count, MAX_ATTEMPTS
    from src.api.job_queue import enqueue_job, queue_length

    current_count = get_attempt_count(req.team_name)
    if current_count >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=400,
            detail=f"'{req.team_name}' has already used all {MAX_ATTEMPTS} submission attempts."
        )

    enqueue_job(_run_submission_job, req.team_name, req.repo_url)
    return {
        "status": "received",
        "team_name": req.team_name,
        "attempt_number": current_count + 1,
        "position_in_queue": queue_length(),
    }


@app.get("/practice/{team_name}")
def get_practice_result(team_name: str):
    """
    Public -- no login needed, same as checking status. Practice feedback
    was never gated behind judge approval in the first place, so there's
    nothing to protect here the way official scores are protected.
    """
    from src.agent.practice_store import get_practice

    entry = get_practice(team_name)
    if entry is None:
        return {"status": "not_found"}
    return entry


@app.get("/status/{team_name}")
def get_status(team_name: str):
    """Public: no login needed, just a status word -- no scores or evidence revealed here."""
    from src.agent.review_queue import get
    entry = get(team_name)
    if entry is None:
        return {"status": "not_found"}
    return {"status": entry["status"]}


@app.get("/attempts/{team_name}")
def get_attempts(team_name: str):
    """Public: how many of the 3 submission attempts this team has used so far."""
    from src.agent.attempt_tracker import get_attempt_count, MAX_ATTEMPTS
    used = get_attempt_count(team_name)
    return {"attempts_used": used, "attempts_remaining": MAX_ATTEMPTS - used, "max_attempts": MAX_ATTEMPTS}


@app.get("/submission/{team_name}", dependencies=[Depends(require_judge_session)])
def get_submission(team_name: str):
    """Judge-only: full scorecard + evidence for one team, regardless of status."""
    from src.agent.review_queue import get
    entry = get(team_name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No submission found for '{team_name}'.")
    return entry


@app.get("/failures", dependencies=[Depends(require_judge_session)])
def list_failures():
    """
    Judge-only: every submission that failed silently in the background
    (Like: a name collision, a repo that couldn't be reached). Without
    this, a team whose submission failed would just look like they never
    submitted at all this is where to check if a team says "I
    submitted but nothing's showing up."
    """
    import json
    from src.api.job_queue import FAILURE_LOG

    if not FAILURE_LOG.exists():
        return {"failures": []}
    with FAILURE_LOG.open(encoding="utf-8") as f:
        return {"failures": [json.loads(line) for line in f if line.strip()]}


@app.get("/report/{team_name}")
def get_report(team_name: str):
    """Public: returns the report ONLY if released report.py itself enforces that."""
    from src.agent.report import generate_team_report
    return {"report": generate_team_report(team_name)}


@app.get("/queue", dependencies=[Depends(require_judge_session)])
def list_queue():
    """Judge-only: everything currently pending review."""
    from src.agent.review_queue import list_pending
    return {"pending": list_pending()}


@app.post("/approve", dependencies=[Depends(require_judge_session)])
def approve_submission(req: ApproveRequest):
    from src.agent.review_queue import approve
    try:
        entry = approve(req.team_name, judge_notes=req.notes, bonus_percent=req.bonus_percent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return entry


@app.post("/release", dependencies=[Depends(require_judge_session)])
def release_submission(req: ReleaseRequest):
    from src.agent.review_queue import release
    try:
        entry = release(req.team_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return entry


@app.post("/chat")
@limiter.limit("20/minute")
def chat(request: Request, req: ChatRequest):
    from src.chatbot.chatbot import answer_question
    answer = answer_question(req.question, thread_id=req.thread_id)
    return {"answer": answer}


@app.get("/health")
def health():
    """No auth needed just confirms the API is actually running."""
    return {"status": "ok"}
