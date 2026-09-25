"""
Run with:
  cd /home/edison/frappe/redcross-bench
  bench --site redcross.local execute redcross_digital.scripts.migrate_partner_logos.run

Or pipe directly:
  bench --site redcross.local execute \
    redcross_digital.scripts.migrate_partner_logos.run
"""

import frappe
import shutil
import os

# Map: Partners doc name → source image path (relative to bench root)
PARTNER_LOGOS = [
    ("esa",                  "../../redcross-digital/public/assets/images/partners/esa.jpg"),
    ("safaricom-foundation", "../../redcross-digital/public/assets/images/partners/safaricom_foundation.png"),
    ("university-nairobi",   "../../redcross-digital/public/assets/images/partners/uon.jpg"),
    ("world-bank",           "../../redcross-digital/public/assets/images/partners/GFDRR.jpeg"),
    ("google-org",           "../../redcross-digital/public/assets/images/partners/google.jpg"),
    ("un-ocha",              "../../redcross-digital/public/assets/images/partners/ocha.jpg"),
    ("icrc",                 "../../redcross-digital/public/assets/images/partners/icrc.jpg"),
    ("ifrc",                 "../../redcross-digital/public/assets/images/partners/ifrc.jpg"),
    ("krcs",                 "../../redcross-digital/public/assets/images/logo/KRCS_logo.jpeg"),
]


def run():
    bench_path = frappe.utils.get_bench_path()
    site = frappe.local.site
    public_files_dir = os.path.join(bench_path, "sites", site, "public", "files")
    os.makedirs(public_files_dir, exist_ok=True)

    for doc_name, rel_src in PARTNER_LOGOS:
        src = os.path.join(bench_path, rel_src)
        if not os.path.exists(src):
            print(f"  [SKIP] {doc_name}: source not found at {src}")
            continue

        filename = os.path.basename(src)
        dst = os.path.join(public_files_dir, filename)

        # Copy the file into Frappe's public/files
        shutil.copy2(src, dst)
        file_url = f"/files/{filename}"

        # Upsert a File doc so Frappe tracks it
        if not frappe.db.exists("File", {"file_url": file_url}):
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "file_url": file_url,
                "is_private": 0,
                "folder": "Home/Attachments",
                "attached_to_doctype": "Partners",
                "attached_to_name": doc_name,
            })
            file_doc.insert(ignore_permissions=True)

        # Update the Partners record
        doc = frappe.get_doc("Partners", doc_name)
        doc.logo = file_url
        doc.save(ignore_permissions=True)
        print(f"  [OK] {doc_name:25s} → {file_url}")

    frappe.db.commit()
    print("\nAll partner logos migrated.")
