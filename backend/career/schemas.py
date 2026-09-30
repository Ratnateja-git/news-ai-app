"""Public models for the in-memory Career Coach interview state."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Difficulty = Literal["beginner", "intermediate", "advanced"]
InterviewType = Literal["technical", "behavioral", "HR", "mixed"]
class CandidateSession(BaseModel): session_id: str
class InterviewQuestion(BaseModel): text: str; category: str; difficulty: Difficulty
class InterviewAnswer(BaseModel): answer: str = Field(min_length=1, max_length=6000)
class InterviewEvaluation(BaseModel): score: int; strengths: list[str]; weaknesses: list[str]; feedback: str
class InterviewSession(BaseModel):
    interview_session_id: str; candidate_session_id: str; job_description: dict; interview_type: InterviewType; difficulty: Difficulty; question_number: int = 1; questions: list[InterviewQuestion] = []; asked_questions: list[str] = Field(default_factory=list); answers: list[str] = []; evaluations: list[InterviewEvaluation] = []; strengths: list[str] = []; weaknesses: list[str] = []; covered_topics: list[str] = []; current_question: str = ""; created_at: datetime = Field(default_factory=datetime.utcnow)
class InterviewStartRequest(BaseModel): candidate_session_id: str; job_description: str | None = Field(default=None, max_length=30000); interview_type: InterviewType = "mixed"; difficulty: Difficulty = "intermediate"
class InterviewAnswerRequest(InterviewAnswer): interview_session_id: str


class JDAnalyzeRequest(BaseModel):
    """Request for the lightweight career multi-agent pipeline."""
    session_id: str
    job_description: str = Field(min_length=1, max_length=30000)


class JDRequirementConflict(BaseModel):
    requirement_a: str
    requirement_b: str
    reason: str


class ContradictionResult(BaseModel):
    contradiction_detected: bool = False
    severity: Literal["none", "low", "medium", "high"] = "none"
    conflicts: list[JDRequirementConflict] = Field(default_factory=list)
    recommended_interpretation: str | None = None
    should_warn_user: bool = False
