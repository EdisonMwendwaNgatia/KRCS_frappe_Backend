from pathlib import Path

import frappe
from frappe.utils.file_manager import save_file


SOURCE_DIR = Path("/home/edison/redcross-digital/public/assets/images/people")


def run():
    print("=" * 70)
    print("MIGRATING PERSON IMAGES TO FRAPPE")
    print("=" * 70)

    people = frappe.get_all(
        "Person",
        fields=["name", "external_id", "full_name", "avatar"],
        order_by="name",
    )

    if not people:
        frappe.throw("No Person records found.")

    migrated = 0
    skipped = 0

    for person in people:
        name = person["name"]
        external_id = person["external_id"]
        current_avatar = person.get("avatar")

        if not current_avatar:
            print(f"SKIPPED {external_id}: no avatar path configured")
            skipped += 1
            continue

        if current_avatar.startswith("/files/"):
            print(f"SKIPPED {external_id}: already using Frappe file {current_avatar}")
            skipped += 1
            continue

        if not current_avatar.startswith("/assets/images/people/"):
            print(
                f"SKIPPED {external_id}: unexpected avatar path {current_avatar}"
            )
            skipped += 1
            continue

        filename = Path(current_avatar).name
        source_path = SOURCE_DIR / filename

        if not source_path.exists():
            print(
                f"ERROR {external_id}: source image not found: {source_path}"
            )
            continue

        content = source_path.read_bytes()

        print(
            f"Uploading {external_id}: "
            f"{filename} ({len(content):,} bytes)"
        )

        file_doc = save_file(
            fname=filename,
            content=content,
            dt="Person",
            dn=name,
            is_private=0,
        )

        frappe.db.set_value(
            "Person",
            name,
            "avatar",
            file_doc.file_url,
        )

        print(
            f"UPDATED {external_id}: "
            f"{current_avatar} -> {file_doc.file_url}"
        )

        migrated += 1

    frappe.db.commit()

    print()
    print("=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"People found: {len(people)}")
    print(f"Images migrated: {migrated}")
    print(f"Skipped: {skipped}")
    print()
