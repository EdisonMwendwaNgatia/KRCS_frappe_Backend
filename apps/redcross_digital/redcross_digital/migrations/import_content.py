import json
from pathlib import Path
from datetime import datetime

import frappe


APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = APP_ROOT / "migration_data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(filename):
    """Load a JSON file that may be a bare array or an object wrapping an array."""
    path = DATA_DIR / filename

    if not path.exists():
        frappe.throw(f"Migration file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        # Supports files shaped like: {"people": [...]}, {"projects": [...]}
        for value in data.values():
            if isinstance(value, list):
                return value
        # A single object (e.g. site.json) — return as-is
        return data

    if not isinstance(data, list):
        frappe.throw(
            f"{filename} must contain a JSON array, an object containing an array, "
            f"or a single object."
        )

    return data


def clean_url(value):
    if not value:
        return value
    # Handle markdown-style URLs: [https://x](https://x)
    if value.startswith("[") and "](" in value and value.endswith(")"):
        try:
            return value.split("](", 1)[1][:-1]
        except Exception:
            pass
    return value


def clean_date(value):
    """Convert source dates like 'August 18, 2024' to YYYY-MM-DD."""
    if not value:
        return None

    if isinstance(value, str):
        value = value.strip()

        for fmt in (
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

    frappe.throw(f"Unsupported date format: {value}")


def upsert_doc(doctype, external_id, values):
    """Insert or update a doc identified by external_id."""
    if not external_id:
        frappe.throw(f"{doctype}: record is missing required external_id: {values}")

    existing_name = frappe.db.get_value(
        doctype, {"external_id": external_id}, "name"
    )

    if existing_name:
        doc = frappe.get_doc(doctype, existing_name)
        for fieldname, value in values.items():
            if fieldname != "external_id":
                setattr(doc, fieldname, value)
        doc.save(ignore_permissions=True)
        return "updated", doc.name

    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.insert(ignore_permissions=True)
    return "created", doc.name


# ---------------------------------------------------------------------------
# Importers
# ---------------------------------------------------------------------------

def import_site():
    """Singleton Site doc (no external_id)."""
    data = load_json("site.json")
    if isinstance(data, list):
        data = data[0] if data else {}

    contact = data.get("contact") or {}
    social = data.get("social") or {}

    values = {
        "site_name": data.get("name"),
        "short_name": data.get("shortName"),
        "tagline": data.get("tagline"),
        "description": data.get("description"),
        "url": clean_url(data.get("url")),
        "official_redcross_url": clean_url(data.get("officialRedCrossUrl")),
        "contact": json.dumps(contact) if contact else None,
        "social": json.dumps(social) if social else None,
    }

    existing = frappe.db.get_value("Site", {}, "name")
    if existing:
        doc = frappe.get_doc("Site", existing)
        for k, v in values.items():
            setattr(doc, k, v)
        doc.save(ignore_permissions=True)
        action, name = "updated", doc.name
    else:
        doc = frappe.get_doc({"doctype": "Site", **values})
        doc.insert(ignore_permissions=True)
        action, name = "created", doc.name

    print(f"Site {action}: {name}")
    return (1, 0) if action == "created" else (0, 1)


def import_people():
    records = load_json("people.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "slug": item.get("slug"),
            "full_name": item.get("name"),
            "role": item.get("role"),
            "department": item.get("department"),
            "is_volunteer": item.get("isVolunteer", False),
            "short_bio": item.get("shortBio"),
            "bio": item.get("bio"),
            "avatar": item.get("avatar"),
            "expertise": json.dumps(item.get("expertise", [])),
            "email": item.get("email"),
            "linkedin": clean_url(item.get("linkedin")),
            "twitter": clean_url(item.get("twitter")),
            "github": clean_url(item.get("github")),
            "featured": item.get("featured", False),
        }

        action, name = upsert_doc("Person", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Person {action}: {name}")

    return created, updated


def import_thematic_areas():
    records = load_json("thematicAreas.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "slug": item.get("slug"),
            "number": item.get("number"),
            "title": item.get("title"),
            "short_title": item.get("shortTitle"),
            "tag_line": item.get("tagline"),
            "description": item.get("description"),
            "detailed_description": item.get("detailedDescription"),
            "capabilities": json.dumps(item.get("capabilities", [])),
            "impact_metrics": json.dumps(item.get("impactMetrics", [])),
            "icon_name": item.get("iconName"),
            "featured_image_url": item.get("featuredImageUrl"),
        }

        action, name = upsert_doc("Thematic Areas", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Thematic Area {action}: {name}")

    return created, updated


def import_projects():
    records = load_json("projects.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "slug": item.get("slug"),
            "title": item.get("title"),
            "category": item.get("category"),
            "year": item.get("year"),
            "description": item.get("description"),
            "short_description": item.get("shortDescription"),
            "challange": item.get("challenge"),           # NB: field name is "challange" in your doctype
            "solution": item.get("solution"),
            "impact": item.get("impact"),
            "impact_metrics": json.dumps(item.get("impactMetrics", [])),
            "technologies": json.dumps(item.get("technologies", [])),
            "thematic_area_slug": item.get("thematicAreaSlug"),
            "countries": json.dumps(item.get("countries", [])),
            "team_ids": json.dumps(item.get("teamIds", [])),
            "partner_ids": json.dumps(item.get("partnerIds", [])),  # field is partner_ids, not partnet_ids
            "featured": item.get("featured", False),
            "image": item.get("image"),
            "gallery": json.dumps(item.get("gallery", [])),
            "demo_url": clean_url(item.get("demoUrl")),
            "github_url": clean_url(item.get("githubUrl")),
        }

        action, name = upsert_doc("Projects", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Project {action}: {name}")

    return created, updated


def import_partners():
    records = load_json("partners.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "partner_name": item.get("name"),
            "category": item.get("category"),
            "logo": item.get("logo"),
            "description": item.get("description"),
            "website": clean_url(item.get("website")),
            "collaboration_focus": item.get("collaborationFocus"),
            "featured": item.get("featured", False),
        }

        action, name = upsert_doc("Partners", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Partner {action}: {name}")

    return created, updated


def import_countries():
    records = load_json("countries.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "code": item.get("code"),
            "country_name": item.get("name"),
            "region": item.get("region"),
            "is_active": item.get("isActive", False),
            "short_description": item.get("shortDescription"),
            "active_initiatives_count": item.get("activeInitiativesCount", 0),
            "digital_products_count": item.get("digitalProductsCount", 0),
            "data_services_count": item.get("dataServicesCount", 0),
            "key_initiatives": json.dumps(item.get("keyInitiatives", [])),
            "coordinates": json.dumps(item.get("coordinates") or {}),
            "partner": item.get("partner"),
            "since": item.get("since"),
            "image": item.get("image"),
            "image_alt": item.get("imageAlt"),
            "field_note": item.get("fieldNote"),
        }

        action, name = upsert_doc("Countries", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Country {action}: {name}")

    return created, updated


def import_blogs():
    records = load_json("blogs.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "slug": item.get("slug"),
            "title": item.get("title"),
            "excerpt": item.get("excerpt"),
            "content": json.dumps(item.get("content", [])),
            "category": item.get("category"),
            "published_date": clean_date(item.get("publishedDate")),
            "read_time": item.get("readTime"),
            "author": json.dumps(item.get("author") or {}),
            "cover_image": item.get("coverImage"),
            "flickr_album_url": clean_url(item.get("flickrAlbumUrl")),
            "gallery_images": json.dumps(item.get("galleryImages", [])),
            "video_embed_url": clean_url(item.get("videoEmbedUrl")),
            "tags": json.dumps(item.get("tags", [])),
            "featured": item.get("featured", False),
        }

        action, name = upsert_doc("Blogs", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Blog {action}: {name}")

    return created, updated


def import_testimonials():
    records = load_json("testimonials.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "quote": item.get("quote"),
            "author_name": item.get("authorName"),
            "author_role": item.get("authorRole"),
            "organization": item.get("organization"),
            "location": item.get("location"),
            "avatar": item.get("avatar"),
            "category": item.get("category"),
            "featured": item.get("featured", False),
        }

        action, name = upsert_doc("Testimonials", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Testimonial {action}: {name}")

    return created, updated


def import_innovations():
    records = load_json("innovations.json")
    created = updated = 0

    for item in records:
        values = {
            "external_id": item.get("id"),
            "title": item.get("title"),
            "what_we_tested": item.get("what_we_tested"),
            "why_we_tested": item.get("why_we_tested"),
            "what_we_learned": item.get("what_we_learned"),
            "what_worked": json.dumps(item.get("what_worked", [])),
            "what_didnt_work": json.dumps(item.get("what_didnt_work", [])),
            "what_to_improve": json.dumps(item.get("what_to_improve", [])),
            "recommendation": item.get("recommendation"),
        }

        action, name = upsert_doc("Innovations", item.get("id"), values)
        created += action == "created"
        updated += action == "updated"
        print(f"Innovation {action}: {name}")

    return created, updated


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run():
    print("=" * 70)
    print("KENYA RED CROSS CONTENT MIGRATION")
    print("=" * 70)

    frappe.flags.in_migrate = True
    results = {}

    print("\n--- SITE ---")
    results["Site"] = import_site()

    print("\n--- PEOPLE ---")
    results["Person"] = import_people()

    print("\n--- THEMATIC AREAS ---")
    results["Thematic Areas"] = import_thematic_areas()

    print("\n--- PARTNERS ---")
    results["Partners"] = import_partners()

    print("\n--- COUNTRIES ---")
    results["Countries"] = import_countries()

    print("\n--- PROJECTS ---")
    results["Projects"] = import_projects()

    print("\n--- BLOGS ---")
    results["Blogs"] = import_blogs()

    print("\n--- TESTIMONIALS ---")
    results["Testimonials"] = import_testimonials()

    print("\n--- INNOVATIONS ---")
    results["Innovations"] = import_innovations()

    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    for doctype, (created, updated) in results.items():
        print(f"{doctype}: {created} created, {updated} updated")

    frappe.db.commit()
    print("\nMigration completed successfully.")


if __name__ == "__main__":
    run()
