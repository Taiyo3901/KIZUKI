import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listDetections, type DetectionRow } from "../api";
import { DETECTION_LABEL, formatDate, percent, STATUS_FILTERS } from "../utils";

/** Same colours as the map's list: red = needs a look, amber = confirmed, green = no change, grey = the rest. */
const tone = (status: string) => (status === "no_change" ? "ok" : status === "needs_review" || status === "confirmed_change" ? status : "");

export default function QueuePage() {
  const [status, setStatus] = useState("needs_review");
  const [sort, setSort] = useState<"newest" | "confidence">("newest");
  const [rows, setRows] = useState<DetectionRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setRows(null);
    setError("");
    listDetections({ status, sort }).then(setRows).catch(() => setError("一覧を読み込めませんでした"));
  }, [status, sort]);

  return (
    <main className="pad">
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="状態">
          {STATUS_FILTERS.map((f) => (
            <button key={f.value} className={status === f.value ? "on" : ""} aria-pressed={status === f.value} onClick={() => setStatus(f.value)}>
              {f.label}
            </button>
          ))}
        </div>
        <label className="muted">
          並べ替え{" "}
          <select value={sort} onChange={(e) => setSort(e.target.value as "newest" | "confidence")}>
            <option value="newest">新しい順</option>
            <option value="confidence">確信度の高い順</option>
          </select>
        </label>
      </div>

      {error && <p role="alert" className="error">{error}</p>}
      {!rows && !error && <p>読み込み中…</p>}
      {rows && rows.length === 0 && (
        <div className="empty">{status === "needs_review" ? "確認待ちの判定はありません。" : "この状態の判定はありません。"}</div>
      )}
      {rows && rows.length > 0 && (
        <ul className="rows">
          <li className="rows-head" aria-hidden>
            <span>撮影ポイント</span><span>変化の種類</span><span>確信度</span><span>撮影日時</span><span>状態</span><span />
          </li>
          {rows.map((r) => (
            <li key={r.id}>
              <Link className={`row-link ${tone(r.status)}`} to={`/detections/${r.id}`}>
                <span className="spot">{r.spotName}</span>
                <span className="cats">
                  {r.categories.length ? r.categories.map((c) => <span key={c} className="cat">{c}</span>) : <span className="muted">—</span>}
                </span>
                <span className="conf">{percent(r.maxConfidence)}</span>
                <span className="when">{formatDate(r.createdAt)}</span>
                <span className={`chip ${tone(r.status)}`}>{DETECTION_LABEL[r.status]}</span>
                <span className="chev" aria-hidden>›</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
