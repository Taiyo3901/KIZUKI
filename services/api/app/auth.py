"""Authentication and authorization.

firebase mode: Firebase ID token in `Authorization: Bearer`. Tourists are anonymous users; admins carry the
custom claims role="admin" and siteIds=[...] (CLAUDE.md section 8). App Check token in `X-Firebase-AppCheck`.
ADMIN_OPEN=on (demo only): every signed-in user, anonymous ones too, is an administrator of ADMIN_OPEN_SITE_IDS.
dev mode (local only): `X-Dev-User: anon:<uid>` or `X-Dev-User: admin:<uid>:<siteId>,<siteId>`.
"""
from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException, Request

from app.config import SETTINGS


@dataclass
class Principal:
    uid: str
    is_admin: bool = False
    site_ids: list[str] = field(default_factory=list)


_firebase_ready = False


def _firebase():
    global _firebase_ready
    import firebase_admin
    if not _firebase_ready:
        firebase_admin.initialize_app()  # uses the Cloud Run service account / ADC
        _firebase_ready = True


def get_principal(authorization: str | None = Header(None), x_dev_user: str | None = Header(None)) -> Principal:
    if SETTINGS.auth_mode == "dev":
        if not x_dev_user:
            raise HTTPException(401, "X-Dev-User header required in dev mode")
        kind, _, rest = x_dev_user.partition(":")
        if kind == "anon":
            return Principal(uid=rest or "anon-dev")
        if kind == "admin":
            uid, _, sites = rest.partition(":")
            return Principal(uid=uid or "admin-dev", is_admin=True, site_ids=[s for s in sites.split(",") if s])
        raise HTTPException(401, "bad X-Dev-User")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    from firebase_admin import auth
    _firebase()
    try:
        claims = auth.verify_id_token(authorization.split(" ", 1)[1])
    except Exception:
        raise HTTPException(401, "invalid token")
    is_admin = claims.get("role") == "admin"
    site_ids = list(claims.get("siteIds", []))
    if SETTINGS.admin_open:   # demo mode: any valid token (anonymous too) may use the admin screen for the open sites
        is_admin = True
        site_ids = sorted(set(site_ids) | {s.strip() for s in SETTINGS.admin_open_site_ids.split(",") if s.strip()})
    return Principal(uid=claims["uid"], is_admin=is_admin, site_ids=site_ids)


def require_admin(p: Principal = Depends(get_principal)) -> Principal:
    if not p.is_admin:
        raise HTTPException(403, "admin only")
    return p


def check_site_access(p: Principal, site_id: str) -> None:
    if site_id not in p.site_ids:
        raise HTTPException(403, "no access to this site")


def verify_app_check(x_firebase_appcheck: str | None = Header(None)) -> None:
    """Rejects requests without a valid App Check token (only when APP_CHECK=on)."""
    if not SETTINGS.app_check:
        return
    if not x_firebase_appcheck:
        raise HTTPException(401, "missing App Check token")
    from firebase_admin import app_check
    _firebase()
    try:
        app_check.verify_token(x_firebase_appcheck)
    except Exception:
        raise HTTPException(401, "invalid App Check token")
