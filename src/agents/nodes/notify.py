from html import escape

from src.agents.state import JobRadarState, LetterIssue, ScoredJob, job_key, strong_matches
from src.db.seen_jobs import SeenJob, mark_seen
from src.utils.telegram import send_lines, send_plain


def _seen_record(item: ScoredJob) -> SeenJob:
    job = item["job"]
    return {
        "key": job_key(job),
        "title": job["title"],
        "url": job["url"],
        "score": item["job_match"].match_score,
    }


def _link(item: ScoredJob) -> str:
    job = item["job"]
    return f'<a href="{escape(job["url"], quote=True)}">{escape(job["title"])}</a>'


def _digest_lines(ranked: list[ScoredJob], state: JobRadarState) -> list[str]:
    checked = len(state["scored_jobs"])
    lines = [f"<b>JobRadar digest</b>\n{checked} new jobs scored, {len(ranked)} strong matches."]
    if not ranked:
        lines.append("No matches today.")

    retries = state["failed_scores"] + len(strong_matches(state["scored_jobs"])) - len(ranked)
    if retries:
        lines.append(f"⚠️ {retries} jobs failed and will be tried again on the next run.")

    for rank, item in enumerate(ranked, 1):
        lines.append(f'{rank}. <b>{item["job_match"].match_score}/100</b> {_link(item)}')
    return lines


def _send_job(rank: int, item: ScoredJob, letter: str, issues: list[LetterIssue]) -> bool:
    match = item["job_match"]
    lines = [f'<b>#{rank} {_link(item)}</b>', f"<b>Score:</b> {match.match_score}/100", escape(match.rationale)]
    if issues:
        lines.append("⚠️ <b>Unverified letter. Check these points before using it:</b>")
        for issue in issues:
            quote = f'"{escape(issue["quote"])}": ' if issue["quote"] else ""
            lines.append(f'• {quote}{escape(issue["reason"])}')
    # Both messages are always attempted, so one failure doesn't hide the other part.
    header_sent = send_lines(lines)
    letter_sent = send_plain(letter)
    return header_sent and letter_sent


def notify_telegram_node(state: JobRadarState) -> dict:
    """
    Sends a ranked digest, then each strong match with its letter.
    Jobs are recorded as seen only once they're handled, so failed sends are retried on the next run.
    """
    letters = state["cover_letters"]
    strong = strong_matches(state["scored_jobs"])
    strong_keys = {job_key(item["job"]) for item in strong}

    # A strong match whose letter failed isn't sent. It's left unseen and retried next run.
    ranked = sorted(
        (item for item in strong if job_key(item["job"]) in letters),
        key=lambda item: item["job_match"].match_score,
        reverse=True,
    )

    # Weak matches need no notification, so they're finished as soon as they've been scored.
    finished = [_seen_record(s) for s in state["scored_jobs"] if job_key(s["job"]) not in strong_keys]

    digest_sent = send_lines(_digest_lines(ranked, state))
    for rank, item in enumerate(ranked, 1):
        key = job_key(item["job"])
        if _send_job(rank, item, letters[key], state["letter_issues"].get(key, [])):
            finished.append(_seen_record(item))
        else:
            digest_sent = False

    mark_seen(finished)
    return {"digest_sent": digest_sent}
