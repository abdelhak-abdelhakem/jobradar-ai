from src.agents.state import JobRadarState, job_key
from src.db.seen_jobs import seen_keys


def dedup_node(state: JobRadarState) -> dict:
    """
    Keeps jobs that haven't been finished in an earlier run.
    Jobs are recorded as seen later, in notify_node, once they've been handled.
    Failed scrapes are dropped here and never recorded, so the next run tries them again.
    """
    seen = seen_keys()
    new_jobs = {}
    failed = 0

    for job in state["job_listings"]:
        if not job["description"]:
            failed += 1
        elif job_key(job) not in seen:
            new_jobs[job_key(job)] = job

    duplicates = len(state["job_listings"]) - failed - len(new_jobs)
    print(f"\n{len(new_jobs)} new jobs found, {duplicates} duplicates skipped, {failed} failed scrapes.")
    return {"new_jobs": list(new_jobs.values())}
