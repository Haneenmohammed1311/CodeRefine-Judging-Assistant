"""
Generates the report a TEAM actually sees -- built from the queue entry,
and only for entries that have been explicitly released. This is the
"here's your grade, here's why, here's how to improve" document.

Kept as a separate function from the scorecard data itself: the internal
scorecard (with confidence levels, raw evidence, judge notes) and the
team-facing report (readable, encouraging, actionable) are different
audiences with different needs, even though they come from the same data.
"""

from src.agent.review_queue import get
from src.agent.rubric import RUBRIC, BONUS_MAX_PERCENT


def generate_team_report(team_name: str) -> str:
    entry = get(team_name)
    if entry is None:
        return f"No grading record found for '{team_name}'."

    if entry["status"] != "released":
        return (
            f"Results for '{team_name}' are not yet available "
            f"(current status: {entry['status']})."
        )

    lines = [f"# CodeRefine Results — {team_name}", ""]

    weight_by_criterion = {r["criterion"]: r["weight_percent"] for r in RUBRIC}
    total_percent = sum(item.get("score_percent", 0) for item in entry["scorecard"])
    lines.append(f"**Total score:** {total_percent} / 100 (plus any bonus, see below)\n")

    for item in entry["scorecard"]:
        max_for_this = weight_by_criterion.get(item["criterion"], "?")
        lines.append(f"## {item['criterion']}: {item.get('score_percent', 0)} / {max_for_this}")
        lines.append(f"{item['justification']}")
        if item.get("confidence") == "low":
            lines.append(
                "\n_Note: this criterion had limited supporting evidence during review -- "
                "if you believe this score doesn't reflect your submission, please reach "
                "out to the organizers._"
            )
        lines.append("")

    lines.append(
        f"_Bonus (up to {BONUS_MAX_PERCENT} points) is assessed directly by the judge "
        "and is not included in the total above unless noted in the judge's notes._\n"
    )

    if entry.get("judge_notes"):
        lines.append("## Judge's notes")
        lines.append(entry["judge_notes"])
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: poetry run python -m src.agent.report \"Team Name\"")
    else:
        print(generate_team_report(sys.argv[1]))
