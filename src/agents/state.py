from typing import NotRequired, TypedDict

from pydantic import BaseModel, Field, field_validator

from src.config import MATCH_SCORE_THRESHOLD


class JobMatch(BaseModel):
    # The field order is deliberate: the model reasons before it commits to a score.
    rationale: str
    matched_skills: list[str]
    missing_skills: list[str]
    is_internship: bool = Field(..., description="true only if the posting is an internship (stage)")
    match_score: int = Field(..., description="the match score, from 0 to 100")

    @field_validator("match_score")
    @classmethod
    def score_must_be_valid(cls, score: int) -> int:
        if not 0 <= score <= 100:
            raise ValueError(f"match_score must be between 0 and 100, got {score}")
        return score

    @field_validator("matched_skills", "missing_skills")
    @classmethod
    def no_empty_strings(cls, v):
        return [s for s in v if s.strip() != ""]


class LetterCheck(BaseModel):
    unsupported_claims: list[str] = Field(
        ..., description="claims about the candidate that the profile doesn't support; empty if none"
    )


class Job(TypedDict):
    source: str
    id: str
    title: str
    url: str
    description: str | None  # None when the detail page couldn't be fetched
    company: NotRequired[str]


class ScoredJob(TypedDict):
    job: Job
    job_match: JobMatch


class JobRadarState(TypedDict):
    job_listings: list[Job]             # written by scrape_node
    new_jobs: list[Job]                 # written by dedup_node
    profile: str                        # written by load_profile_node
    scored_jobs: list[ScoredJob]        # written by score_job_node
    failed_scores: int                  # written by score_job_node
    cover_letters: dict[str, str]       # job key -> letter; written by draft and revise nodes
    letter_issues: dict[str, list[str]] # job key -> unsupported claims; written by verify node
    revision_round: int                 # written by revise_letter_node
    digest_sent: bool                   # written by notify_telegram_node


def initial_state() -> JobRadarState:
    return {
        "job_listings": [],
        "new_jobs": [],
        "profile": "",
        "scored_jobs": [],
        "failed_scores": 0,
        "cover_letters": {},
        "letter_issues": {},
        "revision_round": 0,
        "digest_sent": False,
    }


def job_key(job: Job) -> str:
    """Unique across sources, since two job boards could use the same ID."""
    return f"{job['source']}:{job['id']}"


def strong_matches(scored_jobs: list[ScoredJob]) -> list[ScoredJob]:
    return [s for s in scored_jobs if s["job_match"].match_score >= MATCH_SCORE_THRESHOLD]


def format_job(job: Job) -> str:
    return f"{job['title']}\n\n{job['description']}"
