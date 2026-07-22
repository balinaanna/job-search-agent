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
from safe_capture_policy import capture_capability


SOURCES = {"linkedin", "indeed", "eluta"}
GENERIC_TEXT = {"apply", "apply now", "view job", "view jobs", "see job", "see jobs", "learn more", "jobs", "job alert"}
LOCATION_TERMS = ("remote", "canada", "british columbia", " bc", "vancouver", "richmond", "burnaby", "surrey", "toronto", "ontario", "calgary", "alberta")


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


class EmailTextParser(HTMLParser):
    BLOCKS = {"br", "div", "p", "li", "tr", "td", "h1", "h2", "h3", "h4", "h5", "h6"}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag.casefold() in self.BLOCKS: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag.casefold() in self.BLOCKS: self.parts.append("\n")
    def handle_data(self, data): self.parts.append(data)
    def lines(self) -> list[str]:
        return [" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.split()]


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


def alert_lines(body: str) -> list[str]:
    parser = EmailTextParser(); parser.feed(body)
    return parser.lines()


def location_like(value: str) -> bool:
    normalized = f" {value.casefold()}"
    return any(term in normalized for term in LOCATION_TERMS)


def anchor_metadata(anchor_text: str, lines: list[str]) -> dict[str, str | None]:
    title = " ".join(anchor_text.split()).strip(" |–—-")
    company = location = None
    at_match = re.match(r"^(.+?)\s+at\s+(.+?)(?:\s+[·|]\s+(.+))?$", title, re.I)
    if at_match:
        title, company, location = (value.strip() if value else None for value in at_match.groups())
    candidates: list[str] = []
    index = next((i for i, line in enumerate(lines) if title.casefold() in line.casefold()), None)
    if index is not None:
        for line in lines[index + 1:index + 7]:
            cleaned = line.strip(" |–—-")
            lowered = cleaned.casefold()
            if len(cleaned) < 2 or lowered in GENERIC_TEXT or lowered == title.casefold() or lowered.startswith(("view ", "apply ", "posted ")):
                continue
            candidates.append(cleaned)
    if not location:
        location = next((item for item in candidates if location_like(item)), None)
    if not company:
        company = next((item for item in candidates if item != location and not location_like(item) and len(item) <= 120), None)
    excerpt_parts = [item for item in candidates if item not in {company, location}][:3]
    excerpt = " · ".join(excerpt_parts)[:500] or None
    return {"title": title or anchor_text, "company": company, "location": location, "email_excerpt": excerpt}


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
    body = email_body(content); parser = AnchorParser(); parser.feed(body); lines = alert_lines(body)
    if not parser.anchors:
        parser.anchors = [("Job from alert", match) for match in re.findall(r"https?://[^\s<>\"]+", body)]
    results = []
    for text, link in parser.anchors:
        metadata = anchor_metadata(text, lines)
        unwrapped = unwrap_url(link)
        plan = automatic_capture_plan(unwrapped)
        url = canonical_job_url(unwrapped, source)
        result_source = source
        if not url and plan:
            parsed = urlparse(unwrapped)
            url = urlunparse(("https", parsed.netloc.casefold(), parsed.path.rstrip("/"), "", "", ""))
            result_source = plan["platform"]
        title = str(metadata["title"] or "")
        if not url or len(title) < 4 or title.casefold() in GENERIC_TEXT: continue
        results.append({"source": result_source, "title": title[:300], "posting_url": url, "company": metadata["company"], "location": metadata["location"], "email_excerpt": metadata["email_excerpt"]})
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
        if "capture_error" not in columns: self.connection.execute("ALTER TABLE alert_jobs ADD COLUMN capture_error TEXT")
        if "capture_updated_at" not in columns: self.connection.execute("ALTER TABLE alert_jobs ADD COLUMN capture_updated_at TEXT")
        if "company" not in columns: self.connection.execute("ALTER TABLE alert_jobs ADD COLUMN company TEXT")
        if "location" not in columns: self.connection.execute("ALTER TABLE alert_jobs ADD COLUMN location TEXT")
        if "email_excerpt" not in columns: self.connection.execute("ALTER TABLE alert_jobs ADD COLUMN email_excerpt TEXT")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS gmail_alert_messages (uid TEXT PRIMARY KEY, processed_at TEXT NOT NULL)""")
        self._consolidate_url_aliases()
        self.connection.commit()
    def _consolidate_url_aliases(self) -> int:
        """Merge legacy URL variants that identify the same board posting."""
        rows = self.connection.execute("SELECT * FROM alert_jobs ORDER BY received_at").fetchall()
        groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in rows:
            canonical = canonical_job_url(row["posting_url"], row["source"]) or row["posting_url"]
            groups.setdefault((row["source"], canonical), []).append(row)
        removed = 0
        for (_, canonical), matches in groups.items():
            if len(matches) < 2:
                continue
            survivor = max(matches, key=lambda row: (row["status"] == "captured", bool(row["lead_id"]), row["received_at"]))
            others = [row for row in matches if row["id"] != survivor["id"]]
            def first_value(name: str):
                return next((row[name] for row in [survivor, *others] if row[name]), None)
            self.connection.executemany("DELETE FROM alert_jobs WHERE id=?", [(row["id"],) for row in others])
            self.connection.execute("""UPDATE alert_jobs SET posting_url=?, title=?, company=?, location=?, email_excerpt=?,
              lead_id=?, capture_error=?, capture_updated_at=? WHERE id=?""", (
                canonical, first_value("title"), first_value("company"), first_value("location"),
                first_value("email_excerpt"), first_value("lead_id"), first_value("capture_error"),
                first_value("capture_updated_at"), survivor["id"],
            ))
            removed += len(others)
        return removed
    def import_alert(self, source: str, content: str) -> dict:
        jobs = parse_alert(source, content); added = 0; timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection:
            for job in jobs:
                job_id = hashlib.sha256(job["posting_url"].encode()).hexdigest()[:20]
                cursor = self.connection.execute("INSERT OR IGNORE INTO alert_jobs(id,source,title,posting_url,status,received_at,company,location,email_excerpt) VALUES (?, ?, ?, ?, 'needs_capture', ?, ?, ?, ?)", (job_id, job["source"], job["title"], job["posting_url"], timestamp, job.get("company"), job.get("location"), job.get("email_excerpt")))
                added += cursor.rowcount
                if cursor.rowcount == 0:
                    self.connection.execute("""UPDATE alert_jobs SET
                      company=COALESCE(company, ?), location=COALESCE(location, ?),
                      email_excerpt=COALESCE(email_excerpt, ?)
                      WHERE posting_url=?""", (job.get("company"), job.get("location"), job.get("email_excerpt"), job["posting_url"]))
        return {"found": len(jobs), "added": added, "duplicates": len(jobs) - added, "jobs": self.list()}
    def list(self) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM alert_jobs ORDER BY received_at DESC").fetchall()
        return [dict(row) for row in rows]
    def get(self, job_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM alert_jobs WHERE id=?", (job_id,)).fetchone()
        if not row: raise KeyError(job_id)
        return dict(row)
    def queue_safe_captures(self) -> list[str]:
        queued: list[str] = []
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection:
            rows = self.connection.execute("SELECT id, posting_url FROM alert_jobs WHERE status IN ('needs_capture','safe_capture_failed')").fetchall()
            for row in rows:
                if capture_capability(row["posting_url"])["mode"] != "automatic_available":
                    continue
                self.connection.execute("UPDATE alert_jobs SET status='safe_capture_queued', capture_error=NULL, capture_updated_at=? WHERE id=?", (timestamp, row["id"]))
                queued.append(row["id"])
        return queued
    def claim_safe_capture(self) -> dict | None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute("SELECT * FROM alert_jobs WHERE status='safe_capture_queued' ORDER BY received_at LIMIT 1").fetchone()
            if not row:
                self.connection.commit(); return None
            timestamp = datetime.now(timezone.utc).isoformat()
            self.connection.execute("UPDATE alert_jobs SET status='safe_capturing', capture_updated_at=? WHERE id=?", (timestamp, row["id"]))
            self.connection.commit()
            return {**dict(row), "status": "safe_capturing", "capture_updated_at": timestamp}
        except Exception:
            self.connection.rollback(); raise
    def mark_safe_capture_failed(self, job_id: str, error: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE alert_jobs SET status='safe_capture_failed', capture_error=?, capture_updated_at=? WHERE id=?", (error[-2000:], datetime.now(timezone.utc).isoformat(), job_id))
    def mark_captured(self, source: str, posting_url: str, lead_id: str) -> None:
        canonical = canonical_job_url(posting_url, source) or posting_url
        with self.connection:
            rows = self.connection.execute("SELECT id, posting_url FROM alert_jobs WHERE source=?", (source,)).fetchall()
            matching_ids = [row["id"] for row in rows if (canonical_job_url(row["posting_url"], source) or row["posting_url"]) == canonical]
            if matching_ids:
                self.connection.executemany("UPDATE alert_jobs SET status='captured', lead_id=?, capture_error=NULL, capture_updated_at=? WHERE id=?", [(lead_id, datetime.now(timezone.utc).isoformat(), job_id) for job_id in matching_ids])
    def gmail_processed(self, uid: str) -> bool:
        return self.connection.execute("SELECT 1 FROM gmail_alert_messages WHERE uid=?", (uid,)).fetchone() is not None
    def mark_gmail_processed(self, uid: str) -> None:
        with self.connection: self.connection.execute("INSERT OR IGNORE INTO gmail_alert_messages VALUES (?, ?)", (uid, datetime.now(timezone.utc).isoformat()))
    def close(self) -> None:
        self.connection.close()
