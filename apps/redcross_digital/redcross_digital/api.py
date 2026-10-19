import json
import re

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint
from frappe.utils import validate_email_address


PUBLIC_DOCTYPES = [
    "Site",
    "Testimonials",
    "Blogs",
    "Countries",
    "Partners",
    "Thematic Areas",
    "Projects",
    "Person",
    "Innovations",
    # ── KRCS Digital Transformation Platform ──
    "Knowledge Resource",
    "Digital Story",
    "News Item",
]

# Fields scrubbed from every response
BASE_SCRUB = {
    "owner", "modified_by", "creation", "modified",
    "idx", "docstatus", "_user_tags", "_comments",
    "_assign", "_liked_by", "_seen",
}

# Fields scrubbed from child-table rows
CHILD_SCRUB = {
    "name", "parent", "parentfield", "parenttype",
    "idx", "docstatus", "owner", "modified_by",
    "creation", "modified",
}

# Per-doctype extra scrubbing
DOCTYPES_SCRUB = {
    "Person": {"email"},   # only PII we collect
}


JSON_FIELDS = {
    "expertise",
    "impact_metrics",
    "technologies",
    "countries",
    "team_ids",
    "partner_ids",
    "gallery",
    "content",
    "author",
    "gallery_images",
    "tags",
    "key_initiatives",
    "coordinates",
    "what_worked",
    "what_didnt_work",
    "what_to_improve",
}

CACHE_TTL = 300          # seconds
MAX_LIMIT = 500
MAX_SUBMISSION_BODY_BYTES = 24 * 1024

FEEDBACK_SUBMISSION_MODES = {"identified", "anonymous"}
FEEDBACK_STAKEHOLDER_TYPES = {
    "staff",
    "volunteer",
    "community_member",
    "partner",
    "other_stakeholder",
}
FEEDBACK_CATEGORIES = {
    "problem",
    "accessibility_barrier",
    "ux_issue",
    "training_need",
    "new_idea",
    "improvement_opportunity",
    "other",
}
FEEDBACK_PLATFORMS = {"web", "mobile_app", "kiosk", "sms", "in_person"}
FEEDBACK_SEVERITIES = {"low", "medium", "high", "critical"}


def _clean_child(child) -> dict:
    """Scrub internal fields from a child-table row."""
    if not isinstance(child, dict):
        return child

    out = {}
    for key, value in child.items():
        if key in CHILD_SCRUB:
            continue

        if key in JSON_FIELDS and isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass

        out[key] = value

    return out


def _clean(doctype: str, row: dict) -> dict:
    """Strip internal fields and deserialize JSON-encoded columns."""
    drop = BASE_SCRUB | DOCTYPES_SCRUB.get(doctype, set())

    cleaned = {}
    for key, value in row.items():
        if key in drop:
            continue

        if key in JSON_FIELDS and isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Not valid JSON — leave the raw string alone.
                pass

        # Recurse into child-table arrays (Table / Table MultiSelect fields)
        if isinstance(value, list):
            value = [_clean_child(c) for c in value]

        cleaned[key] = value

    return cleaned


def _assert_public(doctype: str):
    if doctype not in PUBLIC_DOCTYPES:
        frappe.throw(
            f"DocType '{doctype}' is not exposed publicly",
            frappe.PermissionError,
        )


@frappe.whitelist(allow_guest=True)
def list_docs(doctype: str, limit: int = 100, start: int = 0, filters: str = None):
    """
    Public read-only list endpoint with pagination metadata.

    GET /api/method/redcross_digital.api.list_docs?doctype=Projects&limit=50&start=0
    Optional: &filters={"status":"Active"}
    """
    _assert_public(doctype)

    limit = max(1, min(cint(limit) or 100, MAX_LIMIT))
    start = max(0, cint(start) or 0)
    parsed_filters = frappe.parse_json(filters) if filters else None

    cache_key = f"pub_api:list:{doctype}:{limit}:{start}:{filters or ''}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    rows = frappe.get_all(
        doctype,
        fields=["*"],
        filters=parsed_filters,
        limit_page_length=limit,
        limit_start=start,
        order_by="creation desc",
    )

    total = (
        frappe.db.count(doctype, filters=parsed_filters)
        if parsed_filters
        else frappe.db.count(doctype)
    )

    payload = {
        "data": [_clean(doctype, r) for r in rows],
        "total": total,
        "limit": limit,
        "start": start,
        "has_next": (start + limit) < total,
    }

    frappe.cache().set_value(cache_key, payload, expires_in_sec=CACHE_TTL)
    return payload


@frappe.whitelist(allow_guest=True)
def get_doc(doctype: str, name: str):
    """
    Public read-only single-doc endpoint.

    GET /api/method/redcross_digital.api.get_doc?doctype=Blogs&name=b1
    """
    _assert_public(doctype)

    cache_key = f"pub_api:doc:{doctype}:{name}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    if not frappe.db.exists(doctype, name):
        frappe.throw("Not found", frappe.DoesNotExistError)

    doc = frappe.get_doc(doctype, name).as_dict()
    payload = _clean(doctype, doc)

    frappe.cache().set_value(cache_key, payload, expires_in_sec=CACHE_TTL)
    return payload


@frappe.whitelist(allow_guest=True)
def get_site_config():
    """
    Returns the single Site document (singleton) as the public site config.

    GET /api/method/redcross_digital.api.get_site_config
    """
    cache_key = "pub_api:site_config"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    rows = frappe.get_all("Site", fields=["*"], limit_page_length=1)
    if not rows:
        frappe.throw("Site configuration not found", frappe.DoesNotExistError)

    payload = _clean("Site", rows[0])
    frappe.cache().set_value(cache_key, payload, expires_in_sec=CACHE_TTL)
    return payload


@frappe.whitelist(allow_guest=True)
def list_all():
    """
    One-shot endpoint that returns everything you need for a static build.

    GET /api/method/redcross_digital.api.list_all
    """
    # Version the key so cached responses from earlier releases cannot keep returning
    # protected submission records that are no longer in the public allowlist.
    cache_key = "pub_api:list_all:v2"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    out = {}
    for dt in PUBLIC_DOCTYPES:
        rows = frappe.get_all(
            dt,
            fields=["*"],
            limit_page_length=1000,
            order_by="creation desc",
        )
        out[dt] = [_clean(dt, r) for r in rows]

    frappe.cache().set_value(cache_key, out, expires_in_sec=CACHE_TTL)
    return out


def _bust_cache(doc, method=None):
    """Optional doc-event hook — clears the public API cache on any write."""
    if getattr(doc, "doctype", None) in PUBLIC_DOCTYPES:
        frappe.cache().delete_keys("pub_api:*")


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="email", limit=30, seconds=60 * 60, methods="POST")
def submit_feedback():
    """
    Whitelisted endpoint for public website feedback submissions.
    Saves new feedback documents into tabFeedback in MariaDB.

    POST /api/method/redcross_digital.api.submit_feedback
    """
    data = _submission_payload()
    if _is_honeypot_submission(data):
        return _discarded_submission("Feedback received.")

    submission_mode = _submission_choice(
        data, "submission_mode", FEEDBACK_SUBMISSION_MODES, "identified"
    )

    full_name = _submission_text(data, "full_name", 140, required=submission_mode == "identified")
    email = _submission_email(data, required=submission_mode == "identified")
    phone = _submission_phone(data)
    stakeholder_type = _submission_choice(
        data, "stakeholder_type", FEEDBACK_STAKEHOLDER_TYPES, default="community_member"
    )
    stakeholder_type_other = _submission_text(data, "stakeholder_type_other", 140)
    if stakeholder_type == "other_stakeholder" and not stakeholder_type_other:
        frappe.throw("Please specify your stakeholder type.", frappe.ValidationError)

    feedback_category = _submission_choice(
        data, "feedback_category", FEEDBACK_CATEGORIES, default="other"
    )
    platform_used = _submission_choice(
        data, "platform_used", FEEDBACK_PLATFORMS, default="web"
    )
    severity = _submission_choice(data, "severity", FEEDBACK_SEVERITIES, default="medium")
    subject = _submission_text(data, "subject", 140, required=True)
    description = _submission_text(data, "description", 12000, required=True, multiline=True)
    suggestion = _submission_text(data, "suggestion", 6000, multiline=True)
    privacy_accepted = _submission_bool(data, "privacy_accepted", required=True)
    if not privacy_accepted:
        frappe.throw("You must accept the privacy notice to submit feedback.", frappe.ValidationError)

    doc = frappe.get_doc({
        "doctype": "Feedback",
        "submission_mode": submission_mode,
        "full_name": full_name if submission_mode == "identified" else "Anonymous",
        "email": email if submission_mode == "identified" else "",
        "phone": phone if submission_mode == "identified" else "",
        "stakeholder_type": stakeholder_type,
        "stakeholder_type_other": stakeholder_type_other,
        "organisation": _submission_text(data, "organisation", 140),
        "country": _submission_text(data, "country", 140),
        "region": _submission_text(data, "region", 140),
        "digital_service": _submission_text(data, "digital_service", 140),
        "project": _submission_text(data, "project", 140),
        "platform_used": platform_used,
        "feedback_category": feedback_category,
        "severity": severity,
        "subject": subject,
        "description": description,
        "suggestion": suggestion,
        "accessibility_impacted": _submission_bool(data, "accessibility_impacted"),
        "accessibility_area": _submission_text(data, "accessibility_area", 2000, multiline=True),
        "consent_to_contact": _submission_bool(data, "consent_to_contact"),
        "privacy_accepted": 1,
        "status": "new",
    })

    doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "name": doc.name,
        "message": "Feedback record created in MariaDB."
    }


def _submission_payload():
    """Read a bounded JSON or form submission and require an object payload."""
    request = frappe.request
    if request:
        if request.method.upper() != "POST":
            frappe.throw("Submissions must use POST.", frappe.ValidationError)

        content_length = request.content_length
        if content_length and content_length > MAX_SUBMISSION_BODY_BYTES:
            frappe.throw("Submission is too large.", frappe.ValidationError)

        raw_body = request.get_data(cache=True)
        if len(raw_body) > MAX_SUBMISSION_BODY_BYTES:
            frappe.throw("Submission is too large.", frappe.ValidationError)

        if raw_body and request.is_json:
            try:
                data = json.loads(raw_body)
            except (TypeError, ValueError):
                frappe.throw("Submission must contain valid JSON.", frappe.ValidationError)
        else:
            data = dict(frappe.form_dict)
    else:
        data = dict(frappe.form_dict)

    if not isinstance(data, dict):
        frappe.throw("Submission must be a JSON object.", frappe.ValidationError)
    data.pop("cmd", None)
    return data


def _submission_text(data, field, max_length, required=False, multiline=False):
    value = data.get(field, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        frappe.throw(f"{field.replace('_', ' ').capitalize()} must be text.", frappe.ValidationError)

    value = value.strip()
    if required and not value:
        frappe.throw(f"{field.replace('_', ' ').capitalize()} is required.", frappe.ValidationError)
    if len(value) > max_length:
        frappe.throw(
            f"{field.replace('_', ' ').capitalize()} must be {max_length} characters or fewer.",
            frappe.ValidationError,
        )
    if "\x00" in value or (not multiline and ("\n" in value or "\r" in value)):
        frappe.throw(f"{field.replace('_', ' ').capitalize()} contains invalid characters.", frappe.ValidationError)
    return value


def _submission_email(data, required=True):
    email = _submission_text(data, "email", 140, required=required)
    if not email:
        return ""

    normalized = validate_email_address(email, throw=True)
    if not normalized or "," in normalized:
        frappe.throw("Enter one valid email address.", frappe.ValidationError)
    return normalized


def _submission_phone(data):
    phone = _submission_text(data, "phone", 32)
    if phone:
        digits = re.sub(r"\D", "", phone)
        if not re.fullmatch(r"\+?[0-9][0-9\s().-]*", phone) or not 7 <= len(digits) <= 15:
            frappe.throw("Enter a valid phone number.", frappe.ValidationError)
    return phone


def _submission_choice(data, field, choices, default):
    value = _submission_text(data, field, 140) or default
    if value not in choices:
        frappe.throw(f"Invalid {field.replace('_', ' ')} selection.", frappe.ValidationError)
    return value


def _submission_bool(data, field, required=False):
    value = data.get(field)
    if value is None or value == "":
        if required:
            frappe.throw(f"{field.replace('_', ' ').capitalize()} is required.", frappe.ValidationError)
        return 0
    if value in (True, 1, "1", "true", "True", "yes", "on"):
        return 1
    if value in (False, 0, "0", "false", "False", "no", "off"):
        return 0
    frappe.throw(f"{field.replace('_', ' ').capitalize()} must be true or false.", frappe.ValidationError)


def _is_honeypot_submission(data):
    """Silently discard submissions that filled the contact form's hidden field."""
    value = data.get("website_url")
    return bool(str(value or "").strip())


def _discarded_submission(message):
    """Return the normal success shape to avoid helping simple bots adapt."""
    return {"status": "success", "name": None, "message": message}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="email", limit=10, seconds=60 * 60, methods="POST")
def submit_inquiry():
    """Persist a public general contact inquiry without granting Guest DocType access."""
    data = _submission_payload()
    if _is_honeypot_submission(data):
        return _discarded_submission("Inquiry received.")

    full_name = _submission_text(data, "full_name", 140, required=True)
    email = _submission_email(data)
    phone = _submission_phone(data)
    organization = _submission_text(data, "organization", 140)
    subject = _submission_text(data, "subject", 140, required=True)
    message = _submission_text(data, "message", 10000, required=True, multiline=True)
    doc = frappe.get_doc({
        "doctype": "Inquiry",
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "organization": organization,
        "subject": subject,
        "message": message,
        "status": "New",
        "submitted_at": frappe.utils.now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    return {"status": "success", "name": doc.name, "message": "Inquiry saved."}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="email", limit=10, seconds=60 * 60, methods="POST")
def submit_partnership_proposal():
    """Persist a public partnership proposal without granting Guest DocType access."""
    data = _submission_payload()
    if _is_honeypot_submission(data):
        return _discarded_submission("Proposal received.")

    organization = _submission_text(data, "organization", 140, required=True)
    contact_person = _submission_text(data, "contact_person", 140, required=True)
    email = _submission_email(data)
    phone = _submission_phone(data)
    collaboration_area = _submission_text(data, "collaboration_area", 140, required=True)
    proposal_title = _submission_text(data, "proposal_title", 140, required=True)
    proposal_summary = _submission_text(
        data, "proposal_summary", 12000, required=True, multiline=True
    )
    doc = frappe.get_doc({
        "doctype": "Partnership Proposal",
        "organization": organization,
        "contact_person": contact_person,
        "email": email,
        "phone": phone,
        "collaboration_area": collaboration_area,
        "proposal_title": proposal_title,
        "proposal_summary": proposal_summary,
        "status": "New",
        "submitted_at": frappe.utils.now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    return {"status": "success", "name": doc.name, "message": "Partnership proposal saved."}
