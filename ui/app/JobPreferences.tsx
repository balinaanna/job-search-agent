"use client";

import { useEffect, useState } from "react";

type Preferences = {
  objective: { primary: string; secondary: string };
  target_role_families: { priority_1: string[]; priority_2: string[] };
  preferred_work_characteristics: string[];
  work_arrangement: {
    preferred: string[]; location_base: string; travel_acceptable: string; travel_avoid: string;
    has_licence: boolean; regular_car_access: boolean; driving_rule: string;
  };
  employment: { types_preferred: string[]; sponsorship_required: boolean };
  fit_scoring: { weights: Record<string, number>; hard_reject_conditions: string[] };
  application_strategy: { apply_when: string[]; do_not_apply_when: string[]; human_approval_required_before: string[] };
};

const WEIGHT_LABELS: Array<[string, string]> = [
  ["responsibilities_match", "Responsibilities match"],
  ["evidence_strength", "Evidence strength"],
  ["people_facing_alignment", "People-facing alignment"],
  ["technology_match", "Technology match"],
  ["seniority_match", "Seniority match"],
  ["logistics_match", "Logistics match"],
];

export function JobPreferences() {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [message, setMessage] = useState(""), [saving, setSaving] = useState(false);
  useEffect(() => { fetch("http://localhost:8787/api/profile/job-preferences").then(async (response) => { const value = await response.json(); if (!response.ok) throw new Error(value.error); return value; }).then(setPrefs).catch(() => setMessage("Start the local workflow service to edit job preferences.")); }, []);

  const lines = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);
  const weightTotal = prefs ? Object.values(prefs.fit_scoring.weights).reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0) : 0;

  async function save() {
    if (!prefs) return;
    setSaving(true); setMessage("");
    try {
      const response = await fetch("http://localhost:8787/api/profile/job-preferences", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(prefs) });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Job preferences could not be saved.");
      setPrefs(value);
      setMessage("Saved. These preferences will guide fit scoring and hard-reject rules for future analyses.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Job preferences could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return <section className="settings-panel job-preferences-page" aria-label="Job fit and application preferences">
      <div className="section-heading"><div><p className="eyebrow">FIT &amp; APPLICATION PREFERENCES</p><h2>What should count as a good fit?</h2><p className="settings-subtext">Separate from Search settings, which control what gets discovered — these guide fit scoring and hard-reject rules once a job is analyzed.</p></div></div>
      {!prefs ? <p className="settings-message" role="status">{message || "Loading your preferences…"}</p> : <>
        <div className="settings-grid">
          <label><strong>Primary objective</strong><span>The main goal fit scoring should optimize for.</span><input type="text" value={prefs.objective.primary} onChange={(event) => setPrefs({ ...prefs, objective: { ...prefs.objective, primary: event.target.value } })} /></label>
          <label><strong>Secondary objective</strong><span>A supporting direction to lean toward.</span><input type="text" value={prefs.objective.secondary} onChange={(event) => setPrefs({ ...prefs, objective: { ...prefs.objective, secondary: event.target.value } })} /></label>
        </div>
        <div className="settings-grid">
          <label><strong>Priority 1 target roles</strong><span>One title per line, highest priority first.</span><textarea rows={7} value={prefs.target_role_families.priority_1.join("\n")} onChange={(event) => setPrefs({ ...prefs, target_role_families: { ...prefs.target_role_families, priority_1: lines(event.target.value) } })} /></label>
          <label><strong>Priority 2 target roles</strong><span>Worth considering, but lower priority.</span><textarea rows={7} value={prefs.target_role_families.priority_2.join("\n")} onChange={(event) => setPrefs({ ...prefs, target_role_families: { ...prefs.target_role_families, priority_2: lines(event.target.value) } })} /></label>
        </div>
        <label className="full-width-field"><strong>Preferred work characteristics</strong><span>One characteristic per line.</span><textarea rows={5} value={prefs.preferred_work_characteristics.join("\n")} onChange={(event) => setPrefs({ ...prefs, preferred_work_characteristics: lines(event.target.value) })} /></label>
        <fieldset>
          <legend>Work arrangement</legend>
          <div className="settings-grid">
            <label><strong>Preferred arrangements</strong><span>One per line (e.g. Hybrid, Remote).</span><textarea rows={4} value={prefs.work_arrangement.preferred.join("\n")} onChange={(event) => setPrefs({ ...prefs, work_arrangement: { ...prefs.work_arrangement, preferred: lines(event.target.value) } })} /></label>
            <label><strong>Location base</strong><span>Used to judge commute distance.</span><input type="text" value={prefs.work_arrangement.location_base} onChange={(event) => setPrefs({ ...prefs, work_arrangement: { ...prefs.work_arrangement, location_base: event.target.value } })} /></label>
            <label><strong>Acceptable travel</strong><input type="text" value={prefs.work_arrangement.travel_acceptable} onChange={(event) => setPrefs({ ...prefs, work_arrangement: { ...prefs.work_arrangement, travel_acceptable: event.target.value } })} /></label>
            <label><strong>Travel to avoid</strong><input type="text" value={prefs.work_arrangement.travel_avoid} onChange={(event) => setPrefs({ ...prefs, work_arrangement: { ...prefs.work_arrangement, travel_avoid: event.target.value } })} /></label>
          </div>
          <div className="settings-checkboxes">
            <label><input type="checkbox" checked={prefs.work_arrangement.has_licence} onChange={(event) => setPrefs({ ...prefs, work_arrangement: { ...prefs.work_arrangement, has_licence: event.target.checked } })} /><span>Has a driver's licence</span></label>
            <label><input type="checkbox" checked={prefs.work_arrangement.regular_car_access} onChange={(event) => setPrefs({ ...prefs, work_arrangement: { ...prefs.work_arrangement, regular_car_access: event.target.checked } })} /><span>Has regular car access</span></label>
          </div>
          <label className="full-width-field"><strong>Driving rule</strong><span>The rule applied when scoring driving requirements.</span><textarea rows={2} value={prefs.work_arrangement.driving_rule} onChange={(event) => setPrefs({ ...prefs, work_arrangement: { ...prefs.work_arrangement, driving_rule: event.target.value } })} /></label>
        </fieldset>
        <fieldset>
          <legend>Employment</legend>
          <div className="settings-grid">
            <label><strong>Preferred employment types</strong><span>One per line.</span><textarea rows={4} value={prefs.employment.types_preferred.join("\n")} onChange={(event) => setPrefs({ ...prefs, employment: { ...prefs.employment, types_preferred: lines(event.target.value) } })} /></label>
            <label className="checkbox-field"><input type="checkbox" checked={prefs.employment.sponsorship_required} onChange={(event) => setPrefs({ ...prefs, employment: { ...prefs.employment, sponsorship_required: event.target.checked } })} /><span>Requires sponsorship</span></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Fit-scoring weights <small className={weightTotal === 100 ? "weight-total-ok" : "weight-total-bad"}>Total: {weightTotal}/100</small></legend>
          <div className="weights-grid">
            {WEIGHT_LABELS.map(([key, label]) => <label key={key}><strong>{label}</strong><input type="number" min={0} max={100} value={prefs.fit_scoring.weights[key] ?? 0} onChange={(event) => setPrefs({ ...prefs, fit_scoring: { ...prefs.fit_scoring, weights: { ...prefs.fit_scoring.weights, [key]: Number(event.target.value) } } })} /></label>)}
          </div>
          <label className="full-width-field"><strong>Hard-reject conditions</strong><span>One per line. A match forces "do not apply" regardless of score.</span><textarea rows={6} value={prefs.fit_scoring.hard_reject_conditions.join("\n")} onChange={(event) => setPrefs({ ...prefs, fit_scoring: { ...prefs.fit_scoring, hard_reject_conditions: lines(event.target.value) } })} /></label>
        </fieldset>
        <fieldset>
          <legend>Application strategy</legend>
          <div className="settings-grid">
            <label><strong>Apply when</strong><span>One condition per line.</span><textarea rows={5} value={prefs.application_strategy.apply_when.join("\n")} onChange={(event) => setPrefs({ ...prefs, application_strategy: { ...prefs.application_strategy, apply_when: lines(event.target.value) } })} /></label>
            <label><strong>Do not apply when</strong><span>One condition per line.</span><textarea rows={5} value={prefs.application_strategy.do_not_apply_when.join("\n")} onChange={(event) => setPrefs({ ...prefs, application_strategy: { ...prefs.application_strategy, do_not_apply_when: lines(event.target.value) } })} /></label>
          </div>
          <label className="full-width-field"><strong>Human approval required before</strong><span>One checkpoint per line. These stay separate from AGENTS.md's own safety rules.</span><textarea rows={6} value={prefs.application_strategy.human_approval_required_before.join("\n")} onChange={(event) => setPrefs({ ...prefs, application_strategy: { ...prefs.application_strategy, human_approval_required_before: lines(event.target.value) } })} /></label>
        </fieldset>
        <div className="settings-footer"><p role="status">{message}</p><button type="button" onClick={save} disabled={saving || weightTotal !== 100}>{saving ? "Saving…" : "Save job preferences"}</button></div>
      </>}
    </section>;
}
