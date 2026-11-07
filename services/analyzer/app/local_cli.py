"""Try the whole pipeline on two local files, in memory (no cloud). Uses env vars like the service does.

  python -m app.local_cli <reference.jpg> <photo.jpg>
Set JUDGE_MODE=vertex (+ GOOGLE_CLOUD_PROJECT, GEMINI_MODEL_FAST) to use the real Gemini.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.deps import build_deps
from pipeline.run import analyze_upload
from shared.schemas.models import LatLng, Reference, Spot


def main() -> None:
    ref_path, photo_path = Path(sys.argv[1]), Path(sys.argv[2])
    d = build_deps()
    d.storage.write("references/demo/ref1.jpg", ref_path.read_bytes())
    spot_id = d.repo.add_spot(Spot(siteId="site1", name="デモの撮影ポイント", location=LatLng(lat=0, lng=0),
                                   templateId="stone_wall"))
    # the in-memory repo numbers spots itself; re-key the upload under that id
    d.storage.write(f"uploads/{spot_id}/photo1.jpg", photo_path.read_bytes())
    d.repo.add_reference(Reference(spotId=spot_id, storagePath="references/demo/ref1.jpg"))
    res = analyze_upload(f"uploads/{spot_id}/photo1.jpg", "local-user", datetime.now(timezone.utc), d)
    out = {"outcome": res.outcome, "faces_blurred": res.faces_blurred, "max_confidence": res.max_confidence,
           "api_calls": res.api_calls, "quality": res.quality.model_dump() if res.quality else None}
    if res.detection_id:
        out["detection"] = json.loads(d.repo.get_detection(res.detection_id).model_dump_json())
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
