"""
The API layer wraps everything already built in main.py, review_queue.py,
report.py, and chatbot.py as real HTTP endpoints a website can call.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
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


class ReleaseRequest(BaseModel):
    team_name: str


class ChatRequest(BaseModel):
    question: str
    thread_id: str = "web-session"


class LoginRequest(BaseModel):
    password: str


def _run_grading_job(team_name: str, repo_url: str) -> None:
    """Runs in the background so the submission endpoint can respond instantly."""
    from src.agent.graph import grade_repo
    from src.logging_utils import log_scorecard
    from src.agent.review_queue import add_pending

    result = grade_repo(team_name=team_name, repo_url=repo_url)
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


def _run_practice_job(team_name: str, repo_url: str) -> None:
    """
    Runs in the background, same pattern as official grading. Note what's
    NOT here: no review_queue call at all this path never touches the
    judge-approval system.
    """
    from src.agent.graph import give_practice_feedback
    from src.logging_utils import log_practice_feedback
    from src.agent.practice_store import complete_practice

    result = give_practice_feedback(team_name=team_name, repo_url=repo_url)
    log_practice_feedback(team_name=team_name, repo_url=repo_url, feedback=result["feedback"])
    complete_practice(team_name, result["feedback"])


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


@app.post("/submissions", dependencies=[Depends(require_team_session)])
@limiter.limit("10/minute")
def submit(request: Request, req: SubmissionRequest, background_tasks: BackgroundTasks):
    """
    A team submits their repo. Responds immediately with "received"
    grading happens afterward in the background, since it can take real
    time (an LLM call, not an instant lookup).
    """
    background_tasks.add_task(_run_grading_job, req.team_name, req.repo_url)
    return {"status": "received", "team_name": req.team_name}


@app.post("/practice", dependencies=[Depends(require_team_session)])
@limiter.limit("10/minute")
def submit_practice(request: Request, req: SubmissionRequest, background_tasks: BackgroundTasks):
    """
    A practice trial no score, no judge review, visible to the team
    the moment it's done. Structurally separate from /submissions above:
    this endpoint never calls anything in review_queue.py.
    """
    from src.agent.practice_store import start_practice

    start_practice(req.team_name, req.repo_url)
    background_tasks.add_task(_run_practice_job, req.team_name, req.repo_url)
    return {"status": "received", "team_name": req.team_name}


@app.get("/practice/{team_name}")
def get_practice_result(team_name: str):
    """
    Public no login needed, same as checking status. Practice feedback
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
    """Public: no login needed, just a status word no scores or evidence revealed here."""
    from src.agent.review_queue import get
    entry = get(team_name)
    if entry is None:
        return {"status": "not_found"}
    return {"status": entry["status"]}


@app.get("/submission/{team_name}", dependencies=[Depends(require_judge_session)])
def get_submission(team_name: str):
    """Judge-only: full scorecard + evidence for one team, regardless of status."""
    from src.agent.review_queue import get
    entry = get(team_name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No submission found for '{team_name}'.")
    return entry


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
        entry = approve(req.team_name, judge_notes=req.notes)
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
