import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { addReference, ApiError, listReferences, listSpots, setReferenceActive, type ReferenceRow, type SpotRow } from "../api";
import { SEASON_LABEL, TIME_LABEL } from "../utils";

/** Season / time-of-day reference photos of one spot (CLAUDE.md section 4, P1). The analyzer picks the closest one. */
export default function ReferencesPage() {
  const { id = "" } = useParams();
  const [spot, setSpot] = useState<SpotRow | null>(null);
  const [refs, setRefs] = useState<ReferenceRow[] | null>(null);
  const [error, setError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [season, setSeason] = useState("");
  const [timeOfDay, setTimeOfDay] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = () => listReferences(id).then(setRefs).catch(() => setError("基準写真を読み込めませんでした"));

  useEffect(() => {
    void reload();
    listSpots().then((all) => setSpot(all.find((s) => s.spotId === id) ?? null)).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function toggle(r: ReferenceRow) {
    setError("");
    try {
      await setReferenceActive(id, r.referenceId, !r.active);
      await reload();
    } catch (e) {
      setError(e instanceof ApiError && e.status === 409 ? "使用中の基準写真は1枚以上必要です" : "変更できませんでした");
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await addReference(id, file, season, timeOfDay);
      setFile(null);
      (e.target as HTMLFormElement).reset();
      await reload();
    } catch {
      setError("追加できませんでした");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="pad">
      <Link className="back" to="/map">‹ 地図へ戻る</Link>
      <div className="pagehead">
        <h1>{spot?.name ?? "基準写真"}</h1>
      </div>

      <form className="refadd" onSubmit={(e) => void add(e)}>
        <input type="file" accept="image/*" aria-label="基準写真" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
        <select value={season} onChange={(e) => setSeason(e.target.value)} aria-label="季節">
          <option value="">季節</option>
          {Object.entries(SEASON_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={timeOfDay} onChange={(e) => setTimeOfDay(e.target.value)} aria-label="時間帯">
          <option value="">時間帯</option>
          {Object.entries(TIME_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button className="primary" disabled={busy || !file}>{busy ? "追加しています…" : "追加"}</button>
      </form>

      {error && <p role="alert" className="error">{error}</p>}
      {!refs && !error && <p>読み込み中…</p>}
      {refs && refs.length === 0 && <div className="empty">基準写真がありません</div>}
      {refs && refs.length > 0 && (
        <ul className="refgrid">
          {refs.map((r) => (
            <li key={r.referenceId} className={`ref${r.active ? "" : " off"}`}>
              <img src={r.url} alt="" />
              <div className="body">
                <span>{[r.season && SEASON_LABEL[r.season], r.timeOfDay && TIME_LABEL[r.timeOfDay]].filter(Boolean).join("・") || "指定なし"}</span>
                <button className={`chip togglechip ${r.active ? "ok" : "plain"}`} onClick={() => void toggle(r)} aria-pressed={r.active}
                        title={r.active ? "押すと無効にします" : "押すと有効にします"}>
                  {r.active ? "使用中" : "無効"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
