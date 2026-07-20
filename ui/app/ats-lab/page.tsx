"use client";

import { useState } from "react";

export default function AtsCompatibilityLab() {
  const [step, setStep] = useState(1);
  return <main style={{ maxWidth: 760, margin: "40px auto", padding: 24, fontFamily: "Arial, sans-serif" }}>
    <header><small>LOCAL TEST PAGE · NO DATA IS SENT</small><h1>ATS compatibility lab</h1><p>This simulated application exercises common Greenhouse and Lever-style controls. It has no submission endpoint.</p></header>
    <form onSubmit={(event) => event.preventDefault()} style={{ display: "grid", gap: 18, padding: 22, border: "1px solid #ccd8d1", borderRadius: 12 }}>
      {step === 1 ? <>
        <label>Why are you interested in this role?<textarea name="motivation" rows={5} style={{ display: "block", width: "100%" }} /></label>
        <label>LinkedIn profile URL<input name="linkedin" type="url" style={{ display: "block", width: "100%" }} /></label>
        <fieldset><legend>Are you authorized to work in Canada?</legend><label><input type="radio" name="authorization" value="yes" /> Yes</label><label><input type="radio" name="authorization" value="no" /> No</label></fieldset>
        <label>Years of relevant experience<select name="experience" defaultValue=""><option value="">Select…</option><option>Less than 1 year</option><option>1–3 years</option><option>4–6 years</option><option>7+ years</option></select></label>
        <label>Resume upload<input name="resume" type="file" accept=".pdf" /></label>
        <button type="button" onClick={() => setStep(2)}>Continue to step 2</button>
      </> : <>
        <label>What are your salary expectations?<input name="salary" type="text" style={{ display: "block", width: "100%" }} /></label>
        <fieldset><legend>Will you require immigration sponsorship?</legend><label><input type="radio" name="sponsorship" value="yes" /> Yes</label><label><input type="radio" name="sponsorship" value="no" /> No</label></fieldset>
        <label><input name="truthful" type="checkbox" /> I confirm that the information provided is accurate.</label>
        <div role="group" aria-label="Voluntary self-identification"><label>Disability status<select name="disability" defaultValue=""><option value="">Choose not to answer</option><option>No</option><option>Yes</option></select></label></div>
        <div style={{ padding: 12, background: "#fff5e8", borderRadius: 8 }}><strong>End of test form</strong><p style={{ marginBottom: 0 }}>There is intentionally no Submit button. Use “Scan current step” in the adapter panel.</p></div>
      </>}
    </form>
  </main>;
}
