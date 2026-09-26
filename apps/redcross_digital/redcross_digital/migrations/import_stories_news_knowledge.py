"""Idempotently import the website's knowledge, story and news content."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import frappe


APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = Path.home() / "redcross-digital"
SOURCE_FILES = {
    "Knowledge Resource": FRONTEND_ROOT / "src/data/knowledgeHubData.ts",
    "Digital Story": FRONTEND_ROOT / "src/data/digitalStories.ts",
    "News Item": FRONTEND_ROOT / "src/data/newsUpdates.ts",
}
IMAGE_ROOT = FRONTEND_ROOT / "public/assets/images/dt_updates"
RESOURCE_IMAGE_BY_ID = {
    "kr-001": "relief.jpg",
    "kr-002": "hunger.jpg",
    "kr-003": "app.jpg",
    "kr-004": "meeting.jpg",
    "kr-005": "teaching.jpg",
    "kr-006": "person_standing.jpg",
    "kr-007": "whites.jpg",
    "kr-008": "meeting.jpg",
}


def _extract_records(path: Path, variable: str) -> list[dict]:
    """Extract literal object records from the existing TypeScript datasets."""
    source = path.read_text(encoding="utf-8")
    match = re.search(rf"export const {re.escape(variable)}\s*:[^=]*=\s*\[", source)
    if not match:
        raise ValueError(f"Could not find {variable} array in {path}")
    start = match.end()
    depth = 1
    quote = None
    escaped = False
    end = start
    while end < len(source) and depth:
        char = source[end]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        end += 1
    if depth:
        raise ValueError(f"Unterminated {variable} array in {path}")

    body = source[start : end - 1]
    records = []
    index = 0
    while index < len(body):
        if body[index] != "{":
            index += 1
            continue
        object_start = index
        depth = 0
        quote = None
        escaped = False
        while index < len(body):
            char = body[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            elif char in ("'", '"', "`"):
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    index += 1
                    break
            index += 1
        records.append(json.loads(_typescript_object_to_json(body[object_start:index])))
    return records


def _typescript_object_to_json(value: str) -> str:
    """Convert this project's JSON-like object literals, including template strings."""
    # All keys are simple identifiers. Replace them only outside string literals.
    output = []
    index = 0
    quote = None
    escaped = False
    while index < len(value):
        char = value[index]
        if quote:
            if quote == "'":
                if escaped:
                    output.append("\\" + char)
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "'":
                    quote = None
                    output.append('"')
                elif char == '"':
                    output.append('\\"')
                elif char == "\n":
                    output.append("\\n")
                elif char == "\r":
                    output.append("\\r")
                else:
                    output.append(char)
            elif quote == "`":
                if escaped:
                    output.append("\\" + char)
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "`":
                    quote = None
                    output.append('"')
                elif char == '"':
                    output.append('\\"')
                elif char == "\n":
                    output.append("\\n")
                elif char == "\r":
                    output.append("\\r")
                else:
                    output.append(char)
            else:
                if escaped:
                    output.append("\\" + char)
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quote = None
                    output.append(char)
                else:
                    output.append(char)
            index += 1
            continue
        if char in ('"', "'", "`"):
            quote = char
            output.append('"')
            index += 1
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(value) and (value[end].isalnum() or value[end] == "_"):
                end += 1
            token = value[index:end]
            lookahead = end
            while lookahead < len(value) and value[lookahead].isspace():
                lookahead += 1
            if lookahead < len(value) and value[lookahead] == ":":
                output.append(json.dumps(token))
            elif token in ("true", "false", "null"):
                output.append(token)
            else:
                output.append(token)
            index = end
            continue
        output.append(char)
        index += 1
    converted = "".join(output)
    converted = re.sub(r",\s*([}\]])", r"\1", converted)
    return converted


def _copy_image(source_path: str | None) -> str | None:
    if not source_path:
        return None
    relative = source_path.removeprefix("/assets/images/dt_updates/")
    source = IMAGE_ROOT / relative
    if not source.is_file():
        raise FileNotFoundError(f"Source image missing: {source}")
    destination = Path(frappe.get_site_path("public", "files", source.name))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)
    return f"/files/{destination.name}"


def _upsert(doctype: str, key: str, external_id: str, values: dict) -> tuple[str, str]:
    field = {"Knowledge Resource": "knowledge_id", "Digital Story": "story_id", "News Item": "news_id"}[doctype]
    existing = frappe.db.get_value(doctype, {field: external_id}, "name")
    if existing:
        doc = frappe.get_doc(doctype, existing)
        action = "updated"
    else:
        action = "created"
        child_values = {name: values.pop(name) for name in list(values) if name in ("audience", "resources")}
        doc = frappe.get_doc({"doctype": doctype, **values})
        for fieldname, rows in child_values.items():
            for row in rows:
                doc.append(fieldname, row)
    if action == "updated":
        for fieldname, value in values.items():
            if fieldname in ("audience", "resources"):
                doc.set(fieldname, [])
                for row in value:
                    doc.append(fieldname, row)
            else:
                setattr(doc, fieldname, value)
    if action == "created":
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return action, doc.name


def _resource_values(item: dict) -> dict:
    # Resources have no image property in the TypeScript data. Preserve the
    # established image assignments while moving their files to Frappe.
    for label in item.get("audience", []):
        if not frappe.db.exists("Audience", label):
            frappe.get_doc({"doctype": "Audience", "audience_name": label}).insert(ignore_permissions=True)
    audience = [{"audience": label} for label in item.get("audience", [])]
    return {
        "knowledge_id": item["id"],
        "title": item["title"],
        "resource_type": item["type"],
        "date": item["date"],
        "department_text": item["department"],
        "owner_team": item["owner"],
        "version": item["version"],
        "description": item["description"],
        "audience": audience,
        "tags": json.dumps(item.get("tags", []), ensure_ascii=False),
        "cover_image": _copy_image(f"/assets/images/dt_updates/{RESOURCE_IMAGE_BY_ID[item['id']]}") if item["id"] in RESOURCE_IMAGE_BY_ID else None,
        "legacy_image_path": f"/assets/images/dt_updates/{RESOURCE_IMAGE_BY_ID[item['id']]}" if item["id"] in RESOURCE_IMAGE_BY_ID else None,
    }


def _story_values(item: dict) -> dict:
    return {
        "story_id": item["id"],
        "slug": item["slug"],
        "title": item["title"],
        "subtitle": item["subtitle"],
        "date": item["date"],
        "author": item["author"],
        "author_role": item["authorRole"],
        "tag": item["tag"],
        "cover_image": _copy_image(item.get("coverImage")),
        "challenge": item["challenge"],
        "people": item["people"],
        "solution": item["solution"],
        "experience": item["experience"],
        "learning": item["learning"],
        "impact": item["impact"],
        "safeguarding_note": item.get("safeguardingNote"),
    }


def _news_values(item: dict) -> dict:
    return {
        "news_id": item["id"],
        "slug": item["slug"],
        "title": item["title"],
        "date": item["date"],
        "author": item["author"],
        "department": item["department"],
        "category": item["category"],
        "summary": item["summary"],
        "content": item["content"],
        "resources": item.get("resources", []),
        "image_alt": item.get("imageAlt"),
    }


def run() -> dict:
    """Import every record; keep processing after a bad record and report failures."""
    definitions = [
        ("Knowledge Resource", "KNOWLEDGE_RESOURCES", _resource_values),
        ("Digital Story", "digitalStories", _story_values),
        ("News Item", "newsItems", _news_values),
    ]
    summary = {}
    for doctype, variable, map_values in definitions:
        source = SOURCE_FILES[doctype]
        records = _extract_records(source, variable)
        report = {"source": len(records), "created": 0, "updated": 0, "failed": 0}
        for item in records:
            try:
                values = map_values(item)
                action, name = _upsert(doctype, "id", item["id"], values)
                report[action] += 1
                print(f"{doctype} {action}: {item['id']} -> {name}")
            except Exception as error:
                report["failed"] += 1
                print(f"{doctype} FAILED {item.get('id', '<missing id>')}: {error}")
        summary[doctype] = dict(report)
        print(f"{doctype}: source={report['source']}, created={report['created']}, updated={report['updated']}, failed={report['failed']}")
    frappe.db.commit()
    return summary
