from langgraph.graph import StateGraph, START, END
from src.agents.state import JobRadarState
from src.agents.nodes.scrape import scrape_node
from src.agents.nodes.dedup import dedup_node
from src.agents.nodes.score import retrieve_profile_node, score_job_node
from src.agents.nodes.draft_letter import draft_letter_node
from src.agents.nodes.notify import notify_telegram_node

def route_by_score(state: JobRadarState) -> str:
    """The conditional edge after score_job_node: if match_score >= 70, route to draft_letter_node; otherwise skip straight to notify_telegram_node with just the score (no letter for weak matches)"""
    if not state["scored_jobs"]:
        return "notify_telegram_node"
        
    top_score = max(item["job_match"].match_score for item in state["scored_jobs"])
    if top_score >= 70:
        return "draft_letter_node"
    return "notify_telegram_node"

def compile_graph():
    """Builds and compiles the JobRadar LangGraph state machine."""
    graph = StateGraph(JobRadarState)

    graph.add_node("scrape_node", scrape_node)
    graph.add_node("dedup_node", dedup_node)
    graph.add_node("retrieve_profile_node", retrieve_profile_node)
    graph.add_node("score_job_node", score_job_node)
    graph.add_node("draft_letter_node", draft_letter_node)
    graph.add_node("notify_telegram_node", notify_telegram_node)

    graph.add_edge(START, "scrape_node")
    graph.add_edge("scrape_node", "dedup_node")
    graph.add_edge("dedup_node", "retrieve_profile_node")
    graph.add_edge("retrieve_profile_node", "score_job_node")
    
    graph.add_conditional_edges(
        "score_job_node",
        route_by_score,
        {
            "draft_letter_node": "draft_letter_node",
            "notify_telegram_node": "notify_telegram_node"
        }
    )

    graph.add_edge("draft_letter_node", "notify_telegram_node")  
    graph.add_edge("notify_telegram_node", END)

    return graph.compile()