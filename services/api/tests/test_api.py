"""API tests with in-memory storage/DB, dev auth headers and the demo seed. No network."""
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import SETTINGS
from app.deps import build_state, set_state
from app.dev_seed import SITE_ID, demo_wall
from shared.schemas.models import Box, Change, Detection, LatLng, Photo, Quality, Site, Spot

ADMIN = {"X-Dev-User": "admin:admin1:site1"}
ANON = {"X-Dev-User": "anon:tourist1"}


@pytest.fixture()
def env():
    st = build_state()  # local backend + demo seed: site1, one spot, one pending detection
    set_state(st)
    yield TestClient(main.app), st
    set_state(None)


def spot_id(st):
    return next(iter(st.repo.spots))


def det_id(st):
    return next(iter(st.repo.detections))


def jpeg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def add_other_site_detection(st):
    """A detection that belongs to a different site (site2)."""
    st.repo.sites["site2"] = Site(name="別の城")
    sid = st.repo.add_spot(Spot(siteId="site2", name="別の城の石垣", location=LatLng(lat=0, lng=0), templateId="stone_wall"))
    pid = st.repo.add_photo(Photo(siteId="site2", spotId=sid, storagePath="photos/x.jpg", capturedAt="2026-01-01T00:00:00Z",
                                  quality=Quality(passed=True), uploaderUid="u"))
    return st.repo.add_detection(Detection(siteId="site2", photoId=pid, spotId=sid, referenceId="r", maxConfidence=0.9,
                                           status="needs_review", changes=[Change(category="割れ", box=Box(x=1, y=1, width=1, height=1), confidence=0.9, reason="x")]))


# ------------------------------------------------------------ auth
def test_dev_auth_is_refused_on_cloud_run():
    from dataclasses import replace
    from app.config import assert_safe_for_cloud
    cloud = {"K_SERVICE": "api"}
    with pytest.raises(RuntimeError):
        assert_safe_for_cloud(SETTINGS, cloud)  # defaults are dev/local
    with pytest.raises(RuntimeError):
        assert_safe_for_cloud(replace(SETTINGS, auth_mode="firebase", backend="local"), cloud)
    assert_safe_for_cloud(replace(SETTINGS, auth_mode="firebase", backend="gcp"), cloud)
    assert_safe_for_cloud(SETTINGS, {})  # a developer's PC is fine


def test_missing_auth_is_401_and_anonymous_cannot_use_admin(env):
    c, _ = env
    assert c.get("/admin/detections").status_code == 401
    assert c.get("/admin/detections", headers=ANON).status_code == 403


# ------------------------------------------------------------ tourists
def test_public_spot_info_has_reference_urls_and_no_admin_data(env):
    c, st = env
    body = c.get(f"/spots/{spot_id(st)}").json()
    assert body["name"] and body["references"][0]["url"].startswith("http")
    assert set(body) == {"spotId", "name", "standingNote", "guideText", "guideLayout", "guideLayoutPortrait", "references"}
    assert c.get("/spots/nope").status_code == 404


def test_upload_url_carries_uid_and_is_rate_limited(env):
    c, st = env
    r = c.post(f"/spots/{spot_id(st)}/upload-url", headers=ANON).json()
    assert r["path"].startswith(f"uploads/{spot_id(st)}/") and r["path"].endswith(".jpg")
    assert r["headers"]["x-goog-meta-uid"] == "tourist1" and r["expiresInSeconds"] == SETTINGS.upload_url_expires_s
    for _ in range(SETTINGS.upload_limit - 1):
        assert c.post(f"/spots/{spot_id(st)}/upload-url", headers=ANON).status_code == 200
    assert c.post(f"/spots/{spot_id(st)}/upload-url", headers=ANON).status_code == 429
    # another visitor is not affected
    assert c.post(f"/spots/{spot_id(st)}/upload-url", headers={"X-Dev-User": "anon:other"}).status_code == 200


def test_upload_url_requires_login_and_existing_spot(env):
    c, st = env
    assert c.post(f"/spots/{spot_id(st)}/upload-url").status_code == 401
    assert c.post("/spots/nope/upload-url", headers=ANON).status_code == 404


def test_tourists_cannot_read_detections(env):
    c, st = env
    assert c.get(f"/admin/detections/{det_id(st)}", headers=ANON).status_code == 403


# ------------------------------------------------------------ admin
def test_admin_sees_only_own_site(env):
    c, st = env
    other = add_other_site_detection(st)
    ids = [d["id"] for d in c.get("/admin/detections", headers=ADMIN).json()]
    assert det_id(st) in ids and other not in ids
    assert c.get(f"/admin/detections/{other}", headers=ADMIN).status_code == 403
    assert all(s["siteId"] == SITE_ID for s in c.get("/admin/spots", headers=ADMIN).json())


def test_list_filters_and_sorting(env):
    c, st = env
    assert len(c.get("/admin/detections?status=needs_review", headers=ADMIN).json()) == 1
    assert c.get("/admin/detections?status=no_change", headers=ADMIN).json() == []
    assert c.get("/admin/detections?sort=confidence", headers=ADMIN).status_code == 200
    assert c.get("/admin/detections?sort=zzz", headers=ADMIN).status_code == 422


def test_detail_has_images_changes_and_ai_disclaimer(env):
    c, st = env
    d = c.get(f"/admin/detections/{det_id(st)}", headers=ADMIN).json()
    assert d["photoUrl"] and d["referenceUrl"] and d["changes"][0]["box"]["width"] == 120
    assert "確定は管理者が行います" in d["disclaimer"]


def test_confirmed_change_keeps_the_spot_flagged(env):
    c, st = env
    r = c.patch(f"/admin/detections/{det_id(st)}", json={"status": "confirmed_change"}, headers=ADMIN)
    assert r.status_code == 200
    d = st.repo.get_detection(det_id(st))
    assert d.status == "confirmed_change" and d.reviewedBy == "admin1" and d.reviewedAt
    assert st.repo.get_spot(spot_id(st)).status == "confirmed_change"  # not back to "ok"


def test_false_positive_and_monitoring_return_the_spot_to_ok(env):
    c, st = env
    for decision in ("false_positive", "monitoring"):
        st.repo.update_detection(det_id(st), {"status": "needs_review"})
        st.repo.set_spot_status(spot_id(st), "needs_review")
        c.patch(f"/admin/detections/{det_id(st)}", json={"status": decision}, headers=ADMIN)
        assert st.repo.get_spot(spot_id(st)).status == "ok"


def test_waiting_review_takes_precedence_over_confirmed(env):
    c, st = env
    c.patch(f"/admin/detections/{det_id(st)}", json={"status": "confirmed_change"}, headers=ADMIN)
    st.repo.add_detection(Detection(siteId="site1", photoId="p", spotId=spot_id(st), referenceId="r", maxConfidence=0.9,
                                    status="needs_review", changes=[]))
    second = [i.id for i in st.repo.list_detections(["site1"], status="needs_review")][0]
    st.repo.set_spot_status(spot_id(st), "needs_review")
    # reviewing the new one as a false positive leaves the earlier confirmed change visible
    c.patch(f"/admin/detections/{second}", json={"status": "false_positive"}, headers=ADMIN)
    assert st.repo.get_spot(spot_id(st)).status == "confirmed_change"


def test_decision_rules(env):
    c, st = env
    assert c.patch(f"/admin/detections/{det_id(st)}", json={"status": "needs_review"}, headers=ADMIN).status_code == 422
    other = add_other_site_detection(st)
    assert c.patch(f"/admin/detections/{other}", json={"status": "false_positive"}, headers=ADMIN).status_code == 403
    st.repo.update_detection(det_id(st), {"status": "no_change"})
    assert c.patch(f"/admin/detections/{det_id(st)}", json={"status": "confirmed_change"}, headers=ADMIN).status_code == 409


def test_create_spot_returns_capture_url_and_respects_site_access(env):
    c, st = env
    body = {"siteId": "site1", "name": "新しい場所", "location": {"lat": 1, "lng": 2}, "templateId": "stone_wall"}
    r = c.post("/admin/spots", json=body, headers=ADMIN)
    assert r.status_code == 201 and r.json()["captureUrl"].endswith(f"/capture/{r.json()['spotId']}")
    assert c.post("/admin/spots", json={**body, "siteId": "site2"}, headers=ADMIN).status_code == 403
    assert c.post("/admin/spots", json={**body, "templateId": "nope"}, headers=ADMIN).status_code == 422


def test_reference_upload_is_resized_to_max_edge(env):
    c, st = env
    big = np.random.default_rng(0).integers(0, 255, (1500, 3000, 3), dtype=np.uint8)
    r = c.post(f"/admin/spots/{spot_id(st)}/references", headers=ADMIN,
               files={"file": ("big.jpg", jpeg(big), "image/jpeg")}, data={"season": "winter", "timeOfDay": "morning"})
    assert r.status_code == 201 and max(r.json()["width"], r.json()["height"]) == SETTINGS.max_edge_px
    assert c.post(f"/admin/spots/{spot_id(st)}/references", headers=ADMIN,
                  files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 422
    assert c.post(f"/admin/spots/{spot_id(st)}/references", headers=ADMIN, data={"season": "monsoon"},
                  files={"file": ("a.jpg", jpeg(big), "image/jpeg")}).status_code == 422


def test_reference_management_lists_toggles_and_keeps_one_active(env):
    c, st = env
    sid = spot_id(st)
    first = c.get(f"/admin/spots/{sid}/references", headers=ADMIN).json()
    assert len(first) == 1 and first[0]["active"] is True and first[0]["url"]
    only = first[0]["referenceId"]
    # the last active reference cannot be switched off
    assert c.patch(f"/admin/spots/{sid}/references/{only}", json={"active": False}, headers=ADMIN).status_code == 409
    big = np.random.default_rng(1).integers(0, 255, (300, 400, 3), dtype=np.uint8)
    new = c.post(f"/admin/spots/{sid}/references", headers=ADMIN, data={"season": "autumn"},
                 files={"file": ("a.jpg", jpeg(big), "image/jpeg")}).json()["referenceId"]
    assert c.patch(f"/admin/spots/{sid}/references/{only}", json={"active": False}, headers=ADMIN).status_code == 200
    rows = {r["referenceId"]: r for r in c.get(f"/admin/spots/{sid}/references", headers=ADMIN).json()}
    assert rows[only]["active"] is False and rows[new]["active"] is True and rows[new]["season"] == "autumn"
    # tourists only get the active ones
    assert [r["referenceId"] for r in c.get(f"/spots/{sid}").json()["references"]] == [new]
    assert c.patch(f"/admin/spots/{sid}/references/nope", json={"active": True}, headers=ADMIN).status_code == 404


def test_reference_management_respects_site_access_and_role(env):
    c, st = env
    other = add_other_site_detection(st)
    other_spot = st.repo.get_detection(other).spotId
    assert c.get(f"/admin/spots/{other_spot}/references", headers=ADMIN).status_code == 403
    assert c.get(f"/admin/spots/{spot_id(st)}/references", headers=ANON).status_code == 403


def test_dev_image_links_use_the_address_the_caller_used(env):
    c, st = env
    direct = c.get(f"/admin/spots/{spot_id(st)}/references", headers=ADMIN).json()[0]["url"]
    assert direct.startswith("http://testserver/dev-files/")
    via_phone = c.get(f"/admin/spots/{spot_id(st)}/references", headers={**ADMIN, "X-Dev-Public-Base": "https://192.168.3.3:5173/api"}).json()[0]["url"]
    assert via_phone.startswith("https://192.168.3.3:5173/api/dev-files/")


def test_groups_can_be_created_listed_and_assigned(env):
    c, st = env
    sid = spot_id(st)
    g = c.post("/admin/groups", json={"siteId": "site1", "name": "北面の石垣"}, headers=ADMIN)
    assert g.status_code == 201
    gid = g.json()["groupId"]
    assert [x["name"] for x in c.get("/admin/groups", headers=ADMIN).json()] == ["北面の石垣"]
    assert c.post("/admin/groups", json={"siteId": "site1", "name": "北面の石垣"}, headers=ADMIN).status_code == 409
    assert c.post("/admin/groups", json={"siteId": "site1", "name": "  "}, headers=ADMIN).status_code == 422
    assert c.patch(f"/admin/spots/{sid}", json={"groupId": gid}, headers=ADMIN).status_code == 200
    row = next(s for s in c.get("/admin/spots", headers=ADMIN).json() if s["spotId"] == sid)
    assert row["groupId"] == gid and row["captureUrl"].endswith(f"/capture/{sid}")
    assert c.patch(f"/admin/spots/{sid}", json={"groupId": None}, headers=ADMIN).status_code == 200
    assert st.repo.get_spot(sid).groupId is None


def test_guide_text_is_set_by_admin_and_reaches_the_phone(env):
    c, st = env
    sid = spot_id(st)
    assert c.get(f"/spots/{sid}").json()["guideText"] == ""
    r = c.patch(f"/admin/spots/{sid}", json={"guideText": "  石垣の積み方は「打込接」です。  "}, headers=ADMIN)
    assert r.status_code == 200
    assert c.get(f"/spots/{sid}").json()["guideText"] == "石垣の積み方は「打込接」です。"
    # a patch that only sets the group leaves the text alone, and vice versa
    gid = c.post("/admin/groups", json={"siteId": "site1", "name": "G"}, headers=ADMIN).json()["groupId"]
    c.patch(f"/admin/spots/{sid}", json={"groupId": gid}, headers=ADMIN)
    assert c.get(f"/spots/{sid}").json()["guideText"].startswith("石垣")
    c.patch(f"/admin/spots/{sid}", json={"guideText": ""}, headers=ADMIN)
    assert st.repo.get_spot(sid).groupId == gid and st.repo.get_spot(sid).guideText == ""
    # tourists cannot edit it
    assert c.patch(f"/admin/spots/{sid}", json={"guideText": "x"}, headers=ANON).status_code == 403
    # it can be given when a spot is created
    body = {"siteId": "site1", "name": "新しい場所", "location": {"lat": 1, "lng": 2}, "guideText": "ここは本丸です"}
    new_id = c.post("/admin/spots", json=body, headers=ADMIN).json()["spotId"]
    assert c.get(f"/spots/{new_id}").json()["guideText"] == "ここは本丸です"


def test_groups_respect_site_access(env):
    c, st = env
    add_other_site_detection(st)
    assert c.post("/admin/groups", json={"siteId": "site2", "name": "x"}, headers=ADMIN).status_code == 403
    other_gid = st.repo.add_group(__import__("shared.schemas.models", fromlist=["Group"]).Group(siteId="site2", name="他の城"))
    assert all(x["siteId"] == "site1" for x in c.get("/admin/groups", headers=ADMIN).json())
    # a spot cannot be put into another site's group, and tourists cannot manage groups
    assert c.patch(f"/admin/spots/{spot_id(st)}", json={"groupId": other_gid}, headers=ADMIN).status_code == 422
    assert c.get("/admin/groups", headers=ANON).status_code == 403
    body = {"siteId": "site1", "name": "新しい場所", "location": {"lat": 1, "lng": 2}, "groupId": other_gid}
    assert c.post("/admin/spots", json=body, headers=ADMIN).status_code == 422


# ------------------------------------------------------------ the whole local flow (phone -> analysis -> admin)
def test_local_flow_upload_triggers_analysis_and_shows_up_for_admin(env):
    c, st = env
    sid = spot_id(st)
    url = c.post(f"/spots/{sid}/upload-url", headers=ANON).json()
    path = url["path"]
    changed = demo_wall().copy()
    cv2.rectangle(changed, (300, 200), (420, 280), (30, 30, 200), -1)
    assert c.put(f"/dev-files/{path}", content=jpeg(changed), headers=url["headers"]).status_code == 200
    # the original is gone, the blurred copy and a new detection exist
    assert not st.storage.exists(path)
    new = [i for i in st.repo.list_detections([SITE_ID]) if i.data.model != "demo"]
    assert len(new) == 1 and new[0].data.status == "needs_review"
    assert any(p.uploaderUid == "tourist1" for p in st.repo.photos.values())
    # and the admin can see and open it
    assert c.get(f"/admin/detections/{new[0].id}", headers=ADMIN).status_code == 200


def test_dev_files_only_for_upload_and_reference_prefixes(env):
    c, _ = env
    assert c.put("/dev-files/photos/a/b.jpg", content=b"x").status_code == 403


def test_guide_layout_is_set_by_admin_validated_and_reaches_the_phone(env):
    c, st = env
    sid = spot_id(st)
    assert c.get(f"/spots/{sid}").json()["guideLayout"] is None
    layout = {"version": 1, "background": "#ffffff", "items": [
        {"id": "a", "type": "photo", "x": 0.05, "y": 0.05, "w": 0.5, "h": 0.5, "fit": "cover"},
        {"id": "b", "type": "text", "x": 0.6, "y": 0.05, "w": 0.35, "h": 0.9, "text": "本丸の石垣", "vertical": True,
         "fontSize": None, "color": "#1d2430", "background": None, "bold": False, "align": "start"},
        {"id": "c", "type": "rect", "x": 0.05, "y": 0.7, "w": 0.4, "h": 0.2, "fill": "#e8eef7", "stroke": None,
         "strokeWidth": 4, "radius": 12}]}
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": layout}, headers=ADMIN).status_code == 200
    got = c.get(f"/spots/{sid}").json()["guideLayout"]
    assert got["items"][1]["vertical"] is True and got["items"][1]["text"] == "本丸の石垣"
    # invalid: colour, box outside 0..1, unknown type, non-image data URL, anonymous caller
    bad_color = {**layout, "background": "red"}
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": bad_color}, headers=ADMIN).status_code == 422
    bad_box = {**layout, "items": [{**layout["items"][0], "w": 1.5}]}
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": bad_box}, headers=ADMIN).status_code == 422
    bad_type = {**layout, "items": [{"id": "z", "type": "script", "x": 0, "y": 0, "w": 1, "h": 1}]}
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": bad_type}, headers=ADMIN).status_code == 422
    bad_img = {**layout, "items": [{"id": "i", "type": "image", "x": 0, "y": 0, "w": 1, "h": 1, "src": "https://evil.example/x.png"}]}
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": bad_img}, headers=ADMIN).status_code == 422
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": layout}, headers=ANON).status_code == 403
    # null resets to the default arrangement
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": None}, headers=ADMIN).status_code == 200
    assert c.get(f"/spots/{sid}").json()["guideLayout"] is None


def test_portrait_layout_is_kept_separately_and_must_match_its_orientation(env):
    c, st = env
    sid = spot_id(st)
    item = {"id": "a", "type": "photo", "x": 0.05, "y": 0.05, "w": 0.5, "h": 0.5, "fit": "cover"}
    portrait = {"version": 1, "orientation": "portrait", "background": "#ffffff", "items": [item]}
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayoutPortrait": portrait}, headers=ADMIN).status_code == 200
    got = c.get(f"/spots/{sid}").json()
    assert got["guideLayoutPortrait"]["orientation"] == "portrait" and got["guideLayout"] is None
    # a portrait layout in the landscape slot (and the reverse) is refused
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayout": portrait}, headers=ADMIN).status_code == 422
    landscape = {**portrait, "orientation": "landscape"}
    assert c.patch(f"/admin/spots/{sid}", json={"guideLayoutPortrait": landscape}, headers=ADMIN).status_code == 422
