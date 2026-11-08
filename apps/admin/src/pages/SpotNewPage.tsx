import QRCode from "qrcode";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { addReference, createSpot, listGroups, listSpots, listTemplates, type GroupRow, type SpotRow, type TemplateRow } from "../api";
import { config } from "../config";
import { hasMaps, loadMaps, toLiteral } from "../maps";
import { SPOT_COLOR, SPOT_LABEL } from "../utils";

type Pos = { lat: number; lng: number };

/** Click the map (aerial photo or map) to place the spot; drag the pin to adjust. Existing spots are shown for context. */
function PickMap({ spots, onPick }: { spots: SpotRow[]; onPick: (p: Pos) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  useEffect(() => {
    if (!el.current) return;
    let cancelled = false;
    loadMaps()
      .then(async () => {
        if (cancelled || !el.current) return;
        const { Map } = (await google.maps.importLibrary("maps")) as google.maps.MapsLibrary;
        const { AdvancedMarkerElement, PinElement } = (await google.maps.importLibrary("marker")) as google.maps.MarkerLibrary;
        const map = new Map(el.current, {
          center: spots[0]?.location ?? { lat: 36.2, lng: 138.25 }, // all of Japan until there is a spot to look at
          zoom: spots.length ? 18 : 5,
          mapId: "DEMO_MAP_ID",
          mapTypeId: "hybrid",
          streetViewControl: false,
          fullscreenControl: false,
        });
        const bounds = new google.maps.LatLngBounds();
        for (const s of spots) {
          const pin = new PinElement({ background: SPOT_COLOR[s.status], borderColor: "#fff", glyphColor: "#fff", scale: 0.7 });
          new AdvancedMarkerElement({ map, position: s.location, title: `${s.name}（${SPOT_LABEL[s.status]}）`, content: pin.element });
          bounds.extend(s.location);
        }
        if (spots.length > 1) map.fitBounds(bounds);

        let marker: google.maps.marker.AdvancedMarkerElement | null = null;
        map.addListener("click", (e: google.maps.MapMouseEvent) => {
          const p = toLiteral(e.latLng);
          if (!p) return;
          if (!marker) {
            marker = new AdvancedMarkerElement({ map, position: p, gmpDraggable: true, title: "新しい撮影ポイント" });
            marker.addListener("dragend", () => {
              const q = toLiteral(marker!.position);
              if (q) onPickRef.current(q);
            });
          } else marker.position = p;
          onPickRef.current(p);
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [spots]);

  return <div ref={el} className="map pick" />;
}

export default function SpotNewPage() {
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [spots, setSpots] = useState<SpotRow[] | null>(null);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [groupId, setGroupId] = useState("");
  const siteId = config.devSiteIds[0] ?? "";
  const [name, setName] = useState("");
  const [pos, setPos] = useState<Pos | null>(null);
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [guideText, setGuideText] = useState("");
  const [templateId, setTemplateId] = useState("stone_wall");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ spotId: string; captureUrl: string; qr: string; name: string } | null>(null);

  useEffect(() => {
    listTemplates().then(setTemplates).catch(() => setError("テンプレートを読み込めませんでした"));
    listSpots().then(setSpots).catch(() => setSpots([]));
    listGroups().then(setGroups).catch(() => undefined);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const typed = lat !== "" && lng !== "" && !Number.isNaN(Number(lat)) && !Number.isNaN(Number(lng)) ? { lat: Number(lat), lng: Number(lng) } : null;
    const where = hasMaps ? pos : typed;
    if (!name.trim() || !file || !where) {
      setError(hasMaps ? "名前、地図上の位置、基準写真を入力してください" : "名前、緯度・経度、基準写真を入力してください");
      return;
    }
    setBusy(true);
    try {
      const spot = await createSpot({ siteId, name: name.trim(), standingNote: "", guideText, templateId, groupId: groupId || null, location: where });
      await addReference(spot.spotId, file, "", "");
      setResult({ ...spot, name: name.trim(), qr: await QRCode.toDataURL(spot.captureUrl, { width: 640, margin: 2 }) });
    } catch {
      setError("登録できませんでした");
    } finally {
      setBusy(false);
    }
  }

  if (result)
    return (
      <main className="pad">
        <div className="formcard qrcard">
          <h2>{result.name}</h2>
          <img className="qr" src={result.qr} alt="撮影画面へのQRコード" />
          <p className="muted">{result.captureUrl}</p>
          <div className="no-print" style={{ display: "flex", gap: 8 }}>
            <button className="primary" onClick={() => window.print()}>印刷</button>
            <a className="button" href={result.qr} download={`spot-${result.spotId}.png`}>画像を保存</a>
            <Link className="button" to="/map">完了</Link>
          </div>
        </div>
      </main>
    );

  return (
    <main className={`mapshell${hasMaps ? "" : " nomap"}`}>
      <form onSubmit={(e) => void submit(e)} className="side form">
        <div className="side-top">
          <Link to="/map" className="back">‹ 地図へ戻る</Link>
        </div>
        <div className="side-body fields">
          <label>名前<input value={name} onChange={(e) => setName(e.target.value)} placeholder="例：北面の石垣" /></label>
          {groups.length > 0 && (
            <label>グループ
              <select value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                <option value="">なし</option>
                {groups.map((g) => <option key={g.groupId} value={g.groupId}>{g.name}</option>)}
              </select>
            </label>
          )}
          {templates.length > 1 && (
            <label>対象
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                {templates.map((t) => <option key={t.templateId} value={t.templateId}>{t.name}</option>)}
              </select>
            </label>
          )}
          {hasMaps ? (
            <p className={`where${pos ? " set" : ""}`}>{pos ? `位置　${pos.lat.toFixed(6)}, ${pos.lng.toFixed(6)}` : "右の地図をクリックして、位置を決めます"}</p>
          ) : (
            <div className="row">
              <label>緯度<input inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="35.1856" /></label>
              <label>経度<input inputMode="decimal" value={lng} onChange={(e) => setLng(e.target.value)} placeholder="136.8993" /></label>
            </div>
          )}
          <label>解説文<textarea value={guideText} onChange={(e) => setGuideText(e.target.value)} rows={5} placeholder="撮影した写真と一緒に保存される案内文" /></label>
          <label>基準写真<input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
          {error && <p role="alert" className="error">{error}</p>}
        </div>
        <div className="side-foot">
          <button className="primary" disabled={busy}>{busy ? "登録しています…" : "登録"}</button>
        </div>
      </form>
      {hasMaps && spots && <PickMap spots={spots} onPick={setPos} />}
    </main>
  );
}
