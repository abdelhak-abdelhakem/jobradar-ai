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
from src.settings import load_settings
from src.utils.gmail import send_email
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


def plural(count: int, singular: str, many: str) -> str:
    return f"{count} {singular if count == 1 else many}"


def _summary_sentences(digest: Digest) -> list[str]:
    """The summary in plain sentences, shared by every channel so the counts always read the same."""
    sentences = [f"{plural(digest.scored_count, 'new job', 'new jobs')} scored, "
                 f"{plural(len(digest.jobs), 'strong match', 'strong matches')}."]
    if not digest.jobs:
        sentences.append("No matches today.")
    if digest.retries:
        sentences.append(f"⚠️ {plural(digest.retries, 'job', 'jobs')} failed and will be tried again on the next run.")
    if digest.waiting:
        sentences.append(f"{plural(digest.waiting, 'more strong match', 'more strong matches')} didn't make "
                         f"the top {digest.chosen} and will be scored again on the next run.")
    return sentences


# How to send it on Telegram: HTML, split into messages under Telegram's length limit

def _link(job: DigestJob) -> str:
    return f'<a href="{escape(job.url, quote=True)}">{escape(job.title)}</a>'


def _telegram_summary(digest: Digest) -> list[str]:
    first, *rest = _summary_sentences(digest)   # numbers only, so nothing needs escaping
    lines = [f"<b>JobRadar digest</b>\n{first}", *rest]
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


# How to send it by email: one plain-text email with everything, since email has no length limit

def email_subject(digest: Digest) -> str:
    if not digest.jobs:
        return "JobRadar: no matches today"
    return f"JobRadar: {plural(len(digest.jobs), 'strong match', 'strong matches')}"


def email_text(digest: Digest) -> str:
    parts = ["JobRadar digest", "\n".join(_summary_sentences(digest))]
    if digest.jobs:
        parts.append("\n".join(f"{job.rank}. {job.score}/100  {job.title}\n   {job.url}" for job in digest.jobs))
    for job in digest.jobs:
        section = [f"{'=' * 60}\n#{job.rank} {job.title}", f"Score: {job.score}/100\n{job.url}",
                   f"Why this score:\n{job.rationale}"]
        if job.issues:
            points = "\n".join(f'- "{issue["quote"]}": {issue["reason"]}' if issue["quote"] else f'- {issue["reason"]}'
                               for issue in job.issues)
            section.append(f"⚠️ Unverified letter. Check these points before using it:\n{points}")
        section.append(f"Cover letter draft:\n\n{job.letter}")
        parts.append("\n\n".join(section))
    return "\n\n".join(parts) + "\n"


def send_gmail(digest: Digest) -> ChannelResult:
    """Sends the whole digest as one email, so every job arrives, or none does."""
    if send_email(email_subject(digest), email_text(digest)):
        return ChannelResult(summary_sent=True, delivered={job.key for job in digest.jobs})
    return ChannelResult(summary_sent=False)


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


# Every channel takes the same digest and reports what it delivered. The settings choose which ones run.
SENDERS = {"telegram": send_telegram, "gmail": send_gmail}


def notify_node(state: JobRadarState) -> dict:
    """
    Sends the digest on every chosen channel, then records the finished jobs.
    A job is finished once any channel delivered it; if none did, it's retried on the next run.
    Strong matches that weren't chosen, outside the best K, are left unseen too, so they compete again.
    """
    digest = build_digest(state)
    results = [SENDERS[name](digest) for name in load_settings()["channels"]]
    delivered = set().union(*(result.delivered for result in results))

    # Weak matches need no notification, so they're finished as soon as they've been scored.
    strong_keys = {job_key(item["job"]) for item in strong_matches(state["scored_jobs"])}
    finished = [
        _seen_record(item, state)
        for item in state["scored_jobs"]
        if job_key(item["job"]) not in strong_keys or job_key(item["job"]) in delivered
    ]
    mark_seen(finished)

    # True when at least one channel delivered the whole digest.
    everything_arrived = any(r.summary_sent and len(r.delivered) == len(digest.jobs) for r in results)
    return {"digest_sent": everything_arrived}
