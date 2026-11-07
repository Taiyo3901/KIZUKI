import { DETECTION_STATUS_LABEL, REVIEW_DECISIONS, type DetectionStatus, type ReviewDecision } from "@shared/types";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { decide, getDetection, type ChangeRow, type DetectionDetail } from "../api";
import { clampBox, formatDate, percent } from "../utils";

type Mode = "side" | "overlay";
type Size = { w: number; h: number };

const CHIP: Record<DetectionStatus, string> = {
  needs_review: "needs_review", confirmed_change: "confirmed_change", no_change: "ok", false_positive: "plain", monitoring: "plain",
};

/** Red boxes with a number each. The numbers match the list on the right; the hot one is drawn heavier. */
function Boxes({ changes, size, hot }: { changes: ChangeRow[]; size: Size; hot: number | null }) {
  return (
    <>
      <svg viewBox={`0 0 ${size.w} ${size.h}`} preserveAspectRatio="none" aria-hidden>
        {changes.map((c, i) => (
          <rect key={i} {...clampBox(c.box, size.w, size.h)} fill={hot === i ? "rgba(255,23,68,.18)" : "none"} stroke="#ff1744"
                strokeWidth={hot === i ? 5 : 3} vectorEffect="non-scaling-stroke" />
        ))}
      </svg>
      {changes.map((c, i) => {
        const b = clampBox(c.box, size.w, size.h);
        // Above the box so it does not hide what the box marks; inside when the box touches the top edge.
        const above = b.y / size.h > 0.06;
        return <span key={i} className="pin" style={{ position: "absolute", left: `${(b.x / size.w) * 100}%`, top: `${(b.y / size.h) * 100}%`, transform: above ? "translateY(-100%)" : undefined }}>{i + 1}</span>;
      })}
    </>
  );
}

/** A photo with the change boxes drawn on it. Box coordinates are pixels of the reference photo. */
function Boxed({ url, changes, size, hot, onSize }: { url: string; changes: ChangeRow[]; size: Size | null; hot: number | null; onSize?: (s: Size) => void }) {
  return (
    <div className="boxed">
      <img src={url} alt="" onLoad={(e) => onSize?.({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })} />
      {size && <Boxes changes={changes} size={size} hot={hot} />}
    </div>
  );
}

export default function DetectionPage() {
  const { id = "" } = useParams();
  const [d, setD] = useState<DetectionDetail | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("side");
  const [opacity, setOpacity] = useState(0.5);
  const [size, setSize] = useState<Size | null>(null);
  const [hot, setHot] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getDetection(id).then(setD).catch(() => setError("判定を読み込めませんでした"));
  }, [id]);

  async function choose(s: ReviewDecision) {
    setSaving(true);
    try {
      await decide(id, s);
      setD(await getDetection(id));
    } catch {
      setError("保存できませんでした");
    } finally {
      setSaving(false);
    }
  }

  // Keyboard: 1 / 2 / 3 choose a decision (as in a triage queue). Ignored while typing or with modifier keys.
  const canDecide = d !== null && d.status !== "no_change";
  useEffect(() => {
    if (!canDecide) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || (e.target as HTMLElement).closest("input, select, textarea")) return;
      const s = REVIEW_DECISIONS[Number(e.key) - 1];
      if (s && !saving) void choose(s);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canDecide, saving, id]);

  if (error) return <p role="alert" className="pad error">{error}</p>;
  if (!d) return <p className="pad">読み込み中…</p>;

  const reviewed = d.reviewedBy !== null;
  return (
    <main className="pad">
      <Link className="back" to="/queue">‹ 要確認の一覧へ戻る</Link>
      <div className="pagehead">
        <div>
          <h1>{d.spotName}</h1>
          <p className="muted">撮影：{formatDate(d.capturedAt)}</p>
        </div>
        <span className={`chip ${CHIP[d.status]}`}>{DETECTION_STATUS_LABEL[d.status]}</span>
      </div>

      <div className="review">
        <section aria-label="写真の比較">
          <div className="viewhead">
            <div className="segmented" role="group" aria-label="表示">
              <button className={mode === "side" ? "on" : ""} aria-pressed={mode === "side"} onClick={() => setMode("side")}>並べて見る</button>
              <button className={mode === "overlay" ? "on" : ""} aria-pressed={mode === "overlay"} onClick={() => setMode("overlay")}>重ねて見る</button>
            </div>
            {mode === "overlay" && (
              <label>
                投稿写真の濃さ
                <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
              </label>
            )}
          </div>

          {d.referenceUrl && d.photoUrl && mode === "side" && (
            <div className="pair">
              <figure><figcaption>基準写真</figcaption><Boxed url={d.referenceUrl} changes={d.changes} size={size} hot={hot} onSize={setSize} /></figure>
              <figure><figcaption>投稿写真</figcaption><Boxed url={d.photoUrl} changes={d.changes} size={size} hot={hot} /></figure>
            </div>
          )}
          {d.referenceUrl && d.photoUrl && mode === "overlay" && (
            <div className="boxed stack">
              <img src={d.referenceUrl} alt="" onLoad={(e) => setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })} />
              <img className="top" src={d.photoUrl} alt="" style={{ opacity }} />
              {size && <Boxes changes={d.changes} size={size} hot={hot} />}
            </div>
          )}
        </section>

        <aside className="panel">
          <p className="ai-note">{d.disclaimer}</p>

          <div className="card">
            <h2>AIが見つけた変化</h2>
            {d.changes.length === 0 ? <p className="muted">変化は見つかりませんでした。</p> : (
              <ul className="changes">
                {d.changes.map((c, i) => (
                  <li key={i} className={hot === i ? "hot" : ""} onMouseEnter={() => setHot(i)} onMouseLeave={() => setHot(null)}>
                    <span className="pin">{i + 1}</span>
                    <span className="what">{c.category}<span className="muted">　確信度 {percent(c.confidence)}</span></span>
                    <p className="why">{c.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {canDecide && (
            <div className="card">
              <h2>判定の確定</h2>
              <div className="decide">
                {REVIEW_DECISIONS.map((s, i) => (
                  <button key={s} disabled={saving} className={d.status === s ? "on" : ""} aria-pressed={d.status === s} onClick={() => void choose(s)}>
                    {DETECTION_STATUS_LABEL[s]}<kbd aria-hidden>{i + 1}</kbd>
                  </button>
                ))}
              </div>
              {reviewed && <p className="muted">{formatDate(d.reviewedAt)} に確定</p>}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
