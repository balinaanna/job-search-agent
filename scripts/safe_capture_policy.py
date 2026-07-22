from __future__ import annotations

from urllib.parse import urlsplit


BLOCKED_JOB_BOARD_DOMAINS = ("linkedin.com", "indeed.com", "eluta.ca")
APPROVED_PUBLIC_API_HOSTS = {
    "boards-api.greenhouse.io",
    "api.lever.co",
    "api.eu.lever.co",
}


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
