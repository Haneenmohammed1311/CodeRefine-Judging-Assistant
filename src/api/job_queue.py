"""
A real, single-worker job queue for grading and practice-feedback jobs.

Without this, FastAPI's BackgroundTasks can run multiple submitted jobs
CONCURRENTLY across threads if several teams submit close together
each grading job makes 2 LLM calls, so even a handful of near-simultaneous
submissions can blow through Groq's per-minute token limit. batch_grade.py
already avoids this by processing one team at a time with a pause between
them; this module gives the live API the same guarantee.

One background thread pulls jobs off a queue and runs them one at a time,
in the order they arrived. A submission is accepted instantly either way
(the API still responds right away) the queue only controls the ORDER
and PACE actual grading happens in, not whether a team's request is
acknowledged quickly.
"""

import queue
import threading
import json
from datetime import datetime, timezone
from pathlib import Path

_job_queue: queue.Queue = queue.Queue()
FAILURE_LOG = Path("logs/submission_failures.jsonl")


def _log_failure(func_name: str, args: tuple, error: Exception) -> None:
    """
    Writes every background job failure to a real file, not just the
    console. A print() statement is easy to lose, especially once this
    is deployed somewhere and nobody's watching the terminal live
    this is what a judge or admin would actually check afterward to see
    if any team's submission silently failed (like: a name collision).
    """
    FAILURE_LOG.parent.mkdir(exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job": func_name,
        "args": [str(a) for a in args],
        "error_type": type(error).__name__,
        "error": str(error),
    }
    with FAILURE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"Background job failed (logged to {FAILURE_LOG}): {error}")


def _worker() -> None:
    while True:
        func, args = _job_queue.get()
        try:
            func(*args)
        except Exception as e:
            # A single team's failure should never kill the worker thread
            #  if it did, every submission after it would be silently
            # stuck forever. It's now logged persistently instead of only
            # printed, specifically so something like a name collision
            # (see review_queue.SubmissionCollisionError) doesn't vanish
            # with no trace of what happened to that team's submission.
            _log_failure(func.__name__, args, e)
        finally:
            _job_queue.task_done()


_worker_thread = threading.Thread(target=_worker, daemon=True)
_worker_thread.start()


def enqueue_job(func, *args) -> None:
    """Adds a job to the queue -- it will run once every job ahead of it has finished."""
    _job_queue.put((func, args))


def queue_length() -> int:
    """How many jobs are currently waiting (not counting the one actively running)."""
    return _job_queue.qsize()
