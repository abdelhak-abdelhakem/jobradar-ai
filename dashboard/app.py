"""
View of the pipeline's saved results, with a sidebar to choose the job sources and search keywords for the next run.
It makes no LLM or Telegram calls.

  python -m streamlit run dashboard/app.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altair as alt
import pandas as pd
import streamlit as st

from src.config import MATCH_SCORE_THRESHOLD
from src.db.seen_jobs import all_seen
from src.settings import SOURCES, load_settings, save_settings

# Passes colour-blindness and contrast checks on both Streamlit's light and dark backgrounds.
FINAL_COLOR = "#2a78d6"
LLM_COLOR = "#d95926"
NEUTRAL_COLOR = "#8a8984"

DOMAIN_LABELS = {"direct": "Direct", "adjacent": "Adjacent", "none": "None", None: "Not recorded"}


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


def source_settings() -> None:
    """Sidebar form that chooses which job boards the next run scrapes."""
    st.sidebar.header("Settings")
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
    """Sidebar form that edits the keywords a job must match before it reaches the LLM."""
    current = load_settings()

    with st.sidebar.form("keywords"):
        st.markdown("**Search keywords**")
        st.caption(
            "One keyword per line, matched as whole words. Keywords in capitals, such as AI, "
            "match only in capitals, so AI doesn't match the French \"j'ai\"."
        )
        role_text = st.text_area(
            "Role keywords",
            value="\n".join(current["role_keywords"]),
            help="A job title must contain one of these. Used for Inria; CNRS and CEA filter the contract type on their own site.",
        )
        domain_text = st.text_area(
            "Domain keywords",
            value="\n".join(current["domain_keywords"]),
            help="The job title or description must contain one of these.",
        )
        saved = st.form_submit_button("Save")

    if saved:
        try:
            save_settings(role_keywords=role_text.splitlines(), domain_keywords=domain_text.splitlines())
        except ValueError as e:
            st.sidebar.error(str(e))
        else:
            st.sidebar.success("Saved. The next run uses these keywords. Jobs already handled aren't scored again.")


def results_table(jobs: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Source": source_label(job),
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
    source_settings()
    keyword_settings()

    jobs = all_seen()
    if not jobs:
        st.info("No results yet. Run the pipeline with `python -m scheduler.run_daily`.")
        return

    last_run = max(job["seen_at"] for job in jobs)[:16].replace("T", " ")
    st.caption(f"Last saved: {last_run} UTC. Scores are LLM estimates and can change between runs.")

    if any(job["rationale"] is None for job in jobs):
        st.warning(
            "Some jobs were saved by an older version, so their details are missing. "
            "To fill them in, delete `data/seen_jobs.sqlite3` and run the pipeline again."
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
