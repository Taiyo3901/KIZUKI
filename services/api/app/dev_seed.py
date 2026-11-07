"""Demo data for local development: one site, one spot with a reference photo, and one pending review."""
from datetime import datetime, timezone

import cv2
import numpy as np

from shared.schemas.models import Box, Change, Detection, LatLng, Photo, Quality, Reference, Site, Spot

SITE_ID = "site1"


def demo_wall(seed: int = 0, w: int = 1280, h: int = 853) -> np.ndarray:
    """A stone-like picture (NOT a real wall photo) so the screens have something to show."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 140, np.uint8)
    for y in range(0, h, 85):
        off = 0 if (y // 85) % 2 == 0 else 70
        for x in range(-off, w, 140):
            c = int(rng.integers(100, 180))
            cv2.rectangle(img, (x + 3, y + 3), (x + 137, y + 82), (c, c - 5, c - 15), -1)
    return np.clip(img.astype(np.float32) + rng.normal(0, 10, img.shape), 0, 255).astype(np.uint8)


def _jpeg(img: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()


def seed(repo, storage) -> None:
    from shared.schemas.templates import BUILTIN_TEMPLATES
    repo.sites[SITE_ID] = Site(name="デモ城", address="", adminUids=["admin-dev"])
    repo.templates.update(BUILTIN_TEMPLATES)

    spot = Spot(siteId=SITE_ID, name="北面の石垣（デモ）", location=LatLng(lat=35.1856, lng=136.8993),
                standingNote="石垣の正面、案内板の前から撮影してください", templateId="stone_wall", status="needs_review")
    spot_id = repo.add_spot(spot)

    ref_img = demo_wall()
    ref_path = f"references/{spot_id}/demo.jpg"
    storage.write(ref_path, _jpeg(ref_img))
    ref_id = repo.add_reference(Reference(spotId=spot_id, storagePath=ref_path, season="autumn", timeOfDay="day"))

    after = ref_img.copy()
    cv2.rectangle(after, (600, 400), (720, 480), (30, 30, 200), -1)
    photo_path = f"photos/{spot_id}/demo.jpg"
    storage.write(photo_path, _jpeg(after))
    photo_id = repo.add_photo(Photo(siteId=SITE_ID, spotId=spot_id, storagePath=photo_path,
                                    capturedAt=datetime.now(timezone.utc), quality=Quality(passed=True),
                                    uploaderUid="anon-demo"))
    det = Detection(siteId=SITE_ID, photoId=photo_id, spotId=spot_id, referenceId=ref_id,
                    changes=[Change(category="孕み出し", box=Box(x=600, y=400, width=120, height=80),
                                    confidence=0.82, reason="（デモデータ）石が前に出ているように見えます")],
                    maxConfidence=0.82, status="needs_review", model="demo", createdAt=datetime.now(timezone.utc))
    repo.add_detection(det)
