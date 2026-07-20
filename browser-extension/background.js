const keyFor = (tabId) => `job-agent-session-${tabId}`;

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  const tabId = sender.tab?.id;
  if (!tabId) { respond(null); return false; }
  if (message?.type === "job-agent-register-session") {
    chrome.storage.session.set({ [keyFor(tabId)]: { leadId: message.leadId, token: message.token } }).then(() => respond({ stored: true }));
    return true;
  }
  if (message?.type === "job-agent-get-session") {
    chrome.storage.session.get(keyFor(tabId)).then((value) => respond(value[keyFor(tabId)] || null));
    return true;
  }
  if (message?.type === "job-agent-clear-session") {
    chrome.storage.session.remove(keyFor(tabId)).then(() => respond({ cleared: true }));
    return true;
  }
  return false;
});
