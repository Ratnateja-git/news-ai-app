import re
from difflib import SequenceMatcher
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

PROJECT_SECTION_HEADING = re.compile(
    r"(?i)^\s*(?:(?:academic|personal|technical|professional|selected|key)\s+)?"
    r"projects?(?:\s*&\s*applications?)?\s*:?\s*$"
)
SECTION_HEADING = re.compile(
    r"(?i)^\s*(?:education|academic(?:\s+background)?|experience|work experience|employment|"
    r"internships?|skills|technical skills|certifications?|achievements?|awards?|courses?|"
    r"publications?|volunteer(?:\s+experience)?|leadership|interests?|languages?|references?)\s*:?\s*$"
)
PROJECT_DETAIL = re.compile(
    r"(?i)^(?:built|developed|designed|implemented|created|used|leveraged|deployed|trained|"
    r"tested|integrated|improved|worked|collaborated|led|responsible|technologies?|tools?|"
    r"features?|description|role|link|github|demo)\b"
)


def _clean_project_title(line):
    """Return a project heading, never one of its descriptive bullet points."""
    title = re.sub(r"^\s*(?:[-*•‣▪]|\d+[.)])\s*", "", line).strip()
    if not title or len(title) > 140 or PROJECT_DETAIL.match(title):
        return None
    # A sentence is almost always a project detail rather than its name.
    if title.endswith((".", ";")) or len(title.split()) > 14:
        return None
    # Keep the human-readable project name while dropping common date/stack suffixes.
    title = re.split(r"\s*(?:\||•)\s*", title, maxsplit=1)[0].strip()
    title = re.sub(r"\s+(?:\(|\[)?(?:19|20)\d{2}(?:\s*[-–]\s*(?:19|20)\d{2}|\s*[-–]\s*present)?(?:\)|\])?\s*$", "", title).strip()
    if not title or PROJECT_DETAIL.match(title):
        return None
    return title


def extract_projects(text):
    """Extract project titles from an explicit project section of a resume."""
    lines = text.splitlines()
    in_projects = False
    projects = []
    seen = set()
    for raw_line in lines:
        line = raw_line.strip()
        if PROJECT_SECTION_HEADING.match(line):
            in_projects = True
            continue
        if not in_projects:
            continue
        if SECTION_HEADING.match(line):
            break
        if not line:
            continue
        title = _clean_project_title(line)
        if not title:
            continue
        key = re.sub(r"[^a-z0-9]", "", title.lower())
        if key and key not in seen:
            seen.add(key)
            projects.append(title)
    return projects

def profile(text):
    lines=[x.strip() for x in text.splitlines() if x.strip()]; found=[s for s in SKILLS if re.search(rf"(?i)(?<!\w){re.escape(s)}(?!\w)",text)]
    return {"name":lines[0] if lines and len(lines[0])<80 else None,"email":(m.group() if (m:=re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",text)) else None),"phone":(m.group() if (m:=re.search(r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)",text)) else None),"skills":found,"programming_languages":[s for s in found if s in ("python","java","javascript","sql")],"frameworks":[s for s in found if s in ("fastapi","django","flask","tensorflow","pytorch","react")],"ai_ml_skills":[s for s in found if s in ("machine learning","deep learning","computer vision","tensorflow","pytorch","scikit-learn","opencv")],"education":section(text,"education"),"experience":section(text,"experience"),"internships":section(text,"internship"),"projects":extract_projects(text),"certifications":section(text,"certifications"),"achievements":section(text,"achievements"),"tools":[s for s in found if s in ("docker","kubernetes","aws","azure","git","ollama")],"soft_skills":[]}
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


class JDAnalyzerAgent:
    """Extract a compact, deterministic representation of a job description."""
    # Include common equivalents so detection is semantic enough for ordinary
    # JD wording without making a model call for an obvious conflict.
    EARLY_TERMS = ("entry-level", "entry level", "fresh graduate", "recent graduate", "new graduate", "fresher", "junior-level", "junior level", "graduate trainee", "no experience required", "0-1 years", "willing to learn")
    SENIOR_TERMS = ("senior", "architect", "lead", "principal", "staff", "experienced")

    def analyze(self, description):
        low = description.lower()
        found = [s for s in SKILLS if re.search(rf"(?i)(?<!\w){re.escape(s)}(?!\w)", description)]
        preferred = [s for s in found if re.search(rf"(?is)(?:preferred|nice to have|bonus).*?(?<!\w){re.escape(s)}(?!\w)", description)]
        required = [s for s in found if s not in preferred]
        title_match = re.search(r"(?im)^(?:job title|role|position)\s*[:\-]\s*(.+)$", description)
        title = title_match.group(1).strip() if title_match else next((line.strip(" -:") for line in description.splitlines() if any(term in line.lower() for term in self.SENIOR_TERMS) and len(line) < 100), "Target role")
        years = [int(value) for value in re.findall(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", low)]
        seniority = "entry-level" if any(term in low for term in self.EARLY_TERMS) else ("senior" if any(term in low or term in title.lower() for term in self.SENIOR_TERMS) else "not specified")
        education = re.findall(r"(?im)^.*(?:bachelor|master|degree|b\.tech|b\.s\.|m\.s\.).*$", description)
        responsibilities = [line.strip(" -•\t") for line in description.splitlines() if re.match(r"(?i)^\s*(?:[-•]|design|build|develop|lead|mentor|create|manage)\b", line.strip())][:8]
        return {"job_title": title, "seniority": seniority, "minimum_years_experience": min(years) if years else None, "maximum_typical_experience": max(years) if len(years) > 1 else None, "required_skills": required, "preferred_skills": preferred, "education": education, "responsibilities": responsibilities, "other_requirements": [term for term in self.EARLY_TERMS if term in low], "raw_description": description}


class ContradictionDetectorAgent:
    """Flag conflicting seniority requirements; it never resolves them silently."""
    def analyze(self, jd_analysis):
        raw = jd_analysis["raw_description"].lower()
        years = jd_analysis.get("minimum_years_experience") or 0
        early = [term for term in JDAnalyzerAgent.EARLY_TERMS if term in raw]
        senior = [term for term in JDAnalyzerAgent.SENIOR_TERMS if term in raw or term in jd_analysis["job_title"].lower()]
        conflicts = []
        if years >= 3 and early:
            conflicts.append({"requirement_a": f"{years}+ years experience", "requirement_b": early[0], "reason": "These requirements imply conflicting seniority levels."})
        elif senior and early:
            conflicts.append({"requirement_a": senior[0].title(), "requirement_b": early[0], "reason": "The role title implies senior responsibility while the candidate level is entry-level."})
        return {"contradiction_detected": bool(conflicts), "severity": "high" if conflicts else "none", "conflicts": conflicts, "recommended_interpretation": None, "should_warn_user": bool(conflicts)}


class ResumeMatcherAgent:
    def analyze(self, profile_data, jd_analysis, contradiction):
        baseline = job_match(profile_data, _job_for_existing_match(jd_analysis))
        baseline.update({"baseline_match_score": baseline["match_score"], "experience_match": "demonstrated experience or internships" if profile_data.get("experience") or profile_data.get("internships") else "projects and skills only", "seniority_match": "ambiguous because the job description conflicts" if contradiction["contradiction_detected"] else jd_analysis["seniority"], "contradiction_warning": contradiction if contradiction["contradiction_detected"] else None})
        return baseline


class RecommendationAgent:
    def analyze(self, profile_data, jd_analysis, resume_match, contradiction):
        strengths = resume_match.get("matched_skills", []) + profile_data.get("projects", [])[:2]
        recommendations = list(resume_match.get("recommendations", []))
        if contradiction["contradiction_detected"]:
            recommendations.insert(0, "Because this JD has conflicting seniority requirements, do not rewrite your resume to appear senior or claim years of experience you do not have.")
            recommendations.append("Emphasize legitimate projects, technical skills, problem solving, and willingness to learn.")
        return {"strengths_to_emphasize": strengths, "recommendations": recommendations, "safety_note": "Never invent years of experience, job titles, employment, certifications, responsibilities, or achievements."}


def _job_for_existing_match(jd_analysis):
    """Adapt the new structured analysis to the established scoring function."""
    return {"job_title": jd_analysis["job_title"], "required_skills": jd_analysis["required_skills"], "technical_domains": [], "important_capabilities": [], "keywords": jd_analysis["required_skills"], "contradiction": None}


def analyze_job_description(profile_data, description):
    """Orchestrate the four small agents without a second LLM server or API."""
    jd_analysis = JDAnalyzerAgent().analyze(description)
    contradiction = ContradictionDetectorAgent().analyze(jd_analysis)
    matching_job = _job_for_existing_match(jd_analysis)
    matching_job["contradiction"] = contradiction
    resume_match = ResumeMatcherAgent().analyze(profile_data, jd_analysis, contradiction)
    recommendations = RecommendationAgent().analyze(profile_data, jd_analysis, resume_match, contradiction)
    interview_focus = (["Ask about project architecture and how the candidate would approach the ambiguous role.", "Do not assume the candidate has the senior-level years named in the JD."] if contradiction["contradiction_detected"] else ["Ask evidence-based questions about demonstrated skills and projects."])
    return {"jd_analysis": jd_analysis, "contradiction": contradiction, "resume_match": resume_match, "recommendations": recommendations, "interview_focus": interview_focus, "job": matching_job}


def career_chat_context(session_id):
    candidate = get_candidate(session_id)
    if not candidate or not candidate.get("job"):
        return ""
    conflict = candidate["job"].get("contradiction") or {}
    if not conflict.get("contradiction_detected"):
        return "Career context: a resume and job description are active. Give advice using only demonstrated resume evidence."
    items = "; ".join(f"{item['requirement_a']} vs {item['requirement_b']}" for item in conflict.get("conflicts", []))
    return f"Career context: the active JD has a seniority conflict ({items}). Explain it openly. Do not choose a side or suggest inventing senior experience."

def job(description):
    found=[s for s in SKILLS if re.search(rf"(?i)(?<!\w){re.escape(s)}(?!\w)",description)]; low=description.lower(); title=re.search(r"(?im)^(?:job title|role|position)\s*[:\-]\s*(.+)$",description); role=title.group(1).strip() if title else ("Machine Learning Engineer" if "machine learning engineer" in low else "Target role")
    domains=[name for name,terms in {"Machine Learning":("machine learning",),"Artificial Intelligence":("artificial intelligence","ai development"),"Large Language Models":("large language models","llm"),"AI reasoning":("reasoning data","ai systems reason","structured reasoning")}.items() if any(t in low for t in terms)]
    capability_map={"problem solving":("solve problems","problem solving","difficult problems"),"analytical thinking":("analyze","analytical","analysis"),"logical reasoning":("logical reasoning","think clearly","logical,"),"technical communication":("communicate technical","explain technical","write precisely"),"technical writing":("technical writing","write precisely"),"explaining technical decisions":("explainable","explain"),"understanding trade-offs":("trade-off","tradeoff"),"independent work":("independent","self-directed"),"collaboration":("collaborat","teamwork"),"learning new technologies":("learn new","learning"),"debugging":("debug","troubleshoot"),"system design":("system design","architecture"),"critical thinking":("critical thinking","think clearly"),"structured thinking":("structured reasoning","logical, explainable steps")}
    capabilities=[name for name,terms in capability_map.items() if any(t in low for t in terms)]
    return {"job_title":role,"role_type":role,"work_mode":"remote" if "remote" in low else ("hybrid" if "hybrid" in low else None),"employment_type":"contract" if "contract" in low else ("full-time" if "full-time" in low else None),"required_skills":found,"skills":found,"preferred_skills":[],"technical_domains":domains,"important_capabilities":capabilities,"soft_skills":[x for x in capabilities if "writing" in x or "reasoning" in x],"programming_languages":[s for s in found if s in ("python","java","javascript","sql")],"frameworks":[],"tools":[],"experience_requirements":[],"education_requirements":[],"responsibilities":["Create structured reasoning data for AI systems"] if "structured reasoning data" in low else [],"keywords":found+domains+capabilities,"contradiction":ContradictionDetectorAgent().analyze(JDAnalyzerAgent().analyze(description))}
def job_match(p,j):
    have,need=set(p["skills"]),set(j["required_skills"]); matched,missing=sorted(have&need),sorted(need-have); skill=100*len(matched)/len(need) if need else 0; corpus=" ".join(p.get("skills",[])+p.get("projects",[])).lower(); domain=100*sum(any(word in corpus for word in d.lower().split()) for d in j.get("technical_domains",[]))/max(1,len(j.get("technical_domains",[]))); project=100 if p["projects"] else 20; exp=100 if p["experience"] or p["internships"] else 20; cap=100*sum(any(word in corpus for word in c.lower().split()) for c in j.get("important_capabilities",[]))/max(1,len(j.get("important_capabilities",[]))); key=100*len(have&set(j["keywords"]))/max(1,len(j["keywords"])); parts=([(skill,.4)] if need else [])+[(domain,.2),(project,.15),(exp,.15),(cap,.1),(key,.1)]; total=round(sum(v*w for v,w in parts)/sum(w for _,w in parts))
    return {"match_score":total,"matched_skills":matched,"missing_skills":missing,"domain_match":round(domain),"capability_match":round(cap),"partial_matches":j.get("technical_domains",[]),"relevant_projects":p["projects"][:3],"relevant_experience":(p["experience"]+p["internships"])[:3],"keyword_coverage":round(key),"education_match":bool(p["education"]),"strengths":matched,"skill_gaps":missing,"recommendations":[f"Learn or demonstrate {x} only if genuinely relevant." for x in missing],"disclaimer":"Priya Job Match Score is a heuristic estimate, not a company ATS score."}

def _project_name(project):
    """Keep a project question conversational instead of reciting its skill list."""
    return re.split(r"[|:—-]", project, maxsplit=1)[0].strip() or "your project"

def normalize_interview_question(question):
    """Normalize wording before comparing questions within one interview."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (question or "").lower())).strip()


def questions_are_similar(candidate, previous_questions):
    """Reject exact and substantially similar questions across the whole session."""
    normalized_candidate = normalize_interview_question(candidate)
    if not normalized_candidate:
        return True
    candidate_terms = set(normalized_candidate.split())
    for previous in previous_questions:
        normalized_previous = normalize_interview_question(previous)
        if normalized_candidate == normalized_previous:
            return True
        previous_terms = set(normalized_previous.split())
        overlap = len(candidate_terms & previous_terms) / max(1, len(candidate_terms | previous_terms))
        coverage = len(candidate_terms & previous_terms) / max(1, min(len(candidate_terms), len(previous_terms)))
        similarity = SequenceMatcher(None, normalized_candidate, normalized_previous).ratio()
        if overlap >= 0.78 or coverage >= 0.70 or similarity >= 0.86:
            return True
    return False


def _first_new_question(candidates, asked_questions):
    for question, category in candidates:
        if question and not questions_are_similar(question, asked_questions):
            return question, category
    raise ValueError("No new interview question is available for this session.")


def interview_question(p, j, difficulty, previous_answer="", round_name="project", asked_questions=()):
    """Return one focused, evidence-based interviewer question."""
    project = p["projects"][0] if p["projects"] else None
    project_name = _project_name(project) if project else "your project"
    role_skill = next((s for s in j["required_skills"] if s in p["skills"]), p["skills"][0] if p["skills"] else None)
    tools = p.get("tools", [])
    candidates = []
    conflict = j.get("contradiction") or {}
    if conflict.get("contradiction_detected") and not asked_questions:
        candidates.append(("This role combines senior responsibilities with entry-level expectations. How would you approach it while being clear about the experience you have today?", "jd_ambiguity"))
        candidates.append((f"Tell me about a project where you made an architectural decision in {project_name}.", "architecture"))
    if previous_answer:
        answer = previous_answer.lower()
        tech = next((s for s in p["skills"] if re.search(rf"(?<!\w){re.escape(s)}(?!\w)", answer)), None)
        if tech:
            candidates.append((f"You mentioned {tech}. What implementation choice did you make, and what trade-off did you consider?", "follow_up"))
            candidates.append((f"How did you test or validate the {tech} part of {project_name}?", "follow_up"))
        candidates.append((f"Using {project_name}, give one concrete example of your role, a challenge, and the result.", "follow_up"))
    elif round_name == "project" and project:
        candidates.append((f"Tell me about your {project_name} project. What problem does it solve, and how did you build it?", "project"))
        candidates.append((f"What was your individual contribution to {project_name}, and how did you measure whether it worked?", "project"))
    elif round_name == "technical" and role_skill:
        candidates.append((f"Why did you choose {role_skill} for your work, and what did it help you achieve?", "technical"))
        candidates.append((f"What limitation did you encounter with {role_skill}, and how did you work around it?", "technical"))
    elif round_name == "architecture" and project:
        candidates.append((f"How would you explain the architecture of your {project_name} project from user input to the final response?", "architecture"))
        candidates.append((f"Which component in {project_name} would you redesign first for reliability, and why?", "architecture"))
    elif round_name == "problem_solving":
        candidates.append(("If an AI feature became too slow for a real-time user experience, how would you investigate and improve the latency?", "problem_solving"))
        candidates.append((f"How would you profile {project_name} to separate model, API, database, and network latency?", "problem_solving"))
    elif round_name == "fundamentals" and any(x in j.get("technical_domains",[]) for x in ("Machine Learning","Artificial Intelligence")):
        candidates.append(("What is the difference between supervised and unsupervised learning, and when would you use each?", "fundamentals"))
        candidates.append((f"How would you choose an evaluation metric for an AI feature in {project_name}?", "fundamentals"))
    missing = sorted(set(j.get("required_skills", [])) - set(p.get("skills", [])))
    if round_name == "gap" and missing:
        candidates.append((f"You do not demonstrate {missing[0]} on your resume. How would you approach learning it if this role required it?", "skill_gap"))
    elif round_name == "behavioral":
        candidates.append(("Tell me about a difficult technical problem you faced and how you worked through it.", "behavioral"))
        candidates.append((f"Describe a time you had to explain a technical decision in {project_name} to someone else.", "behavioral"))
    elif round_name == "integration" and project:
        focus = tools[0] if tools else (role_skill or "your technical components")
        candidates.append((f"What integration challenge did you face connecting {focus} in {project_name}, and how did you solve it?", "integration"))
    elif round_name == "testing" and project:
        candidates.append((f"How did you test {project_name}, and what failure case was most important to cover?", "testing"))
    elif round_name == "impact" and project:
        candidates.append((f"What outcome or user impact did {project_name} achieve, and how would you improve it next?", "impact"))
    elif round_name == "learning" and role_skill:
        candidates.append((f"What did you learn while using {role_skill} in {project_name}, and how would you apply it differently next time?", "learning"))
    if not candidates and project:
        candidates.append((f"Walk me through {project_name}: your role, implementation choices, and what you learned.", "project"))
    if not candidates:
        candidates.append(("Tell me about yourself and how your verified skills relate to this target role.", "HR"))
    return _first_new_question(candidates, asked_questions)

def evaluate_answer(answer):
    words=len(answer.split()); lower=answer.lower(); evidence=bool(re.search(r"\b(i|we|built|implemented|tested|measured|because|result)\b", lower)); depth=bool(re.search(r"\b(trade-?off|architecture|design|challenge|performance|scal)\w*\b", lower)); score=clamp(30+min(words,160)*.25+(25 if evidence else 0)+(20 if depth else 0))
    weaknesses=[] if evidence else ["Use a concrete example and explain your contribution."]
    if not depth: weaknesses.append("Explain one technical decision, rationale, or trade-off.")
    feedback = "Your answer was relevant" + (" and included a concrete example." if evidence else ", but it would be stronger with a concrete example from your work.") + (" You also explained technical reasoning well." if depth else " Add why you chose the approach and one trade-off.")
    return {"score":score,"strengths":(["Provided evidence or an example"] if evidence else [])+(["Discussed technical reasoning"] if depth else []),"weaknesses":weaknesses,"feedback":feedback+" This evaluates answer content and communication indicators, not confidence or personality."}
