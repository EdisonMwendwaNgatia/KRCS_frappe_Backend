"""Restrict contact submission records to authorized Desk staff."""

import frappe


def execute():
	permissions = [{
		"role": "System Manager",
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 0,
		"report": 0,
		"export": 0,
		"print": 0,
		"email": 0,
		"share": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
	}]

	for doctype in ("Feedback", "Inquiry", "Partnership Proposal"):
		doc = frappe.get_doc("DocType", doctype)
		doc.set("permissions", permissions)
		doc.save(ignore_permissions=True)

	frappe.db.commit()
