from src.agents.state import JobRadarState
from src.utils.telegram import send_message

def notify_telegram_node(state: JobRadarState) -> JobRadarState:
    """send notification in telegram"""
    for item in state["scored_jobs"]:
        job_id = item["doc"].metadata["job_id"]
        score = item["job_match"].match_score
        title = item["doc"].metadata.get("title", "Unknown")
        url = item["doc"].metadata["url"]
        cover_letter = state["cover_letters"].get(job_id, "") 
        
        if len(cover_letter) > 10: # check if the cover letter exist 
            send_message(f"""*🎯 {title}*

*Score:* {score}/100
*cover letter: * {cover_letter}  
[View Job]({url})""")
        else: 
            send_message(f"""*🎯 {title}*

*Score:* {score}/100

[View Job]({url})""")
            
    state["digest_sent"] = True
    return state