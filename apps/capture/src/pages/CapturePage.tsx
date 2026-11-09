import type { PublicSpot } from "@shared/types";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, getSpot, uploadPhoto } from "../api";
import { captureJpeg, drawCover, SMALL_H, SMALL_W, toGray } from "../camera";
import { config } from "../config";
import { AutoShutter, estimateOverlap, guidance, type Gray, type Overlap } from "../overlap";
import { composeGuideImage, hasGuide } from "../compose";
import { photoFileName, saveToPhone } from "../save";
import { pinchZoom, zoomRangeOf, type ZoomRange } from "../zoom";
import { currentPosition, distanceM, formatDistance } from "../sensors";

const TICK_MS = 250;
const RING_R = 34;
const RING_LEN = 2 * Math.PI * RING_R;
const SEEN_KEY = "kizuki.notes.seen";
/** After an automatic shot the shutter waits until the view has clearly moved off, so it does not fire again and again. */
const REARM_BELOW = 0.6;
type Phase = "loading" | "ready" | "error";
type Shot = {
  id: number; blob: Blob; thumb: string; name: string; status: "sending" | "sent" | "failed"; error?: string;
  /** The picture to save on the phone: the photo with the spot's guide text laid out beside it (see compose.ts). */
  saveBlob?: Blob; saveUrl?: string;
};

function notesSeen(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

function rememberNotes() {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    /* private mode: the notes simply show again next time */
  }
}

/** Which way to turn the camera, from the displacement estimate. Content shifted right = pan right. */
function arrows(o: Overlap | null, okScore: number, dead = 1) {
  if (!o || o.score >= okScore || o.bestScore < 0.2) return { up: false, down: false, left: false, right: false };
  return { up: o.dy < -dead, down: o.dy > dead, left: o.dx < -dead, right: o.dx > dead };
}

function NotesSheet({ onClose }: { onClose: () => void }) {
  return (
    <div className="sheet-backdrop">
      <section className="sheet" role="dialog" aria-modal="true" aria-labelledby="notes-title">
        <h2 id="notes-title">撮影の前に</h2>
        <ul>
          <li>ガイドに風景が重なると、自動で撮影されます</li>
          <li>石垣に触れたり、立入禁止の場所に入ったりしないでください</li>
          <li>歩きながら撮影しないでください</li>
          <li>ほかの人が大きく写らないようにしてください</li>
        </ul>
        <button className="primary" onClick={onClose} autoFocus>撮影を始める</button>
      </section>
    </div>
  );
}

export default function CapturePage() {
  const { spotId = "" } = useParams();
  const videoRef = useRef<HTMLVideoElement>(null);
  const refImgRef = useRef<HTMLImageElement>(null);
  const shooting = useRef(false);

  const [spot, setSpot] = useState<PublicSpot | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [camReady, setCamReady] = useState(false);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("カメラを起動しています…");
  const [progress, setProgress] = useState(0);
  const [overlap, setOverlap] = useState<Overlap | null>(null);
  const [ghost, setGhost] = useState(0.5);
  const [notesOpen, setNotesOpen] = useState(() => !notesSeen());
  const notesOpenRef = useRef(notesOpen);
  notesOpenRef.current = notesOpen;
  const [viewing, setViewing] = useState(false);
  const viewingRef = useRef(false);
  viewingRef.current = viewing;
  const [farFromSpot, setFarFromSpot] = useState<number | null>(null);
  const askedPosition = useRef(false);
  const [shots, setShots] = useState<Shot[]>([]);
  const nextShotId = useRef(1);
  // Pinch zoom. `zoom` is what the visitor asked for; `digital` is the part done by cropping on the phone
  // (all of it on iPhone, none where the camera zooms itself).
  const [zoom, setZoom] = useState(1);
  const range = useRef<ZoomRange>({ min: 1, max: 1, hardware: false });
  const trackRef = useRef<MediaStreamTrack | undefined>(undefined);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ dist: number; zoom: number } | null>(null);
  const digital = range.current.hardware ? 1 : zoom;
  const digitalRef = useRef(1);
  digitalRef.current = digital;
  // 1) spot info (reference photo URL)
  useEffect(() => {
    getSpot(spotId)
      .then((s) => (s.references.length ? setSpot(s) : fail("この撮影ポイントには基準写真がまだ登録されていません")))
      .catch((e) => fail(e instanceof ApiError && e.status === 404 ? "撮影ポイントが見つかりません" : "通信に失敗しました"));
  }, [spotId]);

  function fail(msg: string) {
    setError(msg);
    setPhase("error");
  }

  // 2) camera: started at once, in parallel with the spot request (sign-in and a cold API start can take seconds)
  useEffect(() => {
    // `cancelled` makes a superseded run (React re-runs effects in development) stop quietly: its stream is
    // released and its late results are ignored, instead of interrupting the newer run's video.play().
    let cancelled = false;
    let stream: MediaStream | undefined;
    // Browsers hide `mediaDevices` entirely on pages that are not https (or localhost); say so instead of hanging.
    if (!navigator.mediaDevices?.getUserMedia) {
      fail("カメラを使えません。https で始まるアドレスで開いてください");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 2560 } }, audio: false })
      .then(async (s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        trackRef.current = s.getVideoTracks()[0];
        range.current = zoomRangeOf(trackRef.current);
        const v = videoRef.current!;
        v.srcObject = s;
        await v.play();
        if (!cancelled) setCamReady(true);
      })
      .catch(() => {
        if (!cancelled) fail("カメラを使えません。許可を確認してください");
      });
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // ready = camera running AND the spot (reference photo) loaded
  useEffect(() => {
    if (camReady && spot && phase === "loading") {
      setHint("ガイドを読み込んでいます…");
      setPhase("ready");
    }
  }, [camReady, spot, phase]);

  // 3) position check, once, after the notes are closed so the browser's prompt follows them.
  useEffect(() => {
    if (!spot || notesOpen || askedPosition.current) return;
    askedPosition.current = true;
    currentPosition()
      .then((here) => {
        const d = distanceM(here, spot.location);
        setFarFromSpot(d > config.nearSpotM ? d : null);
      })
      .catch(() => setFarFromSpot(null)); // declined or unavailable: simply no notice
  }, [spot, notesOpen]);

  function patchShot(id: number, patch: Partial<Shot>) {
    setShots((all) => all.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  async function send(shot: Shot) {
    patchShot(shot.id, { status: "sending", error: undefined });
    try {
      await uploadPhoto(spotId, shot.blob);
      patchShot(shot.id, { status: "sent" });
    } catch (e) {
      patchShot(shot.id, { status: "failed", error: e instanceof ApiError && e.status === 429 ? "撮影回数の上限です" : "送信できませんでした" });
    }
  }

  /** Takes one photo and sends it in the background, so the next one can be taken straight away. */
  async function shoot() {
    if (shooting.current || !videoRef.current) return;
    shooting.current = true;
    try {
      const blob = await captureJpeg(videoRef.current, config.maxUploadEdgePx, digitalRef.current);
      const shot: Shot = { id: nextShotId.current++, blob, thumb: URL.createObjectURL(blob), name: photoFileName(spotId), status: "sending" };
      setShots((all) => [...all, shot]);
      void send(shot);
      // build the saved picture in the background, so saving later is instant (sharing needs to run right after a tap)
      if (spot && hasGuide(spot)) {
        void composeGuideImage(blob, spot)
          .then((saveBlob) => patchShot(shot.id, { saveBlob, saveUrl: URL.createObjectURL(saveBlob) }))
          .catch(() => undefined); // falls back to the plain photo
      }
    } finally {
      shooting.current = false;
    }
  }

  // 4) overlap guidance + auto shutter
  useEffect(() => {
    if (phase !== "ready") return;
    const shutter = new AutoShutter(config.autoShutterScore, config.autoShutterHoldMs);
    let armed = true;
    const live = document.createElement("canvas");
    const ref = document.createElement("canvas");
    live.width = ref.width = SMALL_W;
    live.height = ref.height = SMALL_H;
    const lctx = live.getContext("2d", { willReadFrequently: true })!;
    const rctx = ref.getContext("2d", { willReadFrequently: true })!;
    let refGray: Gray | null = null;

    const id = setInterval(() => {
      const v = videoRef.current, img = refImgRef.current;
      if (!v || !img || !v.videoWidth || !img.complete || !img.naturalWidth) return;
      if (!refGray) {
        drawCover(rctx, img, img.naturalWidth, img.naturalHeight, SMALL_W, SMALL_H);
        refGray = toGray(rctx, SMALL_W, SMALL_H);
      }
      drawCover(lctx, v, v.videoWidth, v.videoHeight, SMALL_W, SMALL_H, digitalRef.current);
      const o = estimateOverlap(toGray(lctx, SMALL_W, SMALL_H), refGray);
      setOverlap(o);
      setHint(guidance(o, config.autoShutterScore));
      if (o.score < REARM_BELOW) armed = true;
      if (notesOpenRef.current || viewingRef.current || !armed) {
        shutter.reset(); // reading the notes, or the shot just taken is still lined up
        setProgress(0);
        return;
      }
      const now = performance.now();
      const fire = shutter.update(o.score, now);
      setProgress(shutter.progress(now));
      if (fire) {
        shutter.reset();
        armed = false;
        void shoot();
      }
    }, TICK_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  function applyZoom(z: number) {
    setZoom(z);
    if (range.current.hardware) void trackRef.current?.applyConstraints({ advanced: [{ zoom: z } as MediaTrackConstraintSet] }).catch(() => undefined);
  }

  const spread = () => {
    const [a, b] = [...pointers.current.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  };
  function onPointerDown(e: React.PointerEvent) {
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2) pinch.current = { dist: spread(), zoom };
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2 && pinch.current) {
      applyZoom(pinchZoom(pinch.current.zoom, pinch.current.dist, spread(), range.current.min, range.current.max));
    }
  }
  function onPointerEnd(e: React.PointerEvent) {
    pointers.current.delete(e.pointerId);
    pinch.current = null;
  }

  function closeNotes() {
    rememberNotes();
    setNotesOpen(false);
  }

  if (phase === "error")
    return (
      <main className="center">
        <p role="alert">{error}</p>
        {spot && <button onClick={() => setPhase("ready")}>もう一度撮る</button>}
      </main>
    );

  const aligned = overlap !== null && overlap.score >= config.autoShutterScore;
  const arrow = arrows(overlap, config.autoShutterScore);
  const last = shots[shots.length - 1];

  return (
    <main className="capture">
      <div className={`viewfinder${aligned ? " aligned" : ""}`} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
           onPointerUp={onPointerEnd} onPointerCancel={onPointerEnd}>
        <video ref={videoRef} playsInline muted style={digital > 1 ? { transform: `scale(${digital})` } : undefined} />
        {spot && (
          <img ref={refImgRef} className="overlay" style={{ opacity: ghost }} src={spot.references[0].url} alt="" crossOrigin="anonymous"
               onError={() => setHint("ガイドの画像を読み込めません")} />
        )}
        <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
        {arrow.up && <span className="arrow up" aria-hidden>▲</span>}
        {arrow.down && <span className="arrow down" aria-hidden>▼</span>}
        {arrow.left && <span className="arrow left" aria-hidden>◀</span>}
        {arrow.right && <span className="arrow right" aria-hidden>▶</span>}
        <div className="hint" aria-live="polite">{hint}</div>
      </div>

      {farFromSpot !== null && (
        <p className="notice" role="status">撮影ポイントから{formatDistance(farFromSpot)}離れています</p>
      )}

      {last && (
        <div className="shot" role="status">
          <button className="thumb" onClick={() => setViewing(true)} aria-label="写真を大きく表示"><img src={last.thumb} alt="" /></button>
          <span className={`shot-state ${last.status}`}>
            {shots.length}枚目　{last.status === "sending" ? "送信中" : last.status === "sent" ? "送信済み" : last.error}
          </span>
          {last.status === "failed" && <button className="chip" onClick={() => void send(last)}>再送信</button>}
          <button className="chip" onClick={() => void saveToPhone(last.saveBlob ?? last.blob, last.name)}>保存</button>
        </div>
      )}

      <div className="controls">
        <label className="ghost-control">
          <span>ガイドの濃さ</span>
          <input type="range" min={0.1} max={0.9} step={0.05} value={ghost} onChange={(e) => setGhost(Number(e.target.value))} />
        </label>
        <button className="shutter" onClick={() => void shoot()} disabled={phase !== "ready" || notesOpen || viewing} aria-label="撮影する">
          <svg viewBox="0 0 80 80" aria-hidden>
            <circle cx="40" cy="40" r={RING_R} className="ring-track" />
            <circle cx="40" cy="40" r={RING_R} className="ring-fill" style={{ strokeDasharray: RING_LEN, strokeDashoffset: RING_LEN * (1 - progress) }} />
          </svg>
          <span className="shutter-core" />
        </button>
        <div className="side-control">
          <button className="help" onClick={() => setNotesOpen(true)} aria-label="撮影の注意">?</button>
        </div>
      </div>

      {viewing && last && (
        <div className="viewer" role="dialog" aria-modal="true" aria-label="撮影した写真">
          <img src={last.saveUrl ?? last.thumb} alt="" />
          <button className="viewer-close" onClick={() => setViewing(false)} aria-label="閉じる">×</button>
          <button className="chip viewer-save" onClick={() => void saveToPhone(last.saveBlob ?? last.blob, last.name)}>保存</button>
        </div>
      )}
      {notesOpen && <NotesSheet onClose={closeNotes} />}
    </main>
  );
}
