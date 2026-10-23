# Kenya Red Cross Digital Transformation Frappe app

This Frappe v16 app owns the website's content DocTypes, public read API, contact-submission handlers, publishing workflow, and related file migrations. The Next.js frontend calls this app through `redcross_digital.api` for public content and through authenticated Frappe REST resources for admin CRUD.

## Install and update

The app is installed into a Frappe bench, not run as a standalone Python service. On a new site:

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/EdisonMwendwaNgatia/KRCS_frappe_Backend.git --branch version-16
bench --site <site-name> install-app redcross_digital
```

After pulling app changes, sync DocTypes and execute queued patches:

```bash
cd /path/to/frappe-bench
bench --site <site-name> migrate
```

The bench supplies Frappe and its runtime dependencies. The app declares Python `>=3.14` in `pyproject.toml`. Install pre-commit hooks from this app directory with `pre-commit install`.

## Documentation

- [Operations, API contract, DocTypes, publishing, submissions, and migration procedures](docs/operations.md)

## Main modules

| Path | Purpose |
| --- | --- |
| `redcross_digital/api.py` | Public collection/single-record reads, public submissions, input validation, rate limits, response scrubbing, and public API cache invalidation. |
| `redcross_digital/kenya_red_cross_digital_transformation_platform/doctype/` | DocType schemas and controllers. JSON files are the version-controlled field and permission definitions. |
| `redcross_digital/patches.txt` and `redcross_digital/patches/` | Post-model-sync publishing initialization and contact-submission permission tightening. |
| `redcross_digital/migrations/` | Explicit content and file migration utilities. These are not all automatic schema patches. |
| `redcross_digital/test_api.py` | Focused unit tests for guest API behavior and submissions. |

## Testing

Run the focused unit module on a test site:

```bash
bench --site <site-name> set-config allow_tests true
bench --site <site-name> run-tests --module redcross_digital.test_api --test-category unit
# If tests were disabled before this run, restore that setting afterward:
bench --site <site-name> set-config allow_tests false
```

If `allow_tests` was already enabled, leave it enabled.

The tests mock document writes and cache interactions; they do not create production submissions. Use a disposable/test site for integration tests that exercise real Frappe records. Run `pre-commit run --all-files` for configured Ruff, formatting, and static checks.

## Operational guidance

Frappe is the system of record for website-managed content. Do not expose private submission DocTypes in the public allowlist or grant Guest roles direct access. Keep endpoint input validation and DocType permissions in sync, and use the migration patch workflow for schema/permission changes that must be applied on deployed sites.

Do not put site credentials, database passwords, or private session tokens in this repository or in frontend `NEXT_PUBLIC_*` variables. Configure site-specific values through Frappe site configuration and deployment environment settings.
