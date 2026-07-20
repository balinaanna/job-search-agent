# Browser form-filling adapter

This local Chrome extension fills only answers approved in the Job Search Agent.
It never clicks a submit button, never fills password or file inputs, and reports
CAPTCHAs, new fields, unmatched questions, and unsupported controls.

Version 0.3 supports text fields, text areas, select menus, radio groups, and
explicit checkbox answers. File uploads stay manual. On multi-step forms, use
the adapter's **Scan current step** button after moving to the next page. The
authorized session stays scoped to the same browser tab across ATS redirects.

For local development, open `chrome://extensions`, enable Developer mode, choose
**Load unpacked**, and select this `browser-extension` directory. Keep the local
workflow service running while using it.
