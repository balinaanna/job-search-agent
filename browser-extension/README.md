# Browser job capture and form-filling assistant

This local Chrome extension fills only answers approved in the Job Search Agent.
It never clicks a submit button, never fills password or file inputs, and reports
CAPTCHAs, new fields, unmatched questions, and unsupported controls.

Version 0.5 adds a user-initiated **Capture this job** button on individual
LinkedIn, Indeed, and Eluta job pages. It reads the visible posting, refuses
incomplete captures, and sends complete postings into the local discovery queue.
It does not crawl search results or capture pages without your click.

The assistant also supports text fields, text areas, select menus, radio groups, and
explicit checkbox answers. Ambiguous file uploads stay manual. On multi-step forms, use
the adapter's **Scan current step** button after moving to the next page. The
authorized session stays scoped to the same browser tab across ATS redirects.

Resume and cover-letter uploads are disabled by default. When separately
authorized in the application workspace, the adapter uploads only the approved
PDFs into clearly labelled fields after verifying their SHA-256 hashes.

For local development, open `chrome://extensions`, enable Developer mode, choose
**Load unpacked**, and select this `browser-extension` directory. Keep the local
workflow service running while using it.
