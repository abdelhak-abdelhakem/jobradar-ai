# TODO: Future implementation# JobRadar AI 🎯

An autonomous LangGraph agent that scrapes Paris AI job boards daily, scores postings against my profile via hybrid RAG retrieval, drafts personalized cover letters for strong matches, and delivers a ranked digest to Telegram.

> **Status:** Prototype complete — multi-source scraping and EC2 deployment in progress.

---

## Demo

One pipeline run: **153 jobs scraped → scored → 11 cover letters drafted → Telegram digest delivered** in a single autonomous execution for **$0.23**.

---

## Architecture

```
START
  → scrape_node          # scrapes Inria job board (full detail pages)
  → dedup_node           # skips already-seen jobs via ID-based Chroma check
  → retrieve_profile_node # hybrid RAG retrieval (BM25 + embeddings) over CV
  → score_job_node        # LLM scores each job → JobMatch (score, rationale, skills)
  → [score ≥ 70?]
        yes → draft_letter_node   # RAG-augmented cover letter generation
        no  → notify_telegram_node
  → notify_telegram_node  # formats and pushes digest to Telegram
  → END
```

### Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM | OpenAI GPT (gpt-5-nano) |
| Embeddings | text-embedding-3-small |
| Vector store | ChromaDB (persistent) |
| Hybrid retrieval | BM25 + ChromaDB + EnsembleRetriever |
| Structured output | Pydantic + `with_structured_output()` |
| Observability | LangSmith |
| Notifications | Telegram Bot API |
| Scraping | requests + BeautifulSoup |

---

## Project Structure

```
jobradar-ai/
├── data/
│   ├── chroma/                  # persistent vector stores
│   └── profile/
│       └── my_profile.md        # CV and project descriptions (RAG source)
├── scheduler/
│   └── run_daily.py             # entrypoint — runs the full pipeline
└── src/
    ├── agents/
    │   ├── graph.py             # LangGraph graph definition
    │   ├── state.py             # JobRadarState TypedDict
    │   └── nodes/
    │       ├── scrape.py        # Inria scraper with full detail pages
    │       ├── dedup.py         # ID-based deduplication against Chroma
    │       ├── score.py         # hybrid retrieval + LLM scoring
    │       ├── draft_letter.py  # RAG-augmented cover letter generation
    │       └── notify.py        # Telegram digest formatter and sender
    ├── rag/
    │   ├── ingest.py            # chunks and embeds profile documents
    │   ├── retriever.py         # EnsembleRetriever (BM25 + Chroma)
    │   └── vectorstore.py       # ChromaDB client wrapper
    ├── scrapers/
    │   ├── inria_offres.py      # Inria jobs scraper ✅
    │   ├── linkedin.py          # coming soon
    │   └── welcome_to_jungle.py # coming soon
    ├── api/
    │   └── main.py              # FastAPI dashboard (coming soon)
    ├── evaluation/
    │   └── ragas_eval.py        # scoring precision evaluation (coming soon)
    ├── db/
    │   ├── models.py            # SQLModel: JobPosting, Application, ScoreLog
    │   └── session.py
    ├── utils/
    │   └── telegram.py          # send_message() helper
    └── config.py                # centralized configuration
```

---

## Pipeline Results (Prototype Run — June 25, 2026)

| Metric | Value |
|---|---|
| Jobs scraped (Inria) | 153 |
| Duplicates skipped | 0 (first run) |
| Jobs scored | 153 |
| Jobs with score ≥ 70 | 11 |
| Cover letters drafted | 11 |
| Telegram notifications sent | 153 |
| Total tokens | 897,700 |
| Total cost | $0.2339 |
| Runtime | 70 min (sequential — `.batch()` optimization pending) |

---

## Setup

**1. Clone and install**
```bash
git clone https://github.com/abdelhak-abdelhakem/jobradar-ai.git
cd jobradar-ai
pip install -r requirements.txt
```

**2. Environment variables**

Create a `.env` file:
```env
OPENAI_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
CHAT_ID=your_chat_id
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=jobradar-ai
```

**3. Ingest your profile**
```bash
python src/rag/ingest.py
```

**4. Run the pipeline**
```bash
python scheduler/run_daily.py
```

---

## Roadmap

- [x] Inria scraper with full detail page extraction
- [x] ID-based deduplication against ChromaDB
- [x] Hybrid RAG retrieval (BM25 + embeddings) over candidate profile
- [x] Structured job scoring via Pydantic + LangGraph
- [x] Conditional cover letter drafting (score ≥ 70)
- [x] Telegram digest notifications
- [x] LangSmith observability
- [ ] `.batch()` parallelization (target: < 10 min runtime)
- [ ] Welcome to the Jungle scraper
- [ ] LinkedIn scraper
- [ ] Cross-source embedding dedup
- [ ] FastAPI dashboard (`GET /jobs`, `GET /jobs/{id}/letter`)
- [ ] SQLModel job tracking database
- [ ] RAGAS-style scoring evaluation
- [ ] AWS EC2 daily scheduler deployment

---

## About

Built as the capstone project of a 4-week LangGraph preparation program, completed in 15 days (June 10–25, 2026). Preceded by:

- **[learning-langgraph](https://github.com/abdelhak-abdelhakem/learning-langgraph)** — exercises and mini-projects covering LangGraph, Pydantic structured output, hybrid RAG, web scraping, and Telegram integration
- **[Hasnaoui Bot](https://github.com/abdelhak-abdelhakem)** — production enterprise RAG chatbot (Context Precision 0.892, Answer Relevancy 0.702, $0.00079/query) that established the hybrid retrieval pattern used here

---

*Abdelhak ABDELHAKEM — AI Engineering Student, Université Djillali Liabès*
*[GitHub](https://github.com/abdelhak-abdelhakem) · [LinkedIn](https://linkedin.com/in/abdelhak-abdelhakem)*