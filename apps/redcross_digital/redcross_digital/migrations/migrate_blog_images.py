import urllib.request
import json
import frappe
from frappe.utils.file_manager import save_file

def download_and_save(url: str, dt: str, dn: str, prefix: str) -> str:
    if not url or url.startswith("/files/"):
        return url
    
    print(f"Downloading {prefix} for {dn}: {url[:60]}...")
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
    
    # Determine extension
    ext = "jpg"
    if "png" in url.lower():
        ext = "png"
    elif "webp" in url.lower():
        ext = "webp"
    
    filename = f"blog_{prefix}_{dn}.{ext}"
    
    file_doc = save_file(
        fname=filename,
        content=content,
        dt=dt,
        dn=dn,
        is_private=0
    )
    print(f"Saved -> {file_doc.file_url}")
    return file_doc.file_url

def run():
    print("=" * 70)
    print("MIGRATING BLOG IMAGES TO FRAPPE")
    print("=" * 70)

    # Map author name to person avatar in Frappe
    people = frappe.get_all("Person", fields=["name", "full_name", "avatar"])
    person_avatar_map = {p["full_name"].strip(): p["avatar"] for p in people if p.get("avatar")}

    blogs = frappe.get_all("Blogs", fields=["name", "title", "cover_image", "gallery_images", "author"])

    for b in blogs:
        dn = b["name"]
        doc = frappe.get_doc("Blogs", dn)

        # 1. Cover image
        if doc.cover_image and not doc.cover_image.startswith("/files/"):
            doc.cover_image = download_and_save(doc.cover_image, "Blogs", dn, "cover")

        # 2. Gallery images
        if doc.gallery_images:
            try:
                gallery = json.loads(doc.gallery_images) if isinstance(doc.gallery_images, str) else doc.gallery_images
                if isinstance(gallery, list):
                    new_gallery = []
                    for idx, g_url in enumerate(gallery):
                        if g_url and not g_url.startswith("/files/"):
                            new_url = download_and_save(g_url, "Blogs", dn, f"gallery_{idx}")
                            new_gallery.append(new_url)
                        else:
                            new_gallery.append(g_url)
                    doc.gallery_images = json.dumps(new_gallery)
            except Exception as e:
                print(f"Error processing gallery for {dn}: {e}")

        # 3. Author avatar matching
        if doc.author:
            try:
                author_obj = json.loads(doc.author) if isinstance(doc.author, str) else doc.author
                if isinstance(author_obj, dict):
                    author_name = author_obj.get("name", "").strip()
                    if author_name in person_avatar_map:
                        author_obj["avatar"] = person_avatar_map[author_name]
                        print(f"Updated author avatar for {author_name} -> {person_avatar_map[author_name]}")
                    doc.author = json.dumps(author_obj)
            except Exception as e:
                print(f"Error processing author for {dn}: {e}")

        doc.save(ignore_permissions=True)
        print(f"Updated Blogs doc: {dn}")

    frappe.db.commit()
    print("FINISHED MIGRATING BLOG IMAGES!")
