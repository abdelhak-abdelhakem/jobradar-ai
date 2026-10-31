"""Runs the real graph end to end, with the LLM, Telegram, and the job board faked."""
from conftest import make_job, make_match

from src.agents.graph import compile_graph
from src.agents.state import initial_state
from src.config import MAX_LETTER_REVISIONS, NON_INTERNSHIP_MAX_SCORE
from src.db.seen_jobs import seen_keys


def run():
    return compile_graph().invoke(initial_state())


def all_text(world):
    return "\n".join(world.sent)


# Dedup

def test_second_run_finds_no_new_jobs(world):
    run()
    calls_after_first = dict(world.calls)
    world.sent.clear()

    run()

    assert world.calls == calls_after_first
    assert not any("Internship in NLP" in message for message in world.sent)


def test_new_job_is_processed_on_a_later_run(world):
    run()
    world.jobs = world.jobs + [make_job("2", "Internship in vision")]
    world.sent.clear()

    run()

    assert world.calls["score"] == 2
    assert "Internship in vision" in all_text(world)
    assert world.sent.count(world.letter) == 1


def test_weak_match_is_seen_without_a_letter(world):
    world.scores = {"Internship": 30}
    run()
    assert world.calls["draft"] == 0
    assert seen_keys() == {"inria:1"}


def test_failed_send_is_not_seen_and_is_retried(world):
    world.telegram_up = False
    result = run()
    assert result["digest_sent"] is False
    assert seen_keys() == set()

    world.telegram_up = True
    assert run()["digest_sent"] is True
    assert seen_keys() == {"inria:1"}
    assert world.letter in world.sent


def test_failed_scrape_is_not_scored_or_seen(world):
    world.jobs = [make_job("1", description=None), make_job("2", "Internship in vision")]
    run()
    assert world.calls["score"] == 1
    assert seen_keys() == {"inria:2"}


def test_same_id_on_another_source_is_a_new_job(world):
    run()
    world.jobs = [{**make_job(), "source": "wttj"}]
    run()
    assert seen_keys() == {"inria:1", "wttj:1"}


# Failures in one job don't affect the others

def test_llm_failure_on_one_job_leaves_the_others_scored(world):
    world.jobs = [make_job("1", "Internship broken"), make_job("2", "Internship fine")]
    world.scores = {"broken": RuntimeError("LLM failed")}

    result = run()

    assert [s["job"]["id"] for s in result["scored_jobs"]] == ["2"]
    assert seen_keys() == {"inria:2"}
    assert "1 jobs failed" in all_text(world)


def test_failed_letter_is_retried_next_run(world):
    world.draft_error = True
    run()
    assert seen_keys() == set()

    world.draft_error = False
    run()
    assert seen_keys() == {"inria:1"}
    assert world.letter in world.sent


# Scoring

def test_non_internship_cannot_reach_the_threshold(world):
    world.scores = {"Internship": make_match(95, is_internship=False)}
    result = run()
    assert result["scored_jobs"][0]["job_match"].match_score == NON_INTERNSHIP_MAX_SCORE
    assert world.calls["draft"] == 0


# Claim check

def test_clean_letter_is_not_revised(world):
    run()
    assert world.calls["revise"] == 0
    assert "Unverified" not in all_text(world)


def test_unsupported_claim_is_revised_and_then_passes(world):
    world.unsupported = {"truthful": ["I developed LangGraph"]}
    result = run()
    assert world.calls["revise"] == 1
    assert world.revised_letter in world.sent
    assert world.letter not in world.sent
    assert "Unverified" not in all_text(world)
    assert result["letter_issues"]["inria:1"] == []


def test_claim_that_survives_revisions_is_flagged(world):
    world.unsupported = {"letter": ["Audio data experience"]}
    run()
    assert world.calls["revise"] == MAX_LETTER_REVISIONS
    assert "Unverified" in all_text(world)
    assert "Audio data experience" in all_text(world)


def test_only_failing_letters_are_rechecked(world):
    world.jobs = [make_job("1"), make_job("2", "Internship two")]
    world.letter = "Dear team, a truthful letter. Abdelhak"
    world.unsupported = {"never matches": ["x"]}
    run()
    assert world.calls["check"] == 2


def test_placeholder_signature_is_caught_without_the_llm(world):
    for placeholder in ["Nom du candidat", "Candidate Name", "Candidat", "[Your name]"]:
        world.letter = f"Madame,\n\nUne lettre.\n\nCordialement,\n{placeholder}"
        world.revised_letter = world.letter
        world.jobs = [make_job(placeholder)]
        world.sent.clear()
        run()
        assert "placeholder" in all_text(world), placeholder


def test_real_name_is_not_a_placeholder(world):
    world.letter = "Dear team,\n\nThe candidate pool is large.\n\nAbdelhak ABDELHAKEM"
    run()
    assert world.calls["revise"] == 0


# Digest

def test_digest_has_real_titles_and_is_ranked(world):
    world.jobs = [make_job("1", "Internship low"), make_job("2", "Internship high")]
    world.scores = {"low": 72, "high": 90}
    run()
    digest = world.sent[0]
    assert "Unknown" not in all_text(world)
    assert digest.index("Internship high") < digest.index("Internship low")


def test_quiet_day_still_sends_a_message(world):
    world.jobs = []
    result = run()
    assert result["digest_sent"] is True
    assert "No matches today" in world.sent[0]
