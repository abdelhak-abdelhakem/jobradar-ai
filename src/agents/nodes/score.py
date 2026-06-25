from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from src.agents.state import JobRadarState, JobMatch
from src.rag.retriever import ensemble_retriever
from src.config import LLM_MODEL, LLM_TEMPERATURE

# Initialize structured LLM for scoring
llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
structured_llm = llm.with_structured_output(JobMatch)

def retrieve_profile_node(state: JobRadarState) -> JobRadarState:
    """"""
    scored_jobs = []
    list_of_new_jobs = state["new_jobs"]
    for new_job in list_of_new_jobs:
        chunks = ensemble_retriever.invoke(new_job.page_content[:500])
        scored_jobs.append({
            "doc": new_job,        # original job document
            "chunks": chunks       # retrieved profile chunks
        })
    state["scored_jobs"] = scored_jobs
    return state

def score_job_node(state: JobRadarState) -> JobRadarState:
    """"""
    updated_scored_jobs = []
    for item in state["scored_jobs"]:
        # item has doc + chunks already
        # invoke structured_llm, write job_match back into item
        context = item["chunks"]
        question = item["doc"]
        
        template = """You are a technical recruiter. Evaluate this candidate profile against the job description and return a structured assessment.
    
        Candidate Profile and Project Readme:
        {context}
    
        Question: {question}
        """
        prompt = PromptTemplate.from_template(template)

        formatted_context = "\n\n".join(doc.page_content for doc in context)
        rag_chain = prompt | structured_llm
        answer = rag_chain.invoke({"context": formatted_context, "question": question.page_content})
        
        updated_scored_jobs.append({
            "doc": question,       # original job document
            "chunks": context,     # retrieved profile chunks
            "job_match": answer    # structured_llm answer
        })
        
    state["scored_jobs"] = updated_scored_jobs
    return state