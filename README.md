# JobRadar AI 🎯

An LLM pipeline built with LangGraph that finds AI internships on the Inria job board, scores them against my CV, drafts cover letters for strong matches, fact-checks those letters against the CV, and sends a ranked digest to Telegram.

Most of the flow is fixed. The agent-style part is the letter loop, where an LLM check decides whether each letter goes back for revision.

> **Status:** Working prototype with one job source. Letters are drafts for me to review, and nothing is sent to employers.

---

## Architecture

```
START
  → scrape_node            # finds internships on the Inria board and fetches full pages
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
- **The internship requirement is enforced in code:** non-internships are capped at a score of 40, whatever the LLM returns.
- **Failures stay contained:** one failed LLM call doesn't stop the batch.

### Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph |
| LLM | OpenAI gpt-5-nano |
| Structured output | Pydantic + `with_structured_output()` |
| Job history | SQLite |
| Observability | LangSmith (optional) |
| Notifications | Telegram Bot API |
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

## Tests

The tests run the real graph with the LLM, Telegram, and the job board faked, so they need no API keys and cost nothing.

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

## Earlier results

The first prototype run, on June 25, 2026, scraped and scored 153 Inria jobs, drafted 11 letters, and used 897,700 tokens for $0.23 in 70 minutes. That version had no batching, keyword filter, or letter check, so these numbers don't describe the current pipeline.

---

## Roadmap

- [x] Inria scraper with full page extraction
- [x] Dedup across runs
- [x] Structured job scoring
- [x] Cover letter drafting with a claim check and revision loop
- [x] Ranked Telegram digest
- [x] Tests and CI
- [ ] Label jobs and publish scoring results
- [ ] Re-measure runtime and cost
- [ ] Telegram approval step with a LangGraph checkpointer and `interrupt`
- [ ] More job sources that allow automated access
- [ ] Job normalization and dedup across sources
- [ ] Dashboard and application tracking
- [ ] Daily scheduled deployment

---

## About

Built as the capstone project of a 4-week LangGraph preparation program, with the first version completed in 15 days (June 10–25, 2026). Preceded by:

- **[learning-langgraph](https://github.com/abdelhak-abdelhakem/learning-langgraph)** — exercises and mini-projects covering LangGraph, Pydantic structured output, hybrid RAG, web scraping, and Telegram integration
- **[Hasnaoui Bot](https://github.com/abdelhak-abdelhakem)** — production enterprise RAG chatbot (Context Precision 0.892, Answer Relevancy 0.702, $0.00079/query)

---

*Abdelhak ABDELHAKEM — AI Engineering Student, Université Djillali Liabès*
*[GitHub](https://github.com/abdelhak-abdelhakem) · [LinkedIn](https://linkedin.com/in/abdelhak-abdelhakem)*
