"""
Sends the results of a run, then records which jobs are finished.

What to say and how to send it are kept apart: build_digest() turns the state into plain data, and each
channel formats and sends that same data its own way. A channel reports which jobs it delivered, so a job
can count as finished when any channel delivered it.
"""
from dataclasses import dataclass, field
from html import escape

from src.agents.state import JobRadarState, LetterIssue, ScoredJob, job_key, strong_matches
from src.db.seen_jobs import SeenJob, mark_seen
from src.utils.telegram import send_lines, send_plain


# What to say: plain data, with no formatting for any channel

@dataclass
class DigestJob:
    key: str
    rank: int
    title: str
    url: str
    score: int
    rationale: str
    letter: str
    issues: list[LetterIssue]


@dataclass
class Digest:
    scored_count: int       # new jobs scored in this run
    retries: int            # jobs that failed and will be tried again on the next run
    chosen: int             # strong matches chosen for a letter: all of them, or the best K
    waiting: int            # strong matches outside the best K, scored again on the next run
    jobs: list[DigestJob]   # the chosen jobs whose letter was written, best first


@dataclass
class ChannelResult:
    summary_sent: bool                                # the digest summary arrived
    delivered: set[str] = field(default_factory=set)  # keys of the jobs that arrived with their letter


def build_digest(state: JobRadarState) -> Digest:
    """Turns the state into the digest every channel sends. Pure: it sends and saves nothing."""
    letters = state["cover_letters"]
    by_key = {job_key(item["job"]): item for item in state["scored_jobs"]}

    # letter_keys is already best first. A job whose letter failed isn't sent, and is retried next run.
    ranked = [by_key[key] for key in state["letter_keys"] if key in letters]
    jobs = [
        DigestJob(
            key=job_key(item["job"]),
            rank=rank,
            title=item["job"]["title"],
            url=item["job"]["url"],
            score=item["job_match"].match_score,
            rationale=item["job_match"].rationale,
            letter=letters[job_key(item["job"])],
            issues=state["letter_issues"].get(job_key(item["job"]), []),
        )
        for rank, item in enumerate(ranked, 1)
    ]
    chosen = len(state["letter_keys"])
    return Digest(
        scored_count=len(state["scored_jobs"]),
        retries=state["failed_scores"] + chosen - len(jobs),
        chosen=chosen,
        waiting=len(strong_matches(state["scored_jobs"])) - chosen,
        jobs=jobs,
    )


# How to send it on Telegram: HTML, split into messages under Telegram's length limit

def _link(job: DigestJob) -> str:
    return f'<a href="{escape(job.url, quote=True)}">{escape(job.title)}</a>'


def _telegram_summary(digest: Digest) -> list[str]:
    lines = [f"<b>JobRadar digest</b>\n{digest.scored_count} new jobs scored, {len(digest.jobs)} strong matches."]
    if not digest.jobs:
        lines.append("No matches today.")
    if digest.retries:
        lines.append(f"⚠️ {digest.retries} jobs failed and will be tried again on the next run.")
    if digest.waiting:
        jobs = "strong match" if digest.waiting == 1 else "strong matches"
        lines.append(f"{digest.waiting} more {jobs} didn't make the top {digest.chosen} "
                     "and will be scored again on the next run.")
    for job in digest.jobs:
        lines.append(f"{job.rank}. <b>{job.score}/100</b> {_link(job)}")
    return lines


def _telegram_job(job: DigestJob) -> list[str]:
    lines = [f"<b>#{job.rank} {_link(job)}</b>", f"<b>Score:</b> {job.score}/100", escape(job.rationale)]
    if job.issues:
        lines.append("⚠️ <b>Unverified letter. Check these points before using it:</b>")
        for issue in job.issues:
            quote = f'"{escape(issue["quote"])}": ' if issue["quote"] else ""
            lines.append(f'• {quote}{escape(issue["reason"])}')
    return lines


def send_telegram(digest: Digest) -> ChannelResult:
    """Sends the summary, then each job with its letter. A job is delivered when both of its parts arrive."""
    result = ChannelResult(summary_sent=send_lines(_telegram_summary(digest)))
    for job in digest.jobs:
        # Both messages are always attempted, so one failure doesn't hide the other part.
        header_sent = send_lines(_telegram_job(job))
        letter_sent = send_plain(job.letter)
        if header_sent and letter_sent:
            result.delivered.add(job.key)
    return result


# Recording what's finished

def _seen_record(item: ScoredJob, state: JobRadarState) -> SeenJob:
    job = item["job"]
    match = item["job_match"]
    key = job_key(job)
    return {
        "key": key,
        "title": job["title"],
        "url": job["url"],
        "score": match.match_score,
        "company": job.get("company"),
        "llm_score": item["llm_score"],
        "domain_fit": match.domain_fit,
        "contract_type": match.contract_type,
        "rationale": match.rationale,
        "matched_skills": match.matched_skills,
        "missing_skills": match.missing_skills,
        "letter": state["cover_letters"].get(key),
        "issues": state["letter_issues"].get(key, []),
    }


def notify_telegram_node(state: JobRadarState) -> dict:
    """
    Sends the digest, then records the finished jobs.
    Jobs are recorded as seen only once they're delivered, so failed sends are retried on the next run.
    Strong matches that weren't chosen, outside the best K, are left unseen too, so they compete again.
    """
    digest = build_digest(state)
    result = send_telegram(digest)

    # Weak matches need no notification, so they're finished as soon as they've been scored.
    strong_keys = {job_key(item["job"]) for item in strong_matches(state["scored_jobs"])}
    finished = [
        _seen_record(item, state)
        for item in state["scored_jobs"]
        if job_key(item["job"]) not in strong_keys or job_key(item["job"]) in result.delivered
    ]
    mark_seen(finished)

    everything_arrived = result.summary_sent and len(result.delivered) == len(digest.jobs)
    return {"digest_sent": everything_arrived}
