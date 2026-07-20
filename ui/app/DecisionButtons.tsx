"use client";

import { useEffect, useState } from "react";

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

  if (["pursue", "pass"].includes(status)) {
    return <div className={`decision-saved ${status}`}><strong>{labels[status]}</strong><span>{status === "pursue" ? "Ready for application strategy" : "Removed from active consideration"}</span></div>;
  }

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
