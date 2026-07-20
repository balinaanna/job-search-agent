"use client";

import { useEffect, useState } from "react";

type Run = { id: string; status: string; error?: string | null };

export function AnalyzeButton({ leadId }: { leadId: string }) {
  const [run, setRun] = useState<Run | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!run || !["analysis_requested", "analysis_running"].includes(run.status)) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`http://localhost:8787/api/runs/${run.id}`);
      if (!response.ok) return;
      const next = await response.json();
      setRun(next);
      if (next.status === "analysis_completed") {
        setMessage("Analysis complete. Refreshing…");
        window.setTimeout(() => window.location.reload(), 500);
      }
      if (next.status === "analysis_failed") setMessage(next.error || "Analysis needs attention.");
    }, 1200);
    return () => window.clearInterval(timer);
  }, [run]);

  async function analyze() {
    setMessage("Starting evidence-based analysis…");
    try {
      const response = await fetch(`http://localhost:8787/api/jobs/${leadId}/analyze`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Analysis could not start.");
      setRun(payload);
      setMessage("Analysis queued. You can leave this page while it runs.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The local workflow service is not running.");
    }
  }

  const working = run && ["analysis_requested", "analysis_running"].includes(run.status);
  return <div className="analyze-control"><button type="button" disabled={Boolean(working)} onClick={analyze}>{working ? "Analyzing…" : "Analyze"}</button>{message && <span role="status">{message}</span>}</div>;
}
