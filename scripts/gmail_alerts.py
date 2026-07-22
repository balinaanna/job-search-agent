from __future__ import annotations

import imaplib
import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Callable

from job_alert_inbox import AlertInboxStore


KEYRING_SERVICE = "anna-job-search-agent-gmail"


def load_config(path: Path) -> dict:
    if not path.exists(): return {"connected": False, "email": "", "poll_minutes": 10}
    value = json.loads(path.read_text(encoding="utf-8")); return {"connected": bool(value.get("connected")), "email": value.get("email", ""), "poll_minutes": value.get("poll_minutes", 10)}


def save_config(path: Path, email: str, poll_minutes: int = 10) -> dict:
    email = email.strip().casefold()
    if "@" not in email: raise ValueError("Enter a valid Gmail address.")
    if poll_minutes not in {5, 10, 15, 30, 60}: raise ValueError("Choose a supported check interval.")
    value = {"connected": True, "email": email, "poll_minutes": poll_minutes}
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8"); return value


def keyring_set(email: str, password: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, email, password.replace(" ", ""))
    except Exception as exc:
        raise ValueError("The Gmail app password could not be stored in macOS Keychain.") from exc


def keyring_get(email: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, email)
    except Exception as exc:
        raise ValueError("The Gmail app password could not be read from macOS Keychain.") from exc


def source_from_message(sender: str, subject: str) -> str | None:
    value = f"{sender} {subject}".casefold()
    return next((source for source in ("linkedin", "indeed", "eluta") if source in value), None)


def poll_gmail(config: dict, store: AlertInboxStore, password_getter: Callable[[str], str | None] = keyring_get, reprocess_processed: bool = False) -> dict:
    password = password_getter(config["email"])
    if not password: raise ValueError("Gmail app password is missing from Keychain.")
    client = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imported = messages = 0
    try:
        client.login(config["email"], password); client.select("INBOX", readonly=True)
        status, data = client.uid("search", None, 'OR OR FROM "linkedin" FROM "indeed" FROM "eluta"')
        if status != "OK": raise ValueError("Gmail could not search the inbox.")
        for uid in (data[0] or b"").split()[-100:]:
            uid_text = uid.decode();
            already_processed = store.gmail_processed(uid_text)
            if already_processed and not reprocess_processed: continue
            status, body = client.uid("fetch", uid, "(BODY.PEEK[])")
            if status != "OK" or not body or not isinstance(body[0], tuple): continue
            raw = body[0][1]; message = BytesParser(policy=policy.default).parsebytes(raw)
            source = source_from_message(str(message.get("From", "")), str(message.get("Subject", "")))
            if not source: continue
            result = store.import_alert(source, raw.decode("utf-8", errors="replace")); imported += result["added"]; messages += 1
            if not already_processed: store.mark_gmail_processed(uid_text)
    finally:
        try: client.logout()
        except imaplib.IMAP4.error: pass
    return {"messages": messages, "jobs_added": imported}
