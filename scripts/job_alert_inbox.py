from __future__ import annotations

import hashlib
import html
import re
import sqlite3
import json
from datetime import datetime, timezone
from email import policy
from email.parser import Parser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, unquote, urlparse, urlunparse

from safe_capture_policy import automatic_capture_plan


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
        job_id = re.search(r"/jobs/view/(?:[^/?#]*-)?(\d+)(?:/|$)", parsed.path)
        if job_id: return f"https://www.linkedin.com/jobs/view/{job_id.group(1)}"
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
        unwrapped = unwrap_url(link)
        plan = automatic_capture_plan(unwrapped)
        url = canonical_job_url(unwrapped, source)
        result_source = source
        if not url and plan:
            parsed = urlparse(unwrapped)
            url = urlunparse(("https", parsed.netloc.casefold(), parsed.path.rstrip("/"), "", "", ""))
            result_source = plan["platform"]
        title = " ".join(text.split()).strip(" |–—-")
        if not url or len(title) < 4 or title.casefold() in GENERIC_TEXT: continue
        results.append({"source": result_source, "title": title[:300], "posting_url": url})
    unique = {item["posting_url"]: item for item in results}
    return list(unique.values())


def save_captured_posting(payload: dict, output_directory: Path) -> Path:
    source = payload.get("source")
    if source not in SOURCES: raise ValueError("Capture source must be LinkedIn, Indeed, or Eluta.")
    required = {}
    for name in ("company", "role", "posting_url", "description_text"):
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip(): raise ValueError(f"Captured {name.replace('_', ' ')} is required.")
        required[name] = value.strip()
    if len(required["description_text"]) < 200: raise ValueError("Capture the complete job description before importing.")
    if sourceFor := canonical_job_url(required["posting_url"], source): required["posting_url"] = sourceFor
    else: raise ValueError("The captured URL does not match its job source.")
    posting = {**required, "application_url": payload.get("application_url") or required["posting_url"], "external_job_id": None, "platform": source, "location_raw": payload.get("location_raw"), "workplace_type_raw": payload.get("workplace_type_raw"), "employment_type_raw": payload.get("employment_type_raw"), "department": None, "salary": {"minimum": None, "maximum": None, "currency": None, "period": None, "source": None}, "posted_date": payload.get("posted_date"), "deadline": None, "collected_at": datetime.now(timezone.utc).isoformat(), "search_query": f"{source} job alert"}
    output_directory.mkdir(parents=True, exist_ok=True)
    name = f"captured-{source}-{hashlib.sha256(required['posting_url'].encode()).hexdigest()[:20]}.json"
    path = output_directory / name; path.write_text(json.dumps(posting, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


class AlertInboxStore:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path); self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE IF NOT EXISTS alert_jobs (id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, posting_url TEXT NOT NULL UNIQUE, status TEXT NOT NULL, received_at TEXT NOT NULL)""")
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(alert_jobs)")}
        if "lead_id" not in columns: self.connection.execute("ALTER TABLE alert_jobs ADD COLUMN lead_id TEXT")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS gmail_alert_messages (uid TEXT PRIMARY KEY, processed_at TEXT NOT NULL)""")
        self.connection.commit()
    def import_alert(self, source: str, content: str) -> dict:
        jobs = parse_alert(source, content); added = 0; timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection:
            for job in jobs:
                job_id = hashlib.sha256(job["posting_url"].encode()).hexdigest()[:20]
                cursor = self.connection.execute("INSERT OR IGNORE INTO alert_jobs(id,source,title,posting_url,status,received_at) VALUES (?, ?, ?, ?, 'needs_capture', ?)", (job_id, job["source"], job["title"], job["posting_url"], timestamp))
                added += cursor.rowcount
        return {"found": len(jobs), "added": added, "duplicates": len(jobs) - added, "jobs": self.list()}
    def list(self) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM alert_jobs ORDER BY received_at DESC").fetchall()
        return [dict(row) for row in rows]
    def get(self, job_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM alert_jobs WHERE id=?", (job_id,)).fetchone()
        if not row: raise KeyError(job_id)
        return dict(row)
    def mark_captured(self, source: str, posting_url: str, lead_id: str) -> None:
        canonical = canonical_job_url(posting_url, source) or posting_url
        with self.connection:
            rows = self.connection.execute("SELECT id, posting_url FROM alert_jobs WHERE source=?", (source,)).fetchall()
            matching_ids = [row["id"] for row in rows if (canonical_job_url(row["posting_url"], source) or row["posting_url"]) == canonical]
            if matching_ids:
                self.connection.executemany("UPDATE alert_jobs SET status='captured', lead_id=? WHERE id=?", [(lead_id, job_id) for job_id in matching_ids])
    def gmail_processed(self, uid: str) -> bool:
        return self.connection.execute("SELECT 1 FROM gmail_alert_messages WHERE uid=?", (uid,)).fetchone() is not None
    def mark_gmail_processed(self, uid: str) -> None:
        with self.connection: self.connection.execute("INSERT OR IGNORE INTO gmail_alert_messages VALUES (?, ?)", (uid, datetime.now(timezone.utc).isoformat()))
    def close(self) -> None:
        self.connection.close()
