"""Production implementations on Firestore and Cloud Storage.

NOT yet exercised against a real project (needs the emulator or a deployed bucket); imports are lazy so
local runs and tests never need google-cloud-* packages.
"""
from datetime import datetime, timedelta, timezone

from shared.adapters.ports import Stored
from shared.schemas.models import Detection, Group, Photo, Reference, Site, Spot, Template


class GcsStorage:
    def __init__(self, bucket: str):
        import google.auth
        from google.cloud import storage
        # cloud-platform scope: the IAM signBlob call used for signed URLs is refused with Storage-only scopes
        creds, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self._client = storage.Client(credentials=creds, project=project)
        self._bucket = self._client.bucket(bucket)

    def read(self, path: str) -> bytes:
        return self._bucket.blob(path).download_as_bytes()

    def write(self, path: str, data: bytes, content_type: str = "image/jpeg") -> None:
        self._bucket.blob(path).upload_from_string(data, content_type=content_type)

    def delete(self, path: str) -> None:
        blob = self._bucket.blob(path)
        if blob.exists():
            blob.delete()

    def exists(self, path: str) -> bool:
        return self._bucket.blob(path).exists()

    def _signing_kwargs(self) -> dict:
        """On Cloud Run the credentials have no private key, so V4 signing must go through the IAM signBlob API:
        pass the service account's email and a fresh access token (it needs roles/iam.serviceAccountTokenCreator
        on itself). With a key-file credential the library signs locally and no extra arguments are needed."""
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        creds = self._client._credentials
        if isinstance(creds, service_account.Credentials):
            return {}
        if not creds.valid:
            creds.refresh(Request())
        return {"service_account_email": creds.service_account_email, "access_token": creds.token}

    def signed_upload_url(self, path: str, content_type: str, expires_s: int, headers: dict[str, str]) -> str:
        return self._bucket.blob(path).generate_signed_url(
            version="v4", expiration=timedelta(seconds=expires_s), method="PUT",
            content_type=content_type, headers=headers, **self._signing_kwargs())

    def signed_download_url(self, path: str, expires_s: int) -> str:
        return self._bucket.blob(path).generate_signed_url(
            version="v4", expiration=timedelta(seconds=expires_s), method="GET", **self._signing_kwargs())


def _dump(model) -> dict:
    return model.model_dump(mode="python")


class FirestoreRepository:
    def __init__(self, project: str | None = None):
        from google.cloud import firestore
        self._fs = firestore.Client(project=project)
        self._firestore = firestore

    # sites / templates
    def get_site(self, site_id: str) -> Site | None:
        d = self._fs.collection("sites").document(site_id).get()
        return Site(**d.to_dict()) if d.exists else None

    def get_template(self, template_id: str) -> Template | None:
        d = self._fs.collection("templates").document(template_id).get()
        return Template(**d.to_dict()) if d.exists else None

    # spots
    def get_spot(self, spot_id: str) -> Spot | None:
        d = self._fs.collection("spots").document(spot_id).get()
        return Spot(**d.to_dict()) if d.exists else None

    def list_spots(self, site_ids: list[str] | None) -> list[Stored[Spot]]:
        q = self._fs.collection("spots")
        if site_ids is not None:
            out: list[Stored[Spot]] = []
            for i in range(0, len(site_ids), 30):  # Firestore "in" supports up to 30 values
                for d in q.where("siteId", "in", site_ids[i:i + 30]).stream():
                    out.append(Stored(d.id, Spot(**d.to_dict())))
            return out
        return [Stored(d.id, Spot(**d.to_dict())) for d in q.stream()]

    def add_spot(self, spot: Spot) -> str:
        data = _dump(spot)
        data["createdAt"] = self._firestore.SERVER_TIMESTAMP
        _, ref = self._fs.collection("spots").add(data)
        return ref.id

    def set_spot_status(self, spot_id: str, status: str) -> None:
        self._fs.collection("spots").document(spot_id).update({"status": status})

    def update_spot(self, spot_id: str, fields: dict) -> None:
        self._fs.collection("spots").document(spot_id).update(fields)

    # groups
    def get_group(self, group_id: str) -> Group | None:
        d = self._fs.collection("groups").document(group_id).get()
        return Group(**d.to_dict()) if d.exists else None

    def list_groups(self, site_ids: list[str] | None) -> list[Stored[Group]]:
        q = self._fs.collection("groups")
        if site_ids is None:
            return [Stored(d.id, Group(**d.to_dict())) for d in q.stream()]
        out: list[Stored[Group]] = []
        for i in range(0, len(site_ids), 30):  # Firestore "in" supports up to 30 values
            out += [Stored(d.id, Group(**d.to_dict())) for d in q.where("siteId", "in", site_ids[i:i + 30]).stream()]
        return out

    def add_group(self, group: Group) -> str:
        data = _dump(group)
        data["createdAt"] = self._firestore.SERVER_TIMESTAMP
        _, ref = self._fs.collection("groups").add(data)
        return ref.id

    # references
    def list_references(self, spot_id: str, active_only: bool = True) -> list[Stored[Reference]]:
        q = self._fs.collection("references").where("spotId", "==", spot_id)
        if active_only:
            q = q.where("active", "==", True)
        return [Stored(d.id, Reference(**d.to_dict())) for d in q.stream()]

    def add_reference(self, ref: Reference) -> str:
        _, r = self._fs.collection("references").add(_dump(ref))
        return r.id

    def get_reference(self, reference_id: str) -> Reference | None:
        d = self._fs.collection("references").document(reference_id).get()
        return Reference(**d.to_dict()) if d.exists else None

    def update_reference(self, reference_id: str, fields: dict) -> None:
        self._fs.collection("references").document(reference_id).update(fields)

    # photos / detections
    def get_photo(self, photo_id: str) -> Photo | None:
        d = self._fs.collection("photos").document(photo_id).get()
        return Photo(**d.to_dict()) if d.exists else None

    def add_photo(self, photo: Photo) -> str:
        _, r = self._fs.collection("photos").add(_dump(photo))
        return r.id

    def add_detection(self, det: Detection) -> str:
        data = _dump(det)
        data["createdAt"] = self._firestore.SERVER_TIMESTAMP
        _, r = self._fs.collection("detections").add(data)
        return r.id

    def get_detection(self, detection_id: str) -> Detection | None:
        d = self._fs.collection("detections").document(detection_id).get()
        return Detection(**d.to_dict()) if d.exists else None

    def list_detections(self, site_ids: list[str] | None, status: str | None = None,
                        order_by: str = "createdAt") -> list[Stored[Detection]]:
        field = "maxConfidence" if order_by == "confidence" else "createdAt"
        direction = self._firestore.Query.DESCENDING
        out: list[Stored[Detection]] = []
        chunks = [None] if site_ids is None else [site_ids[i:i + 30] for i in range(0, len(site_ids), 30)]
        for chunk in chunks:
            q = self._fs.collection("detections")
            if chunk is not None:
                q = q.where("siteId", "in", chunk)
            if status:
                q = q.where("status", "==", status)
            # Needs a composite index (siteId, status, <order field>); see infra/firestore.indexes.json.
            for d in q.order_by(field, direction=direction).stream():
                out.append(Stored(d.id, Detection(**d.to_dict())))
        return out

    def update_detection(self, detection_id: str, fields: dict) -> None:
        self._fs.collection("detections").document(detection_id).update(fields)

    # upload rate limiting (a small log collection; documents expire via a Firestore TTL policy on "expireAt")
    def count_recent_uploads(self, uid: str, spot_id: str, window_s: int) -> int:
        since = datetime.now(timezone.utc) - timedelta(seconds=window_s)
        q = (self._fs.collection("uploadRequests").where("uid", "==", uid)
             .where("spotId", "==", spot_id).where("at", ">=", since))
        return sum(1 for _ in q.stream())

    def record_upload_request(self, uid: str, spot_id: str) -> None:
        now = datetime.now(timezone.utc)
        self._fs.collection("uploadRequests").add(
            {"uid": uid, "spotId": spot_id, "at": now, "expireAt": now + timedelta(days=1)})
