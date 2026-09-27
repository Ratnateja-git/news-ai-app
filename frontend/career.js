// Career Coach uses the existing browser voice UI for spoken answers; this
// small controller keeps resume data in the current browser session only.
(() => {
  let sessionId = sessionStorage.getItem("priya_candidate_session_id"), interviewId = null;
  const byId = id => document.querySelector(`#${id}`);
  const show = (id, value) => { const el=byId(id); if (el) el.textContent=value; };
  async function api(path, options={}) {
    const r=await fetch(window.priyaApiUrl ? window.priyaApiUrl(path) : path,options);
    let d=null;
    try { d=await r.json(); } catch (_) { /* A proxy/server error may be HTML or plain text. */ }
    if(!r.ok) throw new Error(d?.detail||"Career Coach is temporarily unavailable. Please try again.");
    if(!d) throw new Error("Career Coach returned an unexpected response. Please try again.");
    return d;
  }
  const requireSession = () => { if (!sessionId) throw new Error("Please upload your resume first."); };
  if (sessionId) show("career-status", "Resume session restored. You can analyze a job description.");
  byId("career-upload")?.addEventListener("change", async e => { try { const f=e.target.files[0]; if(!f) return; const form=new FormData(); form.append("resume",f); const d=await api("/career/resume/upload",{method:"POST",body:form}); sessionId=d.candidate_session_id || d.session_id; sessionStorage.setItem("priya_candidate_session_id", sessionId); show("career-status","Resume ready. Click Analyze Resume."); } catch(e) { show("career-status",e.message); }});
  byId("career-analyze")?.addEventListener("click", async () => { try { requireSession(); const d=await api("/career/resume/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId})}); show("resume-score",`Priya Resume Score: ${d.overall_score}/100`); } catch(e) { show("career-status",e.message); }});
  byId("career-match")?.addEventListener("click", async () => { try { requireSession(); const description=byId("job-description").value.trim(); if (!description) throw new Error("Job description cannot be empty."); const parsed=await api("/career/job/parse",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId,description})}); const d=await api("/career/job/match",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId})}); const recommendations=d.recommendations.length ? d.recommendations.join("\n• ") : "Your demonstrated skills are aligned with this role."; show("job-match",`Role: ${parsed.job_title}\nWork Mode: ${parsed.work_mode||"Not specified"}\nEmployment: ${parsed.employment_type||"Not specified"}\nDomains: ${parsed.technical_domains.join(", ")||"No technical domains detected"}\nCapabilities: ${parsed.important_capabilities.join(", ")||"No specific capabilities detected"}\n\nPriya Job Match Score: ${d.match_score}%\nMatched: ${d.matched_skills.join(", ")||"None demonstrated"}\nGaps: ${d.missing_skills.join(", ")||"None identified"}\n\nRecommendations:\n• ${recommendations}`); } catch(e) { show("career-status",e.message); }});
  byId("interview-start")?.addEventListener("click", async () => { try { if(!sessionId) throw new Error("Upload a PDF resume first."); const d=await api("/career/interview/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({candidate_session_id:sessionId,interview_type:"mixed",difficulty:"intermediate"})}); interviewId=d.interview_session_id; show("interview-question",d.question); } catch(e) { show("career-status",e.message); }});
  byId("interview-answer")?.addEventListener("click", async () => { try { if(!interviewId) throw new Error("Start an interview first."); const answer=byId("interview-text").value.trim(); const d=await api("/career/interview/answer",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({interview_session_id:interviewId,answer})}); show("interview-feedback",`Score: ${d.score}/100 — ${d.feedback}`); show("interview-question",d.next_question); } catch(e) { show("career-status",e.message); }});
})();
