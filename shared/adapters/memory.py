"""In-memory / local-disk implementations for development and tests. No cloud access."""
import itertools
import time
from datetime import datetime, timezone
from pathlib import Path

from shared.adapters.ports import Stored
from shared.schemas.models import Detection, Group, Photo, Reference, Site, Spot, Template


class MemoryStorage:
    """Keeps objects in a dict; if root is given, mirrors them on disk (handy to look at results)."""

    def __init__(self, root: Path | None = None):
        self._objs: dict[str, bytes] = {}
        self._root = root

    def read(self, path: str) -> bytes:
        if path in self._objs:
            return self._objs[path]
        if self._root and (self._root / path).exists():
            return (self._root / path).read_bytes()
        raise FileNotFoundError(path)

    def write(self, path: str, data: bytes, content_type: str = "image/jpeg") -> None:
        self._objs[path] = data
        if self._root:
            f = self._root / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)

    def delete(self, path: str) -> None:
        self._objs.pop(path, None)
        if self._root and (self._root / path).exists():
            (self._root / path).unlink()

    def exists(self, path: str) -> bool:
        return path in self._objs or bool(self._root and (self._root / path).exists())

    def signed_upload_url(self, path: str, content_type: str, expires_s: int, headers: dict[str, str]) -> str:
        return f"memory://upload/{path}?exp={int(time.time()) + expires_s}"

    def signed_download_url(self, path: str, expires_s: int) -> str:
        return f"memory://download/{path}?exp={int(time.time()) + expires_s}"


class MemoryRepository:
    def __init__(self):
        self.sites: dict[str, Site] = {}
        self.templates: dict[str, Template] = {}
        self.spots: dict[str, Spot] = {}
        self.groups: dict[str, Group] = {}
        self.references: dict[str, Reference] = {}
        self.photos: dict[str, Photo] = {}
        self.detections: dict[str, Detection] = {}
        self._upload_log: list[tuple[str, str, float]] = []
        self._seq = itertools.count(1)

    def _id(self, prefix: str) -> str:
        return f"{prefix}{next(self._seq):04d}"

    # sites / templates
    def get_site(self, site_id): return self.sites.get(site_id)
    def get_template(self, template_id): return self.templates.get(template_id)

    # spots
    def get_spot(self, spot_id): return self.spots.get(spot_id)

    def list_spots(self, site_ids):
        return [Stored(i, s) for i, s in self.spots.items() if site_ids is None or s.siteId in site_ids]

    def add_spot(self, spot):
        sid = self._id("spot")
        self.spots[sid] = spot if spot.createdAt else spot.model_copy(update={"createdAt": datetime.now(timezone.utc)})
        return sid

    def set_spot_status(self, spot_id, status):
        self.spots[spot_id] = self.spots[spot_id].model_copy(update={"status": status})

    def update_spot(self, spot_id, fields):
        self.spots[spot_id] = type(self.spots[spot_id])(**{**self.spots[spot_id].model_dump(), **fields})  # validates

    # groups
    def get_group(self, group_id): return self.groups.get(group_id)

    def list_groups(self, site_ids):
        return [Stored(i, g) for i, g in self.groups.items() if site_ids is None or g.siteId in site_ids]

    def add_group(self, group):
        gid = self._id("grp")
        self.groups[gid] = group if group.createdAt else group.model_copy(update={"createdAt": datetime.now(timezone.utc)})
        return gid

    # references
    def list_references(self, spot_id, active_only=True):
        return [Stored(i, r) for i, r in self.references.items()
                if r.spotId == spot_id and (r.active or not active_only)]

    def add_reference(self, ref):
        rid = self._id("ref")
        self.references[rid] = ref
        return rid

    def get_reference(self, reference_id): return self.references.get(reference_id)

    def update_reference(self, reference_id, fields):
        self.references[reference_id] = self.references[reference_id].model_copy(update=fields)

    # photos / detections
    def get_photo(self, photo_id): return self.photos.get(photo_id)

    def add_photo(self, photo):
        pid = self._id("photo")
        self.photos[pid] = photo
        return pid

    def add_detection(self, det):
        did = self._id("det")
        # like Firestore's SERVER_TIMESTAMP: stamp the creation time if the caller did not
        self.detections[did] = det if det.createdAt else det.model_copy(update={"createdAt": datetime.now(timezone.utc)})
        return did

    def get_detection(self, detection_id): return self.detections.get(detection_id)

    def list_detections(self, site_ids, status=None, order_by="createdAt"):
        out = []
        for i, d in self.detections.items():
            if site_ids is not None and d.siteId not in site_ids:
                continue
            if status and d.status != status:
                continue
            out.append(Stored(i, d))
        key = (lambda s: s.data.maxConfidence) if order_by == "confidence" else (lambda s: s.data.createdAt or datetime.min.replace(tzinfo=timezone.utc))
        return sorted(out, key=key, reverse=True)

    def update_detection(self, detection_id, fields):
        self.detections[detection_id] = self.detections[detection_id].model_copy(update=fields)

    # upload rate limiting
    def count_recent_uploads(self, uid, spot_id, window_s):
        now = time.time()
        return sum(1 for u, s, t in self._upload_log if u == uid and s == spot_id and now - t < window_s)

    def record_upload_request(self, uid, spot_id):
        self._upload_log.append((uid, spot_id, time.time()))
