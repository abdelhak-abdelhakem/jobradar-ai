"""The digest every channel sends. build_digest is pure, so these tests need no fakes."""
from conftest import make_job, make_match

from src.agents.nodes.notify import ChannelResult, Digest, build_digest, send_telegram
from src.agents.state import initial_state


def scored(job_id, title, score_value):
    return {"job": make_job(job_id, title), "job_match": make_match(score_value), "llm_score": score_value}


def state_with(scored_jobs, letter_keys, letters, **extra):
    return {**initial_state(), "scored_jobs": scored_jobs, "letter_keys": letter_keys, "cover_letters": letters, **extra}


def test_digest_lists_the_chosen_jobs_with_letters_best_first():
    state = state_with(
        [scored("1", "Good", 80), scored("2", "Best", 95), scored("3", "Weak", 30)],
        letter_keys=["inria:2", "inria:1"],
        letters={"inria:2": "Letter for Best", "inria:1": "Letter for Good"},
        letter_issues={"inria:1": [{"quote": "I know audio.", "reason": "Not in the CV."}]},
    )

    digest = build_digest(state)

    assert [(job.rank, job.title, job.score) for job in digest.jobs] == [(1, "Best", 95), (2, "Good", 80)]
    assert digest.jobs[0].letter == "Letter for Best"
    assert digest.jobs[1].issues[0]["quote"] == "I know audio."
    assert (digest.scored_count, digest.retries, digest.waiting) == (3, 0, 0)


def test_a_job_whose_letter_failed_is_counted_as_a_retry():
    state = state_with([scored("1", "A", 80), scored("2", "B", 90)], ["inria:2", "inria:1"], {"inria:2": "Letter"},
                       failed_scores=1)
    digest = build_digest(state)
    assert [job.key for job in digest.jobs] == ["inria:2"]
    assert digest.retries == 2   # one failed score, one failed letter


def test_strong_matches_outside_the_best_k_are_counted_as_waiting():
    state = state_with([scored("1", "A", 80), scored("2", "B", 90), scored("3", "C", 75)], ["inria:2"],
                       {"inria:2": "Letter"})
    digest = build_digest(state)
    assert (digest.chosen, digest.waiting) == (1, 2)


def test_building_the_digest_changes_nothing_in_the_state():
    state = state_with([scored("1", "A", 80)], ["inria:1"], {"inria:1": "Letter"})
    before = repr(state)
    build_digest(state)
    assert repr(state) == before


def test_telegram_reports_only_the_jobs_that_fully_arrived(world, monkeypatch):
    digest = build_digest(state_with(
        [scored("1", "A", 80), scored("2", "B", 90)], ["inria:2", "inria:1"],
        {"inria:2": "Letter that arrives", "inria:1": "Letter that fails"},
    ))
    send = world.fake_post

    def post(url, json, timeout):
        if json["text"] == "Letter that fails":
            world.telegram_up = False
        try:
            return send(url, json, timeout)
        finally:
            world.telegram_up = True

    monkeypatch.setattr("src.utils.telegram.requests.post", post)
    result = send_telegram(digest)

    assert result == ChannelResult(summary_sent=True, delivered={"inria:2"})


def test_an_empty_digest_still_sends_a_summary(world):
    result = send_telegram(Digest(scored_count=4, retries=0, chosen=0, waiting=0, jobs=[]))
    assert result == ChannelResult(summary_sent=True)
    assert "No matches today." in world.sent[0]
