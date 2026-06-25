from typing import TypedDict
from pydantic import BaseModel , Field , field_validator


class JobMatch (BaseModel):
    match_score: int = Field(...,
                             description="the macth score must be between 0 to 100")
    rationale: str 
    matched_skills: list[str] 
    missing_skills: list[str] 

    @field_validator("match_score")
    @classmethod
    def score_must_be_valid(cls, score:int)-> int:
        if not 0 <= score <= 100:
            raise ValueError(f"match_score must be between 0 and 100, got {score}")
        return score
    
    @field_validator("matched_skills", "missing_skills")
    @classmethod
    def no_empty_strings(cls, v):
        cleaned = [s for s in v if s.strip() != ""]
        return cleaned


class JobRadarState(TypedDict):
    job_listings: list      # written by scrape_node
    new_jobs: list          # written by dedup_node
    scored_jobs: list       # written by retrieve_profile_node + score_job_node
    cover_letters: dict     # written by draft_letter_node
    digest_sent: bool       # written by notify_telegram_node



