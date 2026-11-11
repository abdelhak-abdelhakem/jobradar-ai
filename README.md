# JobRadar AI 🎯

An AI agent built with LangGraph that finds AI internships or PhD positions on three French research job boards (Inria, CNRS, and CEA), scores them against my CV, drafts cover letters for strong matches, fact-checks those letters against the CV, and sends a ranked digest to Telegram, Gmail, or both.

Most steps run in a fixed order on purpose, so the agent stays predictable, cheap, and testable. The agentic part is the letter loop: the agent checks its own letter against the CV, and that check decides whether the letter goes back for revision, up to 2 times.

> **Status:** Working prototype with three job sources. Letters are drafts for me to review, and nothing is sent to employers.

---

## Architecture

```
START
  → scrape_node            # finds offers of the chosen contract type on the Inria, CNRS, and CEA boards and fetches full pages
  → dedup_node             # drops jobs already finished in an earlier run (SQLite)
  → load_profile_node      # loads the whole CV
  → score_job_node         # LLM scores each job → JobMatch (rationale, skills, score)
  → [any score ≥ 70?]
        no  → notify_node
        yes → draft_letter_node
                → verify_letter_node   # checks each letter's claims against the CV
                → [unsupported claims and revisions left?]
                      yes → revise_letter_node → back to verify_letter_node
                      no  → notify_node
  → notify_node            # sends the digest and letters on each channel, then records finished jobs
  → END
```

### Design decisions

- **Whole CV instead of RAG:** the first version retrieved up to 6 chunks of 300 characters, under a third of a 6 KB CV. Letters came back signed "Nom du candidat" and scores were based on fragments, so the LLM now gets the whole CV.
- **Jobs are recorded only once they're handled:** failed scrapes, scores, letters, and Telegram sends are all retried on the next run.
- **Key requirements are enforced in code:** whatever score the LLM returns, jobs with another contract type than the one searched for are capped at 40, jobs with no link to the candidate's experience at 60, and jobs in a new domain that use familiar methods at 79.
- **Flagged sentences get deleted:** if a rewrite keeps a sentence the checker flagged, code removes it. The last revision round only deletes, so it can't add new claims.
- **The LLM reports facts, code applies the rules:** the LLM reports each posting's contract type (internship, PhD, or other) and code compares it with the one searched for. The allowed types come from one list in `src/config.py`, so the scoring schema, the settings, and the dashboard can't disagree.
- **Failures stay contained:** one failed LLM call doesn't stop the batch, and one broken job board doesn't stop the others.
- **Boilerplate is ignored when filtering:** each board repeats the same "about us" text on every offer, and Inria's mentions AI, so the keyword filter skips it. On CEA the filter also skips the lab description, which often mentions AI even when the internship doesn't.

### Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph |
| LLM | OpenAI gpt-5-nano |
| Structured output | Pydantic + `with_structured_output()` |
| Job history | SQLite |
| Observability | LangSmith (optional) |
| Notifications | Telegram Bot API, Gmail over SMTP |
| Dashboard | Streamlit + Altair |
| Scraping | requests + BeautifulSoup |
| Tests and CI | pytest + GitHub Actions |

---

## Setup

```bash
git clone https://github.com/abdelhak-abdelhakem/jobradar-ai.git
cd jobradar-ai
pip install -r requirements.txt

cp .env.example .env                                       # then fill in your keys (Gmail is optional)
cp data/profile/example_profile.md data/profile/my_profile.md   # then replace with your CV

python -m scheduler.run_daily
```

To get the digest by email, create a Gmail [App Password](https://myaccount.google.com/apppasswords) (it needs 2-Step Verification), put the address and the password in `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` in `.env`, and choose Gmail in the dashboard. A separate Gmail account for JobRadar keeps your own account out of it.

The first run scores every matching job. Later runs only process new ones. A run sends a Telegram message even when nothing matches, so you can tell a quiet day from a broken pipeline. Each call runs the pipeline once; to run it automatically, see [Schedule](#schedule). Two runs never overlap: a run started while another is still going exits at once.

## Dashboard

A page showing every scored job: its source, the LLM's score against the final score, the rationale, skills, and letter draft. It uses saved results, so it makes no API calls.

The sidebar sets up the next run:

- **Contract type:** an internship or a PhD position. CNRS and CEA filter on it in their own search forms; CEA publishes its PhD offers on another site, so PhD searches skip it. Inria has no such filter, so a job title there must contain one of the contract type's role keywords, such as "stage" or "M2" for internships and "PhD" or "thèse" for PhD positions. These come from the contract type in `src/config.py` and aren't a separate setting, so they can never disagree with it.
- **Job sources:** which job boards to scrape.
- **Search keywords:** the domain keywords a job's title or description must match before it reaches the LLM, one per line. Keywords in capitals, such as "AI", match only in capitals, so "AI" doesn't match the French "j'ai".
- **Letters:** a letter for every strong match (70 or more), or only for the best K, from 1 to 50. Each letter costs several LLM calls (draft, claim check, revisions), so a small K makes runs cheaper. With the best K, the other strong matches aren't recorded: the next run scores them again and they compete with the new jobs, and the digest says how many are waiting. A job that never makes the top K is scored again on every run while it's still listed.
- **Notifications:** Telegram (the default), Gmail, or both. A job counts as sent once any chosen channel delivers it, so if Telegram is down but Gmail works, it isn't sent again the next day; if every channel fails, it's retried. Gmail sends the whole digest, letters included, as one email to the address in `.env`. The form warns when a chosen channel has no credentials there.
- **Schedule:** off, every day, or every week at a chosen time; see [Schedule](#schedule).

The settings are saved in `data/settings.json`. Each setting that's missing or invalid falls back to its default: internships, every board, and the domain keywords in `src/config.py`. Changing the settings doesn't rescore jobs that earlier runs already handled. To apply new settings to them, **Clear history** in the sidebar deletes the saved jobs, so the next run scores every listed job again and drafts new letters, which costs OpenAI credit. It asks for confirmation and first copies the database to `data/seen_jobs.backup.sqlite3`; to undo, copy that file back to `data/seen_jobs.sqlite3`.

```bash
python -m streamlit run dashboard/app.py
```

## Schedule

The dashboard's **Schedule** form runs the pipeline every day or every week at a chosen time, on Linux. The dashboard can't run it itself, because Streamlit only runs while its page is open, so the form installs a systemd user timer in `~/.config/systemd/user/` (no `sudo` needed):

- `jobradar.timer` wakes up at the chosen time, and `jobradar.service` runs `python -m scheduler.run_daily`.
- The computer must be on. A run missed while it was off happens as soon as it's back on (`Persistent=true`).
- Choosing **Off** stops the timer and removes both files.

```bash
systemctl --user list-timers jobradar.timer   # when the next run is
journalctl --user -u jobradar.service         # what the runs printed
```

User timers run while you're logged in. To run them when you're logged out too, run `loginctl enable-linger` once. On Windows or macOS, use Task Scheduler or launchd to run `python -m scheduler.run_daily` instead.

## Tests

The tests run the real graph with the LLM, Telegram, and the job boards faked, so they need no API keys and cost nothing.

```bash
pip install -r requirements-dev.txt
pytest
```

## Measuring scoring quality

Compare the LLM's scores with your own judgement:

```bash
python -m src.evaluation.evaluate_scoring export data/eval_labels.csv
# fill in the label column: 1 = I'd apply, 0 = I wouldn't (aim for 30 to 50 jobs)
python -m src.evaluation.evaluate_scoring report data/eval_labels.csv
```

This reports precision@k and rank correlation. No results yet, because the jobs still need labelling.

---

## Results

### Latest run (November 5, 2026)

| Step | Inria | CNRS | CEA | Total |
|---|---|---|---|---|
| Internships listed | 15 | 10 | 95 | 120 |
| Passed the keyword filter | 9 | 3 | 46 | 58 |
| New since earlier runs | 1 | 3 | 46 | 50 |

Of the 50 new jobs, 23 scored 70 or more and got a letter. 21 letters passed the claim check, and 2 were sent marked as unverified after 2 revisions. The run took 17 minutes 27 seconds and cost $0.21 in OpenAI usage.

Known issue: a few internships where AI is only a tool for another science, such as biology image analysis or particle physics, were rated an "adjacent" fit and scored 72 to 75. Raising the threshold wouldn't fix this, because they score close to relevant jobs. The fix belongs in the scoring prompt.

### First prototype

The first prototype run, on June 25, 2026, scraped and scored 153 Inria jobs, drafted 11 letters, and used 897,700 tokens for $0.23 in 70 minutes. That version had no batching, keyword filter, or letter check, so these numbers don't describe the current pipeline.

---

## Roadmap

- [x] Inria scraper with full page extraction
- [x] Dedup across runs
- [x] Structured job scoring
- [x] Cover letter drafting with a claim check and revision loop
- [x] Ranked Telegram digest
- [x] Gmail as a second channel
- [x] Tests and CI
- [x] Results dashboard
- [x] Choose the job sources in the dashboard
- [x] Edit the search keywords in the dashboard
- [x] Choose the contract type in the dashboard (internship or PhD)
- [x] Clear the job history from the dashboard
- [x] Letters for every strong match or only the best K
- [ ] Label jobs and publish scoring results
- [x] Re-measure runtime and cost
- [ ] Telegram approval step with a LangGraph checkpointer and `interrupt`
- [x] CNRS and CEA scrapers
- [ ] Stricter "adjacent" domain fit in scoring
- [ ] More job sources that allow automated access
- [ ] Job normalization and dedup across sources
- [ ] Application tracking
- [x] Scheduled runs with a systemd timer

---

## About

Built as the capstone project of a 4-week LangGraph preparation program, with the first version completed in 15 days (June 10–25, 2026). Presented on November 11, 2026, as the project for the *Séminaires et Workshop IA* module at Université Djillali Liabès.

Preceded by:

- **[learning-langgraph](https://github.com/abdelhak-abdelhakem/learning-langgraph)** — exercises and mini-projects covering LangGraph, Pydantic structured output, hybrid RAG, web scraping, and Telegram integration
- **[Hasnaoui Bot](https://github.com/abdelhak-abdelhakem)** — production enterprise RAG chatbot (Context Precision 0.892, Answer Relevancy 0.702, $0.00079/query)

---

*Abdelhak ABDELHAKEM — AI Engineering Student, Université Djillali Liabès*
*[GitHub](https://github.com/abdelhak-abdelhakem) · [LinkedIn](https://linkedin.com/in/abdelhak-abdelhakem)*
