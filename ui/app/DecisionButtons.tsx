"use client";

import { useEffect, useState } from "react";

type Run = { id: string; status: string; error?: string | null };
type Finding = { finding_id: string; severity: string; location: string; problem: string; why_it_matters: string; revision_instruction: string };
type ReviewData = {
  resume: string;
  review: { review_score: { total: number }; verdict: string; first_impression: string; strengths: string[]; findings: Finding[] };
  trace: { elements: Array<{ element_id: string; final_text: string; evidence_ids: string[] }> };
};

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
    fetch(`http://localhost:8787/api/jobs/${leadId}/workflow`)
      .then((response) => response.ok ? response.json() : null)
      .then((run) => run?.status && setStatus(run.status))
      .catch(() => undefined);
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

  if (["strategy_completed", "resume_plan_requested", "resume_plan_running", "resume_plan_failed"].includes(status)) return <ApplicationStart leadId={leadId} initialStatus={status} onStatus={setStatus} />;
  if (["resume_plan_completed", "resume_draft_requested", "resume_draft_running", "resume_draft_failed"].includes(status)) return <ResumeDraftAction leadId={leadId} initialStatus={status} onStatus={setStatus} />;
  if (["resume_draft_completed", "resume_revision_completed", "resume_review_requested", "resume_review_running", "resume_review_failed", "resume_review_completed"].includes(status)) return <ResumeReviewAction leadId={leadId} initialStatus={status} onStatus={setStatus} />;
  if (["resume_approved", "resume_finalization_requested", "resume_finalization_running", "resume_finalization_failed"].includes(status)) return <ResumeFinalizationAction leadId={leadId} initialStatus={status} onStatus={setStatus} />;
  if (["resume_finalization_completed", "resume_pdf_requested", "resume_pdf_running", "resume_pdf_failed", "resume_pdf_review_required"].includes(status)) return <ResumePdfAction leadId={leadId} initialStatus={status} onStatus={setStatus} />;
  if (status === "resume_pdf_completed") return <div className="decision-saved pursue"><strong>Resume PDF ready</strong><span>Content and layout approved. Nothing has been submitted.</span></div>;
  if (["resume_revision_requested", "resume_revision_running", "resume_revision_failed"].includes(status)) return <ResumeRevisionAction leadId={leadId} initialStatus={status} onStatus={setStatus} />;
  if (["pursue", "strategy_requested", "strategy_running", "strategy_failed"].includes(status)) return <StrategyAction leadId={leadId} initialStatus={status} onStatus={setStatus} />;
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
