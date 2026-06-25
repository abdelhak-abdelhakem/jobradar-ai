from src.agents.graph import compile_graph

if __name__ == "__main__":
    app = compile_graph()
    app.invoke({
        "job_listings": [],
        "new_jobs": [],
        "scored_jobs": [],
        "cover_letters": {},
        "digest_sent": False
    })