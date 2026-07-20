(async function () {
  document.documentElement.setAttribute("data-job-agent-extension", chrome.runtime.getManifest().version);
  window.dispatchEvent(new CustomEvent("job-agent-extension-ready", { detail: chrome.runtime.getManifest().version }));
  if (globalThis.JobAgentCapture?.sourceForUrl(location.href)) {
    const captureButton = document.createElement("button");
    captureButton.type = "button"; captureButton.textContent = `Capture this job · v${chrome.runtime.getManifest().version}`;
    captureButton.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:2147483646;padding:10px 14px;border:0;border-radius:8px;background:#1f684f;color:white;font:600 13px Arial,sans-serif;box-shadow:0 5px 18px #0003";
    captureButton.addEventListener("click", async () => {
      captureButton.disabled = true; captureButton.textContent = "Capturing…";
      try {
        const posting = globalThis.JobAgentCapture.extract(document, location.href);
        const response = await fetch("http://localhost:8787/api/job-alerts/capture", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(posting) });
        const result = await response.json(); if (!response.ok) throw new Error(result.error || "Capture failed.");
        captureButton.textContent = "Captured for analysis"; captureButton.style.background = "#315f9a";
      } catch (error) { captureButton.textContent = error instanceof Error ? error.message : "Capture failed"; captureButton.style.maxWidth = "360px"; captureButton.style.background = "#9a5227"; captureButton.disabled = false; }
    });
    const addButton = () => { if (!document.body.contains(captureButton)) document.body.appendChild(captureButton); };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addButton, { once: true }); else addButton();
  }
  const parameters = new URLSearchParams(location.hash.replace(/^#/, ""));
  let leadId = parameters.get("jobAgentLead"); let token = parameters.get("jobAgentToken");
  if (leadId && token) {
    await chrome.runtime.sendMessage({ type: "job-agent-register-session", leadId, token });
    parameters.delete("jobAgentLead"); parameters.delete("jobAgentToken");
    const cleanHash = parameters.toString();
    history.replaceState(null, "", `${location.pathname}${location.search}${cleanHash ? `#${cleanHash}` : ""}`);
  } else {
    const stored = await chrome.runtime.sendMessage({ type: "job-agent-get-session" });
    leadId = stored?.leadId; token = stored?.token;
  }
  if (!leadId || !token || !globalThis.JobAgentMatcher) return;
  if (document.readyState === "loading") await new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve, { once: true }));

  function notice(title, detail, warning, rescan) {
    document.getElementById("job-agent-notice")?.remove();
    const panel = document.createElement("aside");
    panel.id = "job-agent-notice";
    panel.style.cssText = `position:fixed;right:18px;top:18px;z-index:2147483647;max-width:340px;padding:14px 16px;border-radius:10px;background:${warning ? "#fff4e8" : "#eff9f3"};border:1px solid ${warning ? "#d99b58" : "#6da989"};color:#173f30;font:13px/1.4 Arial,sans-serif;box-shadow:0 8px 30px #0002`;
    panel.innerHTML = `<strong style="display:block;margin-bottom:4px"></strong><span></span><button type="button" style="display:block;margin-top:9px;padding:6px 9px;border:0;border-radius:6px;background:#173f30;color:#fff;font:12px Arial,sans-serif">Scan current step</button>`;
    panel.querySelector("strong").textContent = title; panel.querySelector("span").textContent = detail;
    panel.querySelector("button").addEventListener("click", rescan);
    document.body.appendChild(panel);
  }

  function setValue(field, value) {
    if (field instanceof HTMLSelectElement) {
      const option = globalThis.JobAgentMatcher.chooseOption([...field.options], value);
      if (!option) return false; field.value = option.value;
    } else if ((field.type || "").toLowerCase() === "radio") {
      const group = field.name ? [...document.querySelectorAll(`input[type="radio"][name="${CSS.escape(field.name)}"]`)] : [field];
      const selected = globalThis.JobAgentMatcher.chooseOption(group.map((item) => ({ field: item, label: globalThis.JobAgentMatcher.optionLabel(item) })), value);
      if (!selected) return false;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked")?.set;
      if (!setter) return false; setter.call(selected.field, true); field = selected.field;
    } else if ((field.type || "").toLowerCase() === "checkbox") {
      const group = field.name ? [...document.querySelectorAll(`input[type="checkbox"][name="${CSS.escape(field.name)}"]`)] : [field];
      const selected = group.length > 1 ? globalThis.JobAgentMatcher.chooseOption(group.map((item) => ({ field: item, label: globalThis.JobAgentMatcher.optionLabel(item) })), value) : null;
      const target = selected?.field || field; const intent = selected ? true : globalThis.JobAgentMatcher.booleanIntent(value);
      if (intent === null) return false;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked")?.set;
      if (!setter) return false; setter.call(target, intent); field = target;
    } else {
      const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      if (!setter) return false; setter.call(field, value);
    }
    field.dispatchEvent(new Event("input", { bubbles: true })); field.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  async function sha256(buffer) {
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  async function uploadApprovedDocuments(payload) {
    const uploaded = []; const blockers = [];
    const fields = [...document.querySelectorAll('input[type="file"]')];
    for (const field of fields) {
      const label = globalThis.JobAgentMatcher.fieldLabel(field) || "unlabelled file field";
      const kind = globalThis.JobAgentMatcher.documentKind(label);
      if (!kind) { blockers.push(`Ambiguous file field: ${label}`); continue; }
      const documentInfo = payload.documents?.[kind];
      if (!payload.document_upload_authorized || !documentInfo) { blockers.push(`Manual file upload required: ${label}`); continue; }
      try {
        if (field.files?.length) {
          const existingHash = await sha256(await field.files[0].arrayBuffer());
          if (existingHash === documentInfo.sha256) { uploaded.push({ kind, filename: field.files[0].name, sha256: existingHash }); continue; }
          blockers.push(`Document field already contains a different file: ${label}`); continue;
        }
        const response = await fetch(`http://localhost:8787/api/jobs/${encodeURIComponent(leadId)}/browser-document?token=${encodeURIComponent(token)}&kind=${kind}`);
        if (!response.ok) throw new Error("approved document unavailable");
        const bytes = await response.arrayBuffer(); const actualHash = await sha256(bytes);
        if (actualHash !== documentInfo.sha256 || response.headers.get("X-Content-SHA256") !== documentInfo.sha256) throw new Error("document integrity mismatch");
        const transfer = new DataTransfer(); transfer.items.add(new File([bytes], documentInfo.filename, { type: "application/pdf" })); field.files = transfer.files;
        field.dispatchEvent(new Event("input", { bubbles: true })); field.dispatchEvent(new Event("change", { bubbles: true }));
        uploaded.push({ kind, filename: documentInfo.filename, sha256: actualHash });
      } catch (error) { blockers.push(`Document upload stopped for ${label}: ${error instanceof Error ? error.message : "unknown error"}`); }
    }
    return { uploaded, blockers };
  }

  const endpoint = `http://localhost:8787/api/jobs/${encodeURIComponent(leadId)}/browser-fill?token=${encodeURIComponent(token)}`;
  async function scan() {
    try {
      const response = await fetch(endpoint); const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "The approved answer session is unavailable.");
      if (payload.never_submit !== true) throw new Error("The server did not provide the no-submit safety flag.");
      const fields = globalThis.JobAgentMatcher.eligibleFields(document);
      const result = globalThis.JobAgentMatcher.matchAnswers(payload.answers, fields);
      const filled = []; const failed = [];
      for (const match of result.matches) {
        if (setValue(match.field, match.answer.answer)) filled.push({ question_id: match.answer.question_id, label: match.label });
        else failed.push(match.answer.question);
      }
      const captcha = Boolean(document.querySelector('iframe[src*="captcha" i], [class*="captcha" i], [id*="captcha" i]'));
      const documentResult = await uploadApprovedDocuments(payload);
      const blockers = [...failed, ...(captcha ? ["CAPTCHA detected"] : []), ...documentResult.blockers, ...result.unusedFields.map((label) => `Unreviewed field: ${label}`)];
      await fetch(`http://localhost:8787/api/jobs/${encodeURIComponent(leadId)}/browser-fill-report?token=${encodeURIComponent(token)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filled, uploaded: documentResult.uploaded, unmatched: result.unmatched, blockers }) });
      notice("Application assistant", blockers.length ? `${filled.length} answer(s) and ${documentResult.uploaded.length} document(s) filled. Review ${blockers.length + result.unmatched.length} unmatched or blocked item(s). Nothing was submitted.` : `${filled.length} approved answer(s) and ${documentResult.uploaded.length} approved document(s) filled. Review every field. Nothing was submitted.`, blockers.length > 0 || result.unmatched.length > 0, scan);
    } catch (error) {
      if (error instanceof Error && /not active|token/i.test(error.message)) await chrome.runtime.sendMessage({ type: "job-agent-clear-session" });
      notice("Application assistant stopped", error instanceof Error ? error.message : "The form could not be filled.", true, scan);
    }
  }
  await scan();
})();
