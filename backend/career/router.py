from fastapi import APIRouter,File,HTTPException,UploadFile
from pydantic import BaseModel,Field
from .core import add_candidate,get_candidate,job,job_match,profile,score,text_from_pdf,interview_question,evaluate_answer,save_candidate
from .schemas import InterviewAnswerRequest, InterviewStartRequest
from .storage import CareerStorageError
router=APIRouter(prefix="/career",tags=["career"]); MAX=5*1024*1024
class Session(BaseModel): session_id:str
class JD(Session): description:str=Field(max_length=30000)
@router.post("/resume/upload")
async def upload(resume:UploadFile=File(...)):
    if not (resume.filename or "").lower().endswith(".pdf") or resume.content_type not in {"application/pdf","application/x-pdf"}: raise HTTPException(415,"Upload a PDF resume.")
    data=await resume.read(); await resume.close()
    if not data or len(data)>MAX: raise HTTPException(413,"Resume must be a non-empty PDF under 5 MB.")
    try: text=text_from_pdf(data)
    except ValueError as e: raise HTTPException(422,str(e)) from e
    p=profile(text)
    try: sid=add_candidate(p,text)
    except CareerStorageError as e: raise HTTPException(503,"Career Coach storage is temporarily unavailable. Please try again.") from e
    return {"session_id":sid,"candidate_session_id":sid,"resume":p}
def candidate_or_404(sid):
    try: c=get_candidate(sid)
    except CareerStorageError as e: raise HTTPException(503,"Career Coach storage is temporarily unavailable. Please try again.") from e
    if not sid: raise HTTPException(400,"Please upload your resume first.")
    if not c: raise HTTPException(404,"Resume session not found. Please upload your resume again.")
    return c
@router.post("/resume/analyze")
def analyze(r:Session):
    c=candidate_or_404(r.session_id); return c["resume_analysis"]
@router.post("/job/parse")
def parse(r:JD):
    if not r.description.strip(): raise HTTPException(400,"Job description cannot be empty.")
    c=candidate_or_404(r.session_id); c["job"]=job(r.description)
    try: save_candidate(r.session_id,c)
    except CareerStorageError as e: raise HTTPException(503,"Career Coach storage is temporarily unavailable. Please try again.") from e
    return c["job"]
@router.post("/job/match")
def match(r:Session):
    c=candidate_or_404(r.session_id)
    if not c["job"]: raise HTTPException(422,"Parse a job description before matching.")
    return job_match(c["profile"],c["job"])
@router.post("/resume/tailor")
def tailor(r:Session):
    c=candidate_or_404(r.session_id)
    if not c["job"]: raise HTTPException(422,"Parse a job description before tailoring.")
    return {"improved_summary":"Use only verified skills and projects: [add target-role focus based on your actual experience].","recommended_skills_order":[s for s in c["job"]["required_skills"] if s in c["profile"]["skills"]],"project_bullet_improvements":[f"For: {p} — describe contribution and [Add a measurable result if available]." for p in c["profile"]["projects"][:3]],"missing_keywords":sorted(set(c["job"]["required_skills"])-set(c["profile"]["skills"])),"safety_note":"No jobs, technologies, certifications, or metrics were invented."}

_interviews = {}
@router.post("/interview/start")
def start_interview(request: InterviewStartRequest):
    candidate = candidate_or_404(request.candidate_session_id)
    if request.job_description: candidate["job"] = job(request.job_description)
    if not candidate["job"]: raise HTTPException(422, "Provide or parse a job description before starting an interview.")
    from uuid import uuid4
    iid=str(uuid4()); question, category=interview_question(candidate["profile"],candidate["job"],request.difficulty,round_name="project")
    _interviews[iid]={"candidate_id":request.candidate_session_id,"type":request.interview_type,"difficulty":request.difficulty,"questions":[{"text":question,"category":category}],"answers":[],"evaluations":[],"covered_topics":[category],"rounds":["project","technical","architecture","problem_solving","fundamentals","behavioral"],"round_index":0}
    return {"interview_session_id":iid,"question_number":1,"question":question,"category":category,"difficulty":request.difficulty}

@router.post("/interview/answer")
def interview_answer(request: InterviewAnswerRequest):
    state=_interviews.get(request.interview_session_id)
    if not state: raise HTTPException(404,"Interview session was not found.")
    evaluation=evaluate_answer(request.answer); previous=state["difficulty"]
    if evaluation["score"] < 50 and previous == "advanced": state["difficulty"]="intermediate"
    elif evaluation["score"] > 75 and previous == "beginner": state["difficulty"]="intermediate"
    candidate=candidate_or_404(state["candidate_id"])
    # A weak or partial answer earns a focused follow-up; otherwise move to
    # the next uncovered interview round so the interview stays varied.
    if evaluation["score"] < 65:
        next_question,category=interview_question(candidate["profile"],candidate["job"],state["difficulty"],request.answer)
    else:
        state["round_index"]=min(state["round_index"]+1,len(state["rounds"])-1); round_name=state["rounds"][state["round_index"]]
        next_question,category=interview_question(candidate["profile"],candidate["job"],state["difficulty"],round_name=round_name)
    state["answers"].append(request.answer); state["evaluations"].append(evaluation); state["questions"].append({"text":next_question,"category":category}); state["covered_topics"].append(category)
    return evaluation | {"next_question":next_question,"next_category":category,"next_difficulty":state["difficulty"]}

@router.get("/interview/report/{interview_session_id}")
def interview_report(interview_session_id:str):
    state=_interviews.get(interview_session_id)
    if not state: raise HTTPException(404,"Interview session was not found.")
    scores=[x["score"] for x in state["evaluations"]]; overall=round(sum(scores)/len(scores)) if scores else 0
    weak=[w for x in state["evaluations"] for w in x["weaknesses"]]; strong=[s for x in state["evaluations"] for s in x["strengths"]]
    labels={"technical_knowledge":overall,"project_knowledge":overall,"problem_solving":overall,"communication":overall,"clarity":overall,"role_alignment":overall,"behavioral":overall}
    return {"overall_score":overall,**labels,"strongest_area":"Project knowledge" if strong else "Complete interview answers","weakest_area":"Communication" if weak else "Continue practicing","repeated_weaknesses":sorted(set(weak)),"strengths":sorted(set(strong)),"improvement_areas":sorted(set(weak)),"recommended_topics":["Explain technical decisions and trade-offs"],"recommended_questions":["What trade-off did you make, and why?"]}
