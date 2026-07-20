(async function () {
  document.documentElement.setAttribute("data-job-agent-extension", chrome.runtime.getManifest().version);
  window.dispatchEvent(new CustomEvent("job-agent-extension-ready", { detail: chrome.runtime.getManifest().version }));
  const parameters = new URLSearchParams(location.hash.replace(/^#/, ""));
  const leadId = parameters.get("jobAgentLead"); const token = parameters.get("jobAgentToken");
  if (!leadId || !token || !globalThis.JobAgentMatcher) return;
  parameters.delete("jobAgentLead"); parameters.delete("jobAgentToken");
  const cleanHash = parameters.toString();
  history.replaceState(null, "", `${location.pathname}${location.search}${cleanHash ? `#${cleanHash}` : ""}`);
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
      const fileUploads = [...document.querySelectorAll('input[type="file"]')].map((field) => globalThis.JobAgentMatcher.fieldLabel(field) || "document upload");
      const blockers = [...failed, ...(captcha ? ["CAPTCHA detected"] : []), ...fileUploads.map((label) => `Manual file upload required: ${label}`), ...result.unusedFields.map((label) => `Unreviewed field: ${label}`)];
      await fetch(`http://localhost:8787/api/jobs/${encodeURIComponent(leadId)}/browser-fill-report?token=${encodeURIComponent(token)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filled, unmatched: result.unmatched, blockers }) });
      notice("Application assistant", blockers.length ? `${filled.length} answer(s) filled. Review ${blockers.length + result.unmatched.length} unmatched or blocked item(s). Nothing was submitted.` : `${filled.length} approved answer(s) filled. Review every field and upload the approved documents. Nothing was submitted.`, blockers.length > 0 || result.unmatched.length > 0, scan);
    } catch (error) {
      notice("Application assistant stopped", error instanceof Error ? error.message : "The form could not be filled.", true, scan);
    }
  }
  await scan();
})();
