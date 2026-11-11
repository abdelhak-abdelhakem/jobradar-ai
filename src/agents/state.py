from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field, field_validator

from src.config import CONTRACTS, MATCH_SCORE_THRESHOLD

# The LLM reports the posting's contract type, and code compares it with the one searched for.
# "other" covers everything else, such as postdoc, engineer, CDI, CDD, or apprenticeship positions.
ContractType = Literal[tuple([*CONTRACTS, "other"])]


class JobMatch(BaseModel):
    # The field order is deliberate: the model reasons before it commits to a score.
    rationale: str
    matched_skills: list[str]
    missing_skills: list[str]
    contract_type: ContractType = Field(..., description="the type of contract the posting offers")
    domain_fit: Literal["direct", "adjacent", "none"] = Field(
        ..., description="how the candidate's experience relates to the posting's main domain"
    )
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


class UnsupportedClaim(BaseModel):
    quote: str = Field(..., description="the complete sentence, copied exactly from the letter")
    reason: str = Field(..., description="why the profile doesn't support it")


class LetterCheck(BaseModel):
    unsupported_claims: list[UnsupportedClaim] = Field(
        ..., description="facts about the candidate that the profile doesn't support; empty if none"
    )
    discusses_job_topic: bool = Field(
        ..., description="true only if the letter connects the candidate to this job's specific topic"
    )


class LetterIssue(TypedDict):
    quote: str | None   # the flagged text, or None if the issue is about the letter as a whole
    reason: str


class Job(TypedDict):
    source: str
    id: str
    title: str
    url: str
    description: str | None  # None when the detail page couldn't be fetched
    company: NotRequired[str]


class ScoredJob(TypedDict):
    job: Job
    job_match: JobMatch     # match_score here is the final score, after the caps
    llm_score: int          # the score the LLM gave before the caps


class JobRadarState(TypedDict):
    job_listings: list[Job]             # written by scrape_node
    new_jobs: list[Job]                 # written by dedup_node
    profile: str                        # written by load_profile_node
    scored_jobs: list[ScoredJob]        # written by score_job_node
    failed_scores: int                  # written by score_job_node
    cover_letters: dict[str, str]       # job key -> letter; written by draft and revise nodes
    letter_issues: dict[str, list[LetterIssue]]  # job key -> problems; written by verify node
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
