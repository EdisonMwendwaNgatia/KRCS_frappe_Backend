import json

import frappe
from frappe.utils import cint


PUBLIC_DOCTYPES = [
    "Site",
    "Testimonials",
    "Blogs",
    "Countries",
    "Partners",
    "Thematic Areas",
    "Projects",
    "Person",
    "Feedback",
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
    cache_key = "pub_api:list_all"
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


@frappe.whitelist(allow_guest=True)
def submit_feedback():
    """
    Whitelisted endpoint for public website feedback submissions.
    Saves new feedback documents into tabFeedback in MariaDB.

    POST /api/method/redcross_digital.api.submit_feedback
    """
    if frappe.request and frappe.request.data:
        try:
            data = json.loads(frappe.request.data)
        except Exception:
            data = frappe.form_dict
    else:
        data = frappe.form_dict

    submission_mode = data.get("submission_mode", "identified")
    subject = data.get("subject")
    description = data.get("description")
    feedback_category = data.get("feedback_category", "other")
    stakeholder_type = data.get("stakeholder_type", "community_member")

    if not subject or not description:
        frappe.throw("Subject and Description are required fields.")

    doc = frappe.get_doc({
        "doctype": "Feedback",
        "submission_mode": submission_mode,
        "full_name": data.get("full_name") if submission_mode == "identified" else "Anonymous",
        "email": data.get("email") if submission_mode == "identified" else "",
        "phone": data.get("phone") if submission_mode == "identified" else "",
        "stakeholder_type": stakeholder_type,
        "stakeholder_type_other": data.get("stakeholder_type_other"),
        "organisation": data.get("organisation"),
        "country": data.get("country"),
        "region": data.get("region"),
        "digital_service": data.get("digital_service"),
        "project": data.get("project"),
        "platform_used": data.get("platform_used", "web"),
        "feedback_category": feedback_category,
        "severity": data.get("severity", "medium"),
        "subject": subject,
        "description": description,
        "suggestion": data.get("suggestion"),
        "accessibility_impacted": 1 if data.get("accessibility_impacted") else 0,
        "accessibility_area": data.get("accessibility_area"),
        "consent_to_contact": 1 if data.get("consent_to_contact") else 0,
        "privacy_accepted": 1 if data.get("privacy_accepted") else 0,
        "status": "new",
    })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "name": doc.name,
        "message": "Feedback record created in MariaDB."
    }


def _submission_payload():
    """Read a JSON submission body, falling back to form fields."""
    if frappe.request and frappe.request.data:
        try:
            return json.loads(frappe.request.data)
        except (TypeError, ValueError):
            pass
    return frappe.form_dict


def _required_submission_fields(data, fields):
    missing = [field for field in fields if not str(data.get(field) or "").strip()]
    if missing:
        frappe.throw("Required fields: " + ", ".join(missing))


@frappe.whitelist(allow_guest=True)
def submit_inquiry():
    """Persist a public general contact inquiry without granting Guest DocType access."""
    data = _submission_payload()
    _required_submission_fields(data, ("full_name", "email", "subject", "message"))
    doc = frappe.get_doc({
        "doctype": "Inquiry",
        "full_name": str(data["full_name"]).strip(),
        "email": str(data["email"]).strip(),
        "phone": str(data.get("phone") or "").strip(),
        "organization": str(data.get("organization") or "").strip(),
        "subject": str(data["subject"]).strip(),
        "message": str(data["message"]).strip(),
        "status": "New",
        "submitted_at": frappe.utils.now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "name": doc.name, "message": "Inquiry saved."}


@frappe.whitelist(allow_guest=True)
def submit_partnership_proposal():
    """Persist a public partnership proposal without granting Guest DocType access."""
    data = _submission_payload()
    _required_submission_fields(data, ("organization", "contact_person", "email", "collaboration_area", "proposal_title", "proposal_summary"))
    doc = frappe.get_doc({
        "doctype": "Partnership Proposal",
        "organization": str(data["organization"]).strip(),
        "contact_person": str(data["contact_person"]).strip(),
        "email": str(data["email"]).strip(),
        "phone": str(data.get("phone") or "").strip(),
        "collaboration_area": str(data["collaboration_area"]).strip(),
        "proposal_title": str(data["proposal_title"]).strip(),
        "proposal_summary": str(data["proposal_summary"]).strip(),
        "status": "New",
        "submitted_at": frappe.utils.now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "name": doc.name, "message": "Partnership proposal saved."}
