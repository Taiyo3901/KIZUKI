"""API settings (environment variables)."""
import os
from dataclasses import dataclass


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    backend: str = os.environ.get("BACKEND", "local")              # local | gcp
    auth_mode: str = os.environ.get("AUTH_MODE", "dev")            # dev | firebase
    app_check: bool = os.environ.get("APP_CHECK", "off") == "on"   # verify Firebase App Check on upload-url
    bucket: str = os.environ.get("STORAGE_BUCKET", "")
    gcp_project: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    capture_base_url: str = os.environ.get("CAPTURE_BASE_URL", "http://localhost:5173")
    cors_origins: str = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174")
    max_edge_px: int = _i("MAX_UPLOAD_EDGE_PX", 2048)
    upload_url_expires_s: int = _i("UPLOAD_URL_EXPIRES_S", 300)
    download_url_expires_s: int = _i("DOWNLOAD_URL_EXPIRES_S", 3600)
    upload_limit: int = _i("UPLOAD_LIMIT_PER_WINDOW", 10)          # per anonymous uid and spot
    upload_window_s: int = _i("UPLOAD_WINDOW_S", 3600)
    # local development only
    dev_base_url: str = os.environ.get("DEV_BASE_URL", "http://localhost:8080")
    dev_analyze_on_upload: bool = os.environ.get("DEV_ANALYZE_ON_UPLOAD", "on") == "on"


SETTINGS = Settings()


def assert_safe_for_cloud(settings: Settings, env: dict | None = None) -> None:
    """Fail closed: on Cloud Run (K_SERVICE is set) the dev auth header and the in-memory backend must be off.
    Both default to "dev"/"local", so a deploy that forgets the environment variables would otherwise let
    anyone send `X-Dev-User: admin:...` and act as an administrator."""
    env = os.environ if env is None else env
    if env.get("K_SERVICE") and (settings.auth_mode != "firebase" or settings.backend != "gcp"):
        raise RuntimeError("Refusing to start on Cloud Run with AUTH_MODE!=firebase or BACKEND!=gcp")
