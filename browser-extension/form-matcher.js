(function (root) {
  function normalize(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  function fieldLabel(field) {
    const doc = field.ownerDocument || document;
    const explicit = field.id ? doc.querySelector(`label[for="${CSS.escape(field.id)}"]`) : null;
    const wrapping = field.closest("label");
    const fieldset = field.closest("fieldset");
    const legend = fieldset?.querySelector("legend")?.innerText || "";
    const group = field.closest('[role="radiogroup"], [role="group"]');
    const groupLabel = group?.getAttribute("aria-label") || (group?.getAttribute("aria-labelledby") ? doc.getElementById(group.getAttribute("aria-labelledby"))?.innerText : "") || "";
    const own = optionLabel(field);
    return normalize(`${legend || groupLabel} ${own}`);
  }

  function optionLabel(field) {
    const doc = field.ownerDocument || document;
    const explicit = field.id ? doc.querySelector(`label[for="${CSS.escape(field.id)}"]`) : null;
    const wrapping = field.closest("label");
    return normalize(explicit?.innerText || wrapping?.innerText || field.getAttribute("aria-label") || field.getAttribute("placeholder") || field.value || field.getAttribute("name") || "");
  }

  function similarity(question, label) {
    const left = normalize(question); const right = normalize(label);
    if (!left || !right) return 0;
    if (left.includes(right) || right.includes(left)) return 1;
    const canonical = (word) => ({ authorized: "authoriz", authorization: "authoriz", authorize: "authoriz", expectations: "expect", expected: "expect" }[word] || word);
    const a = new Set(left.split(" ").filter((word) => word.length > 2).map(canonical));
    const b = new Set(right.split(" ").filter((word) => word.length > 2).map(canonical));
    const overlap = [...a].filter((word) => b.has(word)).length;
    return overlap / Math.max(a.size, b.size, 1);
  }

  function eligibleFields(doc) {
    return [...doc.querySelectorAll("textarea, select, input")].filter((field) => {
      const type = (field.getAttribute("type") || "text").toLowerCase();
      return !field.disabled && !field.readOnly && !["hidden", "password", "file", "submit", "button", "image", "reset"].includes(type);
    });
  }

  function chooseOption(options, answer) {
    let best = null;
    for (const option of options) {
      const label = option.label ?? option.textContent ?? option.value ?? "";
      const score = similarity(answer, label);
      if (!best || score > best.score) best = { option, score };
    }
    return best && best.score >= 0.5 ? best.option : null;
  }

  function booleanIntent(value) {
    const normalized = normalize(value);
    if (/^(yes|true|agree|agreed|confirmed|i agree|i confirm)$/.test(normalized)) return true;
    if (/^(no|false|disagree|decline|not applicable|n a)$/.test(normalized)) return false;
    return null;
  }

  function matchAnswers(answers, fields) {
    const used = new Set(); const matches = []; const unmatched = [];
    for (const answer of answers) {
      let best = null;
      for (const field of fields) {
        if (used.has(field)) continue;
        let score = similarity(answer.question, fieldLabel(field));
        if (["radio", "checkbox"].includes((field.type || "").toLowerCase())) {
          score += similarity(answer.answer, optionLabel(field)) * 0.35;
        }
        if (!best || score > best.score) best = { field, score, label: fieldLabel(field) };
      }
      if (best && best.score >= 0.34) {
        used.add(best.field);
        const type = (best.field.type || "").toLowerCase();
        if (["radio", "checkbox"].includes(type) && best.field.name) {
          fields.filter((field) => (field.type || "").toLowerCase() === type && field.name === best.field.name).forEach((field) => used.add(field));
        }
        matches.push({ answer, ...best });
      }
      else unmatched.push({ question_id: answer.question_id, question: answer.question });
    }
    return { matches, unmatched, unusedFields: fields.filter((field) => !used.has(field)).map((field) => fieldLabel(field)).filter(Boolean) };
  }

  root.JobAgentMatcher = { normalize, similarity, matchAnswers, eligibleFields, fieldLabel, optionLabel, chooseOption, booleanIntent };
})(globalThis);
