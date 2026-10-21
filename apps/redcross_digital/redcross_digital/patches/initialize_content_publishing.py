"""Keep all content that was already public visible during workflow rollout."""

import frappe


PUBLISHABLE_DOCTYPES = (
    "Testimonials",
    "Blogs",
    "Countries",
    "Partners",
    "Thematic Areas",
    "Projects",
    "Person",
    "Innovations",
    "Knowledge Resource",
    "Digital Story",
    "News Item",
)


def execute():
    for doctype in PUBLISHABLE_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            raise RuntimeError(f"Cannot initialize publishing workflow: missing {doctype} DocType")
        if not frappe.get_meta(doctype).has_field("publication_status"):
            raise RuntimeError(f"Cannot initialize publishing workflow: {doctype} is missing publication_status")

        # This one-time post-model-sync patch preserves visibility for every existing record.
        frappe.db.sql(
            f"UPDATE `tab{doctype}` SET publication_status = 'Published' "
            "WHERE IFNULL(publication_status, '') = '' OR publication_status = 'Draft'"
        )
