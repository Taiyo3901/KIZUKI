import type { SpotStatus } from "@shared/types";
import QRCode from "qrcode";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  createGroup, listDetections, listGroups, listReferences, listSpots, setSpotGroup,
  type DetectionRow, type GroupRow, type ReferenceRow, type SpotRow,
} from "../api";
import { config } from "../config";
import { hasMaps, loadMaps } from "../maps";
import { DETECTION_LABEL, formatDate, percent, SPOT_COLOR, SPOT_LABEL, SPOT_STATUSES } from "../utils";

function SpotItem({ s, onOpen }: { s: SpotRow; onOpen: (id: string) => void }) {
  return (
    <li style={{ ["--c" as string]: SPOT_COLOR[s.status] }}>
      <button className="linklike name" onClick={() => onOpen(s.spotId)}>{s.name}</button>
      <span className={`chip ${s.status}`}>{SPOT_LABEL[s.status]}</span>
    </li>
  );
}

/** Spots grouped by structure. With no groups at all, a plain list (no headings). */
function SpotList({ spots, groups, onOpen }: { spots: SpotRow[]; groups: GroupRow[]; onOpen: (id: string) => void }) {
  if (groups.length === 0) {
    return <ul className="spotlist">{spots.map((s) => <SpotItem key={s.spotId} s={s} onOpen={onOpen} />)}</ul>;
  }
  const known = new Set(groups.map((g) => g.groupId));
  const sections = [
    ...groups.map((g) => ({ id: g.groupId, name: g.name, items: spots.filter((s) => s.groupId === g.groupId) })),
    { id: "", name: "グループなし", items: spots.filter((s) => !s.groupId || !known.has(s.groupId)) },
  ].filter((sec) => sec.items.length > 0);
  return (
    <div className="groups">
      {sections.map((sec) => (
        <section key={sec.id || "none"}>
          <h2>{sec.name}<span className="muted">　{sec.items.length}</span></h2>
          <ul className="spotlist">{sec.items.map((s) => <SpotItem key={s.spotId} s={s} onOpen={onOpen} />)}</ul>
        </section>
      ))}
    </div>
  );
}

function Detail({ spot, groups, detections, onClose, onGroup }: {
  spot: SpotRow; groups: GroupRow[]; detections: DetectionRow[]; onClose: () => void; onGroup: (spotId: string, groupId: string | null) => void;
}) {
  const [refs, setRefs] = useState<ReferenceRow[]>([]);
  const [qr, setQr] = useState("");
  useEffect(() => {
    setRefs([]);
    listReferences(spot.spotId).then(setRefs).catch(() => undefined);
    QRCode.toDataURL(spot.captureUrl, { width: 320, margin: 2 }).then(setQr).catch(() => undefined);
  }, [spot.spotId, spot.captureUrl]);
  const mine = detections.filter((d) => d.spotId === spot.spotId).slice(0, 5);

  return (
    <section className="detail" aria-label="撮影ポイントの詳細">
      <div className="detail-head">
        <h2>{spot.name}</h2>
        <button className="icon" onClick={onClose} aria-label="閉じる">×</button>
      </div>
      <span className={`chip ${spot.status}`}>{SPOT_LABEL[spot.status]}</span>

      {groups.length > 0 && (
        <label className="field">グループ
          <select value={spot.groupId ?? ""} onChange={(e) => onGroup(spot.spotId, e.target.value || null)}>
            <option value="">なし</option>
            {groups.map((g) => <option key={g.groupId} value={g.groupId}>{g.name}</option>)}
          </select>
        </label>
      )}

      <h3>保存画像のレイアウト</h3>
      <p className="muted">観光客が保存する画像の、写真と案内文の配置を編集します。</p>
      <Link className="button" to={`/spots/${spot.spotId}/layout`}>レイアウトを編集</Link>

      <h3>最近の判定</h3>
      {mine.length === 0 ? <p className="muted">まだありません</p> : (
        <ul className="mini">
          {mine.map((d) => (
            <li key={d.id}>
              <Link to={`/detections/${d.id}`}>
                <span className={`chip ${d.status === "needs_review" ? "needs_review" : d.status === "no_change" ? "ok" : d.status === "confirmed_change" ? "confirmed_change" : "plain"}`}>{DETECTION_LABEL[d.status]}</span>
                <span>{d.categories.join("・") || "—"}</span>
                <span className="muted">{d.maxConfidence > 0 ? percent(d.maxConfidence) : ""}</span>
                <span className="muted">{formatDate(d.createdAt)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <h3>基準写真　<Link to={`/spots/${spot.spotId}/references`}>管理</Link></h3>
      <div className="thumbs">{refs.slice(0, 4).map((r) => <img key={r.referenceId} src={r.url} alt="" className={r.active ? "" : "off"} />)}</div>

      <h3>QRコード</h3>
      {qr && (
        <div className="qrrow">
          <img src={qr} alt="撮影画面へのQRコード" width={128} height={128} />
          <a className="button" href={qr} download={`spot-${spot.spotId}.png`}>画像を保存</a>
        </div>
      )}
    </section>
  );
}

export default function MapPage() {
  const [spots, setSpots] = useState<SpotRow[] | null>(null);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [detections, setDetections] = useState<DetectionRow[]>([]);
  const [error, setError] = useState("");
  const [mapFailed, setMapFailed] = useState(false);
  const [only, setOnly] = useState<SpotStatus | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [groupName, setGroupName] = useState("");
  const [groupFilter, setGroupFilter] = useState(""); // "" = all, "none" = ungrouped, otherwise a group id
  const [addingGroup, setAddingGroup] = useState(false);
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);

  useEffect(() => {
    listSpots().then(setSpots).catch(() => setError("撮影ポイントを読み込めませんでした"));
    listGroups().then(setGroups).catch(() => undefined);
    listDetections({}).then(setDetections).catch(() => undefined);
  }, []);

  const inGroup = (s: SpotRow) =>
    !groupFilter || (groupFilter === "none" ? !s.groupId || !groups.some((g) => g.groupId === s.groupId) : s.groupId === groupFilter);
  const shown = spots?.filter((s) => (!only || s.status === only) && inGroup(s)) ?? [];
  const current = spots?.find((s) => s.spotId === selected) ?? null;

  // 1) The map itself is created exactly once. (Creating it again whenever the data changed let two runs build a map
  //    on the same element at the same time, which left it blank until the page was visited again.)
  const markersRef = useRef<google.maps.marker.AdvancedMarkerElement[]>([]);
  const libsRef = useRef<{ Pin: typeof google.maps.marker.PinElement; Marker: typeof google.maps.marker.AdvancedMarkerElement } | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const firstCenter = useRef<{ lat: number; lng: number } | null>(null);
  if (spots && !firstCenter.current) firstCenter.current = spots[0]?.location ?? { lat: 35.68, lng: 139.77 };
  const haveSpots = spots !== null;

  useEffect(() => {
    if (!haveSpots || !hasMaps || mapRef.current || !el.current) return;
    let cancelled = false;
    loadMaps()
      .then(async () => {
        const { Map } = (await google.maps.importLibrary("maps")) as google.maps.MapsLibrary;
        const { AdvancedMarkerElement, PinElement } = (await google.maps.importLibrary("marker")) as google.maps.MarkerLibrary;
        if (cancelled || mapRef.current || !el.current) return;
        mapRef.current = new Map(el.current, { center: firstCenter.current!, zoom: 18, mapId: "DEMO_MAP_ID", mapTypeId: "hybrid" });
        libsRef.current = { Pin: PinElement, Marker: AdvancedMarkerElement };
        setMapReady(true);
      })
      .catch((e) => {
        console.error("map failed", e);
        setMapFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [haveSpots]);

  // 2) Pins follow the data and the filters; the map is left alone.
  useEffect(() => {
    const map = mapRef.current;
    const libs = libsRef.current;
    if (!mapReady || !map || !libs) return;
    for (const m of markersRef.current) m.map = null;
    markersRef.current = [];
    const bounds = new google.maps.LatLngBounds();
    for (const s of shown) {
      const pin = new libs.Pin({ background: SPOT_COLOR[s.status], borderColor: "#fff", glyphColor: "#fff" });
      const marker = new libs.Marker({ map, position: s.location, title: `${s.name}（${SPOT_LABEL[s.status]}）`, content: pin.element });
      marker.addListener("click", () => setSelected(s.spotId));
      markersRef.current.push(marker);
      bounds.extend(s.location);
    }
    if (shown.length > 1) map.fitBounds(bounds);
    else if (shown.length === 1) map.setCenter(shown[0].location);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapReady, spots, only, groupFilter, groups]);

  useEffect(() => {
    if (current) mapRef.current?.panTo(current.location);
  }, [current]);

  async function addGroup(e: FormEvent) {
    e.preventDefault();
    const name = groupName.trim();
    if (!name) return;
    try {
      const g = await createGroup(spots?.[0]?.siteId ?? config.devSiteIds[0] ?? "", name);
      setGroups((all) => [...all, g]);
      setGroupName("");
      setAddingGroup(false);
    } catch {
      setError("グループを作成できませんでした（同じ名前がないか確認してください）");
    }
  }

  async function moveToGroup(spotId: string, groupId: string | null) {
    try {
      await setSpotGroup(spotId, groupId);
      setSpots((all) => all?.map((s) => (s.spotId === spotId ? { ...s, groupId } : s)) ?? null);
    } catch {
      setError("グループを変更できませんでした");
    }
  }

  if (!spots) return error ? <p role="alert" className="pad error">{error}</p> : <p className="pad">読み込み中…</p>;

  const showMap = hasMaps && !mapFailed;
  const count = (st: SpotStatus) => spots.filter((s) => s.status === st).length;

  return (
    <main className={`mapshell${showMap ? "" : " nomap"}`}>
      <aside className="side">
        <div className="side-top">
          <div className="segmented" role="group" aria-label="状態で絞り込む">
            {SPOT_STATUSES.map((st) => (
              <button key={st} className={only === st ? "on" : ""} aria-pressed={only === st} onClick={() => setOnly(only === st ? null : st)}>
                <span className="dot" style={{ background: SPOT_COLOR[st] }} />{SPOT_LABEL[st]} {count(st)}
              </button>
            ))}
          </div>
          {groups.length > 0 && (
            <select className="groupsel" value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)} aria-label="表示するグループ">
              <option value="">すべてのグループ</option>
              {groups.map((g) => <option key={g.groupId} value={g.groupId}>{g.name}</option>)}
              <option value="none">グループなし</option>
            </select>
          )}
        </div>
        {error && <p role="alert" className="error side-msg">{error}</p>}
        <div className="side-body">
          {current ? (
            <Detail spot={current} groups={groups} detections={detections} onClose={() => setSelected(null)} onGroup={(id, g) => void moveToGroup(id, g)} />
          ) : spots.length === 0 ? <div className="empty">撮影ポイントがまだありません</div>
            : shown.length === 0 ? <div className="empty">該当なし</div>
            : <SpotList spots={shown} groups={groups} onOpen={setSelected} />}
        </div>
        <div className="side-foot">
          {addingGroup ? (
            <form className="addgroup" onSubmit={(e) => void addGroup(e)}>
              <input value={groupName} onChange={(e) => setGroupName(e.target.value)} placeholder="グループ名（例：天守台）" aria-label="グループ名" autoFocus />
              <button disabled={!groupName.trim()}>作成</button>
              <button type="button" onClick={() => { setAddingGroup(false); setGroupName(""); }}>やめる</button>
            </form>
          ) : (
            <button onClick={() => setAddingGroup(true)}>グループを作る</button>
          )}
          <Link className="button primary" to="/spots/new">撮影ポイントを追加</Link>
        </div>
      </aside>
      {showMap && <div ref={el} className="map" />}
    </main>
  );
}
