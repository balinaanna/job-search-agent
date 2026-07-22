from __future__ import annotations

from urllib.parse import urlsplit


BLOCKED_JOB_BOARD_DOMAINS = ("linkedin.com", "indeed.com", "eluta.ca")
APPROVED_PUBLIC_API_HOSTS = {
    "boards-api.greenhouse.io",
    "api.lever.co",
    "api.eu.lever.co",
}
GREENHOUSE_PUBLIC_HOSTS = {"job-boards.greenhouse.io", "boards.greenhouse.io"}
LEVER_PUBLIC_HOSTS = {"jobs.lever.co", "jobs.eu.lever.co"}


class UnsafeCaptureURL(ValueError):
    """Raised before any request to a disallowed capture destination."""


def host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def validate_automatic_capture_url(url: str) -> str:
    """Allow only reviewed HTTPS APIs; deny job boards and unknown hosts."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or not host:
        raise UnsafeCaptureURL("Safe capture requires a valid HTTPS URL.")
    if any(host_matches(host, domain) for domain in BLOCKED_JOB_BOARD_DOMAINS):
        raise UnsafeCaptureURL(
            f"Automatic access to {host} is blocked; use the manual capture queue."
        )
    if host not in APPROVED_PUBLIC_API_HOSTS:
        raise UnsafeCaptureURL(
            f"Automatic access to {host} is not approved by safe capture mode."
        )
    return url


def automatic_capture_plan(url: str) -> dict[str, str] | None:
    """Translate a recognized public ATS posting URL to its reviewed API."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https":
        return None
    if host in GREENHOUSE_PUBLIC_HOSTS and len(parts) >= 3 and parts[-2] == "jobs" and parts[-1].isdigit():
        board = parts[-3]
        return {
            "platform": "greenhouse",
            "account": board,
            "job_id": parts[-1],
            "api_url": f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{parts[-1]}",
        }
    if host in LEVER_PUBLIC_HOSTS and len(parts) >= 2:
        account, job_id = parts[0], parts[1]
        api_host = "api.eu.lever.co" if host == "jobs.eu.lever.co" else "api.lever.co"
        return {
            "platform": "lever",
            "account": account,
            "job_id": job_id,
            "api_url": f"https://{api_host}/v0/postings/{account}/{job_id}",
        }
    return None


def capture_capability(url: str) -> dict[str, str]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if any(host_matches(host, domain) for domain in BLOCKED_JOB_BOARD_DOMAINS):
        return {"mode": "manual_required", "reason": "Job-board automation is blocked for account safety."}
    if automatic_capture_plan(url):
        return {"mode": "automatic_available", "reason": "A reviewed public ATS API is available."}
    return {"mode": "manual_required", "reason": "This source is not on the reviewed automatic-capture allowlist."}
