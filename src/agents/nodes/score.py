from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from src.agents.state import JobRadarState, JobMatch
from src.rag.retriever import ensemble_retriever
from src.config import LLM_MODEL, LLM_TEMPERATURE

# Initialize structured LLM for scoring
llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
structured_llm = llm.with_structured_output(JobMatch)

def retrieve_profile_node(state: JobRadarState) -> JobRadarState:
    """Retrieves profile chunks for new jobs in parallel."""
    list_of_new_jobs = state["new_jobs"]
    inputs = [new_job.page_content[:500] for new_job in list_of_new_jobs]
    all_chunks = ensemble_retriever.batch(inputs)
    scored_jobs = [
        {
            "doc": job,          
            "chunks": chunks    
        }
        for job, chunks in zip(list_of_new_jobs, all_chunks)
    ]
    state["scored_jobs"] = scored_jobs
    return state


def score_job_node(state: JobRadarState) -> JobRadarState:
    """Scores jobs in parallel using the LLM."""
    template = """You are a technical recruiter. Evaluate this candidate profile against the job description and return a structured assessment.
    
        Candidate Profile and Project Readme:
        {context}
    
        Question: {question}
        """
    prompt = PromptTemplate.from_template(template)
    rag_chain = prompt | structured_llm

    inputs = []
    all_chunks = []
    all_doc = []
    for item in state["scored_jobs"]:
        context = item["chunks"]
        question = item["doc"]

        all_chunks.append(context)
        all_doc.append(question)

        formatted_context = "\n\n".join(c.page_content for c in context)
        inputs.append(
            {"context": formatted_context, 
            "question": question.page_content}
            )
        
    answers = rag_chain.batch(inputs)

    updated_scored_jobs = [
        {
            "doc": question,       # original job document
            "chunks": context,     # retrieved profile chunks
            "job_match": answer    # structured_llm answer
        }
        for question, context,answer in zip(all_doc, all_chunks,answers)
    ]

    state["scored_jobs"] = updated_scored_jobs
    return state