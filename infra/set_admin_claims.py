"""Make a Firebase user an administrator of some sites (CLAUDE.md section 8: role="admin", siteIds=[...]).

  python infra/set_admin_claims.py <uid> <siteId> [<siteId> ...]

Uses application default credentials (gcloud auth application-default login). The user must sign out and in
again (or refresh the ID token) before the new claims take effect. Not yet run against a real project.
"""
import sys

import firebase_admin
from firebase_admin import auth


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    uid, site_ids = sys.argv[1], sys.argv[2:]
    firebase_admin.initialize_app()
    auth.set_custom_user_claims(uid, {"role": "admin", "siteIds": site_ids})
    print(f"{uid}: role=admin siteIds={site_ids}")


if __name__ == "__main__":
    main()
