"""Runs the real graph end to end, with the LLM, Telegram, and the job board faked."""
import fcntl

from conftest import make_job, make_match
from langchain_core.prompts import PromptTemplate

from src.agents.nodes import score

from src.agents.graph import compile_graph
from src.agents.state import initial_state
from src.config import (
    ADJACENT_DOMAIN_MAX_SCORE,
    CONTRACTS,
    MAX_LETTER_REVISIONS,
    NO_DOMAIN_FIT_MAX_SCORE,
    WRONG_CONTRACT_MAX_SCORE,
)
from src.db.seen_jobs import seen_keys
from src.agents.nodes.notify import SENDERS
from src.settings import CHANNELS, save_settings
from scheduler import run_daily


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
    assert "1 job failed" in all_text(world)


def test_failed_letter_is_retried_next_run(world):
    world.draft_error = True
    run()
    assert seen_keys() == set()

    world.draft_error = False
    run()
    assert seen_keys() == {"inria:1"}
    assert world.letter in world.sent


# Delivery: every strong match, or only the best K

def four_jobs(world):
    world.jobs = [make_job("1", "Internship A"), make_job("2", "Internship B"),
                  make_job("3", "Internship C"), make_job("4", "Internship weak")]
    world.scores = {"weak": 30, "Internship A": 80, "Internship B": 95, "Internship C": 75}


def test_top_k_drafts_letters_only_for_the_best_k(world):
    save_settings(delivery="top_k", top_k=2)
    four_jobs(world)

    result = run()

    assert result["letter_keys"] == ["inria:2", "inria:1"]
    assert world.calls["draft"] == 2
    assert "1 more strong match didn't make the top 2" in all_text(world)
    # The weak job is finished; the strong job outside the top 2 is left unseen, so it competes again.
    assert seen_keys() == {"inria:1", "inria:2", "inria:4"}


def test_a_job_outside_the_top_k_competes_again_on_the_next_run(world):
    save_settings(delivery="top_k", top_k=2)
    four_jobs(world)
    run()
    world.calls["score"] = 0

    result = run()

    assert world.calls["score"] == 1              # only Internship C is scored again
    assert result["letter_keys"] == ["inria:3"]   # and with no better job left, it gets its letter
    assert seen_keys() == {"inria:1", "inria:2", "inria:3", "inria:4"}


def test_every_strong_match_gets_a_letter_by_default(world):
    four_jobs(world)
    run()
    assert world.calls["draft"] == 3
    assert "didn't make the top" not in all_text(world)


def test_a_settings_change_during_a_run_does_not_change_its_letters(world, monkeypatch):
    save_settings(delivery="top_k", top_k=1)
    four_jobs(world)
    draft = world.fake_draft

    def draft_while_the_user_changes_the_settings(inputs):
        save_settings(delivery="all")
        return draft(inputs)

    monkeypatch.setattr(world, "fake_draft", draft_while_the_user_changes_the_settings)
    run()

    assert world.calls["draft"] == 1
    assert world.sent.count(world.letter) == 1
    assert seen_keys() == {"inria:2", "inria:4"}


# Scoring

def test_other_contract_cannot_reach_the_threshold(world):
    world.scores = {"Internship": make_match(95, contract_type="other")}
    result = run()
    assert result["scored_jobs"][0]["job_match"].match_score == WRONG_CONTRACT_MAX_SCORE
    assert world.calls["draft"] == 0


def test_phd_search_caps_internships_and_keeps_phd_positions(world):
    save_settings(contract_type="phd")
    world.jobs = [make_job("1", "Internship in NLP"), make_job("2", "PhD in NLP")]
    world.scores = {"Internship": make_match(95), "PhD": make_match(95, contract_type="phd")}

    scores = {s["job"]["id"]: s["job_match"].match_score for s in run()["scored_jobs"]}

    assert scores == {"1": WRONG_CONTRACT_MAX_SCORE, "2": 95}
    assert world.calls["draft"] == 1


def test_scoring_prompt_gets_the_contract_type_searched_for(world):
    save_settings(contract_type="phd")
    run()
    inputs = world.score_inputs[0]
    assert inputs["target"] == CONTRACTS["phd"]["description"]
    assert "internship for an internship (stage)" in inputs["contract_types"]


def test_scoring_prompt_uses_exactly_the_inputs_it_gets(world):
    # The fake LLM replaces the whole chain, prompt included, so check the real prompt against the inputs.
    run()
    assert set(PromptTemplate.from_template(score.TEMPLATE).input_variables) == set(world.score_inputs[0])


def test_no_domain_fit_cannot_reach_the_threshold(world):
    world.scores = {"Internship": make_match(95, domain_fit="none")}
    result = run()
    assert result["scored_jobs"][0]["job_match"].match_score == NO_DOMAIN_FIT_MAX_SCORE
    assert world.calls["draft"] == 0


def test_adjacent_domain_can_qualify_but_not_reach_the_top_band(world):
    world.scores = {"Internship": make_match(95, domain_fit="adjacent")}
    result = run()
    assert result["scored_jobs"][0]["job_match"].match_score == ADJACENT_DOMAIN_MAX_SCORE
    assert world.calls["draft"] == 1


def test_direct_domain_score_is_not_capped(world):
    world.scores = {"Internship": make_match(95, domain_fit="direct")}
    assert run()["scored_jobs"][0]["job_match"].match_score == 95


def test_lower_cap_wins_when_both_apply(world):
    world.scores = {"Internship": make_match(95, contract_type="other", domain_fit="none")}
    assert run()["scored_jobs"][0]["job_match"].match_score == WRONG_CONTRACT_MAX_SCORE


def test_score_below_the_cap_is_unchanged(world):
    world.scores = {"Internship": make_match(50, domain_fit="none")}
    assert run()["scored_jobs"][0]["job_match"].match_score == 50


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


def test_flagged_sentence_the_rewrite_keeps_is_deleted(world):
    false_claim = "I have worked with audio data."
    world.letter = f"Dear team,\n\nI like NLP. {false_claim} I use Python.\n\nAbdelhak"
    world.revised_letter = world.letter  # the rewrite ignores the problem
    world.unsupported = {false_claim: [false_claim]}

    result = run()

    final = result["cover_letters"]["inria:1"]
    assert false_claim not in final
    assert "I like NLP. I use Python." in final
    assert false_claim not in "".join(world.sent)
    assert "Unverified" not in all_text(world)


def test_last_round_deletes_without_calling_the_llm(world):
    first = "I have worked with audio data."
    second = "I am an expert in C++."
    world.letter = f"Dear team,\n\n{first}\n\nI use Python.\n\nAbdelhak"
    world.revised_letter = f"Dear team,\n\n{second}\n\nI use Python.\n\nAbdelhak"
    world.unsupported = {first: [first], second: [second]}

    result = run()

    assert world.calls["revise"] == MAX_LETTER_REVISIONS - 1
    assert second not in result["cover_letters"]["inria:1"]
    assert "I use Python." in result["cover_letters"]["inria:1"]


def test_claim_that_cannot_be_located_is_flagged(world):
    world.unsupported = {"letter": ["Audio data experience"]}
    run()
    assert "Unverified" in all_text(world)
    assert "Audio data experience" in all_text(world)


def test_generic_letter_is_revised_and_then_passes(world):
    world.off_topic_text = "truthful"
    run()
    assert world.calls["revise"] == 1
    assert world.revised_letter in world.sent
    assert "Unverified" not in all_text(world)


def test_letter_that_stays_generic_is_flagged(world):
    world.off_topic_text = "letter"
    run()
    assert "connect the candidate" in all_text(world)


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


def test_missing_signature_is_added(world):
    world.letter = "Dear team,\n\nA truthful letter.\n\nSincerely,"
    run()
    assert "Sincerely,\nAbdelhak" in all_text(world)


def test_signature_survives_deleting_the_last_sentence(world):
    false_claim = "I have worked with audio data."
    world.letter = f"Dear team,\n\nI use Python.\n\n{false_claim}\n\nAbdelhak"
    world.revised_letter = world.letter
    world.unsupported = {false_claim: [false_claim]}
    assert run()["cover_letters"]["inria:1"].endswith("Abdelhak")


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


# Running on a schedule

def test_run_daily_runs_the_pipeline(world):
    assert run_daily.main() is True
    assert world.calls["score"] == 1


def test_a_run_is_skipped_while_another_holds_the_lock(world, run_lock, capsys):
    with open(run_lock, "w") as other_run:
        fcntl.flock(other_run, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert run_daily.main() is False

    assert world.calls["score"] == 0
    assert "already in progress" in capsys.readouterr().out
    assert run_daily.main() is True   # the lock is free once the other run ends


# Notification channels: a job is finished once any channel delivered it

def test_telegram_is_the_only_channel_by_default(world, smtp):
    run()
    assert world.letter in world.sent
    assert smtp.sent == []


def test_gmail_only_sends_one_email_and_no_telegram_message(world, smtp):
    save_settings(channels=["gmail"])
    result = run()

    assert world.sent == []
    [email] = smtp.sent
    assert world.letter in email.get_content()
    assert seen_keys() == {"inria:1"}
    assert result["digest_sent"] is True


def test_jobs_are_finished_when_telegram_fails_but_gmail_works(world, smtp):
    save_settings(channels=["telegram", "gmail"])
    world.telegram_up = False

    result = run()

    assert seen_keys() == {"inria:1"}   # Gmail delivered it, so it isn't sent again tomorrow
    assert result["digest_sent"] is True


def test_jobs_are_finished_when_gmail_fails_but_telegram_works(world, smtp):
    save_settings(channels=["telegram", "gmail"])
    smtp.down = True
    run()
    assert seen_keys() == {"inria:1"}


def test_jobs_are_retried_when_every_channel_fails(world, smtp):
    save_settings(channels=["telegram", "gmail"])
    world.telegram_up = False
    smtp.down = True

    result = run()

    assert seen_keys() == set()
    assert result["digest_sent"] is False


def test_every_channel_setting_has_a_sender():
    assert set(SENDERS) == set(CHANNELS)
