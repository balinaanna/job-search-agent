from __future__ import annotations

import hashlib
import html
import re
import sqlite3
from datetime import datetime, timezone
from email import policy
from email.parser import Parser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, unquote, urlparse, urlunparse


SOURCES = {"linkedin", "indeed", "eluta"}
GENERIC_TEXT = {"apply", "apply now", "view job", "view jobs", "see job", "see jobs", "learn more", "jobs", "job alert"}


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.current = None; self.text = []; self.anchors = []
    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "a": self.current = dict(attrs).get("href"); self.text = []
    def handle_data(self, data):
        if self.current: self.text.append(data)
    def handle_endtag(self, tag):
        if tag.casefold() == "a" and self.current:
            self.anchors.append((" ".join("".join(self.text).split()), html.unescape(self.current)))
            self.current = None; self.text = []


def email_body(value: str) -> str:
    try:
        message = Parser(policy=policy.default).parsestr(value)
        if not message.get("From") and not message.is_multipart(): return value
        parts = []
        for part in message.walk():
            if part.get_content_type() in {"text/html", "text/plain"} and part.get_content_disposition() != "attachment":
                parts.append(part.get_content())
        return "\n".join(parts) or value
    except (ValueError, TypeError, LookupError):
        return value


def unwrap_url(value: str) -> str:
    current = html.unescape(value.strip())
    for _ in range(3):
        parsed = urlparse(current); query = parse_qs(parsed.query)
        nested = next((query[key][0] for key in ("url", "target", "dest", "destination", "redirect", "u") if query.get(key)), None)
        if not nested: break
        current = unquote(nested)
    return current


def canonical_job_url(value: str, source: str) -> str | None:
    value = unwrap_url(value); parsed = urlparse(value); host = parsed.netloc.casefold().removeprefix("www.")
    if source == "linkedin" and host.endswith("linkedin.com") and "/jobs/view/" in parsed.path:
        return urlunparse(("https", "www.linkedin.com", parsed.path.rstrip("/"), "", "", ""))
    if source == "indeed" and host.endswith("indeed.com"):
        job_key = parse_qs(parsed.query).get("jk", [None])[0]
        if job_key and ("viewjob" in parsed.path or "clk" in parsed.path): return f"https://ca.indeed.com/viewjob?{urlencode({'jk': job_key})}"
    if source == "eluta" and host.endswith("eluta.ca"):
        excluded = {"", "/", "/jobs", "/search", "/postjobs", "/employers"}
        if parsed.path not in excluded and not parsed.path.endswith("-jobs"):
            return urlunparse(("https", "www.eluta.ca", parsed.path, "", "", ""))
    return None


def parse_alert(source: str, content: str) -> list[dict]:
    if source not in SOURCES: raise ValueError("Source must be LinkedIn, Indeed, or Eluta.")
    if not isinstance(content, str) or not content.strip(): raise ValueError("Paste or upload a job-alert email first.")
    body = email_body(content); parser = AnchorParser(); parser.feed(body)
    if not parser.anchors:
        parser.anchors = [("Job from alert", match) for match in re.findall(r"https?://[^\s<>\"]+", body)]
    results = []
    for text, link in parser.anchors:
        url = canonical_job_url(link, source)
        title = " ".join(text.split()).strip(" |–—-")
        if not url or len(title) < 4 or title.casefold() in GENERIC_TEXT: continue
        results.append({"source": source, "title": title[:300], "posting_url": url})
    unique = {item["posting_url"]: item for item in results}
    return list(unique.values())


class AlertInboxStore:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path); self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE IF NOT EXISTS alert_jobs (id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, posting_url TEXT NOT NULL UNIQUE, status TEXT NOT NULL, received_at TEXT NOT NULL)""")
        self.connection.commit()
    def import_alert(self, source: str, content: str) -> dict:
        jobs = parse_alert(source, content); added = 0; timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection:
            for job in jobs:
                job_id = hashlib.sha256(job["posting_url"].encode()).hexdigest()[:20]
                cursor = self.connection.execute("INSERT OR IGNORE INTO alert_jobs VALUES (?, ?, ?, ?, 'needs_capture', ?)", (job_id, source, job["title"], job["posting_url"], timestamp))
                added += cursor.rowcount
        return {"found": len(jobs), "added": added, "duplicates": len(jobs) - added, "jobs": self.list()}
    def list(self) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM alert_jobs ORDER BY received_at DESC").fetchall()
        return [dict(row) for row in rows]
    def close(self) -> None:
        self.connection.close()
