"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";

type Run = { id: string; status: string; error?: string | null };
type Finding = { finding_id: string; severity: string; location: string; problem: string; why_it_matters: string; revision_instruction: string };
type ReviewData = {
  resume: string;
  review: { review_score: { total: number }; verdict: string; first_impression: string; strengths: string[]; findings: Finding[] };
  trace: { elements: Array<{ element_id: string; final_text: string; evidence_ids: string[] }> };
};
type CoverLetterPlan = { recommendation: "write" | "optional" | "skip"; strategic_role: { rationale: string; adds_beyond_resume: string }; core_message: { thesis: string }; structure: { paragraph_count: number; target_words_min: number; target_words_max: number } };
type CoverLetterReviewData = { letter: string; review: { score: number; verdict: string; first_impression: { summary: string }; findings: Array<{ finding_id: string; severity: string; paragraph_id: string; issue: string; impact: string; revision_instruction: string }> }; trace: { paragraphs: Array<{ paragraph_id: string; text: string; evidence_ids: string[] }> } };
type PackageData = { package: { company: string; role: string; package_version: number; page_counts: { resume: number; cover_letter: number }; identity_checks: Record<string, boolean>; packaged_artifacts: { resume_pdf: string; cover_letter_pdf: string | null } }; checklist: string };
type AnswerPlan = { source_url?: string | null; answers: Array<{ question_id: string; question: string; category: string; status: string; proposed_answer: string | null; evidence_ids: string[]; reason: string }>; answers_approved?: boolean; submission_authorized: boolean };
type BrowserFillReport = { filled: Array<{ question_id: string; label: string }>; uploaded?: Array<{ kind: string; filename: string; sha256: string }>; unmatched: Array<{ question_id: string; question: string }>; blockers: string[]; submit_clicked: boolean };
type ApplicationTrackerData = { company: string; role: string; submitted_at_utc: string; confirmation_evidence: string; confirmation_reference: string; application_status: string; follow_up_date: string | null; expected_response_date: string | null; interview_stage: string | null; next_action: string; notes: string; history: Array<{ at_utc: string; status: string; note: string }> };

const labels: Record<string, string> = {
  pursue: "Pursue",
  pass: "Passed",
  decide_later: "Decide later",
};

export function DecisionButtons({ leadId }: { leadId: string }) {
  const [status, setStatus] = useState("analysis_completed");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const load = () => fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`)
      .then((response) => response.ok ? response.json() : null)
      .then((run) => run?.status && setStatus(run.status))
      .catch(() => undefined);
    void load();
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [leadId]);

  async function decide(decision: "pursue" | "pass" | "decide_later") {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Decision could not be saved.");
      setStatus(payload.status);
      setMessage(decision === "pursue" ? "Saved. Application strategy is now the next permitted step." : "Decision saved.");
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Decision could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  const inWorkspace = (action: ReactNode) => <ApplicationWorkspace status={status}>{action}</ApplicationWorkspace>;

  if (["pursue", "strategy_requested", "strategy_running", "strategy_failed", "strategy_completed", "resume_plan_requested", "resume_plan_running", "resume_plan_failed", "resume_plan_completed", "resume_draft_requested", "resume_draft_running", "resume_draft_failed", "resume_draft_completed", "resume_review_requested", "resume_review_running", "resume_review_failed"].includes(status)) return inWorkspace(<PrepareResumeForReview leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["resume_revision_completed", "resume_review_completed"].includes(status)) return inWorkspace(<ResumeReviewAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["resume_approved", "resume_finalization_requested", "resume_finalization_running", "resume_finalization_failed", "resume_finalization_completed", "resume_pdf_requested", "resume_pdf_running", "resume_pdf_failed"].includes(status)) return inWorkspace(<PrepareUntilGate leadId={leadId} initialStatus={status} onStatus={setStatus} targetStatus="resume_pdf_review_required" title="Finalize approved resume" buttonLabel="Prepare resume PDF for review" readyMessage="The resume PDF is ready for your visual review." steps={resumePdfSteps} />);
  if (status === "resume_pdf_review_required") return inWorkspace(<ResumePdfAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["resume_pdf_completed", "cover_letter_plan_requested", "cover_letter_plan_running", "cover_letter_plan_failed"].includes(status)) return inWorkspace(<PrepareUntilGate leadId={leadId} initialStatus={status} onStatus={setStatus} targetStatus="cover_letter_plan_completed" title="Plan cover letter" buttonLabel="Prepare cover letter decision" readyMessage="The cover letter recommendation is ready for your decision." steps={coverLetterPlanSteps} />);
  if (["cover_letter_plan_completed", "cover_letter_draft_requested", "cover_letter_draft_running", "cover_letter_draft_failed"].includes(status)) return inWorkspace(<CoverLetterDraftAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["cover_letter_draft_completed", "cover_letter_revision_completed", "cover_letter_review_requested", "cover_letter_review_running", "cover_letter_review_failed"].includes(status)) return inWorkspace(<PrepareUntilGate leadId={leadId} initialStatus={status} onStatus={setStatus} targetStatus="cover_letter_review_completed" title="Review cover letter" buttonLabel="Prepare cover letter for review" readyMessage="The cover letter review is ready for your decision." steps={coverLetterReviewSteps} />);
  if (status === "cover_letter_review_completed") return inWorkspace(<CoverLetterReviewAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["cover_letter_approved", "cover_letter_finalization_requested", "cover_letter_finalization_running", "cover_letter_finalization_failed", "cover_letter_finalization_completed", "cover_letter_pdf_requested", "cover_letter_pdf_running", "cover_letter_pdf_failed"].includes(status)) return inWorkspace(<PrepareUntilGate leadId={leadId} initialStatus={status} onStatus={setStatus} targetStatus="cover_letter_pdf_review_required" title="Finalize approved cover letter" buttonLabel="Prepare cover letter PDF for review" readyMessage="The cover letter PDF is ready for your visual review." steps={coverLetterPdfSteps} />);
  if (status === "cover_letter_pdf_review_required") return inWorkspace(<CoverLetterPdfAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["cover_letter_pdf_completed", "cover_letter_skipped", "application_package_requested", "application_package_running", "application_package_failed"].includes(status)) return inWorkspace(<PrepareUntilGate leadId={leadId} initialStatus={status} onStatus={setStatus} targetStatus="application_package_completed" title="Assemble application package" buttonLabel="Build approved application package" readyMessage="The approved application package is ready." steps={applicationPackageSteps} />);
  if (status === "application_package_completed") return inWorkspace(<ApplicationPackageAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["form_questions_saved", "application_answers_requested", "application_answers_running", "application_answers_failed", "application_answers_completed"].includes(status)) return inWorkspace(<ApplicationAnswersAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["application_answers_approved", "form_filling_started", "submission_review_required", "submission_authorized", "submission_in_progress", "submission_blocked", "application_submitted"].includes(status)) return inWorkspace(<FormFillAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["cover_letter_revision_requested", "cover_letter_revision_running", "cover_letter_revision_failed"].includes(status)) return inWorkspace(<CoverLetterRevisionAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (["resume_revision_requested", "resume_revision_running", "resume_revision_failed"].includes(status)) return inWorkspace(<ResumeRevisionAction leadId={leadId} initialStatus={status} onStatus={setStatus} />);
  if (status === "pass") return <div className="decision-saved pass"><strong>{labels[status]}</strong><span>Removed from active consideration</span></div>;

  return <div className="decision-control">
    <span>What would you like to do?</span>
    <div>
      <button className="pursue" disabled={busy} onClick={() => decide("pursue")}>Pursue</button>
      <button disabled={busy} onClick={() => decide("decide_later")}>{status === "decide_later" ? "Saved for later" : "Decide later"}</button>
      <button disabled={busy} onClick={() => decide("pass")}>Pass</button>
    </div>
    {message && <small role="status">{message}</small>}
  </div>;
}

const workspaceStages = ["Analysis", "Strategy", "Resume", "Cover letter", "Package", "Apply"];
function workflowStage(status: string) {
  if (status === "application_submitted") return 6;
  if (status.startsWith("submission_") || status.startsWith("form_") || status.startsWith("application_answers")) return 5;
  if (status.startsWith("application_package") || status === "cover_letter_skipped") return 4;
  if (status.startsWith("cover_letter")) return 3;
  if (status.startsWith("resume_")) return 2;
  if (status.startsWith("strategy") || status === "pursue") return 1;
  return 0;
}
function ApplicationWorkspace({ status, children }: { status: string; children: ReactNode }) {
  const stage = workflowStage(status);
  const reviewRequired = status.includes("review_required") || status.endsWith("review_completed") || status === "submission_review_required";
  return <section className="application-workspace"><header><div><span>APPLICATION PROCESS</span><strong>{reviewRequired ? "Your review is required" : stage === 6 ? "Application recorded" : "Package in progress"}</strong></div><b>{stage === 6 ? "Complete" : workspaceStages[Math.min(stage, 5)]}</b></header><ol className="workflow-progress">{workspaceStages.map((label, index) => <li key={label} className={index < stage || stage === 6 ? "complete" : index === stage ? "current" : ""}><i>{index < stage || stage === 6 ? "✓" : index + 1}</i><span>{label}</span></li>)}</ol><div className="workspace-current"><small>CURRENT STEP · {status.replaceAll("_", " ")}</small>{children}</div><footer>Every document and application action remains behind its required review and approval.</footer></section>;
}

const preparationSteps: Record<string, { endpoint: string; label: string }> = {
  pursue: { endpoint: "strategy", label: "Building application strategy" }, strategy_failed: { endpoint: "strategy", label: "Retrying application strategy" },
  strategy_completed: { endpoint: "resume-plan", label: "Planning the tailored resume" }, resume_plan_failed: { endpoint: "resume-plan", label: "Retrying resume planning" },
  resume_plan_completed: { endpoint: "resume-draft", label: "Drafting the tailored resume" }, resume_draft_failed: { endpoint: "resume-draft", label: "Retrying resume drafting" },
  resume_draft_completed: { endpoint: "resume-review", label: "Reviewing evidence and quality" }, resume_review_failed: { endpoint: "resume-review", label: "Retrying resume review" },
};

const resumePdfSteps = {
  resume_approved: { endpoint: "resume-finalize", label: "Finalizing the approved resume" }, resume_finalization_failed: { endpoint: "resume-finalize", label: "Retrying resume finalization" },
  resume_finalization_completed: { endpoint: "resume-pdf", label: "Rendering the resume PDF" }, resume_pdf_failed: { endpoint: "resume-pdf", label: "Retrying resume PDF rendering" },
};
const coverLetterPlanSteps = {
  resume_pdf_completed: { endpoint: "cover-letter-plan", label: "Evaluating whether a cover letter adds value" }, cover_letter_plan_failed: { endpoint: "cover-letter-plan", label: "Retrying cover letter planning" },
};
const coverLetterReviewSteps = {
  cover_letter_draft_completed: { endpoint: "cover-letter-review", label: "Reviewing cover letter evidence and quality" }, cover_letter_revision_completed: { endpoint: "cover-letter-review", label: "Reviewing the revised cover letter" }, cover_letter_review_failed: { endpoint: "cover-letter-review", label: "Retrying cover letter review" },
};
const coverLetterPdfSteps = {
  cover_letter_approved: { endpoint: "cover-letter-finalize", label: "Finalizing the approved cover letter" }, cover_letter_finalization_failed: { endpoint: "cover-letter-finalize", label: "Retrying cover letter finalization" },
  cover_letter_finalization_completed: { endpoint: "cover-letter-pdf", label: "Rendering the cover letter PDF" }, cover_letter_pdf_failed: { endpoint: "cover-letter-pdf", label: "Retrying cover letter PDF rendering" },
};
const applicationPackageSteps = {
  cover_letter_pdf_completed: { endpoint: "application-package", label: "Assembling the approved application package" }, cover_letter_skipped: { endpoint: "application-package", label: "Assembling the resume-only application package" }, application_package_failed: { endpoint: "application-package", label: "Retrying application package assembly" },
};

function PrepareUntilGate({ leadId, initialStatus, onStatus, targetStatus, title, buttonLabel, readyMessage, steps }: { leadId: string; initialStatus: string; onStatus: (status: string) => void; targetStatus: string; title: string; buttonLabel: string; readyMessage: string; steps: Record<string, { endpoint: string; label: string }> }) {
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("Ready to continue safely to the next review point.");
  const running = initialStatus.endsWith("_requested") || initialStatus.endsWith("_running");
  useEffect(() => {
    if (initialStatus === targetStatus) setMessage(readyMessage);
    else if (initialStatus.endsWith("_failed")) setMessage("This step needs attention. Review the error and retry.");
    else if (!running && steps[initialStatus]) setMessage(`Ready: ${steps[initialStatus].label}.`);
  }, [initialStatus, readyMessage, running, steps, targetStatus]);
  async function prepare() {
    const step = steps[initialStatus];
    if (!step) return;
    setBusy(true);
    try {
      setMessage(`${step.label}…`);
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/${step.endpoint}`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `${step.label} could not start.`);
      onStatus(payload.status);
    } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Preparation stopped."); }
    finally { setBusy(false); }
  }
  return <div className="strategy-action"><div><strong>{title}</strong><span>{message}</span></div><button disabled={busy||running||!steps[initialStatus]} onClick={prepare}>{busy||running ? "Preparing…" : steps[initialStatus]?.label||buttonLabel}</button></div>;
}

function PrepareResumeForReview({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("Ready to build the strategy and tailored resume, then stop for your review.");
  const [practiceOnly, setPracticeOnly] = useState(false), [practiceConfirmed, setPracticeConfirmed] = useState(false);
  const running = initialStatus.endsWith("_requested") || initialStatus.endsWith("_running");
  useEffect(() => { if (!["resume_plan_completed", "resume_draft_failed"].includes(initialStatus)) return; fetch(`http://localhost:8787/api/jobs/${leadId}/application-context`).then((response) => response.ok ? response.json() : null).then((context) => setPracticeOnly(context?.mode === "practice_only")).catch(() => undefined); }, [leadId, initialStatus]);
  useEffect(() => {
    if (initialStatus === "resume_review_completed") setMessage("Resume review is ready for your decision.");
    else if (initialStatus.endsWith("_failed")) setMessage("This step needs attention. Review the error and retry.");
    else if (!running && preparationSteps[initialStatus]) setMessage(`Ready: ${preparationSteps[initialStatus].label}.`);
  }, [initialStatus, running]);
  async function prepare() {
    const step = preparationSteps[initialStatus];
    if (!step) return;
    setBusy(true);
    try {
      setMessage(`${step.label}…`);
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/${step.endpoint}`, { method: "POST", headers: step.endpoint === "resume-draft" ? { "Content-Type": "application/json" } : undefined, body: step.endpoint === "resume-draft" ? JSON.stringify({ practice_only_confirmed: practiceConfirmed }) : undefined });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `${step.label} could not start.`);
      onStatus(payload.status);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Preparation stopped."); }
    finally { setBusy(false); }
  }
  return <div className="strategy-action practice-aware"><div><strong>{practiceOnly ? "Practice-only resume" : "Prepare application"}</strong><span>{practiceOnly ? "Fit assessment: do not apply. Continue only to test or practise the package workflow." : message}</span>{practiceOnly && <label className="practice-confirmation"><input type="checkbox" checked={practiceConfirmed} onChange={(event) => setPracticeConfirmed(event.target.checked)} /> I understand this is not a recommended application and want to draft it for practice.</label>}</div><button disabled={busy||running||!preparationSteps[initialStatus]||practiceOnly&&!practiceConfirmed} onClick={prepare}>{busy||running ? "Preparing…" : practiceOnly ? "Continue as practice" : preparationSteps[initialStatus]?.label||"Prepare resume for review"}</button>{practiceOnly && message && <small role="status">{message}</small>}</div>;
}

function StrategyAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "strategy_failed" ? "The previous strategy run needs attention. You can retry." : "Pursue saved. Strategy is the next permitted step.");
  const working = run && ["strategy_requested", "strategy_running"].includes(run.status);

  useEffect(() => {
    if (!["strategy_requested", "strategy_running", "strategy_failed"].includes(initialStatus)) return;
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`)
      .then((response) => response.ok ? response.json() : null)
      .then((latest) => latest?.id && setRun(latest))
      .catch(() => undefined);
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "strategy_completed") { setMessage("Application strategy completed and validated."); onStatus(next.status); }
      if (next.status === "strategy_failed") setMessage(next.error || "Strategy needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function build() {
    setMessage("Starting application strategy…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/strategy`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Strategy could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Strategy could not start.");
    }
  }

  return <div className="strategy-action"><div><strong>Pursue</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={build}>{working ? "Building strategy…" : "Build strategy"}</button></div>;
}

function ApplicationStart({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "resume_plan_failed" ? "Resume planning needs attention. You can retry." : "Strategy validated. Resume planning is the next step.");
  const working = run && ["resume_plan_requested", "resume_plan_running"].includes(run.status);

  useEffect(() => {
    if (!["resume_plan_requested", "resume_plan_running", "resume_plan_failed"].includes(initialStatus)) return;
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`)
      .then((response) => response.ok ? response.json() : null)
      .then((latest) => latest?.id && setRun(latest))
      .catch(() => undefined);
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "resume_plan_completed") { setMessage("Resume plan completed and validated."); onStatus(next.status); }
      if (next.status === "resume_plan_failed") setMessage(next.error || "Resume planning needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function start() {
    setMessage("Creating application workspace and resume plan…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-plan`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Application could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Application could not start.");
    }
  }

  return <div className="strategy-action"><div><strong>Strategy ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={start}>{working ? "Planning resume…" : "Start application"}</button></div>;
}

function ResumeDraftAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "resume_draft_failed" ? "Resume drafting needs attention. You can retry." : "Resume plan validated. The draft is ready to create.");
  const working = run && ["resume_draft_requested", "resume_draft_running"].includes(run.status);

  useEffect(() => {
    if (!["resume_draft_requested", "resume_draft_running", "resume_draft_failed"].includes(initialStatus)) return;
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`)
      .then((response) => response.ok ? response.json() : null)
      .then((latest) => latest?.id && setRun(latest))
      .catch(() => undefined);
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "resume_draft_completed") { setMessage("Resume draft completed and validated."); onStatus(next.status); }
      if (next.status === "resume_draft_failed") setMessage(next.error || "Resume drafting needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function draft() {
    setMessage("Drafting an evidence-based resume…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-draft`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Resume drafting could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Resume drafting could not start.");
    }
  }

  return <div className="strategy-action"><div><strong>Resume plan ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={draft}>{working ? "Drafting resume…" : "Draft resume"}</button></div>;
}

function ResumeReviewAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [review, setReview] = useState<ReviewData | null>(null);
  const [message, setMessage] = useState(initialStatus === "resume_review_failed" ? "The review needs attention. You can retry." : initialStatus === "resume_revision_completed" ? "The revised resume passed evidence validation and must be reviewed again." : "The draft is ready for a recruiter-style review.");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const working = run && ["resume_review_requested", "resume_review_running"].includes(run.status);

  async function loadReview() {
    const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-review`);
    if (response.ok) setReview(await response.json());
  }

  useEffect(() => {
    if (["resume_review_requested", "resume_review_running", "resume_review_failed"].includes(initialStatus)) {
      fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`)
        .then((response) => response.ok ? response.json() : null)
        .then((latest) => latest?.id && setRun(latest))
        .catch(() => undefined);
    }
    if (initialStatus === "resume_review_completed") void loadReview();
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "resume_review_completed") {
        setMessage("Review completed. The final decision is yours.");
        onStatus(next.status);
        await loadReview();
      }
      if (next.status === "resume_review_failed") setMessage(next.error || "Resume review needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function startReview() {
    setMessage("Reviewing the resume against the job strategy and verified evidence…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-review`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Resume review could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Resume review could not start.");
    }
  }

  async function decide(action: "approve" | "request_revision") {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-decision`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, notes }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Your decision could not be saved.");
      onStatus(payload.status);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Your decision could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  if (!review) return <div className="strategy-action"><div><strong>Resume draft ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={startReview}>{working ? "Reviewing resume…" : "Review resume"}</button></div>;

  return <section className="resume-review">
    <header><div><span>RECRUITER-STYLE REVIEW</span><strong>{review.review.review_score.total}/100</strong></div><b>{review.review.verdict.replaceAll("_", " ")}</b></header>
    <p>{review.review.first_impression}</p>
    <details><summary>Read tailored resume</summary><pre>{review.resume}</pre></details>
    <details open={review.review.findings.some((item) => ["critical", "high"].includes(item.severity))}><summary>Review findings ({review.review.findings.length})</summary>
      <div className="review-findings">{review.review.findings.length ? review.review.findings.map((item) => <article key={item.finding_id}><span className={item.severity}>{item.severity}</span><strong>{item.location}</strong><p>{item.problem}</p><small>{item.revision_instruction}</small></article>) : <p>No revision findings.</p>}</div>
    </details>
    <details><summary>Evidence trace ({review.trace.elements.length} resume elements)</summary><div className="evidence-trace">{review.trace.elements.filter((item) => item.evidence_ids.length).map((item) => <article key={item.element_id}><p>{item.final_text}</p><small>Evidence: {item.evidence_ids.join(", ")}</small></article>)}</div></details>
    <label><span>Revision notes</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Tell the agent what should change before you approve this resume." /></label>
    <div className="review-actions"><button disabled={busy || !notes.trim()} onClick={() => decide("request_revision")}>Request revision</button><button className="approve" disabled={busy} onClick={() => decide("approve")}>Approve resume</button></div>
    {message && <small role="status">{message}</small>}
  </section>;
}

function ResumeRevisionAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "resume_revision_failed" ? "The revision needs attention. You can retry without losing the previous version." : "Your revision notes are saved. The previous resume will be backed up before changes.");
  const working = run && ["resume_revision_requested", "resume_revision_running"].includes(run.status);

  useEffect(() => {
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`)
      .then((response) => response.ok ? response.json() : null)
      .then((latest) => latest?.id && setRun(latest))
      .catch(() => undefined);
  }, [leadId]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "resume_revision_completed") { setMessage("Revision completed and validated."); onStatus(next.status); }
      if (next.status === "resume_revision_failed") setMessage(next.error || "Resume revision needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function revise() {
    setMessage("Creating a controlled revision with a versioned backup…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-revision`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Resume revision could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Resume revision could not start.");
    }
  }

  return <div className="strategy-action"><div><strong>Revision requested</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={revise}>{working ? "Revising resume…" : "Revise resume"}</button></div>;
}

function ResumeFinalizationAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "resume_finalization_failed" ? "Finalization needs attention. The approved draft was not changed." : "Approval recorded. Lock the exact reviewed content before creating a PDF.");
  const working = run && ["resume_finalization_requested", "resume_finalization_running"].includes(run.status);

  useEffect(() => {
    if (!["resume_finalization_requested", "resume_finalization_running", "resume_finalization_failed"].includes(initialStatus)) return;
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((response) => response.ok ? response.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined);
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "resume_finalization_completed") { setMessage("Approved resume locked and validated."); onStatus(next.status); }
      if (next.status === "resume_finalization_failed") setMessage(next.error || "Resume finalization needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function finalize() {
    setMessage("Locking the approved resume…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-finalize`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Finalization could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Finalization could not start.");
    }
  }

  return <div className="strategy-action"><div><strong>Resume approved</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={finalize}>{working ? "Finalizing…" : "Finalize resume"}</button></div>;
}

function ResumePdfAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "resume_pdf_failed" ? "PDF rendering needs attention." : "The approved content is locked. Render the ATS-friendly PDF next.");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const working = run && ["resume_pdf_requested", "resume_pdf_running"].includes(run.status);
  const reviewRequired = initialStatus === "resume_pdf_review_required" || run?.status === "resume_pdf_review_required";

  useEffect(() => {
    if (!["resume_pdf_requested", "resume_pdf_running", "resume_pdf_failed"].includes(initialStatus)) return;
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((response) => response.ok ? response.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined);
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "resume_pdf_review_required") setMessage("Text fidelity passed. Inspect every PDF page before approval.");
      if (next.status === "resume_pdf_failed") setMessage(next.error || "PDF rendering needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run]);

  async function renderPdf() {
    setMessage("Rendering and checking PDF text fidelity…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-pdf`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "PDF rendering could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "PDF rendering could not start.");
    }
  }

  async function decide(action: "approve" | "report_issue") {
    setBusy(true);
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/resume-pdf-decision`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, notes }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "PDF decision could not be saved.");
      onStatus(payload.status);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "PDF decision could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  if (!reviewRequired) return <div className="strategy-action"><div><strong>Final resume ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={renderPdf}>{working ? "Rendering PDF…" : "Create PDF"}</button></div>;

  return <section className="pdf-review"><header><div><strong>Inspect resume PDF</strong><span>Text fidelity already passed</span></div><a href={`http://localhost:8787/api/jobs/${leadId}/resume-pdf`} target="_blank" rel="noreferrer">Open full size</a></header>
    <iframe title="Final resume PDF preview" src={`http://localhost:8787/api/jobs/${leadId}/resume-pdf`} />
    <p>Check every page for clipped or overlapping text, broken characters, awkward page breaks, and unreadably small type.</p>
    <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Describe any layout problem you see." />
    <div><button disabled={busy || !notes.trim()} onClick={() => decide("report_issue")}>Report layout issue</button><button className="approve" disabled={busy} onClick={() => decide("approve")}>PDF looks correct</button></div>
    {message && <small role="status">{message}</small>}
  </section>;
}

function CoverLetterPlanAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [plan, setPlan] = useState<CoverLetterPlan | null>(null);
  const [message, setMessage] = useState(initialStatus === "cover_letter_plan_failed" ? "Cover letter planning needs attention. You can retry." : "Resume package approved. Decide whether a cover letter adds meaningful value.");
  const working = run && ["cover_letter_plan_requested", "cover_letter_plan_running"].includes(run.status);

  async function loadPlan() {
    const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-plan`);
    if (response.ok) setPlan(await response.json());
  }

  useEffect(() => {
    if (["cover_letter_plan_requested", "cover_letter_plan_running", "cover_letter_plan_failed"].includes(initialStatus)) {
      fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((response) => response.ok ? response.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined);
    }
    if (initialStatus === "cover_letter_plan_completed") void loadPlan();
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "cover_letter_plan_completed") { setMessage("Cover letter strategy completed and validated."); onStatus(next.status); await loadPlan(); }
      if (next.status === "cover_letter_plan_failed") setMessage(next.error || "Cover letter planning needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function buildPlan() {
    setMessage("Planning the cover letter from approved evidence…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-plan`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Cover letter planning could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Cover letter planning could not start.");
    }
  }

  if (!plan) return <div className="strategy-action"><div><strong>Resume PDF ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={buildPlan}>{working ? "Planning letter…" : "Plan cover letter"}</button></div>;

  return <section className="cover-letter-plan"><header><div><span>COVER LETTER DECISION</span><strong>{plan.recommendation}</strong></div><b>{plan.structure.paragraph_count} paragraphs · {plan.structure.target_words_min}-{plan.structure.target_words_max} words</b></header><p>{plan.strategic_role.rationale}</p><div><strong>Core message</strong><span>{plan.core_message.thesis}</span></div>{plan.recommendation === "skip" ? <small>The planner found that a letter would not add enough value. The resume package remains ready.</small> : <small>Plan validated. Drafting is the next step.</small>}</section>;
}

function CoverLetterDraftAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [plan, setPlan] = useState<CoverLetterPlan | null>(null);
  const [message, setMessage] = useState(initialStatus === "cover_letter_draft_failed" ? "Cover letter drafting needs attention. You can retry." : "Plan validated. Drafting will stay within its evidence and wording controls.");
  const working = run && ["cover_letter_draft_requested", "cover_letter_draft_running"].includes(run.status);

  useEffect(() => {
    fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-plan`).then((response) => response.ok ? response.json() : null).then((value) => value?.recommendation && setPlan(value)).catch(() => undefined);
    if (["cover_letter_draft_requested", "cover_letter_draft_running", "cover_letter_draft_failed"].includes(initialStatus)) {
      fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((response) => response.ok ? response.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined);
    }
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "cover_letter_draft_completed") { setMessage("Cover letter drafted and evidence trace validated."); onStatus(next.status); }
      if (next.status === "cover_letter_draft_failed") setMessage(next.error || "Cover letter drafting needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function draft() {
    setMessage(plan?.recommendation === "skip" ? "Recording the plan's skip recommendation…" : "Drafting the evidence-based cover letter…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-draft`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Cover letter drafting could not start.");
      if (payload.status === "cover_letter_skipped") onStatus(payload.status); else setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Cover letter drafting could not start.");
    }
  }

  if (!plan) return <div className="strategy-action"><div><strong>Cover letter plan ready</strong><span>{message}</span></div></div>;
  return <section className="cover-letter-plan"><header><div><span>COVER LETTER DECISION</span><strong>{plan.recommendation}</strong></div><b>{plan.structure.paragraph_count} paragraphs · {plan.structure.target_words_min}-{plan.structure.target_words_max} words</b></header><p>{plan.strategic_role.rationale}</p><div><strong>Core message</strong><span>{plan.core_message.thesis}</span></div><div className="plan-action"><small>{message}</small><button disabled={Boolean(working)} onClick={draft}>{working ? "Drafting letter…" : plan.recommendation === "skip" ? "Continue without letter" : "Draft cover letter"}</button></div></section>;
}

function CoverLetterReviewAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [data, setData] = useState<CoverLetterReviewData | null>(null);
  const [message, setMessage] = useState(initialStatus === "cover_letter_review_failed" ? "The review needs attention. You can retry." : initialStatus === "cover_letter_revision_completed" ? "The revised letter passed provenance validation and must be reviewed again." : "The traced draft is ready for a recruiter-style review.");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const working = run && ["cover_letter_review_requested", "cover_letter_review_running"].includes(run.status);

  async function loadReview() {
    const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-review`);
    if (response.ok) setData(await response.json());
  }

  useEffect(() => {
    if (["cover_letter_review_requested", "cover_letter_review_running", "cover_letter_review_failed"].includes(initialStatus)) {
      fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((response) => response.ok ? response.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined);
    }
    if (initialStatus === "cover_letter_review_completed") void loadReview();
  }, [leadId, initialStatus]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "cover_letter_review_completed") { setMessage("Review completed. The decision is yours."); onStatus(next.status); await loadReview(); }
      if (next.status === "cover_letter_review_failed") setMessage(next.error || "Cover letter review needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function startReview() {
    setMessage("Reviewing the letter against its plan and evidence…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-review`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Cover letter review could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Cover letter review could not start.");
    }
  }

  async function decide(action: "approve" | "request_revision") {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-decision`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, notes }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Your decision could not be saved.");
      onStatus(payload.status);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Your decision could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <div className="strategy-action"><div><strong>Cover letter draft ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={startReview}>{working ? "Reviewing letter…" : "Review cover letter"}</button></div>;

  return <section className="resume-review"><header><div><span>COVER LETTER REVIEW</span><strong>{data.review.score}/100</strong></div><b>{data.review.verdict.replaceAll("_", " ")}</b></header><p>{data.review.first_impression.summary}</p>
    <details><summary>Read cover letter</summary><pre>{data.letter}</pre></details>
    <details open={data.review.findings.some((item) => ["critical", "high"].includes(item.severity))}><summary>Review findings ({data.review.findings.length})</summary><div className="review-findings">{data.review.findings.length ? data.review.findings.map((item) => <article key={item.finding_id}><span className={item.severity}>{item.severity}</span><strong>{item.paragraph_id}</strong><p>{item.issue}</p><small>{item.revision_instruction}</small></article>) : <p>No revision findings.</p>}</div></details>
    <details><summary>Evidence trace ({data.trace.paragraphs.length} paragraphs)</summary><div className="evidence-trace">{data.trace.paragraphs.map((item) => <article key={item.paragraph_id}><p>{item.text}</p><small>Evidence: {item.evidence_ids.join(", ")}</small></article>)}</div></details>
    <label><span>Revision notes</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Tell the agent what should change before approval." /></label>
    <div className="review-actions"><button disabled={busy || !notes.trim() || data.review.verdict === "ready"} onClick={() => decide("request_revision")}>Request revision</button><button className="approve" disabled={busy || data.review.verdict !== "ready"} onClick={() => decide("approve")}>Approve cover letter</button></div>
    {data.review.verdict !== "ready" && <small>Resolve the review findings before approval.</small>}{message && <small role="status">{message}</small>}
  </section>;
}

function CoverLetterRevisionAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "cover_letter_revision_failed" ? "The revision needs attention. You can retry without losing the reviewed version." : "Your notes and the authorized review findings are ready for a controlled revision.");
  const working = run && ["cover_letter_revision_requested", "cover_letter_revision_running"].includes(run.status);

  useEffect(() => {
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((response) => response.ok ? response.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined);
  }, [leadId]);

  useEffect(() => {
    if (!working || !run) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "cover_letter_revision_completed") { setMessage("Revision completed and validated."); onStatus(next.status); }
      if (next.status === "cover_letter_revision_failed") setMessage(next.error || "Cover letter revision needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [working, run, onStatus]);

  async function revise() {
    setMessage("Creating a bounded revision with versioned backups…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-revision`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Cover letter revision could not start.");
      setRun(payload);
    } catch (error) {
      setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Cover letter revision could not start.");
    }
  }

  return <div className="strategy-action"><div><strong>Cover letter revision requested</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={revise}>{working ? "Revising letter…" : "Revise cover letter"}</button></div>;
}

function CoverLetterFinalizationAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "cover_letter_finalization_failed" ? "Finalization needs attention. The approved letter was not changed." : "Approval recorded. Lock the exact reviewed letter before rendering.");
  const working = run && ["cover_letter_finalization_requested", "cover_letter_finalization_running"].includes(run.status);
  useEffect(() => { if (initialStatus !== "cover_letter_approved") fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((r) => r.ok ? r.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined); }, [leadId, initialStatus]);
  useEffect(() => { if (!working || !run) return; const timer = window.setInterval(async () => { const response = await fetch(`http://localhost:8787/api/runs/${run.id}`); if (!response.ok) return; const next = await response.json(); setRun(next); if (next.status === "cover_letter_finalization_completed") onStatus(next.status); if (next.status === "cover_letter_finalization_failed") setMessage(next.error || "Cover letter finalization needs attention."); }, 1200); return () => window.clearInterval(timer); }, [working, run, onStatus]);
  async function finalize() { setMessage("Locking the approved cover letter…"); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-finalize`, { method: "POST" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Finalization could not start."); setRun(payload); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Finalization could not start."); } }
  return <div className="strategy-action"><div><strong>Cover letter approved</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={finalize}>{working ? "Finalizing…" : "Finalize cover letter"}</button></div>;
}

function CoverLetterPdfAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState(initialStatus === "cover_letter_pdf_failed" ? "PDF rendering needs attention." : "The approved letter is locked and ready to render.");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const working = run && ["cover_letter_pdf_requested", "cover_letter_pdf_running"].includes(run.status);
  const reviewRequired = initialStatus === "cover_letter_pdf_review_required" || run?.status === "cover_letter_pdf_review_required";
  useEffect(() => { if (["cover_letter_pdf_requested", "cover_letter_pdf_running", "cover_letter_pdf_failed"].includes(initialStatus)) fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((r) => r.ok ? r.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined); }, [leadId, initialStatus]);
  useEffect(() => { if (!working || !run) return; const timer = window.setInterval(async () => { const response = await fetch(`http://localhost:8787/api/runs/${run.id}`); if (!response.ok) return; const next = await response.json(); setRun(next); if (next.status === "cover_letter_pdf_review_required") setMessage("Text fidelity passed. Inspect every page before approval."); if (next.status === "cover_letter_pdf_failed") setMessage(next.error || "PDF rendering needs attention."); }, 1200); return () => window.clearInterval(timer); }, [working, run]);
  async function renderPdf() { setMessage("Rendering and checking the cover-letter PDF…"); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-pdf`, { method: "POST" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "PDF rendering could not start."); setRun(payload); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "PDF rendering could not start."); } }
  async function decide(action: "approve" | "report_issue") { setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/cover-letter-pdf-decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, notes }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "PDF decision could not be saved."); onStatus(payload.status); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "PDF decision could not be saved."); } finally { setBusy(false); } }
  if (!reviewRequired) return <div className="strategy-action"><div><strong>Final cover letter ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={renderPdf}>{working ? "Rendering PDF…" : "Create cover-letter PDF"}</button></div>;
  return <section className="pdf-review"><header><div><strong>Inspect cover-letter PDF</strong><span>Text fidelity already passed</span></div><a href={`http://localhost:8787/api/jobs/${leadId}/cover-letter-pdf`} target="_blank" rel="noreferrer">Open full size</a></header><iframe title="Final cover letter PDF preview" src={`http://localhost:8787/api/jobs/${leadId}/cover-letter-pdf`} /><p>Check every page for clipping, overlapping text, broken characters, inconsistent margins, and awkward page breaks.</p><textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Describe any layout problem you see." /><div><button disabled={busy || !notes.trim()} onClick={() => decide("report_issue")}>Report layout issue</button><button className="approve" disabled={busy} onClick={() => decide("approve")}>PDF looks correct</button></div>{message && <small role="status">{message}</small>}</section>;
}

function ApplicationPackageAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [data, setData] = useState<PackageData | null>(null);
  const [message, setMessage] = useState(initialStatus === "application_package_failed" ? "Package assembly needs attention. No source document was changed." : initialStatus === "cover_letter_skipped" ? "The cover letter was intentionally omitted. Package the approved resume only." : "Approved documents are ready to assemble into the submission package.");
  const [questions, setQuestions] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const working = run && ["application_package_requested", "application_package_running"].includes(run.status);
  async function loadPackage() { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/application-package`); if (response.ok) setData(await response.json()); }
  useEffect(() => { if (["application_package_requested", "application_package_running", "application_package_failed"].includes(initialStatus)) fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((r) => r.ok ? r.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined); if (initialStatus === "application_package_completed") void loadPackage(); }, [leadId, initialStatus]);
  useEffect(() => { if (!working || !run) return; const timer = window.setInterval(async () => { const response = await fetch(`http://localhost:8787/api/runs/${run.id}`); if (!response.ok) return; const next = await response.json(); setRun(next); if (next.status === "application_package_completed") { setMessage("Application package assembled and validated."); onStatus(next.status); await loadPackage(); } if (next.status === "application_package_failed") setMessage(next.error || "Package assembly needs attention."); }, 1200); return () => window.clearInterval(timer); }, [working, run, onStatus]);
  async function assemble() { setMessage("Copying approved files and verifying package integrity…"); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/application-package`, { method: "POST" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Package assembly could not start."); setRun(payload); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Package assembly could not start."); } }
  async function importQuestions() { setSaving(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/form-questions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ questions_text: questions, source_url: sourceUrl }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Questions could not be imported."); onStatus(payload.status); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Questions could not be imported."); } finally { setSaving(false); } }
  if (!data) return <div className="strategy-action"><div><strong>Application documents ready</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={assemble}>{working ? "Assembling package…" : "Assemble application package"}</button></div>;
  const integrityPassed = Object.values(data.package.identity_checks).every(Boolean);
  return <section className="application-package"><header><div><span>APPLICATION PACKAGE</span><strong>Ready for form review</strong></div><b>v{data.package.package_version}</b></header><p>{data.package.company} · {data.package.role}</p><div className="package-files"><article><strong>Resume PDF</strong><span>{data.package.page_counts.resume} page(s)</span></article><article><strong>Cover letter PDF</strong><span>{data.package.packaged_artifacts.cover_letter_pdf ? `${data.package.page_counts.cover_letter} page(s)` : "Intentionally omitted"}</span></article></div><div className="package-integrity"><strong>{integrityPassed ? "File integrity verified" : "Integrity check needs attention"}</strong><span>Packaged files match their approved releases byte-for-byte.</span></div><details><summary>Pre-submission checklist</summary><pre>{data.checklist}</pre></details><div className="form-import"><strong>Import application questions</strong><span>Paste one question per line. Nothing will be entered on the employer site.</span><input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="Application page URL (optional)" /><textarea value={questions} onChange={(event) => setQuestions(event.target.value)} placeholder={'Why are you interested in this role?\nWhat are your salary expectations?\nAre you authorized to work in Canada?'} /><button disabled={saving || !questions.trim()} onClick={importQuestions}>{saving ? "Importing…" : "Import questions"}</button></div><small>Nothing has been uploaded or submitted. Application-form answers still require review.</small>{message && <small role="status">{message}</small>}</section>;
}

function ApplicationAnswersAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [plan, setPlan] = useState<AnswerPlan | null>(null);
  const [message, setMessage] = useState(initialStatus === "application_answers_failed" ? "Answer preparation needs attention. You can retry without changing the package." : "Questions imported. Prepare a reviewable answer plan.");
  const [busy, setBusy] = useState(false);
  const working = run && ["application_answers_requested", "application_answers_running"].includes(run.status);
  async function loadPlan() { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/application-answers`); if (response.ok) setPlan(await response.json()); }
  useEffect(() => { if (["application_answers_requested", "application_answers_running", "application_answers_failed"].includes(initialStatus)) fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`).then((r) => r.ok ? r.json() : null).then((latest) => latest?.id && setRun(latest)).catch(() => undefined); if (["application_answers_completed", "application_answers_approved"].includes(initialStatus)) void loadPlan(); }, [leadId, initialStatus]);
  useEffect(() => { if (!working || !run) return; const timer = window.setInterval(async () => { const response = await fetch(`http://localhost:8787/api/runs/${run.id}`); if (!response.ok) return; const next = await response.json(); setRun(next); if (next.status === "application_answers_completed") { setMessage("Answer plan prepared. Review every answer and flagged question."); onStatus(next.status); await loadPlan(); } if (next.status === "application_answers_failed") setMessage(next.error || "Answer preparation needs attention."); }, 1200); return () => window.clearInterval(timer); }, [working, run, onStatus]);
  async function prepare() { try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/application-answers`, { method: "POST" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Answer preparation could not start."); setRun(payload); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Answer preparation could not start."); } }
  function updateAnswer(questionId: string, value: string) { setPlan((current) => current ? { ...current, answers: current.answers.map((answer) => answer.question_id === questionId ? { ...answer, proposed_answer: value } : answer) } : current); }
  async function approve() { if (!plan) return; setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/application-answers-decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers: plan.answers.map((answer) => ({ question_id: answer.question_id, answer: answer.proposed_answer })) }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Answer approval could not be saved."); setPlan({ ...plan, answers_approved: true }); onStatus(payload.status); setMessage("Answers approved. This does not authorize form filling or submission."); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Answer approval could not be saved."); } finally { setBusy(false); } }
  if (!plan) return <div className="strategy-action"><div><strong>Application questions imported</strong><span>{message}</span></div><button disabled={Boolean(working)} onClick={prepare}>{working ? "Preparing answers…" : "Prepare answer plan"}</button></div>;
  const approved = initialStatus === "application_answers_approved" || plan.answers_approved;
  const incomplete = plan.answers.some((answer) => answer.status !== "attachment_ready" && !answer.proposed_answer?.trim());
  return <section className="application-package"><header><div><span>ANSWER PLAN</span><strong>{approved ? "Answers approved" : "Review required"}</strong></div><b>{plan.answers.length} questions</b></header><div className="answer-list">{plan.answers.map((answer) => <article key={answer.question_id}><div><strong>{answer.question}</strong><span>{answer.category.replaceAll("_", " ")} · {answer.status.replaceAll("_", " ")}</span></div>{answer.status === "attachment_ready" ? <p>{answer.reason}</p> : <textarea disabled={Boolean(approved)} value={answer.proposed_answer || ""} onChange={(event) => updateAnswer(answer.question_id, event.target.value)} placeholder={answer.reason} />}{answer.evidence_ids.length > 0 && <small>Evidence: {answer.evidence_ids.join(", ")}</small>}</article>)}</div>{!approved && <button className="approve-answers" disabled={busy || incomplete} onClick={approve}>{busy ? "Saving approval…" : "Approve reviewed answers"}</button>}<small>{approved ? "Answers are locked for the next stage. Form filling and submission are still not authorized." : "Complete every flagged answer and verify every draft. Approval here does not authorize submission."}</small>{message && <small role="status">{message}</small>}</section>;
}

function FormFillAction({ leadId, initialStatus, onStatus }: { leadId: string; initialStatus: string; onStatus: (status: string) => void }) {
  const [plan, setPlan] = useState<AnswerPlan | null>(null);
  const [packageData, setPackageData] = useState<PackageData | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [checked, setChecked] = useState<string[]>([]);
  const [documentsChecked, setDocumentsChecked] = useState(false);
  const [finalChecks, setFinalChecks] = useState({ answers: false, documents: false, commitments: false, authorize: false });
  const [message, setMessage] = useState("");
  const [submissionEvidence, setSubmissionEvidence] = useState("");
  const [browserReport, setBrowserReport] = useState<BrowserFillReport | null>(null);
  const [extensionVersion, setExtensionVersion] = useState<string | null>(null);
  const [allowDocumentUpload, setAllowDocumentUpload] = useState(false);
  const [recoveryNotes, setRecoveryNotes] = useState("");
  const [recoveryQuestions, setRecoveryQuestions] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { Promise.all([fetch(`http://localhost:8787/api/jobs/${leadId}/application-answers`).then((r) => r.ok ? r.json() : null), fetch(`http://localhost:8787/api/jobs/${leadId}/application-package`).then((r) => r.ok ? r.json() : null)]).then(([answers, pkg]) => { if (answers) { setPlan(answers); setSourceUrl(answers.source_url || ""); } if (pkg) setPackageData(pkg); }).catch(() => setMessage("Workflow service is offline.")); }, [leadId]);
  useEffect(() => { const detect = () => setExtensionVersion(document.documentElement.getAttribute("data-job-agent-extension")); detect(); window.addEventListener("job-agent-extension-ready", detect); const timer = window.setInterval(detect, 1200); return () => { window.removeEventListener("job-agent-extension-ready", detect); window.clearInterval(timer); }; }, []);
  useEffect(() => { if (initialStatus !== "form_filling_started") return; const load = async () => { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/form-fill-session`); if (!response.ok) return; const session = await response.json(); if (session.browser_fill_report) setBrowserReport(session.browser_fill_report); }; void load(); const timer = window.setInterval(load, 1800); return () => window.clearInterval(timer); }, [leadId, initialStatus]);
  async function start() { const popup = window.open("about:blank", "_blank"); setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/form-fill`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_url: sourceUrl, document_upload_authorized: allowDocumentUpload }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Assisted form filling could not start."); if (popup) popup.location.href = payload.browser_launch_url || sourceUrl; onStatus(payload.status); } catch (error) { popup?.close(); setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Assisted form filling could not start."); } finally { setBusy(false); } }
  async function copy(text: string) { try { await navigator.clipboard.writeText(text); setMessage("Answer copied."); } catch { setMessage("Copy was blocked by the browser. Select the answer text manually."); } }
  function toggle(questionId: string) { setChecked((current) => current.includes(questionId) ? current.filter((id) => id !== questionId) : [...current, questionId]); }
  async function ready() { if (!plan) return; setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/form-fill-ready`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ completed_question_ids: checked, documents_checked: documentsChecked }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Final review could not be requested."); onStatus(payload.status); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Final review could not be requested."); } finally { setBusy(false); } }
  async function authorize() { setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/submission-authorization`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers_confirmed: finalChecks.answers, documents_confirmed: finalChecks.documents, commitments_confirmed: finalChecks.commitments, authorize_now: finalChecks.authorize, authorization: "authorize_submission" }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Submission authorization could not be saved."); onStatus(payload.status); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Submission authorization could not be saved."); } finally { setBusy(false); } }
  async function beginSubmission() { window.open(sourceUrl, "_blank", "noopener,noreferrer"); setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/submission-execution`, { method: "POST" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Submission session could not start."); onStatus(payload.status); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Submission session could not start."); } finally { setBusy(false); } }
  async function recordOutcome(outcome: "submitted" | "blocked") { setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/submission-result`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome, evidence: submissionEvidence }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Submission result could not be recorded."); onStatus(payload.status); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Submission result could not be recorded."); } finally { setBusy(false); } }
  async function recover() { setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/submission-recovery`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resolution_notes: recoveryNotes, new_questions_text: recoveryQuestions }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Recovery could not start."); onStatus(payload.status); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Recovery could not start."); } finally { setBusy(false); } }
  if (!plan) return <div className="strategy-action"><div><strong>Loading approved answers</strong><span>{message || "Preparing the assisted application workspace…"}</span></div></div>;
  if (initialStatus === "application_answers_approved") return <section className="application-package"><header><div><span>ASSISTED APPLICATION</span><strong>Ready to fill</strong></div><b>No submission</b></header><div className={extensionVersion ? "extension-status connected" : "extension-status"}><div><strong>{extensionVersion ? "Browser adapter connected" : "Browser adapter setup required"}</strong><span>{extensionVersion ? `Version ${extensionVersion} can fill approved answers.` : "Install the adapter for automatic form filling, or continue manually."}</span></div><b>{extensionVersion ? "Connected" : "Not detected"}</b></div>{!extensionVersion && <details className="extension-setup"><summary>Set up automatic form filling</summary><ol><li><a href="http://localhost:8787/api/browser-extension">Download the browser adapter</a> and unzip it.</li><li>Open <code>chrome://extensions</code> in Chrome.</li><li>Turn on Developer mode, choose <strong>Load unpacked</strong>, and select the unzipped folder.</li><li>Refresh this page. The status above will change to Connected.</li></ol></details>}<p>Open the employer form and use the approved answers and documents. The agent will stop before submission.</p>{extensionVersion && <label className="upload-authorization"><input type="checkbox" checked={allowDocumentUpload} onChange={(event) => setAllowDocumentUpload(event.target.checked)} /><span><strong>Allow document upload for this application</strong><small>Upload only the byte-verified approved resume and cover letter into clearly labelled fields. Ambiguous fields remain manual.</small></span></label>}<div className="form-import"><input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://employer.example/apply" /><button disabled={busy || !sourceUrl.trim()} onClick={start}>{busy ? "Starting…" : extensionVersion ? "Open and auto-fill application" : "Continue without auto-fill"}</button></div>{message && <small role="status">{message}</small>}</section>;
  if (initialStatus === "application_submitted") return <ApplicationTracker leadId={leadId} />;
  if (initialStatus === "submission_blocked") return <section className="application-package"><header><div><span>SUBMISSION BLOCKED</span><strong>Resolve before retrying</strong></div><b>Not applied</b></header><p>{packageData?.package.company} · {packageData?.package.role}</p><div className="package-integrity"><strong>Previous authorization will be revoked</strong><span>The blocker evidence is preserved. Recovery requires fresh answer, document, and submission approval.</span></div><a href={sourceUrl} target="_blank" rel="noreferrer">Inspect employer application</a><div className="recovery-form"><label>What blocked the application, and what needs to change?<textarea value={recoveryNotes} onChange={(event) => setRecoveryNotes(event.target.value)} placeholder="Example: The employer added a required availability question after final review." /></label><label>New questions, one per line (optional)<textarea value={recoveryQuestions} onChange={(event) => setRecoveryQuestions(event.target.value)} placeholder={'What is your earliest available start date?\nDo you accept the updated travel requirement?'} /></label><button disabled={busy || !recoveryNotes.trim()} onClick={recover}>{busy ? "Starting recovery…" : "Revoke authorization and review again"}</button></div>{message && <small role="status">{message}</small>}</section>;
  if (initialStatus === "submission_authorized") return <section className="application-package"><header><div><span>SUBMISSION AUTHORIZED</span><strong>Ready for final action</strong></div><b>Not submitted</b></header><p>{packageData?.package.company} · {packageData?.package.role}</p><div className="package-integrity"><strong>Authorization is scoped to this application</strong><span>The form and documents were reviewed. Continue only while the employer form remains unchanged.</span></div><button className="authorize-submission" disabled={busy} onClick={beginSubmission}>{busy ? "Starting…" : "Begin authorized submission"}</button><small>The employer form will open. Stop if a CAPTCHA, new field, changed declaration, or error appears.</small>{message && <small role="status">{message}</small>}</section>;
  if (initialStatus === "submission_in_progress") return <section className="application-package"><header><div><span>SUBMISSION SESSION</span><strong>Record employer outcome</strong></div><b>Awaiting result</b></header><p>Use the authorized employer form. If it is unchanged, complete the final action there, then copy the confirmation message below.</p><a href={sourceUrl} target="_blank" rel="noreferrer">Return to employer application</a><textarea className="submission-evidence" value={submissionEvidence} onChange={(event) => setSubmissionEvidence(event.target.value)} placeholder="Example: Thank you. Your application has been received.\nOr paste the CAPTCHA, missing-field, or error message." /><div className="submission-result-actions"><button disabled={busy || !submissionEvidence.trim()} onClick={() => recordOutcome("blocked")}>Blocked or changed</button><button className="approve" disabled={busy || !submissionEvidence.trim()} onClick={() => recordOutcome("submitted")}>Submission confirmed</button></div><small>Only choose “Submission confirmed” after the employer displays a success confirmation.</small>{message && <small role="status">{message}</small>}</section>;
  if (initialStatus === "submission_review_required") {
    const allFinalChecks = Object.values(finalChecks).every(Boolean);
    return <section className="application-package"><header><div><span>FINAL REVIEW</span><strong>Authorize this application?</strong></div><b>Not submitted</b></header><p>{packageData?.package.company} · {packageData?.package.role}</p><div className="answer-list">{plan.answers.map((answer) => <article key={answer.question_id}><div><strong>{answer.question}</strong><span>{answer.category.replaceAll("_", " ")}</span></div>{answer.proposed_answer ? <p>{answer.proposed_answer}</p> : <p>Approved document attachment</p>}</article>)}</div><div className="final-confirmations"><label><input type="checkbox" checked={finalChecks.answers} onChange={(event) => setFinalChecks({ ...finalChecks, answers: event.target.checked })} /> I reviewed every answer shown above.</label><label><input type="checkbox" checked={finalChecks.documents} onChange={(event) => setFinalChecks({ ...finalChecks, documents: event.target.checked })} /> I verified the selected resume and cover letter.</label><label><input type="checkbox" checked={finalChecks.commitments} onChange={(event) => setFinalChecks({ ...finalChecks, commitments: event.target.checked })} /> I confirm all salary, travel, relocation, legal, and personal declarations.</label><label className="authorization-check"><input type="checkbox" checked={finalChecks.authorize} onChange={(event) => setFinalChecks({ ...finalChecks, authorize: event.target.checked })} /> I authorize submission of this specific application now.</label></div><div className="form-fill-links"><a href={sourceUrl} target="_blank" rel="noreferrer">Inspect employer form again</a><a href={`http://localhost:8787/api/jobs/${leadId}/resume-pdf`} target="_blank" rel="noreferrer">Inspect resume</a>{packageData?.package.packaged_artifacts.cover_letter_pdf && <a href={`http://localhost:8787/api/jobs/${leadId}/cover-letter-pdf`} target="_blank" rel="noreferrer">Inspect cover letter</a>}</div><button className="authorize-submission" disabled={busy || !allFinalChecks} onClick={authorize}>{busy ? "Recording authorization…" : "Authorize this application for submission"}</button><small>This records permission only. It does not click Submit.</small>{message && <small role="status">{message}</small>}</section>;
  }
  const allChecked = checked.length === plan.answers.length;
  return <section className="application-package"><header><div><span>ASSISTED APPLICATION</span><strong>Fill and verify</strong></div><b>{checked.length}/{plan.answers.length}</b></header>{browserReport && <div className={browserReport.blockers.length || browserReport.unmatched.length ? "browser-report warning" : "browser-report"}><strong>{browserReport.filled.length} answer(s) auto-filled{browserReport.uploaded?.length ? ` · ${browserReport.uploaded.length} document(s) uploaded` : ""}</strong><span>{browserReport.blockers.length + browserReport.unmatched.length ? `${browserReport.blockers.length + browserReport.unmatched.length} item(s) need manual review.` : "No unmatched fields reported. Review everything before continuing."}</span>{browserReport.blockers.length > 0 && <ul>{browserReport.blockers.slice(0, 8).map((blocker) => <li key={blocker}>{blocker}</li>)}</ul>}</div>}<div className="form-fill-links"><a href={sourceUrl} target="_blank" rel="noreferrer">Open employer form</a><a href={`http://localhost:8787/api/jobs/${leadId}/resume-pdf`} target="_blank" rel="noreferrer">Open approved resume</a>{packageData?.package.packaged_artifacts.cover_letter_pdf && <a href={`http://localhost:8787/api/jobs/${leadId}/cover-letter-pdf`} target="_blank" rel="noreferrer">Open approved cover letter</a>}</div><div className="answer-list">{plan.answers.map((answer) => <article key={answer.question_id}><div><strong>{answer.question}</strong><span>{answer.category.replaceAll("_", " ")}</span></div>{answer.proposed_answer && <p>{answer.proposed_answer}</p>}<div className="fill-controls">{answer.proposed_answer && <button onClick={() => copy(answer.proposed_answer || "")}>Copy answer</button>}<label><input type="checkbox" checked={checked.includes(answer.question_id)} onChange={() => toggle(answer.question_id)} /> Confirmed in form</label></div></article>)}</div><label className="document-check"><input type="checkbox" checked={documentsChecked} onChange={(event) => setDocumentsChecked(event.target.checked)} /> I verified the uploaded resume and cover letter selection.</label><button className="approve-answers" disabled={busy || !allChecked || !documentsChecked} onClick={ready}>{busy ? "Saving…" : "Ready for final submission review"}</button><small>This only records that the form appears complete. Do not click Submit.</small>{message && <small role="status">{message}</small>}</section>;
}

function ApplicationTracker({ leadId }: { leadId: string }) {
  const [tracker, setTracker] = useState<ApplicationTrackerData | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { fetch(`http://localhost:8787/api/jobs/${leadId}/application-tracker`).then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Tracker unavailable."); setTracker(payload); }).catch((error) => setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Tracker unavailable.")); }, [leadId]);
  function update(field: keyof ApplicationTrackerData, value: string) { setTracker((current) => current ? { ...current, [field]: value } : current); }
  async function save() { if (!tracker) return; setBusy(true); try { const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/application-tracker`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(tracker) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Tracker update could not be saved."); setTracker(payload); setMessage("Application tracker updated."); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Tracker update could not be saved."); } finally { setBusy(false); } }
  if (!tracker) return <div className="strategy-action"><div><strong>Application submitted</strong><span>{message || "Loading follow-up tracker…"}</span></div></div>;
  return <section className="application-tracker"><header><div><span>APPLICATION TRACKER</span><strong>{tracker.company} · {tracker.role}</strong></div><b>{tracker.application_status.replaceAll("_", " ")}</b></header><div className="tracker-summary"><article><span>Submitted</span><strong>{new Date(tracker.submitted_at_utc).toLocaleDateString()}</strong></article><article><span>Follow up</span><strong>{tracker.follow_up_date || "Not scheduled"}</strong></article><article><span>Reference</span><strong>{tracker.confirmation_reference || "Add reference"}</strong></article></div><details><summary>Employer confirmation</summary><p>{tracker.confirmation_evidence}</p></details><div className="tracker-form"><label>Status<select value={tracker.application_status} onChange={(event) => update("application_status", event.target.value)}><option value="submitted">Submitted</option><option value="follow_up_due">Follow-up due</option><option value="interview">Interview</option><option value="offer">Offer</option><option value="rejected">Rejected</option><option value="withdrawn">Withdrawn</option><option value="closed">Closed</option></select></label><label>Confirmation or reference number<input value={tracker.confirmation_reference} onChange={(event) => update("confirmation_reference", event.target.value)} /></label><label>Follow-up date<input type="date" value={tracker.follow_up_date || ""} onChange={(event) => update("follow_up_date", event.target.value)} /></label><label>Expected response date<input type="date" value={tracker.expected_response_date || ""} onChange={(event) => update("expected_response_date", event.target.value)} /></label><label>Interview stage<input value={tracker.interview_stage || ""} onChange={(event) => update("interview_stage", event.target.value)} placeholder="Recruiter screen, hiring manager, panel…" /></label><label>Next action<input value={tracker.next_action} onChange={(event) => update("next_action", event.target.value)} /></label><label className="tracker-notes">Notes<textarea value={tracker.notes} onChange={(event) => update("notes", event.target.value)} /></label></div><button disabled={busy} onClick={save}>{busy ? "Saving…" : "Save tracker"}</button><details><summary>Status history</summary><ol>{tracker.history.map((item, index) => <li key={`${item.at_utc}-${index}`}><strong>{item.status.replaceAll("_", " ")}</strong><span>{new Date(item.at_utc).toLocaleString()} · {item.note}</span></li>)}</ol></details>{message && <small role="status">{message}</small>}</section>;
}
