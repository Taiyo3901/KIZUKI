"""Local-development storage: like MemoryStorage, but its "signed" URLs point at this API's /dev-files route
so a browser (capture / admin apps) can really PUT and GET images without any cloud."""
import time
from contextvars import ContextVar

from app.config import SETTINGS
from shared.adapters.memory import MemoryStorage


# The address the *caller* used to reach this API, set per request by main.py. The admin screen on the PC reaches it at
# http://localhost:8080; a phone reaches it through the capture dev server (https://<PC-IP>:5173/api), which says so in
# the X-Dev-Public-Base header. Images are linked with whichever the caller used, so each can actually load them.
CURRENT_BASE: ContextVar[str | None] = ContextVar("dev_base", default=None)


def _base() -> str:
    return CURRENT_BASE.get() or SETTINGS.dev_base_url


class DevHttpStorage(MemoryStorage):
    def signed_upload_url(self, path, content_type, expires_s, headers):
        return f"{_base()}/dev-files/{path}?exp={int(time.time()) + expires_s}"

    def signed_download_url(self, path, expires_s):
        return f"{_base()}/dev-files/{path}?exp={int(time.time()) + expires_s}"
