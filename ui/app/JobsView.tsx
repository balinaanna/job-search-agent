"use client";

import { useMemo, useState } from "react";
import { JobWorkflowPanel } from "./JobWorkflowPanel";

type BaseJob = { id: string; company: string; role: string; location: string | null; postingUrl: string; postedDate?: string | null; firstSeenAt?: string | null; discoveryScore: number | null };
type AnalyzedJob = BaseJob & { fitScore: number; recommendation: string; risk: string; nextAction: string };
type JobRow = (AnalyzedJob & { stage: "analyzed" }) | (BaseJob & { stage: "awaiting" });
const recommendationLabel: Record<string, string> = { strong_apply: "Strong match", apply: "Apply", selective_apply: "Stretch", do_not_apply: "Pass" };

function dateLabel(job: JobRow) {
  const value = job.postedDate || job.firstSeenAt;
  if (!value) return "Date unavailable";
  const formatted = new Intl.DateTimeFormat("en-CA", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(value));
  return job.postedDate ? `Posted ${formatted}` : `First seen ${formatted}`;
}

export function JobsView({ analyzedJobs, awaitingAnalysis }: { analyzedJobs: AnalyzedJob[]; awaitingAnalysis: BaseJob[] }) {
  const [search, setSearch] = useState(""), [stage, setStage] = useState("all"), [fit, setFit] = useState("all"), [sort, setSort] = useState("priority"), [visible, setVisible] = useState(10);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const jobs = useMemo<JobRow[]>(() => [...analyzedJobs.map((job) => ({ ...job, stage: "analyzed" as const })), ...awaitingAnalysis.map((job) => ({ ...job, stage: "awaiting" as const }))], [analyzedJobs, awaitingAnalysis]);
  const filtered = useMemo(() => jobs.filter((job) => { const text = `${job.company} ${job.role} ${job.location || ""}`.toLowerCase(); if (search && !text.includes(search.toLowerCase())) return false; if (stage !== "all" && job.stage !== stage) return false; if (fit !== "all" && (job.stage !== "analyzed" || job.recommendation !== fit)) return false; return true; }).sort((left, right) => { if (sort === "company") return left.company.localeCompare(right.company); if (sort === "discovery") return (right.discoveryScore || 0) - (left.discoveryScore || 0); return (right.stage === "analyzed" ? right.fitScore : right.discoveryScore || 0) - (left.stage === "analyzed" ? left.fitScore : left.discoveryScore || 0); }), [jobs, search, stage, fit, sort]);
  const reset = () => setVisible(10);
  return <section className="jobs-workspace" id="analysis-queue">
    <div className="section-heading"><div><p className="eyebrow">ALL ACTIVE ROLES</p><h2>Jobs workspace</h2></div><span>{filtered.length} of {jobs.length} jobs</span></div>
    <div className="jobs-toolbar"><input aria-label="Search jobs" value={search} onChange={(event) => { setSearch(event.target.value); reset(); }} placeholder="Search title, company, or location" /><select aria-label="Filter by stage" value={stage} onChange={(event) => { setStage(event.target.value); reset(); }}><option value="all">All stages</option><option value="analyzed">Analyzed</option><option value="awaiting">Awaiting analysis</option></select><select aria-label="Filter by fit" value={fit} onChange={(event) => { setFit(event.target.value); reset(); }}><option value="all">All fit decisions</option><option value="strong_apply">Strong match</option><option value="apply">Apply</option><option value="selective_apply">Stretch</option><option value="do_not_apply">Pass</option></select><select aria-label="Sort jobs" value={sort} onChange={(event) => setSort(event.target.value)}><option value="priority">Best score</option><option value="discovery">Discovery score</option><option value="company">Company A–Z</option></select></div>
    <div className="jobs-list">{filtered.slice(0, visible).map((job) => <article className="job-result" key={job.id}>
      <header><span className="company-avatar">{job.company.charAt(0)}</span><div><h3>{job.role}</h3><p>{job.company} · {job.location || "Location not stated"}</p><small className="job-date">{dateLabel(job)}</small></div>{job.stage === "analyzed" ? <span className={`recommendation ${job.recommendation}`}>{recommendationLabel[job.recommendation] || job.recommendation}</span> : <span className="awaiting-badge">Awaiting analysis</span>}</header>
      <div className="job-result-score"><strong>{job.stage === "analyzed" ? job.fitScore : job.discoveryScore || 0}</strong><span>{job.stage === "analyzed" ? "verified fit" : "preliminary"}</span></div>
      {job.stage === "analyzed" && <p className="risk"><strong>Main consideration:</strong> {job.risk}</p>}
      <div className="workflow-route"><strong>{job.stage === "analyzed" ? "Application workflow connected" : "Next: evidence-based fit analysis"}</strong>{job.stage === "analyzed" && <span>Decision → Strategy → Resume → Cover letter → Review → Package → Apply</span>}</div>
      <div className="job-result-actions"><button className="open-role-workflow" onClick={() => setSelectedJobId(job.id)}>{selectedJobId === job.id ? "Workflow open" : "Open workflow"}</button><a href={job.postingUrl} target="_blank" rel="noreferrer">View posting</a></div>
    </article>)}{filtered.length === 0 && <div className="empty-state">No jobs match these filters.</div>}</div>
    {selectedJobId && jobs.find((job) => job.id === selectedJobId) && <JobWorkflowPanel job={jobs.find((job) => job.id === selectedJobId)!} onClose={() => setSelectedJobId(null)} />}
    {visible < filtered.length && <button className="load-more" onClick={() => setVisible((count) => count + 10)}>Show 10 more</button>}
  </section>;
}
