import assert from "node:assert/strict";
import test from "node:test";
import vm from "node:vm";
import fs from "node:fs";

const context = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(new URL("./form-matcher.js", import.meta.url), "utf8"), context);
const { normalize, similarity } = context.globalThis.JobAgentMatcher;

test("normalizes application labels", () => assert.equal(normalize("Work authorization (Canada)?"), "work authorization canada"));
test("matches equivalent question labels", () => assert.ok(similarity("Are you authorized to work in Canada?", "Work authorization in Canada") >= 0.5));
test("rejects unrelated fields", () => assert.equal(similarity("Salary expectations", "LinkedIn profile"), 0));

test("content adapter contains no automated click action", () => {
  const source = fs.readFileSync(new URL("./content-script.js", import.meta.url), "utf8");
  assert.equal(/\.click\s*\(/.test(source), false);
  assert.match(source, /never_submit/);
});
