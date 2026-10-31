from langgraph.graph import END, START, StateGraph

from src.agents.nodes.dedup import dedup_node
from src.agents.nodes.draft_letter import draft_letter_node, revise_letter_node, verify_letter_node
from src.agents.nodes.notify import notify_telegram_node
from src.agents.nodes.score import load_profile_node, score_job_node
from src.agents.nodes.scrape import scrape_node
from src.agents.state import JobRadarState, strong_matches
from src.config import MAX_LETTER_REVISIONS


def route_by_score(state: JobRadarState) -> str:
    """Drafts letters if any job is a strong match; otherwise goes straight to the digest."""
    return "draft_letter_node" if strong_matches(state["scored_jobs"]) else "notify_telegram_node"


def route_after_verify(state: JobRadarState) -> str:
    """Sends letters with unsupported claims back for revision, up to the retry limit."""
    has_issues = any(state["letter_issues"].values())
    if has_issues and state["revision_round"] < MAX_LETTER_REVISIONS:
        return "revise_letter_node"
    return "notify_telegram_node"


def compile_graph():
    """Builds and compiles the JobRadar LangGraph state machine."""
    graph = StateGraph(JobRadarState)

    graph.add_node("scrape_node", scrape_node)
    graph.add_node("dedup_node", dedup_node)
    graph.add_node("load_profile_node", load_profile_node)
    graph.add_node("score_job_node", score_job_node)
    graph.add_node("draft_letter_node", draft_letter_node)
    graph.add_node("verify_letter_node", verify_letter_node)
    graph.add_node("revise_letter_node", revise_letter_node)
    graph.add_node("notify_telegram_node", notify_telegram_node)

    graph.add_edge(START, "scrape_node")
    graph.add_edge("scrape_node", "dedup_node")
    graph.add_edge("dedup_node", "load_profile_node")
    graph.add_edge("load_profile_node", "score_job_node")
    graph.add_conditional_edges(
        "score_job_node",
        route_by_score,
        ["draft_letter_node", "notify_telegram_node"],
    )
    graph.add_edge("draft_letter_node", "verify_letter_node")
    graph.add_conditional_edges(
        "verify_letter_node",
        route_after_verify,
        ["revise_letter_node", "notify_telegram_node"],
    )
    graph.add_edge("revise_letter_node", "verify_letter_node")
    graph.add_edge("notify_telegram_node", END)

    return graph.compile()
