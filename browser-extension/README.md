# Browser form-filling adapter

This local Chrome extension fills only answers approved in the Job Search Agent.
It never clicks a submit button, never fills password or file inputs, and reports
CAPTCHAs, new fields, unmatched questions, and unsupported controls.

For local development, open `chrome://extensions`, enable Developer mode, choose
**Load unpacked**, and select this `browser-extension` directory. Keep the local
workflow service running while using it.
