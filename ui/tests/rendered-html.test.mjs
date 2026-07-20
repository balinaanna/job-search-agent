import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the job-search workspace", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>Anna&#x27;s Job Search<\/title>/i);
  assert.match(html, /Good afternoon, Anna/);
  assert.match(html, /Evidence-Based|evidence-based/i);
  assert.match(html, /Nothing submits without you/);
  assert.match(html, /Durable/);
  assert.match(html, /Jobs workspace/);
  assert.match(html, /Search title, company, or location/);
  assert.match(html, /All fit decisions/);
  assert.match(html, /Awaiting analysis/);
  assert.match(html, /Search settings/);
  assert.match(html, /Job alert inbox/);
  assert.match(html, /LinkedIn/);
  assert.match(html, /Indeed/);
  assert.match(html, /Eluta/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
});

test("dashboard uses all exported workflow data and responsive styling", async () => {
  const [page, jobsView, css, data] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/JobsView.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../app/dashboard-data.json", import.meta.url), "utf8"),
  ]);
  assert.match(page, /dashboard-data\.json/);
  assert.match(page, /explicit approval/);
  assert.match(jobsView, /filtered\.slice\(0, visible\)/);
  assert.match(jobsView, /Show 10 more/);
  assert.match(css, /@media \(max-width:950px\)/);
  assert.match(css, /@media \(max-width:600px\)/);
  const parsed = JSON.parse(data);
  assert.ok(parsed.summary.discovered > 0);
  assert.ok(Array.isArray(parsed.awaitingAnalysis));
  assert.ok(Array.isArray(parsed.analyzedJobs));
});
