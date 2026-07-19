#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator, FormatChecker

def load_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data

def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data

def records(data, keys):
    for key in keys:
        if isinstance(data.get(key), list):
            return [x for x in data[key] if isinstance(x, dict)]
    return []

def ids(items):
    return {x["id"] for x in items if isinstance(x.get("id"), str)}

def grouped_ids(data, key):
    out = set()
    root = data.get(key, {})
    if isinstance(root, dict):
        for group in root.values():
            if isinstance(group, list):
                out |= ids([x for x in group if isinstance(x, dict)])
    return out

def schema_errors(data, schema, label):
    out = []
    v = Draft202012Validator(schema, format_checker=FormatChecker())
    for e in v.iter_errors(data):
        loc = ".".join(map(str, e.path)) or "<root>"
        out.append(f"{label} {loc}: {e.message}")
    return out

def allowed_titles(role):
    out = set()
    for key in ("official_title", "title"):
        if isinstance(role.get(key), str):
            out.add(role[key])
    for key in ("approved_title_variants", "title_variants"):
        if isinstance(role.get(key), list):
            out |= {x for x in role[key] if isinstance(x, str)}
    return out

def role_date(role, kind):
    keys = ("start_date", "start", "date_start") if kind == "start" else ("end_date", "end", "date_end")
    for key in keys:
        if key in role:
            return role[key]
    if isinstance(role.get("dates"), dict):
        return role["dates"].get(kind)
    return None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("workspace", type=Path)
    p.add_argument("--profile-dir", type=Path, default=Path("profile"))
    p.add_argument("--resume-schema", type=Path,
        default=Path.home()/".hermes/skills/resume-planner/references/resume-plan-schema.json")
    p.add_argument("--manifest-schema", type=Path,
        default=Path.home()/".hermes/skills/resume-planner/references/application-manifest-schema.json")
    a = p.parse_args()

    try:
        manifest = load_json(a.workspace/"application_manifest.json")
        plan = load_json(a.workspace/"resume_plan.json")
        rs = load_json(a.resume_schema)
        ms = load_json(a.manifest_schema)
        career = load_yaml(a.profile_dir/"career.yaml")
        skills = load_yaml(a.profile_dir/"skills.yaml")
        tech = load_yaml(a.profile_dir/"technologies.yaml")
        evidence = load_yaml(a.profile_dir/"evidence.yaml")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = schema_errors(manifest, ms, "manifest") + schema_errors(plan, rs, "plan")

    roles = records(career, ("employment", "work_history", "roles"))
    role_map = {x["id"]: x for x in roles if isinstance(x.get("id"), str)}
    role_ids = set(role_map)
    project_ids = ids(records(career, ("projects",)))
    education_ids = ids(records(career, ("education",)))
    certification_ids = ids(records(career, ("training_and_certifications", "certifications")))
    skill_ids = grouped_ids(skills, "skills")
    tech_ids = grouped_ids(tech, "technologies")
    evidence_ids = ids(records(evidence, ("evidence", "items")))

    if manifest.get("application_id") != plan.get("application", {}).get("application_id"):
        errors.append("application_id mismatch")
    if manifest.get("application_slug") != plan.get("application", {}).get("application_slug"):
        errors.append("application_slug mismatch")
    if manifest.get("fit", {}).get("score") != plan.get("source", {}).get("fit_score"):
        errors.append("fit score mismatch")
    if manifest.get("fit", {}).get("recommendation") != plan.get("source", {}).get("recommendation"):
        errors.append("recommendation mismatch")

    orders = [x.get("order") for x in plan.get("section_plan", [])
              if isinstance(x, dict) and x.get("included")]
    if len(orders) != len(set(orders)):
        errors.append("duplicate included section order")

    bullet_ids = []
    for i, entry in enumerate(plan.get("experience_plan", [])):
        if not isinstance(entry, dict):
            continue
        rid = entry.get("role_id")
        if rid not in role_ids:
            errors.append(f"unknown role ID: {rid}")
            continue
        role = role_map[rid]
        if entry.get("display_title") not in allowed_titles(role):
            errors.append(f"unapproved display title for {rid}")
        if entry.get("start_date") != role_date(role, "start"):
            errors.append(f"start date mismatch for {rid}")
        if entry.get("end_date") != role_date(role, "end"):
            errors.append(f"end date mismatch for {rid}")
        for j, bullet in enumerate(entry.get("planned_bullets", [])):
            if not isinstance(bullet, dict):
                continue
            bid = bullet.get("bullet_id")
            if isinstance(bid, str):
                bullet_ids.append(bid)
            refs = bullet.get("evidence_ids", [])
            if not refs:
                errors.append(f"{rid} bullet {j} has no evidence")
            for ref in refs:
                if ref not in evidence_ids:
                    errors.append(f"unknown evidence ID {ref}")

    dupes = sorted({x for x in bullet_ids if bullet_ids.count(x) > 1})
    if dupes:
        errors.append("duplicate bullet IDs: " + ", ".join(dupes))

    for group in plan.get("skills_plan", []):
        if not isinstance(group, dict):
            continue
        for item in group.get("items", []):
            if not isinstance(item, dict):
                continue
            valid = skill_ids if item.get("record_type") == "skill" else tech_ids
            if item.get("record_id") not in valid:
                errors.append(f"unknown {item.get('record_type')} ID: {item.get('record_id')}")

    for item in plan.get("project_plan", []):
        if isinstance(item, dict) and item.get("project_id") not in project_ids:
            errors.append(f"unknown project ID: {item.get('project_id')}")

    for name, valid in (("education_plan", education_ids), ("certification_plan", certification_ids)):
        for item in plan.get(name, []):
            if isinstance(item, dict) and item.get("record_id") not in valid:
                errors.append(f"unknown {name} ID: {item.get('record_id')}")

    if not (a.workspace/"resume_plan.md").exists():
        errors.append("resume_plan.md is missing")

    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("Resume plan validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Workspace: {a.workspace}")
    print(f"Preserved fit: {manifest['fit']['score']}/100 ({manifest['fit']['recommendation']})")
    print(f"Format: {plan['resume_format']['length']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
