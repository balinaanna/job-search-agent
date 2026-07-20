(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.JobAgentCapture = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function postingUrl(value) {
    const url = new URL(value); const host = url.hostname.replace(/^www\./, "");
    if (host.endsWith("linkedin.com")) {
      const pathId = url.pathname.match(/\/jobs\/view\/(\d+)/)?.[1]; const jobId = pathId || url.searchParams.get("currentJobId");
      return jobId ? `https://www.linkedin.com/jobs/view/${jobId}` : null;
    }
    if (host.endsWith("indeed.com")) { const key = url.searchParams.get("jk"); return key ? `https://ca.indeed.com/viewjob?jk=${encodeURIComponent(key)}` : null; }
    if (host.endsWith("eluta.ca") && url.pathname.startsWith("/spl/")) return `https://www.eluta.ca${url.pathname}`;
    return null;
  }
  function sourceForUrl(value) { const normalized = postingUrl(value); if (!normalized) return null; const host = new URL(normalized).hostname; return host.includes("linkedin") ? "linkedin" : host.includes("indeed") ? "indeed" : "eluta"; }
  function text(value) { return typeof value === "string" ? value.replace(/<[^>]+>/g, " ").replace(/&nbsp;/gi, " ").replace(/\s+/g, " ").trim() : ""; }
  function firstText(document, selectors) { for (const selector of selectors) { const value = text(document.querySelector(selector)?.textContent); if (value) return value; } return ""; }
  function jobPosting(document) { for (const node of document.querySelectorAll('script[type="application/ld+json"]')) { try { const parsed = JSON.parse(node.textContent || "null"); const values = Array.isArray(parsed) ? parsed : parsed?.["@graph"] || [parsed]; const found = values.find((item) => item?.["@type"] === "JobPosting"); if (found) return found; } catch {} } return null; }
  function locationValue(value) { const location = Array.isArray(value) ? value[0] : value; const address = location?.address || location; return text([address?.addressLocality, address?.addressRegion, address?.addressCountry].filter(Boolean).join(", ")) || text(location?.name); }
  const selectors = {
    linkedin: {
      title: [".job-details-jobs-unified-top-card__job-title h1", ".job-details-jobs-unified-top-card__job-title", ".jobs-unified-top-card__job-title", "h1"],
      company: [".job-details-jobs-unified-top-card__company-name a", ".job-details-jobs-unified-top-card__company-name", ".jobs-unified-top-card__company-name", "[data-company-name]"],
      description: [".jobs-description__content", ".jobs-box__html-content", "#job-details", "[class*='jobs-description']"],
      location: [".job-details-jobs-unified-top-card__primary-description-container", ".jobs-unified-top-card__bullet"],
    },
    indeed: { title: ["h1.jobsearch-JobInfoHeader-title", "h1"], company: ["[data-testid='inlineHeader-companyName']", "[data-company-name]"], description: ["#jobDescriptionText", "[class*='jobDescription']"], location: ["[data-testid='job-location']", "[class*='location']"] },
    eluta: { title: ["h1", "[itemprop='title']"], company: ["[itemprop='hiringOrganization']", "[class*='employer']", "[class*='company']"], description: ["[itemprop='description']", "[class*='description']", "main"], location: ["[itemprop='jobLocation']", "[class*='location']"] },
  };
  function extract(document, url) {
    const source = sourceForUrl(url); if (!source) throw new Error("Open an individual LinkedIn, Indeed, or Eluta job first.");
    const posting = jobPosting(document), fields = selectors[source];
    const title = text(posting?.title) || firstText(document, fields.title);
    const company = text(posting?.hiringOrganization?.name) || firstText(document, fields.company);
    const description = text(posting?.description) || firstText(document, fields.description);
    const location = locationValue(posting?.jobLocation) || firstText(document, fields.location);
    const missing = [!title && "title", !company && "employer", description.length < 200 && "complete description"].filter(Boolean);
    if (missing.length) throw new Error(`Could not identify: ${missing.join(", ")}. Wait for the job panel to finish loading and try again.`);
    const canonical = postingUrl(url);
    return { source, company, role: title, posting_url: canonical, application_url: text(posting?.url) || canonical, description_text: description, location_raw: location || null, workplace_type_raw: posting?.jobLocationType === "TELECOMMUTE" ? "Remote" : null, employment_type_raw: text(posting?.employmentType) || null, posted_date: text(posting?.datePosted) || null };
  }
  return { sourceForUrl, postingUrl, extract };
});
