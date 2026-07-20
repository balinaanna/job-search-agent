"use client";

import { useEffect, useState } from "react";

type DiscoveryRun = { id: string; status: string; error?: string | null; summary?: { discovered?: number; awaitingAnalysis?: number } | null };

export function FindJobsButton() {
  const [run, setRun] = useState<DiscoveryRun | null>(null);
  const [message, setMessage] = useState("");
  const working = run && ["requested", "running"].includes(run.status);
  useEffect(() => { fetch("http://localhost:8787/api/discovery/latest").then((response) => response.ok ? response.json() : null).then((latest) => { if (latest && ["requested", "running", "failed"].includes(latest.status)) { setRun(latest); if (latest.status === "failed") setMessage(latest.error || "The previous search needs attention."); } }).catch(() => undefined); }, []);
  useEffect(() => { if (!working || !run) return; const timer = window.setInterval(async () => { const response = await fetch("http://localhost:8787/api/discovery/latest"); if (!response.ok) return; const next = await response.json(); setRun(next); if (next.status === "completed") { setMessage(`Search complete. ${next.summary?.discovered ?? 0} active leads found.`); window.setTimeout(() => window.location.reload(), 700); } if (next.status === "failed") setMessage(next.error || "Job discovery needs attention."); }, 1400); return () => window.clearInterval(timer); }, [working, run]);
  async function start() { setMessage("Searching configured job sources and ranking new roles…"); try { const response = await fetch("http://localhost:8787/api/discovery", { method: "POST" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "Job search could not start."); setRun(payload); } catch (error) { setMessage(error instanceof TypeError ? "Workflow service is offline." : error instanceof Error ? error.message : "Job search could not start."); } }
  return <div className="find-jobs-control"><button className="search-button" type="button" disabled={Boolean(working)} onClick={start}>{working ? "Finding jobs…" : "Find new jobs"}</button>{message && <span role="status">{message}</span>}</div>;
}
