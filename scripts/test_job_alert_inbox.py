import tempfile
import unittest
from pathlib import Path

from job_alert_inbox import AlertInboxStore, anchor_metadata, company_like, normalize_posted_date, parse_alert, save_captured_posting
from normalize_job_lead import canonicalize_url


class JobAlertInboxTests(unittest.TestCase):
    def test_parses_and_canonicalizes_supported_alerts(self):
        linkedin = parse_alert("linkedin", '<a href="https://www.linkedin.com/jobs/view/12345/?tracking=x">Applied AI Engineer</a>')
        indeed = parse_alert("indeed", '<a href="https://ca.indeed.com/rc/clk?jk=abc123&from=alert">Backend AI Engineer</a>')
        eluta = parse_alert("eluta", '<a href="https://www.eluta.ca/spl/software-engineer-abc123">Software Engineer</a>')
        ziprecruiter = parse_alert("ziprecruiter", '<a href="https://www.ziprecruiter.com/c/Acme/Job/Software-Engineer/-in-Vancouver,BC?jid=abc123&lvk=x">Software Engineer</a>')
        self.assertEqual(linkedin[0]["posting_url"], "https://www.linkedin.com/jobs/view/12345")
        self.assertEqual(indeed[0]["posting_url"], "https://ca.indeed.com/viewjob?jk=abc123")
        self.assertEqual(eluta[0]["title"], "Software Engineer")
        self.assertEqual(ziprecruiter[0]["posting_url"], "https://www.ziprecruiter.com/c/Acme/Job/Software-Engineer/-in-Vancouver,BC?jid=abc123")

    def test_preserves_navigable_ziprecruiter_v2_url_while_deduplicating_by_listing_key(self):
        # ZipRecruiter's /jobs/v2/<blob> pages require the original tracking-bearing blob to
        # load (the stable listing_key alone 404s), so posting_url must stay untouched even
        # though match_id/bid_tracking_data change every time the same job is revisited.
        # Deduplication instead relies on normalize_job_lead.canonicalize_url reducing the
        # blob to its stable listing_key at the lead-identity stage.
        first_visit_url = "https://www.ziprecruiter.com/jobs/v2/eyJsaXN0aW5nX2tleSI6IjEyMyIsIm1hdGNoX2lkIjoiYSJ9?tsid=1"
        second_visit_url = "https://www.ziprecruiter.com/jobs/v2/eyJsaXN0aW5nX2tleSI6IjEyMyIsIm1hdGNoX2lkIjoiYiJ9?tsid=2"
        first_visit = parse_alert("ziprecruiter", f'<a href="{first_visit_url}">GenAI Designer</a>')
        second_visit = parse_alert("ziprecruiter", f'<a href="{second_visit_url}">GenAI Designer</a>')
        self.assertEqual(first_visit[0]["posting_url"], first_visit_url)
        self.assertEqual(second_visit[0]["posting_url"], second_visit_url)
        self.assertEqual(canonicalize_url(first_visit[0]["posting_url"]), "https://www.ziprecruiter.com/jobs/v2/listing/123")
        self.assertEqual(canonicalize_url(first_visit[0]["posting_url"]), canonicalize_url(second_visit[0]["posting_url"]))

    def test_recognizes_ziprecruiter_v2_blob_requiring_base64_padding(self):
        # The v2 blob's length isn't always a multiple of 4, so the URL literally
        # contains a trailing "=" padding character. The regex matching /jobs/v2/<blob>
        # must accept "=" or it silently fails to recognize the URL as ZipRecruiter at all.
        padded_url = (
            "https://www.ziprecruiter.com/jobs/v2/"
            "eyJsaXN0aW5nX2tleSI6IndMb3JER25RaGZvenNacDhVUTZLZUEiLCJtYXRjaF9pZCI6ImEifQ=="
            "?tsid=100000404"
        )
        self.assertTrue(padded_url.split("/jobs/v2/")[1].split("?")[0].endswith("="))
        visit = parse_alert("ziprecruiter", f'<a href="{padded_url}">AI Implementation Consultant</a>')
        self.assertEqual(visit[0]["posting_url"], padded_url)
        self.assertEqual(
            canonicalize_url(visit[0]["posting_url"]),
            "https://www.ziprecruiter.com/jobs/v2/listing/wLorDGnQhfozsZp8UQ6KeA",
        )

    def test_canonicalizes_linkedin_email_and_browser_urls_identically(self):
        email_job = parse_alert("linkedin", '<a href="https://www.linkedin.com/comm/jobs/view/software-engineer-12345?tracking=x">Software Engineer</a>')
        browser_job = parse_alert("linkedin", '<a href="https://www.linkedin.com/jobs/view/12345/">Software Engineer</a>')
        self.assertEqual(email_job[0]["posting_url"], "https://www.linkedin.com/jobs/view/12345")
        self.assertEqual(email_job[0]["posting_url"], browser_job[0]["posting_url"])

    def test_keeps_direct_reviewed_ats_links_from_alerts(self):
        jobs = parse_alert("linkedin", '<a href="https://job-boards.greenhouse.io/acme/jobs/12345?source=email">Platform Engineer</a>')
        self.assertEqual(jobs[0]["source"], "greenhouse")
        self.assertEqual(jobs[0]["posting_url"], "https://job-boards.greenhouse.io/acme/jobs/12345")

    def test_extracts_company_and_location_from_alert_content(self):
        content = '<div><a href="https://www.linkedin.com/jobs/view/12345">AI Engineer</a></div><div>Example AI Inc.</div><div>Vancouver, BC (Hybrid)</div><div>Build applied AI products.</div>'
        job = parse_alert("linkedin", content)[0]
        self.assertEqual(job["company"], "Example AI Inc.")
        self.assertEqual(job["location"], "Vancouver, BC (Hybrid)")
        self.assertIn("Build applied AI", job["email_excerpt"])

    def test_extracts_title_and_company_from_at_pattern(self):
        value = anchor_metadata("Backend Engineer at Acme", [])
        self.assertEqual(value["title"], "Backend Engineer")
        self.assertEqual(value["company"], "Acme")

    def test_rejects_salary_and_interface_labels_as_companies(self):
        self.assertFalse(company_like("$85,000–$95,000 a year"))
        self.assertFalse(company_like("Easily apply"))
        self.assertFalse(company_like("3 connections"))
        self.assertTrue(company_like("Example AI Inc."))

    def test_splits_combined_company_and_location_line(self):
        value = anchor_metadata("AI Engineer", ["AI Engineer", "Example AI Inc. - Vancouver, BC"])
        self.assertEqual(value["company"], "Example AI Inc.")
        self.assertEqual(value["location"], "Vancouver, BC")

    def test_deduplicates_imported_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlertInboxStore(Path(directory) / "jobs.db")
            content = '<a href="https://www.linkedin.com/jobs/view/12345">AI Engineer</a>'
            self.assertEqual(store.import_alert("linkedin", content)["added"], 1)
            result = store.import_alert("linkedin", content)
            self.assertEqual(result["added"], 0); self.assertEqual(result["duplicates"], 1)
            store.close()

    def test_duplicate_import_backfills_missing_email_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlertInboxStore(Path(directory) / "jobs.db")
            url = "https://www.linkedin.com/jobs/view/12345"
            store.connection.execute("INSERT INTO alert_jobs(id,source,title,posting_url,status,received_at) VALUES ('old','linkedin','AI Engineer',?,'needs_capture','2026-07-21T00:00:00Z')", (url,))
            store.connection.commit()
            content = f'<div><a href="{url}">AI Engineer</a></div><div>Example AI</div><div>Vancouver, BC</div>'
            result = store.import_alert("linkedin", content)
            self.assertEqual(result["added"], 0)
            job = store.get("old")
            self.assertEqual(job["company"], "Example AI")
            self.assertEqual(job["location"], "Vancouver, BC")
            store.close()

    def test_store_consolidates_legacy_url_aliases_without_losing_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.db"
            store = AlertInboxStore(path)
            store.connection.execute("INSERT INTO alert_jobs(id,source,title,posting_url,status,received_at,company) VALUES ('legacy','linkedin','AI Engineer','https://www.linkedin.com/comm/jobs/view/ai-engineer-12345?tracking=x','needs_capture','2026-07-20T00:00:00Z','Example AI')")
            store.connection.execute("INSERT INTO alert_jobs(id,source,title,posting_url,status,received_at,lead_id,location) VALUES ('current','linkedin','AI Engineer','https://www.linkedin.com/jobs/view/12345','captured','2026-07-21T00:00:00Z','lead-123','Vancouver, BC')")
            store.connection.commit(); store.close()

            reopened = AlertInboxStore(path)
            jobs = reopened.list()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["posting_url"], "https://www.linkedin.com/jobs/view/12345")
            self.assertEqual(jobs[0]["status"], "captured")
            self.assertEqual(jobs[0]["lead_id"], "lead-123")
            self.assertEqual(jobs[0]["company"], "Example AI")
            self.assertEqual(jobs[0]["location"], "Vancouver, BC")
            reopened.close()

    def test_store_splits_legacy_company_location_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.db"
            store = AlertInboxStore(path)
            store.connection.execute("INSERT INTO alert_jobs(id,source,title,posting_url,status,received_at,location) VALUES ('job','linkedin','AI Engineer','https://www.linkedin.com/jobs/view/12345','needs_capture','2026-07-21T00:00:00Z','Royal Bank of Canada - Vancouver, BC')")
            store.connection.commit(); store.close()

            reopened = AlertInboxStore(path)
            job = reopened.get("job")
            self.assertEqual(job["company"], "Royal Bank of Canada")
            self.assertEqual(job["location"], "Vancouver, BC")
            reopened.close()

    def test_links_captured_alert_to_generated_lead(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlertInboxStore(Path(directory) / "jobs.db")
            content = '<a href="https://www.linkedin.com/jobs/view/12345">AI Engineer</a>'
            store.import_alert("linkedin", content); store.mark_captured("linkedin", "https://www.linkedin.com/jobs/view/12345", "lead-123")
            job = store.list()[0]; self.assertEqual(job["status"], "captured"); self.assertEqual(job["lead_id"], "lead-123"); store.close()

    def test_links_legacy_linkedin_comm_alert_to_browser_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlertInboxStore(Path(directory) / "jobs.db")
            store.connection.execute("INSERT INTO alert_jobs(id,source,title,posting_url,status,received_at,lead_id) VALUES (?, ?, ?, ?, ?, ?, ?)", ("legacy", "linkedin", "AI Engineer", "https://www.linkedin.com/comm/jobs/view/12345", "needs_capture", "2026-07-21T00:00:00+00:00", None))
            store.connection.commit()
            store.mark_captured("linkedin", "https://www.linkedin.com/jobs/view/12345", "lead-123")
            job = store.list()[0]; self.assertEqual(job["status"], "captured"); self.assertEqual(job["lead_id"], "lead-123"); store.close()

    def test_rejects_empty_or_unknown_alerts(self):
        with self.assertRaisesRegex(ValueError, "Source"):
            parse_alert("other", "email")
        with self.assertRaisesRegex(ValueError, "Paste"):
            parse_alert("indeed", "")

    def test_saves_complete_user_captured_posting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_captured_posting({"source": "linkedin", "company": "Example AI", "role": "AI Engineer", "posting_url": "https://www.linkedin.com/jobs/view/12345?tracking=x", "description_text": "Build trustworthy AI products. " * 20, "location_raw": "Canada (Remote)"}, Path(directory))
            self.assertTrue(path.exists())
            self.assertIn('"platform": "linkedin"', path.read_text())

    def test_normalizes_schema_org_posted_timestamp_to_date(self):
        self.assertEqual(normalize_posted_date("2026-07-14T01:29:13.931Z"), "2026-07-14")
        self.assertEqual(normalize_posted_date("2026-07-14T18:30:00-07:00"), "2026-07-14")
        self.assertEqual(normalize_posted_date("2026-07-14"), "2026-07-14")
        self.assertIsNone(normalize_posted_date("posted recently"))

    def test_rejects_incomplete_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "complete job description"):
                save_captured_posting({"source": "eluta", "company": "Example", "role": "Engineer", "posting_url": "https://www.eluta.ca/spl/job-123", "description_text": "Too short"}, Path(directory))

    def test_only_safe_ats_links_enter_background_capture_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlertInboxStore(Path(directory) / "jobs.db")
            store.connection.execute("INSERT INTO alert_jobs(id,source,title,posting_url,status,received_at) VALUES ('safe','greenhouse','Engineer','https://job-boards.greenhouse.io/acme/jobs/12345','needs_capture','2026-07-21T00:00:00Z')")
            store.connection.execute("INSERT INTO alert_jobs(id,source,title,posting_url,status,received_at) VALUES ('blocked','linkedin','Engineer','https://www.linkedin.com/jobs/view/1','needs_capture','2026-07-21T00:00:00Z')")
            store.connection.commit()
            self.assertEqual(store.queue_safe_captures(), ["safe"])
            self.assertEqual(store.claim_safe_capture()["id"], "safe")
            self.assertIsNone(store.claim_safe_capture())
            self.assertEqual(store.get("blocked")["status"], "needs_capture")
            store.close()


if __name__ == "__main__": unittest.main()
