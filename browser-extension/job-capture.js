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
    if (host.endsWith("ziprecruiter.com")) {
      const jid = url.searchParams.get("jid");
      if (jid) return `https://www.ziprecruiter.com${url.pathname}?jid=${encodeURIComponent(jid)}`;
      const v2 = url.pathname.match(/^\/jobs\/v2\/([\w-]+)$/);
      if (v2) {
        try {
          const decoded = JSON.parse(atob(v2[1] + "=".repeat((4 - (v2[1].length % 4)) % 4)));
          if (decoded?.listing_key) return `https://www.ziprecruiter.com/jobs/v2/listing/${encodeURIComponent(decoded.listing_key)}`;
        } catch { /* fall through */ }
      }
      return null;
    }
    return null;
  }
  function sourceForUrl(value) { const normalized = postingUrl(value); if (!normalized) return null; const host = new URL(normalized).hostname; return host.includes("linkedin") ? "linkedin" : host.includes("indeed") ? "indeed" : host.includes("ziprecruiter") ? "ziprecruiter" : "eluta"; }
  function navigableUrl(value) {
    const url = new URL(value); const host = url.hostname.replace(/^www\./, "");
    if (host.endsWith("ziprecruiter.com") && /^\/jobs\/v2\/([\w-]+)$/.test(url.pathname) && !url.searchParams.get("jid")) {
      // The /jobs/v2/<blob> path only loads with its original tracking data intact;
      // the stable listing-key form derived by postingUrl() 404s when visited directly.
      return value;
    }
    return postingUrl(value) || value;
  }
  function text(value) { return typeof value === "string" ? value.replace(/<[^>]+>/g, " ").replace(/&nbsp;/gi, " ").replace(/\s+/g, " ").trim() : ""; }
  function firstText(document, selectors) { for (const selector of selectors) { const value = text(document.querySelector(selector)?.textContent); if (value) return value; } return ""; }
  function semanticDescription(document) {
    const headings = [...document.querySelectorAll("h1, h2, h3, h4, strong")].filter((node) => /^(about the job|job description|about this job)$/i.test(text(node.textContent)));
    const candidates = [];
    for (const heading of headings) {
      let node = heading;
      for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {
        const value = text(node.textContent);
        if (value.length >= 200 && value.length <= 50000) candidates.push(value);
      }
    }
    return candidates.sort((left, right) => left.length - right.length)[0] || "";
  }
  function linkedinTitle(document) { const value = text(document.title); const hiring = value.match(/^(.+?) hiring (.+?) in .+? \| LinkedIn$/i); if (hiring) return { company: hiring[1], title: hiring[2] }; const parts = value.split("|").map(text).filter(Boolean); return parts.length >= 3 && parts.at(-1)?.toLowerCase() === "linkedin" ? { title: parts[0], company: parts[1] } : {}; }
  function ziprecruiterTitle(document) { const heading = document.querySelector('h1[class*="header-md"], h2[class*="header-md"]'); return { title: heading ? text(heading.textContent) : "" }; }
  function jobPosting(document) { for (const node of document.querySelectorAll('script[type="application/ld+json"]')) { try { const parsed = JSON.parse(node.textContent || "null"); const values = Array.isArray(parsed) ? parsed : parsed?.["@graph"] || [parsed]; const found = values.find((item) => item?.["@type"] === "JobPosting"); if (found) return found; } catch {} } return null; }
  function locationValue(value) { const location = Array.isArray(value) ? value[0] : value; const address = location?.address || location; return text([address?.addressLocality, address?.addressRegion, address?.addressCountry].filter(Boolean).join(", ")) || text(location?.name); }
  const selectors = {
    linkedin: {
      title: [".job-details-jobs-unified-top-card__job-title h1", ".job-details-jobs-unified-top-card__job-title", ".jobs-unified-top-card__job-title", "h1"],
      company: [".job-details-jobs-unified-top-card__company-name a", ".job-details-jobs-unified-top-card__company-name", ".jobs-unified-top-card__company-name", "[data-company-name]"],
      description: [".jobs-description-content__text", ".jobs-description__content", ".jobs-description__container", ".jobs-box__html-content", "#job-details", ".jobs-search__job-details--container [class*='description']", ".jobs-search__job-details--wrapper [class*='description']", ".scaffold-layout__detail [class*='description']", "[class*='jobs-description']"],
      location: [".job-details-jobs-unified-top-card__primary-description-container", ".jobs-unified-top-card__bullet"],
    },
    indeed: { title: ["h1.jobsearch-JobInfoHeader-title", "h1"], company: ["[data-testid='inlineHeader-companyName']", "[data-company-name]"], description: ["#jobDescriptionText", "[class*='jobDescription']"], location: ["[data-testid='job-location']", "[class*='location']"] },
    eluta: { title: ["h1", "[itemprop='title']"], company: ["[itemprop='hiringOrganization']", "[class*='employer']", "[class*='company']"], description: ["[itemprop='description']", "[class*='description']", "main"], location: ["[itemprop='jobLocation']", "[class*='location']"] },
    ziprecruiter: { title: [], company: ["a[href^='/co/']", "[data-testid*='company' i]", "[class*='company']"], description: [], location: ["[class*='location']"] },
  };
  function extract(document, url) {
    const source = sourceForUrl(url); if (!source) throw new Error("Open an individual LinkedIn, Indeed, Eluta, or ZipRecruiter job first.");
    const posting = jobPosting(document), fields = selectors[source], titleFallback = source === "linkedin" ? linkedinTitle(document) : source === "ziprecruiter" ? ziprecruiterTitle(document) : {};
    const title = text(posting?.title) || firstText(document, fields.title) || titleFallback.title || "";
    const company = text(posting?.hiringOrganization?.name) || firstText(document, fields.company) || titleFallback.company || "";
    const description = text(posting?.description) || firstText(document, fields.description) || semanticDescription(document);
    const location = locationValue(posting?.jobLocation) || firstText(document, fields.location);
    const missing = [!title && "title", !company && "employer", description.length < 200 && "complete description"].filter(Boolean);
    if (missing.length) throw new Error(`Adapter 0.5.10 could not identify: ${missing.join(", ")}. Expand the job description, then try again.`);
    const realUrl = navigableUrl(url);
    return { source, company, role: title, posting_url: realUrl, application_url: text(posting?.url) || realUrl, description_text: description, location_raw: location || null, workplace_type_raw: posting?.jobLocationType === "TELECOMMUTE" ? "Remote" : null, employment_type_raw: text(posting?.employmentType) || null, posted_date: text(posting?.datePosted) || null };
  }
  return { sourceForUrl, postingUrl, navigableUrl, semanticDescription, extract };
});
