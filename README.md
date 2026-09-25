# KRCS Digital Transformation — Frappe Backend

## Overview

This repository contains the Frappe v16 backend powering the Kenya Red Cross Society (KRCS) Digital Transformation platform. It provides the content and data management layer for the platform, managing migrated platform data and exposing it through a set of public REST API endpoints.

The frontend is a separate Next.js application that consumes these API endpoints.

---

## Technology

- Frappe Framework v16
- Python
- MariaDB
- Redis
- Custom Frappe application: `redcross_digital`

---

## Repository Structure

```
apps/redcross_digital/   → custom KRCS Frappe application
config/                  → bench configuration (Redis, etc.)
sites/                   → Frappe site configuration
Procfile                 → process configuration
patches.txt              → bench patches
.gitignore               → Git ignore rules
```

> `apps/frappe/` is the upstream Frappe framework and is intentionally **not committed** to this repository. It is installed separately via `bench`.

---

## Data / DocTypes

The following content types are currently managed and exposed through the platform:

| DocType | Description |
|---------|-------------|
| `Site` | Singleton site-wide configuration document |
| `Person` | People profiles (team members, etc.) |
| `Projects` | KRCS projects and initiatives |
| `Partners` | Partner organisations |
| `Testimonials` | Testimonials from stakeholders |
| `Blogs` | Blog posts and articles |
| `Countries` | Country records |
| `Thematic Areas` | Thematic programme areas |
| `Innovations` | Innovation case studies |
| `Feedback` | Public feedback submissions |

---

## Public API

All public endpoints are guest-accessible (no authentication required).

### List records (paginated)

```
GET /api/method/redcross_digital.api.list_docs
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `doctype` | string | required | One of the public DocTypes listed above |
| `limit` | int | 100 | Records per page (max 500) |
| `start` | int | 0 | Pagination offset |
| `filters` | JSON | — | Optional filter object, e.g. `{"status":"Active"}` |

**Response:**
```json
{
  "data": [...],
  "total": 42,
  "limit": 100,
  "start": 0,
  "has_next": false
}
```

**Examples:**

```
GET /api/method/redcross_digital.api.list_docs?doctype=Projects&limit=100
GET /api/method/redcross_digital.api.list_docs?doctype=Partners&limit=100
GET /api/method/redcross_digital.api.list_docs?doctype=Person&limit=100
GET /api/method/redcross_digital.api.list_docs?doctype=Thematic%20Areas&limit=100
GET /api/method/redcross_digital.api.list_docs?doctype=Countries&limit=100
```

---

### Get a single document

```
GET /api/method/redcross_digital.api.get_doc?doctype=Blogs&name=<document-name>
```

Returns the full record for a single document by name.

---

### Get site configuration

```
GET /api/method/redcross_digital.api.get_site_config
```

Returns the singleton `Site` document containing platform-wide configuration.

---

### Get all public data (static build)

```
GET /api/method/redcross_digital.api.list_all
```

Returns all records across every public DocType in a single response. Intended for static site generation or full data hydration.

---

### Submit feedback

```
POST /api/method/redcross_digital.api.submit_feedback
```

Accepts public feedback submissions and saves them as `Feedback` documents in the database. Supports both identified and anonymous submission modes.

---

## Local Development

```bash
cd ~/frappe/redcross-bench
bench start
```

The local site is accessible at:

```
http://redcross.local:8000
```

Frappe admin panel:

```
http://redcross.local:8000/app
```

---

## Frontend Integration

The Next.js frontend consumes the backend API via the `NEXT_PUBLIC_FRAPPE_API_URL` environment variable:

```env
NEXT_PUBLIC_FRAPPE_API_URL=http://redcross.local:8000
```

Set this to the appropriate backend URL for your environment (local, staging, or production).

---

## Security

- **Never commit `site_config.json`** — it contains database credentials and local secrets.
- **Never commit database credentials**, API keys, or tokens to this repository.
- Environment-specific secrets must remain outside Git.
- Production credentials should be provided through deployment environment variables or a secrets manager.

---

## Deployment

The backend requires a Frappe-compatible hosting environment with MariaDB and Redis available. Deployment configuration will vary depending on the chosen hosting infrastructure (e.g. bare metal, Docker, managed hosting).
