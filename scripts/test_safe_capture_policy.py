import unittest

from safe_capture_policy import UnsafeCaptureURL, automatic_capture_plan, capture_capability, validate_automatic_capture_url


class SafeCapturePolicyTests(unittest.TestCase):
    def test_allows_reviewed_public_ats_apis(self) -> None:
        for url in (
            "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true",
            "https://api.lever.co/v0/postings/example?mode=json",
            "https://api.eu.lever.co/v0/postings/example?mode=json",
        ):
            self.assertEqual(validate_automatic_capture_url(url), url)

    def test_blocks_job_boards_and_subdomains(self) -> None:
        for url in (
            "https://www.linkedin.com/jobs/view/1",
            "https://ca.indeed.com/viewjob?jk=1",
            "https://www.eluta.ca/spl/job-1",
            "https://www.ziprecruiter.com/jobs/acme-1",
        ):
            with self.assertRaisesRegex(UnsafeCaptureURL, "manual capture queue"):
                validate_automatic_capture_url(url)

    def test_denies_unknown_hosts_and_insecure_urls(self) -> None:
        with self.assertRaisesRegex(UnsafeCaptureURL, "not approved"):
            validate_automatic_capture_url("https://careers.example.com/jobs/1")
        with self.assertRaisesRegex(UnsafeCaptureURL, "HTTPS"):
            validate_automatic_capture_url("http://api.lever.co/v0/postings/example")

    def test_builds_reviewed_api_plans_for_public_ats_links(self) -> None:
        greenhouse = automatic_capture_plan("https://job-boards.greenhouse.io/acme/jobs/12345?source=alert")
        lever = automatic_capture_plan("https://jobs.lever.co/acme/abc-123")
        self.assertEqual(greenhouse["api_url"], "https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345")
        self.assertEqual(lever["api_url"], "https://api.lever.co/v0/postings/acme/abc-123")
        self.assertEqual(capture_capability("https://www.linkedin.com/jobs/view/1")["mode"], "manual_required")
        self.assertEqual(capture_capability("https://www.ziprecruiter.com/jobs/acme-1")["mode"], "manual_required")
        self.assertEqual(capture_capability("https://jobs.lever.co/acme/abc-123")["mode"], "automatic_available")
