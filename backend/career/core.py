import re
from io import BytesIO
from threading import RLock
from uuid import uuid4
from pypdf import PdfReader
from . import storage
import logging

SKILLS=("python","java","javascript","sql","fastapi","django","flask","tensorflow","pytorch","scikit-learn","machine learning","deep learning","computer vision","opencv","docker","kubernetes","aws","azure","git","ollama","gemma","react","node.js")
_lock,_candidates,_interviews=RLock(),{},{}
log=logging.getLogger(__name__)
def clamp(x): return max(0,min(100,round(x)))
def text_from_pdf(data):
    try: text="\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages).strip()
    except Exception as e: raise ValueError("The uploaded file is not a readable PDF.") from e
    if len(text)<20: raise ValueError("The PDF contains no extractable resume text.")
    return text[:100000]
def section(text,name):
    m=re.search(rf"(?ims)^\s*{name}\s*[:\n](.*?)(?=^\s*(?:education|experience|internship|projects|certifications|achievements|skills)\s*[:\n]|\Z)",text)
    return [x.strip(" -•\t") for x in m.group(1).splitlines() if x.strip()] if m else []
def profile(text):
    lines=[x.strip() for x in text.splitlines() if x.strip()]; found=[s for s in SKILLS if re.search(rf"(?i)(?<!\w){re.escape(s)}(?!\w)",text)]
    return {"name":lines[0] if lines and len(lines[0])<80 else None,"email":(m.group() if (m:=re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",text)) else None),"phone":(m.group() if (m:=re.search(r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)",text)) else None),"skills":found,"programming_languages":[s for s in found if s in ("python","java","javascript","sql")],"frameworks":[s for s in found if s in ("fastapi","django","flask","tensorflow","pytorch","react")],"ai_ml_skills":[s for s in found if s in ("machine learning","deep learning","computer vision","tensorflow","pytorch","scikit-learn","opencv")],"education":section(text,"education"),"experience":section(text,"experience"),"internships":section(text,"internship"),"projects":section(text,"projects"),"certifications":section(text,"certifications"),"achievements":section(text,"achievements"),"tools":[s for s in found if s in ("docker","kubernetes","aws","azure","git","ollama")],"soft_skills":[]}
def add_candidate(p,text):
    sid=str(uuid4()); analysis=score(p,text); _candidates[sid]={"profile":p,"resume_analysis":analysis,"job":None}; storage.save(sid,p,analysis); log.info("[CAREER] Candidate session created: %s",sid); return sid
def get_candidate(sid):
    item=_candidates.get(sid) or storage.load(sid)
    if item: _candidates[sid]=item; log.info("[CAREER] Candidate session loaded: %s",sid)
    return item
def save_candidate(sid,item): storage.save(sid,item["profile"],item["resume_analysis"],item.get("job"))
def score(p,text):
    c={"ats_compatibility":100 if p["skills"] and p["education"] else 55,"technical_skills":clamp(len(p["skills"])*12),"projects":clamp(len(p["projects"])*35),"experience":clamp((len(p["experience"])+len(p["internships"]))*45),"achievements":clamp(len(p["achievements"])*40),"impact":clamp(len(re.findall(r"\b\d+(?:%|\+|x)?\b",text))*20),"formatting":90 if len(text.splitlines())>=5 else 50}; weights={"ats_compatibility":15,"technical_skills":20,"projects":20,"experience":15,"achievements":10,"impact":10,"formatting":10}; weak=[k.replace("_"," ") for k,v in c.items() if v<60]
    return {"overall_score":round(sum(c[k]*v for k,v in weights.items())/100),"categories":c,"strengths":[k.replace("_"," ") for k,v in c.items() if v>=70],"weaknesses":weak,"recommendations":[f"Strengthen {x} using only information already in your resume." for x in weak]+(["Add a measurable result if available; do not invent one."] if c["impact"]<60 else []),"disclaimer":"Priya Resume Score is a transparent heuristic estimate, not an employer ATS result."}
def job(description):
    found=[s for s in SKILLS if re.search(rf"(?i)(?<!\w){re.escape(s)}(?!\w)",description)]; low=description.lower(); title=re.search(r"(?im)^(?:job title|role|position)\s*[:\-]\s*(.+)$",description); role=title.group(1).strip() if title else ("Machine Learning Engineer" if "machine learning engineer" in low else "Target role")
    domains=[name for name,terms in {"Machine Learning":("machine learning",),"Artificial Intelligence":("artificial intelligence","ai development"),"Large Language Models":("large language models","llm"),"AI reasoning":("reasoning data","ai systems reason","structured reasoning")}.items() if any(t in low for t in terms)]
    capability_map={"problem solving":("solve problems","problem solving","difficult problems"),"analytical thinking":("analyze","analytical","analysis"),"logical reasoning":("logical reasoning","think clearly","logical,"),"technical communication":("communicate technical","explain technical","write precisely"),"technical writing":("technical writing","write precisely"),"explaining technical decisions":("explainable","explain"),"understanding trade-offs":("trade-off","tradeoff"),"independent work":("independent","self-directed"),"collaboration":("collaborat","teamwork"),"learning new technologies":("learn new","learning"),"debugging":("debug","troubleshoot"),"system design":("system design","architecture"),"critical thinking":("critical thinking","think clearly"),"structured thinking":("structured reasoning","logical, explainable steps")}
    capabilities=[name for name,terms in capability_map.items() if any(t in low for t in terms)]
    return {"job_title":role,"role_type":role,"work_mode":"remote" if "remote" in low else ("hybrid" if "hybrid" in low else None),"employment_type":"contract" if "contract" in low else ("full-time" if "full-time" in low else None),"required_skills":found,"skills":found,"preferred_skills":[],"technical_domains":domains,"important_capabilities":capabilities,"soft_skills":[x for x in capabilities if "writing" in x or "reasoning" in x],"programming_languages":[s for s in found if s in ("python","java","javascript","sql")],"frameworks":[],"tools":[],"experience_requirements":[],"education_requirements":[],"responsibilities":["Create structured reasoning data for AI systems"] if "structured reasoning data" in low else [],"keywords":found+domains+capabilities}
def job_match(p,j):
    have,need=set(p["skills"]),set(j["required_skills"]); matched,missing=sorted(have&need),sorted(need-have); skill=100*len(matched)/len(need) if need else 0; corpus=" ".join(p.get("skills",[])+p.get("projects",[])).lower(); domain=100*sum(any(word in corpus for word in d.lower().split()) for d in j.get("technical_domains",[]))/max(1,len(j.get("technical_domains",[]))); project=100 if p["projects"] else 20; exp=100 if p["experience"] or p["internships"] else 20; cap=100*sum(any(word in corpus for word in c.lower().split()) for c in j.get("important_capabilities",[]))/max(1,len(j.get("important_capabilities",[]))); key=100*len(have&set(j["keywords"]))/max(1,len(j["keywords"])); parts=([(skill,.4)] if need else [])+[(domain,.2),(project,.15),(exp,.15),(cap,.1),(key,.1)]; total=round(sum(v*w for v,w in parts)/sum(w for _,w in parts))
    return {"match_score":total,"matched_skills":matched,"missing_skills":missing,"domain_match":round(domain),"capability_match":round(cap),"partial_matches":j.get("technical_domains",[]),"relevant_projects":p["projects"][:3],"relevant_experience":(p["experience"]+p["internships"])[:3],"keyword_coverage":round(key),"education_match":bool(p["education"]),"strengths":matched,"skill_gaps":missing,"recommendations":[f"Learn or demonstrate {x} only if genuinely relevant." for x in missing],"disclaimer":"Priya Job Match Score is a heuristic estimate, not a company ATS score."}

def _project_name(project):
    """Keep a project question conversational instead of reciting its skill list."""
    return re.split(r"[|:—-]", project, maxsplit=1)[0].strip() or "your project"

def interview_question(p, j, difficulty, previous_answer="", round_name="project"):
    """Return one focused, evidence-based interviewer question."""
    if previous_answer:
        answer = previous_answer.lower()
        tech = next((s for s in p["skills"] if re.search(rf"(?<!\w){re.escape(s)}(?!\w)", answer)), None)
        if tech: return f"You mentioned {tech}. What implementation choice did you make, and what trade-off did you consider?", "follow_up"
        return "Could you give one concrete example, explain your role, and describe the result?", "follow_up"
    project = p["projects"][0] if p["projects"] else None
    role_skill = next((s for s in j["required_skills"] if s in p["skills"]), p["skills"][0] if p["skills"] else None)
    if round_name == "project" and project: return f"Tell me about your {_project_name(project)} project. What problem does it solve, and how did you build it?", "project"
    if round_name == "technical" and role_skill: return f"Why did you choose {role_skill} for your work, and what did it help you achieve?", "technical"
    if round_name == "architecture" and project: return f"How would you explain the architecture of your {_project_name(project)} project from user input to the final response?", "architecture"
    if round_name == "problem_solving": return "If an AI feature became too slow for a real-time user experience, how would you investigate and improve the latency?", "problem_solving"
    if round_name == "fundamentals" and any(x in j.get("technical_domains",[]) for x in ("Machine Learning","Artificial Intelligence")): return "What is the difference between supervised and unsupervised learning, and when would you use each?", "fundamentals"
    missing = sorted(set(j.get("required_skills", [])) - set(p.get("skills", [])))
    if round_name == "gap" and missing: return f"You do not demonstrate {missing[0]} on your resume. How would you approach learning it if this role required it?", "skill_gap"
    if round_name == "behavioral": return "Tell me about a difficult technical problem you faced and how you worked through it.", "behavioral"
    if project: return f"Walk me through your {_project_name(project)} project: your role, implementation choices, and what you learned.", "project"
    return "Tell me about yourself and how your verified skills relate to this target role.", "HR"

def evaluate_answer(answer):
    words=len(answer.split()); lower=answer.lower(); evidence=bool(re.search(r"\b(i|we|built|implemented|tested|measured|because|result)\b", lower)); depth=bool(re.search(r"\b(trade-?off|architecture|design|challenge|performance|scal)\w*\b", lower)); score=clamp(30+min(words,160)*.25+(25 if evidence else 0)+(20 if depth else 0))
    weaknesses=[] if evidence else ["Use a concrete example and explain your contribution."]
    if not depth: weaknesses.append("Explain one technical decision, rationale, or trade-off.")
    feedback = "Your answer was relevant" + (" and included a concrete example." if evidence else ", but it would be stronger with a concrete example from your work.") + (" You also explained technical reasoning well." if depth else " Add why you chose the approach and one trade-off.")
    return {"score":score,"strengths":(["Provided evidence or an example"] if evidence else [])+(["Discussed technical reasoning"] if depth else []),"weaknesses":weaknesses,"feedback":feedback+" This evaluates answer content and communication indicators, not confidence or personality."}
