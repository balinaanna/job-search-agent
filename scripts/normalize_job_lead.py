#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from validate_job_lead import (
    JobLeadValidationError,
    load_json,
    validate_business_rules,
    validate_schema,
)


DEFAULT_SCHEMA_PATH = Path(
    "hermes-skills/job-discovery/references/job-lead-schema.json"
)
DEFAULT_OUTPUT_DIRECTORY = Path("data/job-leads")
DEFAULT_CRITERIA_PATH = Path("strategy/job_search_criteria.json")


TRACKING_QUERY_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
    "src",
    "trk",
    "trackingid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


TECHNICAL_SKILL_PATTERNS: dict[str, tuple[str, ...]] = {
    "Python": (
        r"\bpython\b",
    ),
    "JavaScript": (
        r"\bjavascript\b",
        r"\btypescript\b",
        r"\bnode(?:\.js)?\b",
    ),
    "SQL": (
        r"\bsql\b",
        r"\bpostgres(?:ql)?\b",
        r"\bmysql\b",
    ),
    "REST APIs": (
        r"\brest(?:ful)?\s+api",
        r"\bapi development\b",
        r"\bapi integration\b",
    ),
    "Docker": (
        r"\bdocker\b",
        r"\bcontaineri[sz]ation\b",
    ),
    "Kubernetes": (
        r"\bkubernetes\b",
        r"\bk8s\b",
    ),
    "AWS": (
        r"\baws\b",
        r"\bamazon web services\b",
    ),
    "Azure": (
        r"\bazure\b",
    ),
    "Google Cloud": (
        r"\bgcp\b",
        r"\bgoogle cloud\b",
    ),
    "LLM application development": (
        r"\blarge language model",
        r"\bllm(?:s)?\b",
        r"\bgenerative ai\b",
        r"\bgenai\b",
    ),
    "AI agents": (
        r"\bai agent",
        r"\bagent workflow",
        r"\bagentic\b",
        r"\bmulti-agent\b",
    ),
    "Machine learning": (
        r"\bmachine learning\b",
        r"\bdeep learning\b",
        r"\bml model",
    ),
    "React": (
        r"\breact(?:\.js)?\b",
    ),
    "Git": (
        r"\bgit\b",
        r"\bgithub\b",
        r"\bgitlab\b",
    ),
}


DOMAIN_SKILL_PATTERNS: dict[str, tuple[str, ...]] = {
    "AI-enabled product development": (
        r"\bai[- ]enabled product",
        r"\bai product",
        r"\bllm-powered",
        r"\bgenerative ai product",
    ),
    "Workflow automation": (
        r"\bworkflow automation\b",
        r"\bautomated workflow",
        r"\bprocess automation\b",
    ),
    "Data analytics": (
        r"\bdata analytics\b",
        r"\banalytics\b",
        r"\bdata visualization\b",
    ),
    "Backend systems": (
        r"\bbackend\b",
        r"\bserver-side\b",
        r"\bdistributed system",
    ),
    "Customer implementation": (
        r"\bimplementation\b",
        r"\btechnical onboarding\b",
        r"\bcustomer integration\b",
    ),
}


def non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JobLeadValidationError(
            f"{field_name} must be a non-empty string."
        )

    return value.strip()


def optional_string(value: Any) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        return str(value)

    stripped = value.strip()
    return stripped or None


def normalize_spaces(value: str) -> str:
    return " ".join(value.split())


def normalize_identity(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^\w\s+#.-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def slugify(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")

    return value or "job"


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True,
        )
        if key.casefold() not in TRACKING_QUERY_PARAMETERS
        and not key.casefold().startswith("utm_")
    ]

    normalized_path = parts.path.rstrip("/") or "/"

    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            normalized_path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def description_hash(description: str) -> str:
    normalized = normalize_spaces(description)
    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def build_lead_id(
    company: str,
    role: str,
    canonical_url: str,
    external_job_id: str | None,
) -> str:
    identity_source = external_job_id or canonical_url

    suffix = hashlib.sha256(
        identity_source.encode("utf-8")
    ).hexdigest()[:10]

    company_slug = slugify(company)[:35]
    role_slug = slugify(role)[:55]

    return f"{company_slug}-{role_slug}-{suffix}"


def infer_platform(
    supplied_platform: str | None,
    posting_url: str,
) -> str:
    valid_platforms = {
        "linkedin",
        "indeed",
        "greenhouse",
        "lever",
        "ashby",
        "workday",
        "company_careers",
        "government_board",
        "recruiter",
        "referral",
        "other",
    }

    if supplied_platform:
        normalized = supplied_platform.strip().casefold()

        if normalized in valid_platforms:
            return normalized

    host = urlsplit(posting_url).netloc.casefold()

    if "linkedin." in host:
        return "linkedin"

    if "indeed." in host:
        return "indeed"

    if "greenhouse.io" in host:
        return "greenhouse"

    if "lever.co" in host:
        return "lever"

    if "ashbyhq.com" in host:
        return "ashby"

    if "myworkdayjobs.com" in host or "workday.com" in host:
        return "workday"

    return "company_careers"


def infer_seniority(role: str, description: str) -> str:
    text = f"{role} {description[:1000]}".casefold()

    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "executive",
            (
                r"\bchief\b",
                r"\bvice president\b",
                r"\bvp\b",
            ),
        ),
        (
            "director",
            (
                r"\bdirector\b",
                r"\bhead of\b",
            ),
        ),
        (
            "manager",
            (
                r"\bengineering manager\b",
                r"\bdevelopment manager\b",
                r"\btechnical manager\b",
            ),
        ),
        (
            "principal",
            (
                r"\bprincipal\b",
            ),
        ),
        (
            "staff",
            (
                r"\bstaff\b",
            ),
        ),
        (
            "lead",
            (
                r"\blead\b",
            ),
        ),
        (
            "senior",
            (
                r"\bsenior\b",
                r"\bsr\.?\b",
            ),
        ),
        (
            "junior",
            (
                r"\bjunior\b",
                r"\bjr\.?\b",
            ),
        ),
        (
            "intern",
            (
                r"\bintern(?:ship)?\b",
                r"\bco-op\b",
            ),
        ),
        (
            "entry",
            (
                r"\bentry[- ]level\b",
                r"\bnew grad\b",
                r"\bgraduate engineer\b",
            ),
        ),
        (
            "intermediate",
            (
                r"\bintermediate\b",
                r"\bmid[- ]level\b",
            ),
        ),
    )

    for seniority, patterns in rules:
        if any(re.search(pattern, text) for pattern in patterns):
            return seniority

    return "unspecified"


def infer_primary_function(role: str, description: str) -> str:
    title = role.casefold()
    text = f"{role} {description[:3000]}".casefold()

    title_rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "ai_engineering",
            (
                "ai engineer",
                "artificial intelligence engineer",
                "generative ai engineer",
                "genai engineer",
                "llm engineer",
                "ai application engineer",
                "ai agent engineer",
                "applied ai engineer",
            ),
        ),
        (
            "machine_learning",
            (
                "machine learning engineer",
                "ml engineer",
                "machine learning scientist",
            ),
        ),
        (
            "analytics_engineering",
            (
                "analytics engineer",
            ),
        ),
        (
            "data_engineering",
            (
                "data engineer",
            ),
        ),
        (
            "data_analytics",
            (
                "data analyst",
                "business intelligence analyst",
                "bi analyst",
                "data solutions analyst",
            ),
        ),
        (
            "business_analysis",
            (
                "business analyst",
                "business systems analyst",
                "systems analyst",
            ),
        ),
        (
            "solutions_engineering",
            (
                "solutions engineer",
                "solution engineer",
                "sales engineer",
            ),
        ),
        (
            "implementation",
            (
                "implementation engineer",
                "implementation specialist",
                "implementation consultant",
            ),
        ),
        (
            "customer_success",
            (
                "customer success",
                "client success",
            ),
        ),
        (
            "support",
            (
                "support engineer",
                "technical support",
                "support specialist",
            ),
        ),
        (
            "sales",
            (
                "account executive",
                "sales development",
                "business development representative",
            ),
        ),
        (
            "operations",
            (
                "operations coordinator",
                "operations specialist",
                "operations manager",
            ),
        ),
        (
            "administration",
            (
                "administrator",
                "administrative assistant",
                "executive assistant",
            ),
        ),
        (
            "product",
            (
                "product engineer",
                "product manager",
                "technical product",
            ),
        ),
        (
            "software_engineering",
            (
                "software engineer",
                "software developer",
                "backend engineer",
                "full-stack engineer",
                "full stack engineer",
                "application developer",
                "platform engineer",
            ),
        ),
    )

    for function, phrases in title_rules:
        if any(phrase in title for phrase in phrases):
            return function

    if (
        re.search(r"\bllm(?:s)?\b", text)
        or "generative ai" in text
        or "ai agent" in text
    ) and (
        "engineer" in title
        or "developer" in title
        or "architect" in title
    ):
        return "ai_engineering"

    return "other"


def infer_workplace_type(raw_value: str | None, description: str) -> str:
    text = f"{raw_value or ''} {description}".casefold()

    if "hybrid" in text:
        return "hybrid"

    if "remote" in text or "work from home" in text:
        return "remote"

    if (
        "on-site" in text
        or "onsite" in text
        or "in office" in text
    ):
        return "on_site"

    if "flexible" in text:
        return "flexible"

    return "unspecified"


def infer_employment_type(
    raw_value: str | None,
    description: str,
) -> str:
    text = f"{raw_value or ''} {description[:2000]}".casefold()

    if "internship" in text or "co-op" in text:
        return "internship"

    if "volunteer" in text or "unpaid" in text:
        return "volunteer"

    if "part-time" in text or "part time" in text:
        return "part_time"

    if (
        "temporary full-time" in text
        or "temporary full time" in text
    ):
        return "temporary_full_time"

    if (
        "fixed-term" in text
        or "fixed term" in text
        or "full-time contract" in text
        or "full time contract" in text
    ):
        return "full_time_contract"

    if "independent contractor" in text:
        return "contractor"

    if (
        "full-time" in text
        or "full time" in text
        or "permanent" in text
    ):
        return "full_time_permanent"

    if "contract" in text:
        return "contractor"

    return "unspecified"


def infer_location(
    location_raw: str | None,
    workplace_type: str,
    description: str,
) -> dict[str, Any]:
    raw = location_raw or "Unspecified"
    text = f"{raw} {description}".casefold()
    raw_text = raw.casefold()

    country: str | None = None
    region: str | None = None
    city: str | None = None

    explicit_foreign_countries = {
        "united states": "United States",
        "usa": "United States",
        "germany": "Germany",
        "ireland": "Ireland",
        "spain": "Spain",
        "united kingdom": "United Kingdom",
        "uk": "United Kingdom",
        "colombia": "Colombia",
        "israel": "Israel",
    }
    if "canada" in raw_text:
        country = "Canada"
    else:
        for signal, country_name in explicit_foreign_countries.items():
            if re.search(rf"\b{re.escape(signal)}\b", raw_text):
                country = country_name
                break

    if country is None and (
        "canada" in text or re.search(r"\bcanadian\b", text)
    ):
        country = "Canada"

    if (
        "british columbia" in text
        or re.search(r"\bbc\b", raw.casefold())
    ):
        region = "British Columbia"
        country = country or "Canada"

    known_cities = (
        "Richmond",
        "Vancouver",
        "Burnaby",
        "Surrey",
        "New Westminster",
        "Coquitlam",
        "Victoria",
        "Toronto",
        "Calgary",
        "Edmonton",
        "Ottawa",
        "Montreal",
    )

    for known_city in known_cities:
        if known_city.casefold() in text:
            city = known_city
            break

    canadian_city_regions = {
        "Richmond": "British Columbia",
        "Vancouver": "British Columbia",
        "Burnaby": "British Columbia",
        "Surrey": "British Columbia",
        "New Westminster": "British Columbia",
        "Coquitlam": "British Columbia",
        "Victoria": "British Columbia",
        "Toronto": "Ontario",
        "Ottawa": "Ontario",
        "Calgary": "Alberta",
        "Edmonton": "Alberta",
        "Montreal": "Quebec",
    }
    if city in canadian_city_regions:
        country = "Canada"
        region = region or canadian_city_regions[city]

    can_hire_in_canada: bool | None = None

    positive_canada_patterns = (
        "remote across canada",
        "remote in canada",
        "canada remote",
        "anywhere in canada",
        "eligible to work in canada",
        "based in canada",
    )

    negative_canada_patterns = (
        "united states only",
        "us only",
        "must reside in the united states",
        "cannot hire in canada",
    )

    if country is not None and country != "Canada":
        can_hire_in_canada = False
    elif country == "Canada":
        can_hire_in_canada = True
    elif any(pattern in text for pattern in positive_canada_patterns):
        can_hire_in_canada = True
    elif any(pattern in text for pattern in negative_canada_patterns):
        can_hire_in_canada = False

    relocation_required: bool | None = None

    if "relocation required" in text or "must relocate" in text:
        relocation_required = True
    elif workplace_type == "remote":
        relocation_required = False

    travel_percentage = extract_percentage_near_term(
        description,
        terms=("travel",),
    )

    travel_required: bool | None = None

    if travel_percentage is not None:
        travel_required = travel_percentage > 0
    elif "travel required" in text:
        travel_required = True
    elif "no travel" in text:
        travel_required = False

    return {
        "raw": raw,
        "country": country,
        "region": region,
        "city": city,
        "workplace_type": workplace_type,
        "can_hire_in_canada": can_hire_in_canada,
        "relocation_required": relocation_required,
        "travel_required": travel_required,
        "travel_percentage": travel_percentage,
    }


def extract_percentage_near_term(
    text: str,
    terms: tuple[str, ...],
) -> int | None:
    lowered = text.casefold()

    for term in terms:
        patterns = (
            rf"{re.escape(term)}[^.\n]{{0,50}}?(\d{{1,3}})\s*%",
            rf"(\d{{1,3}})\s*%[^.\n]{{0,50}}?{re.escape(term)}",
        )

        for pattern in patterns:
            match = re.search(pattern, lowered)

            if match:
                value = int(match.group(1))

                if 0 <= value <= 100:
                    return value

    return None


def extract_years_experience(
    description: str,
) -> tuple[float | None, float | None]:
    text = description.casefold()

    range_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*"
        r"(\d+(?:\.\d+)?)\+?\s+years?",
        text,
    )

    if range_match:
        minimum = float(range_match.group(1))
        maximum = float(range_match.group(2))
        return minimum, maximum

    minimum_match = re.search(
        r"\b(?:at least|minimum of|min\.?)?\s*"
        r"(\d+(?:\.\d+)?)\+?\s+years?"
        r"(?:\s+of)?\s+(?:professional\s+)?"
        r"(?:experience|software|development|engineering)",
        text,
    )

    if minimum_match:
        return float(minimum_match.group(1)), None

    return None, None


def infer_customer_facing_level(
    role: str,
    description: str,
) -> str:
    text = f"{role} {description}".casefold()

    primary_phrases = (
        "primary point of contact",
        "own customer relationships",
        "manage a portfolio of customers",
        "customer retention",
        "account growth",
        "customer success manager",
        "account manager",
        "client service coordinator",
    )

    high_phrases = (
        "daily customer interaction",
        "regularly meet with customers",
        "customer-facing role",
        "client-facing role",
        "present product demonstrations",
        "pre-sales",
    )

    moderate_phrases = (
        "work with customers",
        "partner with customers",
        "gather customer requirements",
        "customer implementation",
        "client workshops",
    )

    low_phrases = (
        "occasionally meet with customers",
        "occasional customer interaction",
        "support technical requirements gathering",
    )

    if any(phrase in text for phrase in primary_phrases):
        return "primary_responsibility"

    if any(phrase in text for phrase in high_phrases):
        return "high"

    if any(phrase in text for phrase in moderate_phrases):
        return "moderate"

    if any(phrase in text for phrase in low_phrases):
        return "low"

    customer_terms = (
        "customer",
        "client",
        "stakeholder",
    )

    if not any(term in text for term in customer_terms):
        return "none"

    return "unknown"


def extract_pattern_matches(
    description: str,
    pattern_map: dict[str, tuple[str, ...]],
) -> list[str]:
    matches: list[str] = []

    for label, patterns in pattern_map.items():
        if any(
            re.search(pattern, description, flags=re.IGNORECASE)
            for pattern in patterns
        ):
            matches.append(label)

    return matches


def infer_education(description: str) -> list[str]:
    text = description.casefold()
    education: list[str] = []

    if (
        "bachelor's degree" in text
        or "bachelors degree" in text
        or "bachelor degree" in text
    ):
        education.append("Bachelor's degree")

    if (
        "master's degree" in text
        or "masters degree" in text
        or "master degree" in text
    ):
        education.append("Master's degree")

    if "equivalent practical experience" in text:
        education.append("Equivalent practical experience accepted")

    return education


def infer_boolean_requirement(
    description: str,
    positive_patterns: tuple[str, ...],
    negative_patterns: tuple[str, ...] = (),
) -> bool | None:
    text = description.casefold()

    if any(pattern in text for pattern in negative_patterns):
        return False

    if any(pattern in text for pattern in positive_patterns):
        return True

    return None


def normalize_salary(raw_salary: Any) -> dict[str, Any]:
    default_salary = {
        "minimum": None,
        "maximum": None,
        "currency": None,
        "period": "unknown",
        "source": "not_provided",
    }

    if raw_salary is None:
        return default_salary

    if not isinstance(raw_salary, dict):
        return default_salary

    minimum = raw_salary.get("minimum")
    maximum = raw_salary.get("maximum")
    currency = optional_string(raw_salary.get("currency"))
    period = optional_string(raw_salary.get("period")) or "unknown"
    source = optional_string(raw_salary.get("source")) or "not_provided"

    if currency:
        currency = currency.upper()

    valid_periods = {
        "hour",
        "month",
        "year",
        "project",
        "unknown",
    }

    valid_sources = {
        "employer",
        "platform_estimate",
        "inferred",
        "not_provided",
    }

    if period not in valid_periods:
        period = "unknown"

    if source not in valid_sources:
        source = "not_provided"

    return {
        "minimum": minimum,
        "maximum": maximum,
        "currency": currency,
        "period": period,
        "source": source,
    }


def strategy_version(criteria_path: Path) -> int:
    criteria = load_json(criteria_path)
    version = criteria.get("strategy_version")

    if isinstance(version, bool) or not isinstance(version, int):
        raise JobLeadValidationError(
            f"{criteria_path}: strategy_version must be an integer."
        )

    return version


def normalized_datetime(value: Any) -> str:
    supplied = optional_string(value)

    if supplied:
        return supplied

    return datetime.now().astimezone().isoformat(timespec="seconds")


def build_job_lead(
    raw: dict[str, Any],
    criteria_version: int,
) -> dict[str, Any]:
    company = non_empty_string(raw.get("company"), "company")
    role = non_empty_string(raw.get("role"), "role")
    posting_url = non_empty_string(
        raw.get("posting_url"),
        "posting_url",
    )
    description = non_empty_string(
        raw.get("description_text"),
        "description_text",
    )

    canonical_url = canonicalize_url(posting_url)
    external_job_id = optional_string(raw.get("external_job_id"))
    application_url = (
        optional_string(raw.get("application_url"))
        or canonical_url
    )

    collected_at = normalized_datetime(raw.get("collected_at"))
    workplace_type = infer_workplace_type(
        optional_string(raw.get("workplace_type_raw")),
        description,
    )
    location = infer_location(
        optional_string(raw.get("location_raw")),
        workplace_type,
        description,
    )

    years_minimum, years_maximum = extract_years_experience(
        description
    )

    technical_skills = extract_pattern_matches(
        description,
        TECHNICAL_SKILL_PATTERNS,
    )
    domain_skills = extract_pattern_matches(
        description,
        DOMAIN_SKILL_PATTERNS,
    )

    lead_id = build_lead_id(
        company=company,
        role=role,
        canonical_url=canonical_url,
        external_job_id=external_job_id,
    )

    return {
        "schema_version": 1,
        "lead_id": lead_id,
        "identity": {
            "company": company,
            "role": role,
            "normalized_company": normalize_identity(company),
            "normalized_role": normalize_identity(role),
            "external_job_id": external_job_id,
        },
        "source": {
            "platform": infer_platform(
                optional_string(raw.get("platform")),
                posting_url,
            ),
            "posting_url": posting_url,
            "canonical_url": canonical_url,
            "company_careers_url": optional_string(
                raw.get("company_careers_url")
            ),
            "collected_at": collected_at,
            "first_seen_at": collected_at,
            "last_seen_at": collected_at,
        },
        "position": {
            "title": role,
            "department": optional_string(raw.get("department")),
            "seniority": infer_seniority(role, description),
            "primary_function": infer_primary_function(
                role,
                description,
            ),
        },
        "location": location,
        "employment": {
            "employment_type": infer_employment_type(
                optional_string(raw.get("employment_type_raw")),
                description,
            ),
            "schedule": optional_string(raw.get("schedule")),
            "salary": normalize_salary(raw.get("salary")),
        },
        "content": {
            "description_text": description,
            "description_hash": description_hash(description),
            "summary": optional_string(raw.get("summary")),
            "responsibilities": list(
                dict.fromkeys(raw.get("responsibilities") or [])
            ),
            "qualifications": list(
                dict.fromkeys(raw.get("qualifications") or [])
            ),
            "benefits": list(
                dict.fromkeys(raw.get("benefits") or [])
            ),
        },
        "requirements": {
            "years_experience_min": years_minimum,
            "years_experience_max": years_maximum,
            "education": infer_education(description),
            "technical_skills": technical_skills,
            "domain_skills": domain_skills,
            "clearance_required": infer_boolean_requirement(
                description,
                positive_patterns=(
                    "security clearance required",
                    "must hold security clearance",
                    "eligible for secret clearance",
                    "eligible for reliability status",
                ),
                negative_patterns=(
                    "no security clearance required",
                ),
            ),
            "driving_required": infer_boolean_requirement(
                description,
                positive_patterns=(
                    "valid driver's license required",
                    "valid drivers license required",
                    "must have a driver's license",
                    "must have a drivers license",
                    "reliable vehicle required",
                ),
                negative_patterns=(
                    "driver's license not required",
                    "drivers license not required",
                ),
            ),
            "customer_facing_level": infer_customer_facing_level(
                role,
                description,
            ),
        },
        "application": {
            "application_url": application_url,
            "application_method": (
                optional_string(raw.get("application_method"))
                or "unknown"
            ),
            "deadline": optional_string(raw.get("deadline")),
            "posted_date": optional_string(raw.get("posted_date")),
            "posting_status": (
                optional_string(raw.get("posting_status"))
                or "unknown"
            ),
        },
        "discovery": {
            "search_query": optional_string(
                raw.get("search_query")
            ),
            "criteria_strategy_version": criteria_version,
            "preliminary_score": None,
            "score_components": {
                "title_alignment": None,
                "ai_engineering_alignment": None,
                "software_engineering_alignment": None,
                "technical_stack_alignment": None,
                "experience_alignment": None,
                "location_alignment": None,
                "company_alignment": None,
            },
            "penalties": [],
            "hard_filter_result": "not_evaluated",
            "hard_filter_reasons": [],
            "full_analysis_recommended": None,
        },
        "status": {
            "lead_status": "new",
            "duplicate_of": None,
            "reviewed": False,
            "notes": [],
        },
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize a raw job posting into the canonical "
            "Job Lead contract."
        )
    )

    parser.add_argument(
        "raw_posting_path",
        type=Path,
        help="Path to a raw job-posting JSON file.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Optional output file. When omitted, the lead is written "
            "to data/job-leads/<lead-id>.json."
        ),
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=(
            "Default output directory when --output is omitted. "
            f"Defaults to {DEFAULT_OUTPUT_DIRECTORY}."
        ),
    )

    parser.add_argument(
        "--criteria",
        type=Path,
        default=DEFAULT_CRITERIA_PATH,
        help=(
            "Path to job_search_criteria.json. "
            f"Defaults to {DEFAULT_CRITERIA_PATH}."
        ),
    )

    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help=(
            "Path to job-lead-schema.json. "
            f"Defaults to {DEFAULT_SCHEMA_PATH}."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing normalized lead.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        raw = load_json(args.raw_posting_path)
        schema = load_json(args.schema)
        criteria_version = strategy_version(args.criteria)

        lead = build_job_lead(raw, criteria_version)

        output_path = (
            args.output
            if args.output
            else args.output_directory / f"{lead['lead_id']}.json"
        )

        if output_path.exists() and not args.force:
            raise JobLeadValidationError(
                f"Output already exists: {output_path}. "
                "Use --force to overwrite it."
            )

        errors = validate_schema(lead, schema)
        errors.extend(validate_business_rules(lead))

        if errors:
            print(
                "Normalized Job Lead validation failed:",
                file=sys.stderr,
            )

            for error in errors:
                print(f"- {error}", file=sys.stderr)

            return 1

        write_json(output_path, lead)

        print("Job Lead normalized successfully.")
        print(f"Lead ID: {lead['lead_id']}")
        print(
            "Opportunity: "
            f"{lead['identity']['company']} — "
            f"{lead['identity']['role']}"
        )
        print(
            "Primary function: "
            f"{lead['position']['primary_function']}"
        )
        print(
            "Seniority: "
            f"{lead['position']['seniority']}"
        )
        print(
            "Workplace type: "
            f"{lead['location']['workplace_type']}"
        )
        print(
            "Can hire in Canada: "
            f"{lead['location']['can_hire_in_canada']}"
        )
        print(
            "Customer-facing level: "
            f"{lead['requirements']['customer_facing_level']}"
        )
        print(f"Output: {output_path}")

        return 0

    except JobLeadValidationError as exc:
        print(f"Normalization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
