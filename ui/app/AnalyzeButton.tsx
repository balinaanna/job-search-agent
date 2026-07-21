"use client";

import { useEffect, useState } from "react";

type Run = { id: string; status: string; error?: string | null };

export function AnalyzeButton({ leadId, label = "Analyze" }: { leadId: string; label?: string }) {
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
        setMessage("Analysis complete.");
        window.dispatchEvent(new Event("jobs-changed"));
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
      const unavailable = error instanceof TypeError;
      setMessage(unavailable
        ? "Analysis service is offline. Start the app from the project root with: python3 scripts/run_app.py"
        : error instanceof Error ? error.message : "Analysis could not start.");
    }
  }

  const working = run && ["analysis_requested", "analysis_running"].includes(run.status);
  return <div className="analyze-control"><button type="button" disabled={Boolean(working)} onClick={analyze}>{working ? "Analyzing…" : label}</button>{message && <span role="status">{message}</span>}</div>;
}
