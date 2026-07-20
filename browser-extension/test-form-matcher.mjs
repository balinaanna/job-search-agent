import assert from "node:assert/strict";
import test from "node:test";
import vm from "node:vm";
import fs from "node:fs";

const context = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(new URL("./form-matcher.js", import.meta.url), "utf8"), context);
const { normalize, similarity, chooseOption, booleanIntent, matchAnswers, documentKind } = context.globalThis.JobAgentMatcher;

function groupedField(type, name, legend, option) {
  const fieldset = { querySelector: (selector) => selector === "legend" ? { innerText: legend } : null };
  return {
    id: "", type, name, value: option, ownerDocument: {},
    closest: (selector) => selector === "label" ? { innerText: option } : selector === "fieldset" ? fieldset : null,
    getAttribute: (key) => ({ type, name }[key] || null),
  };
}

test("normalizes application labels", () => assert.equal(normalize("Work authorization (Canada)?"), "work authorization canada"));
test("matches equivalent question labels", () => assert.ok(similarity("Are you authorized to work in Canada?", "Work authorization in Canada") >= 0.5));
test("rejects unrelated fields", () => assert.equal(similarity("Salary expectations", "LinkedIn profile"), 0));
test("selects equivalent dropdown and radio wording", () => {
  const options = [{ label: "No" }, { label: "Yes, I am authorized" }];
  assert.equal(chooseOption(options, "Yes, authorized to work"), options[1]);
});
test("recognizes explicit checkbox intent only", () => {
  assert.equal(booleanIntent("I agree"), true);
  assert.equal(booleanIntent("No"), false);
  assert.equal(booleanIntent("Please review this manually"), null);
});
test("classifies only clearly labelled approved document fields", () => {
  assert.equal(documentKind("Upload your resume / CV"), "resume");
  assert.equal(documentKind("Cover letter PDF"), "cover_letter");
  assert.equal(documentKind("Supporting document"), null);
});
test("matches a common ATS yes-no radio group as one reviewed field", () => {
  const no = groupedField("radio", "sponsorship", "Will you require sponsorship?", "No");
  const yes = groupedField("radio", "sponsorship", "Will you require sponsorship?", "Yes");
  const result = matchAnswers([{ question_id: "q1", question: "Will you require sponsorship?", answer: "Yes" }], [no, yes]);
  assert.equal(result.matches.length, 1);
  assert.equal(result.matches[0].field, yes);
  assert.equal(result.unusedFields.length, 0);
});

test("content adapter contains no automated click action", () => {
  const source = fs.readFileSync(new URL("./content-script.js", import.meta.url), "utf8");
  assert.equal(/\.click\s*\(/.test(source), false);
  assert.match(source, /never_submit/);
  assert.match(source, /data-job-agent-extension/);
  assert.match(source, /job-agent-get-session/);
});

test("background session storage is tab scoped", () => {
  const source = fs.readFileSync(new URL("./background.js", import.meta.url), "utf8");
  assert.match(source, /sender\.tab\?\.id/);
  assert.match(source, /chrome\.storage\.session/);
  assert.match(source, /job-agent-clear-session/);
});

test("capture adapter supports only the approved alert sources", async () => {
  const capture = await import("./job-capture.js");
  assert.equal(capture.default.sourceForUrl("https://www.linkedin.com/jobs/view/123"), "linkedin");
  assert.equal(capture.default.sourceForUrl("https://ca.indeed.com/viewjob?jk=123"), "indeed");
  assert.equal(capture.default.sourceForUrl("https://www.eluta.ca/spl/job-123"), "eluta");
  assert.equal(capture.default.sourceForUrl("https://example.com/jobs/123"), null);
});
