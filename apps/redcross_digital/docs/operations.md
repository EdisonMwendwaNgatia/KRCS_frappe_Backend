# Frappe API and operations guide

## System boundary

The Next.js application owns the public UI and form presentation. This app owns the structured website records and the API used to read and submit them. Public read methods are in `redcross_digital/api.py`; the frontend's admin proxy uses authenticated Frappe resource endpoints. Do not add a duplicate content API without a demonstrated limitation in these existing interfaces.

## Public API

All public methods are whitelisted with guest access. They are read-only except for the three narrowly-scoped submission handlers.

| Method | Request | Response / behavior |
| --- | --- | --- |
| `redcross_digital.api.list_docs` | `GET ?doctype=<DocType>&limit=100&start=0&filters=<JSON>` | `message.data`, `total`, `limit`, `start`, and `has_next`. The limit is capped at 500. Filters can be JSON objects or Frappe filter lists. |
| `redcross_digital.api.get_doc` | `GET ?doctype=<DocType>&name=<document name>` | One scrubbed record. Unpublished documents return not found for publication-aware types. |
| `redcross_digital.api.get_site_config` | `GET` | The first `Site` record as site configuration. |
| `redcross_digital.api.list_all` | `GET` | One map keyed by the public DocType names, with up to 1,000 records per type. |
| `redcross_digital.api.submit_feedback` | `POST` JSON | Validates and inserts a `Feedback` record. |
| `redcross_digital.api.submit_inquiry` | `POST` JSON | Validates and inserts an `Inquiry` record. |
| `redcross_digital.api.submit_partnership_proposal` | `POST` JSON | Validates and inserts a `Partnership Proposal` record. |

Example collection call:

```text
/api/method/redcross_digital.api.list_docs?doctype=Knowledge%20Resource&limit=50&start=0
```

The public content allowlist currently contains `Site`, `Testimonials`, `Blogs`, `Countries`, `Partners`, `Thematic Areas`, `Projects`, `Person`, `Innovations`, `Knowledge Resource`, `Digital Story`, and `News Item`. Contact submission DocTypes must remain outside this allowlist.

### Publication visibility and ordering

All publishable content DocTypes have `publication_status`, `published_on`, and `sort_order`. The public list and single-record methods force `publication_status = Published`; caller filters cannot expose drafts or archived records. Lists use ascending `sort_order`, then descending creation time when that field exists. `Site` is not publication-gated. `list_all` returns these names with spaces as JSON object keys (for example, `message["Digital Story"]`).

The publishing fields are editorial inputs. To publish, set `publication_status` to `Published`, choose `published_on`, and assign `sort_order`; use `Draft` to hold content back and `Archived` to remove it from the public API. Status changes do not automatically set the date or order. Lower `sort_order` values display first. The `initialize_content_publishing` patch preserves existing public records by changing blank/Draft status values to Published once during migration. New records should be reviewed and assigned an explicit status and order.

Responses pass through `_clean()` / `_clean_child()`: internal metadata is removed, `Person.email` is scrubbed from public output, and fields stored as JSON strings are decoded where possible. Add new JSON-backed field names to `JSON_FIELDS` when the API should decode them.

Public responses are cached for 300 seconds. `hooks.py` registers `_bust_cache` after inserts, updates, and deletions; the hook clears keys prefixed by `pub_api:`.

## DocType inventory

The authoritative field definitions and permissions are the JSON files under `redcross_digital/kenya_red_cross_digital_transformation_platform/doctype/`. The following are the public website models and admin content types:

| DocType | Identifiers / key fields | Relationships and media |
| --- | --- | --- |
| `Person` | `external_id`, `slug`, `full_name`, `role`, `department`, `short_bio`, `bio`, `featured`, publishing fields | `avatar` is Attach Image; `expertise` is JSON; `email` is private/scrubbed from public API. |
| `Projects` | `external_id`, `slug`, `title`, `category`, `year`, description/challenge/solution/impact, `featured`, publishing fields | `image` is Attach Image; `gallery`, `technologies`, `countries`, `team_ids`, `partner_ids`, `impact_metrics` are JSON; `thematic_area_slug` references thematic content by slug. |
| `Countries` | `external_id`, `code`, `country_name`, `region`, active/initiative counts, publishing fields | `image` is Attach Image; coordinates and initiatives are JSON; `partner` is currently text. |
| `Thematic Areas` | `external_id`, `slug`, `number`, `title`, descriptions, publishing fields | Capabilities/impact metrics are JSON; `featured_image_url` is currently a URL/text field. |
| `Partners` | `external_id`, `partner_name`, `category`, `description`, website/focus, `featured`, publishing fields | `logo` is Attach Image. |
| `Testimonials` | `external_id`, quote, author, organization/location, category, `featured`, publishing fields | `avatar` is Attach Image. |
| `Blogs` | `external_id`, `slug`, `title`, excerpt, category, `published_date`, `read_time`, `featured`, publishing fields | `content`, `author`, `gallery_images`, `tags` are JSON; cover and author avatar paths may be Frappe files. |
| `Innovations` | `external_id`, title, category, status, period, narratives, publishing fields | `location` links to `Countries`; `lead` links to `Person`; team is text. |
| `Knowledge Resource` | `knowledge_id`, title, resource type, department/team, date/version, description, tags, publishing fields | `resource_type` links to `Resource Type`; `gallery` is a child table; `audience` is a Table MultiSelect; cover is Attach Image. |
| `Digital Story` | `story_id`, `slug`, title/subtitle, date, author, tag, narrative sections, safeguarding note, publishing fields | `cover_image` is Attach Image. |
| `News Item` | `news_id`, `slug`, title, date, author, department/category, summary/content, publishing fields | `resources` is a child table; `cover_image` is Attach Image. |
| `Site` | site name, short name, tagline, description, URLs | `contact` and `social` are JSON. It is a normal DocType in this schema, not a Frappe Single. |

The contact inbox contains `Inquiry`, `Partnership Proposal`, and Frappe's `Feedback` DocType. These are excluded from public read APIs. The app also defines child/helper DocTypes such as `Audience`, `Knowledge Audience`, `Knowledge Image`, `News Resource Link`, `Resource Type`, and innovation-step records; keep table/link fields consistent with those schemas.

## Contact submission validation and permissions

The Next.js contact route is a same-origin proxy to the existing Frappe method. Frappe independently checks the HTTP method, JSON/form payload shape, and a maximum 24 KiB request body. Text is trimmed, length-limited, and checked for invalid control characters. Email and phone values are validated; feedback choice values must belong to server-side allowlists; feedback requires privacy acceptance. A non-empty `website_url` honeypot is silently discarded with a success-shaped response.

`submit_feedback` is limited to 30 calls per hour per rate-limit identity; inquiry and partnership methods are limited to 10 per hour. The Frappe decorator also considers the request IP. The handlers insert with `ignore_permissions=True` only after validation; this is why public Guest DocType access is not needed.

`configure_contact_submission_permissions` sets Desk permissions on Feedback, Inquiry, and Partnership Proposal to System Manager read/write/create with delete disabled. Do not add Guest read, write, report, export, or delete permissions. The admin inbox is read-only; submission status handling is done in Frappe Desk unless a reviewed workflow change is implemented.

## Schema patches

`redcross_digital/patches.txt` runs these after DocType model synchronization:

1. `redcross_digital.patches.initialize_content_publishing`
2. `redcross_digital.patches.configure_contact_submission_permissions`

After adding/changing a DocType or patch, deploy the app and run `bench --site <site-name> migrate`. Patches are one-time migrations. Review data effects before writing any new patch; use a repeatable patch name and do not place one-off record imports in the patch list.

## Content and file migration tools

These utilities are run explicitly and are separate from `bench migrate`:

| Module | Purpose | Notes |
| --- | --- | --- |
| `redcross_digital.migrations.import_content.run` | Upsert Site, people, thematic areas, partners, countries, projects, blogs, testimonials, and innovations from `migration_data/*.json`. | Upserts on `external_id`; prints created/updated summaries. |
| `redcross_digital.migrations.import_stories_news_knowledge.run` | Import Knowledge Resource, Digital Story, and News Item from the frontend TypeScript datasets; copy selected local images to Frappe public files. | Idempotent by `knowledge_id`, `story_id`, and `news_id`; requires a checkout at `~/redcross-digital` and its source image files. Prints per-type failures and commits after processing. |
| `redcross_digital.migrations.migrate_person_images.run` | Attach local person photos to Person records. | Source directory is currently a hard-coded local frontend path; check it before running elsewhere. |
| `redcross_digital.migrations.migrate_blog_images.run` | Move blog cover/gallery media and map author avatars to Frappe file URLs. | Review its source paths and expected files before running. |
| `redcross_digital.scripts.migrate_partner_logos.run` | Copy partner logos to Frappe public files and update Partner records. | Uses paths relative to the bench; inspect expected sources and DocType names first. |

Examples (run only after confirming source data and target site):

```bash
cd /path/to/frappe-bench
bench --site <site-name> execute redcross_digital.migrations.import_content.run
bench --site <site-name> execute redcross_digital.migrations.import_stories_news_knowledge.run
```

Back up the database and public/private files, run these on a staging site first, and compare the created/updated/failed summaries before using the production site. Image scripts have local path assumptions and may replace attachment references. Verify files and record links after any migration. Keep original frontend assets until verification is complete.

## Files and images

Use Frappe `Attach Image` or `Attach` fields for managed media. Public attachment values are `/files/<filename>` and are linked to File records by Frappe's upload/migration code. Do not put private credentials or sensitive submissions in public files. The frontend adds the configured Frappe origin to relative file URLs.

## Development and verification

```bash
bench --site <site-name> run-tests --module redcross_digital.test_api --test-category unit
```

The site must allow test runs (`bench --site <site-name> set-config allow_tests true`). The focused module uses Frappe `UnitTestCase` and mocks persistence for public submission/API rules. The per-DocType `IntegrationTestCase` files are currently generated placeholders; they do not yet provide meaningful record behavior coverage. Use a disposable site for integration tests.

For a public API smoke check, test each relevant `list_docs` call, one `get_doc` per DocType, filters, pagination, and `list_all`. Verify that drafts are excluded from guest reads, submission DocTypes are absent from `list_all`, and attachment URLs resolve from the configured frontend origin.
