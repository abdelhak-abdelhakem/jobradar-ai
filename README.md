# JobRadar AI 🎯

An AI agent built with LangGraph that finds AI internships on three French research job boards (Inria, CNRS, and CEA), scores them against my CV, drafts cover letters for strong matches, fact-checks those letters against the CV, and sends a ranked digest to Telegram.

Most steps run in a fixed order on purpose, so the agent stays predictable, cheap, and testable. The agentic part is the letter loop: the agent checks its own letter against the CV, and that check decides whether the letter goes back for revision, up to 2 times.

> **Status:** Working prototype with three job sources. Letters are drafts for me to review, and nothing is sent to employers.

---

## Architecture

```
START
  → scrape_node            # finds internships on the Inria, CNRS, and CEA boards and fetches full pages
  → dedup_node             # drops jobs already finished in an earlier run (SQLite)
  → load_profile_node      # loads the whole CV
  → score_job_node         # LLM scores each job → JobMatch (rationale, skills, score)
  → [any score ≥ 70?]
        no  → notify_telegram_node
        yes → draft_letter_node
                → verify_letter_node   # checks each letter's claims against the CV
                → [unsupported claims and revisions left?]
                      yes → revise_letter_node → back to verify_letter_node
                      no  → notify_telegram_node
  → notify_telegram_node   # sends the ranked digest and letters, then records finished jobs
  → END
```

### Design decisions

- **Whole CV instead of RAG:** the first version retrieved up to 6 chunks of 300 characters, under a third of a 6 KB CV. Letters came back signed "Nom du candidat" and scores were based on fragments, so the LLM now gets the whole CV.
- **Jobs are recorded only once they're handled:** failed scrapes, scores, letters, and Telegram sends are all retried on the next run.
- **Key requirements are enforced in code:** whatever score the LLM returns, non-internships are capped at 40, jobs with no link to the candidate's experience at 60, and jobs in a new domain that use familiar methods at 79.
- **Flagged sentences get deleted:** if a rewrite keeps a sentence the checker flagged, code removes it. The last revision round only deletes, so it can't add new claims.
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
| Notifications | Telegram Bot API |
| Dashboard | Streamlit + Altair |
| Scraping | requests + BeautifulSoup |
| Tests and CI | pytest + GitHub Actions |

---

## Setup

```bash
git clone https://github.com/abdelhak-abdelhakem/jobradar-ai.git
cd jobradar-ai
pip install -r requirements.txt

cp .env.example .env                                       # then fill in your keys
cp data/profile/example_profile.md data/profile/my_profile.md   # then replace with your CV

python -m scheduler.run_daily
```

The first run scores every matching job. Later runs only process new ones. A run sends a Telegram message even when nothing matches, so you can tell a quiet day from a broken pipeline. It runs once per call, so use cron or similar to run it daily.

## Dashboard

A page showing every scored job: its source, the LLM's score against the final score, the rationale, skills, and letter draft. It uses saved results, so it makes no API calls.

The sidebar chooses which job boards the next run scrapes. The choice is saved in `data/settings.json`, and if that file is missing, every board is used.

```bash
python -m streamlit run dashboard/app.py
```

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
- [x] Tests and CI
- [x] Results dashboard
- [x] Choose the job sources in the dashboard
- [ ] Label jobs and publish scoring results
- [x] Re-measure runtime and cost
- [ ] Telegram approval step with a LangGraph checkpointer and `interrupt`
- [x] CNRS and CEA scrapers
- [ ] Stricter "adjacent" domain fit in scoring
- [ ] More job sources that allow automated access
- [ ] Job normalization and dedup across sources
- [ ] Application tracking
- [ ] Daily scheduled deployment

---

## About

Built as the capstone project of a 4-week LangGraph preparation program, with the first version completed in 15 days (June 10–25, 2026). Presented on November 11, 2026, as the project for the *Séminaires et Workshop IA* module at Université Djillali Liabès.

Preceded by:

- **[learning-langgraph](https://github.com/abdelhak-abdelhakem/learning-langgraph)** — exercises and mini-projects covering LangGraph, Pydantic structured output, hybrid RAG, web scraping, and Telegram integration
- **[Hasnaoui Bot](https://github.com/abdelhak-abdelhakem)** — production enterprise RAG chatbot (Context Precision 0.892, Answer Relevancy 0.702, $0.00079/query)

---

*Abdelhak ABDELHAKEM — AI Engineering Student, Université Djillali Liabès*
*[GitHub](https://github.com/abdelhak-abdelhakem) · [LinkedIn](https://linkedin.com/in/abdelhak-abdelhakem)*
