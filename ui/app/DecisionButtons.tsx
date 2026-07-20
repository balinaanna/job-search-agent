"use client";

import { useEffect, useState } from "react";

type Run = { id: string; status: string; error?: string | null };

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

  if (status === "strategy_completed") return <div className="decision-saved pursue"><strong>Strategy ready</strong><span>Validated and ready for document planning</span></div>;
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
