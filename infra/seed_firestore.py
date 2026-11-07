"""Create the built-in templates (and, with --site, a site) in Firestore.

  python infra/seed_firestore.py [--site <siteId> <name> <adminUid>]

Run from the repository root with PYTHONPATH=. and GOOGLE_CLOUD_PROJECT set. Not yet run against a real project.
"""
import sys

from google.cloud import firestore

from shared.schemas.templates import BUILTIN_TEMPLATES


def main() -> None:
    db = firestore.Client()
    for template_id, t in BUILTIN_TEMPLATES.items():
        db.collection("templates").document(template_id).set(t.model_dump())
        print(f"template {template_id} written")
    if "--site" in sys.argv:
        site_id, name, admin_uid = sys.argv[sys.argv.index("--site") + 1:][:3]
        db.collection("sites").document(site_id).set({"name": name, "address": "", "adminUids": [admin_uid]})
        print(f"site {site_id} written")


if __name__ == "__main__":
    main()
