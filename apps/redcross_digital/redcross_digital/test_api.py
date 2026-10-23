"""Focused tests for the public content API and guest submission handlers."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import set_request

from redcross_digital import api


class MemoryCache:
	"""Small cache fake covering the Frappe APIs used by these handlers."""

	def __init__(self):
		self.values = {}

	def __call__(self):
		return self

	def make_key(self, value):
		return str(value).encode()

	def get(self, key):
		return self.values.get(key)

	def setex(self, key, seconds, value):
		self.values[key] = value

	def incrby(self, key, amount):
		self.values[key] = int(self.values.get(key, 0)) + amount
		return self.values[key]

	def get_value(self, key):
		return self.values.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.values[key] = value

	def delete_keys(self, pattern):
		for key in list(self.values):
			if key.startswith(pattern.rstrip("*")):
				del self.values[key]


class TestPublicApiAndSubmissions(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.cache = MemoryCache()
		self.cache_patch = patch.object(frappe, "cache", self.cache)
		self.cache_patch.start()
		self.addCleanup(self.cache_patch.stop)

		self.previous_request = getattr(frappe.local, "request", None)
		self.previous_form_dict = getattr(frappe.local, "form_dict", None)
		self.previous_request_ip = getattr(frappe.local, "request_ip", None)
		self.addCleanup(self._restore_request_context)

	def _restore_request_context(self):
		for key, value in (
			("request", self.previous_request),
			("form_dict", self.previous_form_dict),
			("request_ip", self.previous_request_ip),
		):
			if value is None:
				if hasattr(frappe.local, key):
					delattr(frappe.local, key)
			else:
				setattr(frappe.local, key, value)

	def _post(self, data, *, method="POST"):
		body = json.dumps(data) if not isinstance(data, bytes) else data
		set_request(method=method, path="/api/method/redcross_digital.api", data=body, content_type="application/json")
		frappe.local.form_dict = frappe._dict({"cmd": "redcross_digital.api.test", "email": data.get("email", "") if isinstance(data, dict) else ""})
		frappe.local.request_ip = "192.0.2.20"

	def _mock_document(self, name="TEST-DOC"):
		doc = Mock()
		doc.name = name
		return doc

	def _valid_feedback(self, **changes):
		data = {
			"submission_mode": "identified",
			"full_name": "Community Member",
			"email": "person@example.org",
			"phone": "+254 712 345 678",
			"stakeholder_type": "community_member",
			"feedback_category": "other",
			"platform_used": "web",
			"severity": "medium",
			"subject": "Service feedback",
			"description": "The service was useful.",
			"privacy_accepted": True,
		}
		data.update(changes)
		return data

	def test_feedback_submission_maps_validated_fields(self):
		self._post(self._valid_feedback())
		doc = self._mock_document("FB-TEST")
		with patch.object(frappe, "get_doc", return_value=doc) as get_doc:
			result = api.submit_feedback()

		values = get_doc.call_args.args[0]
		self.assertEqual(result["name"], "FB-TEST")
		self.assertEqual(values["email"], "person@example.org")
		self.assertEqual(values["privacy_accepted"], 1)
		self.assertEqual(values["status"], "new")
		doc.insert.assert_called_once_with(ignore_permissions=True)

	def test_anonymous_feedback_does_not_retain_contact_details(self):
		self._post(self._valid_feedback(submission_mode="anonymous"))
		doc = self._mock_document("FB-ANON")
		with patch.object(frappe, "get_doc", return_value=doc) as get_doc:
			api.submit_feedback()

		values = get_doc.call_args.args[0]
		self.assertEqual(values["full_name"], "Anonymous")
		self.assertEqual(values["email"], "")
		self.assertEqual(values["phone"], "")

	def test_feedback_rejects_invalid_select_and_missing_privacy_acceptance(self):
		for changes in ({"feedback_category": "admin"}, {"privacy_accepted": False}):
			with self.subTest(changes=changes):
				self._post(self._valid_feedback(**changes))
				with patch.object(frappe, "get_doc") as get_doc:
					with self.assertRaises(frappe.ValidationError):
						api.submit_feedback()
				get_doc.assert_not_called()

	def test_feedback_rejects_bad_email_phone_and_overlong_text(self):
		for changes in (
			{"email": "two@example.org, three@example.org"},
			{"phone": "123"},
			{"subject": "x" * 141},
		):
			with self.subTest(field=next(iter(changes))):
				self._post(self._valid_feedback(**changes))
				with patch.object(frappe, "get_doc") as get_doc:
					with self.assertRaises(frappe.ValidationError):
						api.submit_feedback()
				get_doc.assert_not_called()

	def test_honeypot_discards_submission_without_inserting(self):
		self._post({"website_url": "https://bot.example.org"})
		with patch.object(frappe, "get_doc") as get_doc:
			result = api.submit_inquiry()

		self.assertEqual(result["status"], "success")
		self.assertIsNone(result["name"])
		get_doc.assert_not_called()

	def test_submission_handlers_reject_get_and_oversized_bodies(self):
		self._post({}, method="GET")
		with self.assertRaises(frappe.ValidationError):
			api.submit_inquiry()

		self._post({"message": "x" * (api.MAX_SUBMISSION_BODY_BYTES + 1)})
		with self.assertRaises(frappe.ValidationError):
			api.submit_inquiry()

	def test_inquiry_and_partnership_payloads_are_saved_with_server_status(self):
		inquiry = {
			"full_name": "Contact Person",
			"email": "contact@example.org",
			"subject": "General inquiry",
			"message": "Please contact our team.",
		}
		self._post(inquiry)
		inquiry_doc = self._mock_document("INQ-TEST")
		with (
			patch.object(frappe.utils, "now_datetime", return_value="2026-10-24 12:00:00"),
			patch.object(frappe, "get_doc", return_value=inquiry_doc) as get_doc,
		):
			result = api.submit_inquiry()
		self.assertEqual(result["name"], "INQ-TEST")
		self.assertEqual(get_doc.call_args.args[0]["status"], "New")

		proposal = {
			"organization": "Community Health Group",
			"contact_person": "Partnership Contact",
			"email": "partner@example.org",
			"collaboration_area": "Health",
			"proposal_title": "Community data project",
			"proposal_summary": "A proposal summary.",
		}
		self._post(proposal)
		proposal_doc = self._mock_document("PP-TEST")
		with (
			patch.object(frappe.utils, "now_datetime", return_value="2026-10-24 12:00:00"),
			patch.object(frappe, "get_doc", return_value=proposal_doc) as get_doc,
		):
			result = api.submit_partnership_proposal()
		self.assertEqual(result["name"], "PP-TEST")
		self.assertEqual(get_doc.call_args.args[0]["status"], "New")

	def test_inquiry_rate_limit_stops_the_eleventh_request(self):
		payload = {
			"full_name": "Contact Person",
			"email": "repeat@example.org",
			"subject": "General inquiry",
			"message": "Please contact our team.",
		}
		doc = self._mock_document("INQ-TEST")
		with (
			patch.object(frappe.utils, "now_datetime", return_value="2026-10-24 12:00:00"),
			patch.object(frappe, "get_doc", return_value=doc) as get_doc,
		):
			for _ in range(10):
				self._post(payload)
				api.submit_inquiry()

			self._post(payload)
			with self.assertRaises(frappe.RateLimitExceededError):
				api.submit_inquiry()

		self.assertEqual(get_doc.call_count, 10)

	def test_publication_filters_cannot_expose_drafts(self):
		meta = SimpleNamespace(has_field=lambda field: field in {"publication_status", "sort_order"})
		with patch.object(frappe, "get_meta", return_value=meta):
			self.assertEqual(
				api._publication_filters("Blogs", {"category": "Events"}),
				{"category": "Events", "publication_status": "Published"},
			)
			self.assertEqual(
				api._publication_filters("Blogs", {"publication_status": "Draft"}),
				[
					["Blogs", "publication_status", "=", "Published"],
					["Blogs", "publication_status", "=", "Draft"],
				],
			)

	def test_get_doc_hides_unpublished_records_before_cache_lookup(self):
		meta = SimpleNamespace(has_field=lambda field: field == "publication_status")
		with (
			patch.object(frappe, "get_meta", return_value=meta),
			patch.object(frappe.db, "get_value", return_value="Draft"),
			patch.object(self.cache, "get_value") as cache_get,
			self.assertRaises(frappe.DoesNotExistError),
		):
			api.get_doc("Blogs", "BLOG-DRAFT")
		cache_get.assert_not_called()

	def test_list_docs_enforces_published_filter_order_and_pagination(self):
		meta = SimpleNamespace(has_field=lambda field: field in {"publication_status", "sort_order"})
		rows = [
			{"name": "BLOG-1", "publication_status": "Published", "sort_order": 10},
			{"name": "BLOG-2", "publication_status": "Published", "sort_order": 20},
		]
		with (
			patch.object(frappe, "get_meta", return_value=meta),
			patch.object(frappe, "get_all", return_value=rows) as get_all,
			patch.object(frappe.db, "count", return_value=4) as count,
		):
			result = api.list_docs("Blogs", limit=2, start=1, filters=json.dumps({"category": "Events"}))

		self.assertEqual(result["total"], 4)
		self.assertTrue(result["has_next"])
		self.assertEqual(result["start"], 1)
		kwargs = get_all.call_args.kwargs
		self.assertEqual(kwargs["order_by"], "sort_order asc, creation desc")
		self.assertEqual(kwargs["filters"], {"category": "Events", "publication_status": "Published"})
		self.assertEqual(count.call_args.kwargs["filters"], kwargs["filters"])

	def test_list_all_applies_publication_filter_to_each_content_doctype(self):
		def get_meta(doctype):
			return SimpleNamespace(has_field=lambda field: field in {"publication_status", "sort_order"} and doctype != "Site")

		with (
			patch.object(frappe, "get_meta", side_effect=get_meta),
			patch.object(frappe, "get_all", return_value=[]) as get_all,
		):
			result = api.list_all()

		self.assertEqual(set(result), set(api.PUBLIC_DOCTYPES))
		self.assertEqual(get_all.call_count, len(api.PUBLIC_DOCTYPES))
		for call in get_all.call_args_list:
			doctype = call.args[0]
			if doctype == "Site":
				self.assertIsNone(call.kwargs["filters"])
			else:
				self.assertEqual(
					call.kwargs["filters"],
					[[doctype, "publication_status", "=", "Published"]],
				)
