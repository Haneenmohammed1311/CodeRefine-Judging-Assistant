"""
The API layer wraps everything already built in main.py, review_queue.py,
report.py, and chatbot.py as real HTTP endpoints a website can call.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from src.api.auth import require_team_auth, require_judge_auth

app = FastAPI(title="CodeRefine API")

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5500")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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


@app.post("/submissions", dependencies=[Depends(require_team_auth)])
def submit(req: SubmissionRequest, background_tasks: BackgroundTasks):
    """
    A team submits their repo. Responds immediately with "received"
    grading happens afterward in the background, since it can take real
    time (an LLM call, not an instant lookup).
    """
    background_tasks.add_task(_run_grading_job, req.team_name, req.repo_url)
    return {"status": "received", "team_name": req.team_name}


@app.get("/status/{team_name}")
def get_status(team_name: str):
    """Either role can poll this a team checking their own status, or a judge."""
    from src.agent.review_queue import get
    entry = get(team_name)
    if entry is None:
        return {"status": "not_found"}
    return {"status": entry["status"]}


@app.get("/report/{team_name}")
def get_report(team_name: str):
    """Public-ish: returns the report ONLY if released report.py itself enforces that."""
    from src.agent.report import generate_team_report
    return {"report": generate_team_report(team_name)}


@app.get("/queue", dependencies=[Depends(require_judge_auth)])
def list_queue():
    """Judge-only: everything currently pending review."""
    from src.agent.review_queue import list_pending
    return {"pending": list_pending()}


@app.post("/approve", dependencies=[Depends(require_judge_auth)])
def approve_submission(req: ApproveRequest):
    from src.agent.review_queue import approve
    try:
        entry = approve(req.team_name, judge_notes=req.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return entry


@app.post("/release", dependencies=[Depends(require_judge_auth)])
def release_submission(req: ReleaseRequest):
    from src.agent.review_queue import release
    try:
        entry = release(req.team_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return entry


@app.post("/chat")
def chat(req: ChatRequest):
    from src.chatbot.chatbot import answer_question
    answer = answer_question(req.question, thread_id=req.thread_id)
    return {"answer": answer}


@app.get("/health")
def health():
    """No auth needed just confirms the API is actually running (useful for the platform team to check)."""
    return {"status": "ok"}