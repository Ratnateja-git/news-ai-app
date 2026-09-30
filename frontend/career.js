// Career Coach uses the existing browser voice UI for spoken answers; this
// small controller keeps resume data in the current browser session only.
(() => {
  let sessionId = null, validatedSessionId = null, interviewId = null, currentQuestion = "", careerState = "empty", resumeRevision = 0;
  const byId = id => document.querySelector(`#${id}`);
  const show = (id, value) => { const el=byId(id); if (el) el.textContent=value; };
  const formatList = values => Array.isArray(values) && values.length ? values.join(", ") : "Not detected";
  const renderAnalysis = (analysis, analysisSessionId) => {
    if (analysisSessionId !== validatedSessionId || !analysis || !Number.isFinite(Number(analysis.overall_score))) return;
    show("resume-score", `Priya Resume Score: ${analysis.overall_score}/100`);
  };
  const renderResume = (filename, resume) => {
    if (!resume) return;
    show("resume-details", `Uploaded: ${filename || "resume.pdf"}\nParsed resume information\nName: ${resume.name || "Not detected"}\nEmail: ${resume.email || "Not detected"}\nSkills: ${formatList(resume.skills)}\nProjects: ${resume.projects?.length || 0}\nExperience entries: ${(resume.experience?.length || 0) + (resume.internships?.length || 0)}`);
  };
  const setPracticeVisible = visible => byId("interview-practice")?.classList.toggle("hidden", !visible);
  const clearResumeUi = () => {
    show("resume-score", "");
    show("resume-details", "");
    show("job-match", "");
    byId("jd-conflict")?.classList.add("hidden");
    show("jd-conflict-details", "");
    show("jd-conflict-recommendation", "");
    show("interview-feedback", "");
    byId("interview-questions")?.replaceChildren();
    show("interview-question", "");
    setPracticeVisible(false);
    interviewId = null;
    currentQuestion = "";
    window.priyaActiveInterviewQuestion = "";
  };
  const hasValidResume = () => Boolean(sessionId) && ["ready", "analyzed"].includes(careerState);
  const setCareerState = (nextState, status) => {
    careerState = nextState;
    if (status) show("career-status", status);
    const valid = hasValidResume();
    const busy = ["validating", "uploading", "analyzing"].includes(careerState);
    const analyze = byId("career-analyze");
    const match = byId("career-match");
    const start = byId("interview-start");
    if (analyze) analyze.disabled = !valid || busy;
    if (match) match.disabled = !valid || busy;
    if (start) start.disabled = !valid || busy;
  };
  const clearInvalidResumeState = (status = "Upload a PDF resume to begin.") => {
    resumeRevision += 1;
    sessionId = null;
    validatedSessionId = null;
    sessionStorage.removeItem("priya_candidate_session_id");
    clearResumeUi();
    setCareerState("empty", status);
  };
  const addQuestion = question => {
    currentQuestion = question || "";
    window.priyaActiveInterviewQuestion = currentQuestion;
    show("interview-question", currentQuestion);
    if (!currentQuestion) return;
    const item = document.createElement("li");
    item.textContent = currentQuestion;
    byId("interview-questions")?.append(item);
  };
  const speakCurrentQuestion = async () => {
    if (!currentQuestion) throw new Error("Start a mock interview first.");
    if (typeof window.priyaSpeak !== "function") throw new Error("Kokoro voice is not ready yet. Please try again.");
    await window.priyaSpeak(currentQuestion);
  };
  async function api(path, options={}) {
    const r=await fetch(window.priyaApiUrl ? window.priyaApiUrl(path) : path,options);
    let d=null;
    try { d=await r.json(); } catch (_) { /* A proxy/server error may be HTML or plain text. */ }
    if(!r.ok) throw new Error(d?.detail||"Career Coach is temporarily unavailable. Please try again.");
    if(!d) throw new Error("Career Coach returned an unexpected response. Please try again.");
    return d;
  }
  const requireSession = () => { if (!hasValidResume()) throw new Error("Please upload a valid resume first."); };
  byId("career-upload")?.addEventListener("change", async e => { const f=e.target.files[0]; if(!f) return; clearInvalidResumeState(`Uploading \"${f.name}\" and extracting resume details…`); const revision=resumeRevision; setCareerState("uploading"); try { const form=new FormData(); form.append("resume",f); const d=await api("/career/resume/upload",{method:"POST",body:form}); if (revision !== resumeRevision) return; const nextSessionId=d.candidate_session_id || d.session_id; if (!nextSessionId || !d.resume) throw new Error("Career Coach returned an incomplete resume upload response."); sessionId=nextSessionId; renderResume(d.filename || f.name, d.resume); setCareerState("analyzing", `Resume \"${d.filename || f.name}\" uploaded and parsed successfully. Validating its analysis…`); const analysis=await api("/career/resume/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:nextSessionId})}); if (revision !== resumeRevision || sessionId !== nextSessionId) return; validatedSessionId=nextSessionId; renderAnalysis(analysis, nextSessionId); setCareerState("analyzed", `Resume \"${d.filename || f.name}\" uploaded, parsed, and analyzed successfully.`); } catch(e) { if (revision !== resumeRevision) return; console.error("[Career] Resume upload failed", e); clearInvalidResumeState(e.message || "Resume upload failed. Please try again."); setCareerState("failed", e.message || "Resume upload failed. Please try again."); }});
  byId("career-analyze")?.addEventListener("click", async () => { const analysisSessionId=sessionId, revision=resumeRevision; try { requireSession(); show("resume-score", ""); setCareerState("analyzing", "Analyzing your uploaded resume…"); const d=await api("/career/resume/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:analysisSessionId})}); if (revision !== resumeRevision || analysisSessionId !== validatedSessionId) return; renderAnalysis(d, analysisSessionId); setCareerState("analyzed", "Resume analysis is ready."); } catch(e) { if (revision !== resumeRevision) return; console.error("[Career] Resume analysis failed", e); clearInvalidResumeState(e.message || "Resume analysis failed. Please upload your resume again."); setCareerState("failed", e.message || "Resume analysis failed. Please upload your resume again."); }});
  byId("career-match")?.addEventListener("click", async () => { try { requireSession(); const description=byId("job-description").value.trim(); if (!description) throw new Error("Job description cannot be empty."); const result=await api("/career/jd/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId,job_description:description})}); const parsed=result.jd_analysis, d=result.resume_match, recommendations=result.recommendations.recommendations || []; const conflict=result.contradiction; byId("jd-conflict")?.classList.toggle("hidden", !conflict.contradiction_detected); if(conflict.contradiction_detected) { show("jd-conflict-details", `This job description contains contradictory seniority requirements:\n${conflict.conflicts.map(x=>`• ${x.requirement_a}\n• ${x.requirement_b}`).join("\n")}`); show("jd-conflict-recommendation", result.recommendations.recommendations[0] || "Priya will not assume either interpretation."); } window.priyaCareerSessionId=sessionId; show("job-match",`Role: ${parsed.job_title}\nSeniority: ${parsed.seniority}\n\nBaseline Match: ${d.baseline_match_score}/100\nMatched: ${d.matched_skills.join(", ")||"None demonstrated"}\nGaps: ${d.missing_skills.join(", ")||"None identified"}${conflict.contradiction_detected ? "\n\n⚠️ This is a baseline score, not a definitive hiring probability." : ""}\n\nRecommendations:\n• ${recommendations.join("\n• ") || "Your demonstrated skills are aligned with this role."}`); } catch(e) { show("career-status",e.message); }});
  byId("interview-start")?.addEventListener("click", async () => { try { requireSession(); const d=await api("/career/interview/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({candidate_session_id:sessionId,interview_type:"mixed",difficulty:"intermediate"})}); interviewId=d.interview_session_id; byId("interview-questions").replaceChildren(); addQuestion(d.question); setPracticeVisible(true); show("interview-feedback",""); await speakCurrentQuestion(); } catch(e) { show("career-status",e.message); }});
  byId("interview-ask")?.addEventListener("click", async () => { try { await speakCurrentQuestion(); } catch(e) { show("career-status",e.message); }});
  byId("interview-replay")?.addEventListener("click", async () => { try { await speakCurrentQuestion(); } catch(e) { show("career-status",e.message); }});
  byId("interview-stop")?.addEventListener("click", () => window.priyaStopAudio?.());
  byId("interview-next")?.addEventListener("click", async () => { try { if(!interviewId) throw new Error("Start a mock interview first."); const d=await api("/career/interview/next",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({interview_session_id:interviewId})}); addQuestion(d.question); await speakCurrentQuestion(); } catch(e) { show("career-status",e.message); }});
  byId("interview-answer")?.addEventListener("click", async () => { try { if(!interviewId) throw new Error("Start an interview first."); const answer=byId("interview-text").value.trim(); const d=await api("/career/interview/answer",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({interview_session_id:interviewId,answer})}); show("interview-feedback",`Score: ${d.score}/100 — ${d.feedback}`); byId("interview-text").value=""; addQuestion(d.next_question); } catch(e) { show("career-status",e.message); }});
  // Resume records are server-persistent, but this unauthenticated UI cannot
  // prove a browser-stored ID belongs to the current upload. Start empty.
  clearInvalidResumeState();
  window.addEventListener("pageshow", event => {
    if (event.persisted) clearInvalidResumeState();
  });
})();
