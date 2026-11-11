"""
View of the pipeline's saved results, with a sidebar to choose the contract type, job sources, and search
keywords for the next run.
It makes no LLM or Telegram calls.

  python -m streamlit run dashboard/app.py
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altair as alt
import pandas as pd
import streamlit as st

from src import config
from src.agents.nodes.scrape import FILTERED_BY_CONTRACT
from src.config import CONTRACTS, MATCH_SCORE_THRESHOLD, MAX_TOP_K
from src.db.seen_jobs import all_seen, backup_path, clear_seen
from src.scheduling import ScheduleError, apply_schedule, next_run
from src.settings import CHANNELS, SCHEDULES, SOURCES, WEEKDAYS, load_settings, save_settings

# Passes colour-blindness and contrast checks on both Streamlit's light and dark backgrounds.
FINAL_COLOR = "#2a78d6"
LLM_COLOR = "#d95926"
NEUTRAL_COLOR = "#8a8984"

DOMAIN_LABELS = {"direct": "Direct", "adjacent": "Adjacent", "none": "None", None: "Not recorded"}
CONTRACT_LABELS = {**{name: c["label"] for name, c in CONTRACTS.items()}, "other": "Other", None: "Not recorded"}


def llm_score(job: dict) -> int:
    """Rows saved before the LLM score was recorded fall back to the final score."""
    return job["llm_score"] if job["llm_score"] is not None else job["score"]


def is_strong(job: dict) -> bool:
    return job["score"] >= MATCH_SCORE_THRESHOLD


def score_chart(jobs: list[dict]) -> alt.LayerChart:
    """A dumbbell per job: the LLM's score, the final score after the caps, and the letter cutoff."""
    order = [job["title"] for job in jobs]
    wide = pd.DataFrame({
        "Job": order,
        "LLM score": [llm_score(job) for job in jobs],
        "Final score": [job["score"] for job in jobs],
        "Domain fit": [DOMAIN_LABELS[job["domain_fit"]] for job in jobs],
    })
    long = wide.melt(
        id_vars=["Job", "Domain fit"],
        value_vars=["LLM score", "Final score"],
        var_name="Series",
        value_name="Score",
    )

    y = alt.Y("Job:N", sort=order, title=None, axis=alt.Axis(labelLimit=420, ticks=False, domain=False))
    x_scale = alt.Scale(domain=[0, 100])

    connectors = alt.Chart(wide).mark_rule(strokeWidth=2, color=NEUTRAL_COLOR).encode(
        y=y,
        x=alt.X("LLM score:Q", scale=x_scale),
        x2="Final score:Q",
    )
    cutoff = alt.Chart(pd.DataFrame({"Score": [MATCH_SCORE_THRESHOLD]})).mark_rule(
        strokeDash=[4, 4], strokeWidth=1.5, color=NEUTRAL_COLOR
    ).encode(x=alt.X("Score:Q", scale=x_scale))
    points = alt.Chart(long).mark_circle(size=110, opacity=1).encode(
        y=y,
        x=alt.X(
            "Score:Q",
            scale=x_scale,
            title=f"Score (dashed line: letter cutoff at {MATCH_SCORE_THRESHOLD})",
            axis=alt.Axis(values=list(range(0, 101, 10))),
        ),
        color=alt.Color(
            "Series:N",
            scale=alt.Scale(domain=["LLM score", "Final score"], range=[LLM_COLOR, FINAL_COLOR]),
            legend=alt.Legend(title=None, orient="top"),
        ),
        # "LLM score" sorts after "Final score", so descending draws the final score on top.
        order=alt.Order("Series:N", sort="descending"),
        tooltip=["Job:N", "Series:N", "Score:Q", "Domain fit:N"],
    )
    return (connectors + cutoff + points).properties(height=34 * len(jobs) + 70)


def source_label(job: dict) -> str:
    name = job["key"].split(":", 1)[0]
    return SOURCES.get(name, name)


def skipped_boards_note() -> str:
    """Names the job boards each contract type skips, such as: PhD searches skip CEA, ..."""
    notes = []
    for contract in CONTRACTS.values():
        skipped = [SOURCES[name] for name in FILTERED_BY_CONTRACT if name not in contract["site_codes"]]
        if skipped:
            notes.append(f"{contract['label']} searches skip {', '.join(skipped)}, which has no such offers on its job site.")
    return " ".join(notes)


def contract_settings() -> None:
    """Sidebar form that chooses the contract type the next run searches for."""
    current = load_settings()["contract_type"]
    names = list(CONTRACTS)

    with st.sidebar.form("contract"):
        st.markdown("**Contract type**")
        chosen = st.selectbox(
            "Looking for", names, index=names.index(current), format_func=lambda name: CONTRACTS[name]["label"]
        )
        st.caption(skipped_boards_note())
        saved = st.form_submit_button("Save")

    if saved:
        save_settings(contract_type=chosen)
        st.sidebar.success(f"Saved. The next run looks for {CONTRACTS[chosen]['label']} offers.")


def source_settings() -> None:
    """Sidebar form that chooses which job boards the next run scrapes."""
    current = load_settings()["sources"]

    with st.sidebar.form("sources"):
        st.markdown("**Job sources**")
        chosen = [name for name, label in SOURCES.items() if st.checkbox(label, value=name in current)]
        saved = st.form_submit_button("Save")

    if saved:
        try:
            save_settings(chosen)
        except ValueError as e:
            st.sidebar.error(str(e))
        else:
            st.sidebar.success("Saved. The next run uses these sources.")


def keyword_settings() -> None:
    """Sidebar form that edits the domain keywords a job must match before it reaches the LLM."""
    current = load_settings()

    with st.sidebar.form("keywords"):
        st.markdown("**Search keywords**")
        st.caption(
            "One keyword per line, matched as whole words. Keywords in capitals, such as AI, "
            "match only in capitals, so AI doesn't match the French \"j'ai\"."
        )
        domain_text = st.text_area(
            "Domain keywords",
            value="\n".join(current["domain_keywords"]),
            help="The job title or description must contain one of these.",
        )
        saved = st.form_submit_button("Save")

    if saved:
        try:
            save_settings(domain_keywords=domain_text.splitlines())
        except ValueError as e:
            st.sidebar.error(str(e))
        else:
            st.sidebar.success("Saved. The next run uses these keywords. Jobs already handled aren't scored again.")


def missing_credentials() -> list[str]:
    """Channels whose credentials aren't in .env, so they would send nothing."""
    needed = {
        "telegram": (config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID),
        "gmail": (config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD),
    }
    return [CHANNELS[name] for name, values in needed.items() if not all(values)]


def channel_settings() -> None:
    """Sidebar form that chooses where the digest is sent."""
    current = load_settings()["channels"]

    with st.sidebar.form("channels"):
        st.markdown("**Notifications**")
        chosen = [name for name, label in CHANNELS.items() if st.checkbox(label, value=name in current)]
        st.caption("A job counts as sent once any chosen channel delivers it. Gmail sends one email per run, "
                   "to the address in .env.")
        missing = [label for label in missing_credentials() if label in (CHANNELS[name] for name in current)]
        if missing:
            st.warning(f"No credentials in .env for: {', '.join(missing)}. Nothing will be sent there.")
        saved = st.form_submit_button("Save")

    if saved:
        try:
            save_settings(channels=chosen)
        except ValueError as e:
            st.sidebar.error(str(e))
        else:
            st.sidebar.success(f"Saved. The next run sends to {' and '.join(CHANNELS[name] for name in chosen)}.")


DELIVERY_LABELS = {"all": "Every strong match", "top_k": "Only the best K"}


def delivery_settings() -> None:
    """Sidebar form that chooses which strong matches get a letter: all of them, or the best K."""
    current = load_settings()

    with st.sidebar.form("delivery"):
        st.markdown("**Letters**")
        delivery = st.radio(
            "Write letters for",
            list(DELIVERY_LABELS),
            index=list(DELIVERY_LABELS).index(current["delivery"]),
            format_func=DELIVERY_LABELS.get,
        )
        top_k = st.number_input("K", min_value=1, max_value=MAX_TOP_K, value=current["top_k"], step=1)
        st.caption(
            f"A strong match scores {MATCH_SCORE_THRESHOLD} or more, and each letter costs several LLM calls. "
            "With the best K, the other strong matches aren't recorded, so the next run scores them again "
            "and they compete with the new jobs."
        )
        saved = st.form_submit_button("Save")

    if saved:
        save_settings(delivery=delivery, top_k=int(top_k))
        if delivery == "top_k":
            st.sidebar.success(f"Saved. The next run writes letters for the best {int(top_k)} strong matches.")
        else:
            st.sidebar.success("Saved. The next run writes a letter for every strong match.")


SCHEDULE_LABELS = {"off": "Off, I run it by hand", "daily": "Every day", "weekly": "Every week"}


def schedule_settings() -> None:
    """Sidebar form that installs or removes the systemd timer that runs the pipeline."""
    current = load_settings()
    hour, minute = map(int, current["schedule_time"].split(":"))

    with st.sidebar.form("schedule"):
        st.markdown("**Schedule**")
        schedule = st.radio(
            "Run the pipeline",
            SCHEDULES,
            index=SCHEDULES.index(current["schedule"]),
            format_func=SCHEDULE_LABELS.get,
        )
        day = st.selectbox("Day, for every week", WEEKDAYS, index=WEEKDAYS.index(current["schedule_day"]))
        time = st.time_input("Time", value=datetime.time(hour, minute), step=60)
        upcoming = next_run()
        st.caption(
            (f"Next run: {upcoming}. " if upcoming else "Not scheduled. ")
            + "systemd runs it on this computer, so it must be on; a run missed while it was off happens "
            "when it's back on. Logs: `journalctl --user -u jobradar.service`"
        )
        saved = st.form_submit_button("Save")

    if saved:
        time_text = time.strftime("%H:%M")
        # Apply first and save only if it worked, so the settings never show a schedule systemd doesn't have.
        try:
            message = apply_schedule(schedule, day, time_text)
        except ScheduleError as e:
            st.sidebar.error(str(e))
        else:
            save_settings(schedule=schedule, schedule_day=day, schedule_time=time_text)
            st.sidebar.success(f"Saved. {message}")


def history_settings() -> None:
    """Sidebar form that clears the finished jobs, so the next run scores them again with the new settings."""
    count = len(all_seen())

    with st.sidebar.form("history"):
        st.markdown("**History**")
        st.caption(
            f"{count} jobs are saved. Runs skip them, so new settings only apply to new jobs. "
            "Clearing the history removes these results, and the next run scores every listed job again "
            "and drafts new letters, which costs OpenAI credit."
        )
        confirmed = st.checkbox("I understand the next run costs more")
        cleared = st.form_submit_button("Clear history", disabled=count == 0)

    if cleared:
        if not confirmed:
            st.sidebar.error("Tick the box to confirm first.")
        else:
            deleted = clear_seen()
            st.sidebar.success(f"Cleared {deleted} jobs. A backup was saved to `{os.path.basename(backup_path())}`.")


def results_table(jobs: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Source": source_label(job),
            "Contract": CONTRACT_LABELS[job["contract_type"]],
            "Final score": job["score"],
            "LLM score": llm_score(job),
            "Domain fit": DOMAIN_LABELS[job["domain_fit"]],
            "Result": "Letter written" if job["letter"] else "No letter",
            "Job": job["title"],
            "Link": job["url"],
        }
        for job in jobs
    ])


def show_job(job: dict) -> None:
    st.subheader(job["title"])
    st.caption(f"{source_label(job)} · Contract: {CONTRACT_LABELS[job['contract_type']]}")

    left, middle, right = st.columns(3)
    left.metric("Final score", f"{job['score']}/100")
    middle.metric("LLM score", f"{llm_score(job)}/100")
    right.metric("Domain fit", DOMAIN_LABELS[job["domain_fit"]])
    st.link_button("View job posting", job["url"])

    if job["rationale"]:
        st.markdown("**Why this score**")
        st.write(job["rationale"])

    matched, missing = st.columns(2)
    with matched:
        st.markdown("**Matched skills**")
        st.write(", ".join(job["matched_skills"]) or "None recorded")
    with missing:
        st.markdown("**Missing skills**")
        st.write(", ".join(job["missing_skills"]) or "None recorded")

    if job["issues"]:
        points = "\n".join(
            f"- \"{issue['quote']}\" {issue['reason']}" if issue.get("quote") else f"- {issue['reason']}"
            for issue in job["issues"]
        )
        st.warning(f"Unverified letter. Check these points before using it:\n\n{points}")

    if job["letter"]:
        st.markdown("**Cover letter draft**")
        st.code(job["letter"], language=None, wrap_lines=True)
    else:
        st.info(f"No letter, because the final score is below {MATCH_SCORE_THRESHOLD}.")


def main() -> None:
    st.set_page_config(page_title="JobRadar", layout="wide")
    st.title("JobRadar")
    st.sidebar.header("Settings")
    contract_settings()
    source_settings()
    keyword_settings()
    delivery_settings()
    channel_settings()
    schedule_settings()
    history_settings()

    jobs = all_seen()
    if not jobs:
        st.info("No results yet. Run the pipeline with `python -m scheduler.run_daily`.")
        return

    last_run = max(job["seen_at"] for job in jobs)[:16].replace("T", " ")
    st.caption(f"Last saved: {last_run} UTC. Scores are LLM estimates and can change between runs.")

    if any(job["rationale"] is None for job in jobs):
        st.warning(
            "Some jobs were saved by an older version, so their details are missing. "
            "To fill them in, clear the history in the sidebar and run the pipeline again."
        )

    jobs_scored, strong, capped, to_check = st.columns(4)
    jobs_scored.metric("Jobs scored", len(jobs))
    strong.metric("Strong matches", sum(is_strong(job) for job in jobs))
    capped.metric("Lowered by the caps", sum(llm_score(job) > job["score"] for job in jobs))
    to_check.metric("Letters to check", sum(bool(job["issues"]) for job in jobs))

    st.header("Scores")
    st.altair_chart(score_chart(jobs), width="stretch")

    st.header("All jobs")
    st.dataframe(
        results_table(jobs),
        hide_index=True,
        width="stretch",
        column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
    )

    st.header("Job details")
    selected = st.selectbox("Job", jobs, format_func=lambda job: f"{job['score']}/100  {job['title']}")
    show_job(selected)


main()
