from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from src.agents.state import JobRadarState
from src.config import LLM_MODEL, LLM_TEMPERATURE

llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)



TEMPLATE = """You are an expert Career Coach, HR Specialist, and Professional Cover Letter Writer.

Your task is to generate a highly personalized and professional motivation letter (cover letter) based on:

1. The Job Description provided by the user.
2. The Candidate Profile retrieved from the vector database (CV, skills, education, projects, experience, certifications, languages, achievements).

## Objective

Create a motivation letter that maximizes the alignment between the candidate's profile and the job requirements.

The letter must:

* Highlight the most relevant skills and experiences.
* Demonstrate understanding of the company's needs.
* Explain why the candidate is a strong fit.
* Remain truthful and only use information available in the candidate profile.
* Be professional, persuasive, and human-like.
* Avoid generic statements whenever possible.

## Writing Guidelines

1. Analyze the job description carefully:

* Required skills
* Preferred skills
* Responsibilities
* Technologies
* Industry/domain
* Education requirements

2. Analyze the candidate profile:

* Technical skills
* Projects
* Professional experience
* Academic background
* Certifications
* Languages
* Achievements

3. Identify the strongest matches between the candidate and the position.

4. Generate a motivation letter with the following structure:

### Introduction

* Mention the position.
* Express enthusiasm for the opportunity.

### Body Paragraph 1

* Present the candidate's educational background and relevant expertise.

### Body Paragraph 2

* Highlight the most relevant skills, projects, and experiences that match the job description.

### Body Paragraph 3

* Explain why the candidate is interested in the company or role.
* Show how the candidate can contribute.

### Conclusion

* Reaffirm motivation.
* Thank the recruiter.
* Express availability for an interview.

## Constraints

* Do NOT invent experiences, degrees, projects, companies, certifications, or skills.
* Do NOT mention information that does not exist in the retrieved profile.
* If some job requirements are missing from the profile, focus on transferable skills and learning ability.
* Keep a professional and confident tone.
* Avoid repeating the same information.
* Use clear and concise language.
* Generate between 300 and 500 words unless the user requests otherwise.

## Output Format

Return only the final motivation letter in well-formatted text.

### Input

Job Description:
{question}

### Candidate Profile:

{context}

Generate the motivation letter.
"""

prompt = PromptTemplate.from_template(TEMPLATE)
rag_chain = prompt | llm | StrOutputParser()

def draft_letter_node(state: JobRadarState) -> JobRadarState:
    """
    Filters jobs with a match score of 70+ and uses a batched LLM call to generate 
    personalized cover letters for them.
    """
    
    cover_letters_dict = {} 
    
    inputs_for_llm = []
    valid_job_ids = []
    
    for item in state["scored_jobs"]:
        job_id = item["doc"].metadata["job_id"]
        
        if item["job_match"].match_score < 70: 
            cover_letters_dict[job_id] = {}
        else: 
            formatted_context = "\n\n".join(doc.page_content for doc in item["chunks"])
            
            inputs_for_llm.append({
                "context": formatted_context, 
                "question": item["doc"].page_content
            })
            
            valid_job_ids.append(job_id)

    if inputs_for_llm:
        generated_letters = rag_chain.batch(inputs_for_llm)
        
        for job_id, letter in zip(valid_job_ids, generated_letters):
            cover_letters_dict[job_id] = letter

    state["cover_letters"] = cover_letters_dict
    
    return state