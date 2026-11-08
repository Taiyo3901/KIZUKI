import { cloneLayout, defaultLayout, textOf, type GuideLayout, type Orientation } from "@shared/guideLayout";
import { useEffect, useReducer, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listReferences, listSpots, setSpotGuideLayouts, type SpotRow } from "../api";
import LayoutEditor, { SlideThumb } from "../components/LayoutEditor";

/** Undo history of one layout. `change(next, true)` opens a new undo step, `change(next, false)` replaces the current one. */
interface Hist { steps: GuideLayout[]; at: number }
type Act = { t: "set"; l: GuideLayout } | { t: "change"; l: GuideLayout; push: boolean } | { t: "undo" } | { t: "redo" };
function reduce(h: Hist, a: Act): Hist {
  // one functional update: edits also arrive from window listeners that hold an old copy of the state
  switch (a.t) {
    case "set": return { steps: [a.l], at: 0 };
    case "change": return a.push ? { steps: [...h.steps.slice(0, h.at + 1), a.l], at: h.at + 1 } : { steps: [...h.steps.slice(0, h.at), a.l], at: h.at };
    case "undo": return { ...h, at: Math.max(0, h.at - 1) };
    case "redo": return { ...h, at: Math.min(h.steps.length - 1, h.at + 1) };
  }
}
const useHist = () => useReducer(reduce, { steps: [], at: 0 } as Hist);

const ICON = { undo: "M9 14 4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3", redo: "m15 14 5-5-5-5M20 9H10a6 6 0 0 0 0 12h3" };
const Ico = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>
);
/** Edits how the picture a visitor saves is arranged, one layout for landscape photos and one for portrait photos. */
export default function LayoutPage() {
  const { id = "" } = useParams();
  const [spots, setSpots] = useState<SpotRow[] | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [state, setState] = useState<"" | "saving" | "saved" | "failed">("");
  const [tab, setTab] = useState<Orientation>("landscape");
  const [hl, dl] = useHist();
  const [hp, dp] = useHist();
  const [saved, setSaved] = useState({ landscape: "", portrait: "" });
  const spot = spots?.find((s) => s.spotId === id) ?? null;

  useEffect(() => {
    listSpots().then(setSpots).catch(() => setError("読み込めませんでした"));
    listReferences(id).then((r) => setPhotoUrl((r.find((x) => x.active) ?? r[0])?.url ?? null)).catch(() => undefined);
  }, [id]);

  const loaded = useRef("");
  useEffect(() => {
    if (!spot || loaded.current === spot.spotId) return;
    loaded.current = spot.spotId;
    const land = spot.guideLayout ?? defaultLayout(spot.guideText ?? "", "landscape");
    const port = spot.guideLayoutPortrait ?? defaultLayout(spot.guideText?.trim() || textOf(spot.guideLayout), "portrait");
    dl({ t: "set", l: land });
    dp({ t: "set", l: port });
    setSaved({ landscape: JSON.stringify(land), portrait: JSON.stringify(port) });
  }, [spot, dl, dp]);

  const cur = { landscape: hl, portrait: hp };
  const layouts = { landscape: hl.steps[hl.at], portrait: hp.steps[hp.at] };
  const dispatch = tab === "landscape" ? dl : dp;
  const h = cur[tab];
  const layout = layouts[tab];
  const isDirty = (o: Orientation) => Boolean(layouts[o]) && JSON.stringify(layouts[o]) !== saved[o];
  const dirty = isDirty("landscape") || isDirty("portrait");

  const change = (l: GuideLayout, push: boolean) => { setState(""); dispatch({ t: "change", l, push }); };

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA") return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        dispatch({ t: e.shiftKey ? "redo" : "undo" });
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [dispatch]);

  useEffect(() => {
    if (!dirty) return;
    const on = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", on);
    return () => window.removeEventListener("beforeunload", on);
  }, [dirty]);

  async function save() {
    setState("saving");
    try {
      // only what was edited is sent, so a layout nobody touched stays "not set" (and follows the default)
      const body: { guideLayout?: GuideLayout; guideLayoutPortrait?: GuideLayout } = {};
      if (isDirty("landscape")) body.guideLayout = layouts.landscape;
      if (isDirty("portrait")) body.guideLayoutPortrait = layouts.portrait;
      await setSpotGuideLayouts(id, body);
      setSaved({ landscape: JSON.stringify(layouts.landscape), portrait: JSON.stringify(layouts.portrait) });
      setSpots((all) => all?.map((s) => (s.spotId === id ? { ...s, ...body } : s)) ?? null);
      setState("saved");
    } catch {
      setState("failed");
    }
  }

  if (error) return <p className="pad error">{error}</p>;
  if (!spots || !layout) return <p className="pad">読み込み中…</p>;
  if (!spot) return <p className="pad">撮影ポイントが見つかりません。<Link to="/map">地図へ戻る</Link></p>;

  const others = spots.filter((s) => s.spotId !== id && (tab === "landscape" ? s.guideLayout : s.guideLayoutPortrait));
  const copyFrom = (src: SpotRow | undefined) => {
    const l = tab === "landscape" ? src?.guideLayout : src?.guideLayoutPortrait;
    if (l) change(cloneLayout(l), true);
  };

  return (
    <div className="studio">
      <header className="studio-top">
        <Link className="back" to="/map" onClick={(e) => { if (dirty && !confirm("保存していない変更があります。破棄して戻りますか？")) e.preventDefault(); }}>← 地図</Link>
        <span className="doc"><b>{spot.name}</b><span>保存画像のレイアウト</span></span>
        <span className="grow" />
        <button className="ibtn" title="元に戻す (Ctrl+Z)" disabled={h.at === 0} onClick={() => dispatch({ t: "undo" })}><Ico d={ICON.undo} /></button>
        <button className="ibtn" title="やり直し (Ctrl+Shift+Z)" disabled={h.at >= h.steps.length - 1} onClick={() => dispatch({ t: "redo" })}><Ico d={ICON.redo} /></button>
        <details className="menu">
          <summary className="ibtn" title="その他">⋯</summary>
          <div className="menu-pop">
            {others.length > 0 && (
              <label>ほかのポイントからコピー（{tab === "landscape" ? "横向き" : "縦向き"}）
                <select value="" onChange={(e) => { copyFrom(others.find((s) => s.spotId === e.target.value)); e.target.closest("details")?.removeAttribute("open"); }}>
                  <option value="">選んでください</option>
                  {others.map((s) => <option key={s.spotId} value={s.spotId}>{s.name}</option>)}
                </select>
              </label>
            )}
            <button onClick={(e) => {
              if (confirm("この向きのレイアウトを、初期の配置に戻します。よろしいですか？")) {
                const words = layouts[tab === "landscape" ? "portrait" : "landscape"];
                change(defaultLayout(spot.guideText?.trim() || textOf(layout) || textOf(words), tab), true);
              }
              e.currentTarget.closest("details")?.removeAttribute("open");
            }}>この向きを初期配置に戻す</button>
          </div>
        </details>
        <span className={`savestate ${state}`} role="status">
          {state === "saving" ? "保存中…" : state === "failed" ? "保存できませんでした" : dirty ? "未保存の変更あり" : state === "saved" ? "保存しました" : ""}
        </span>
        <button className="primary small" onClick={() => void save()} disabled={state === "saving" || !dirty}>保存</button>
      </header>
      <LayoutEditor layout={layout} photoUrl={photoUrl} onChange={change}
        slides={(["landscape", "portrait"] as const).map((o, n) => (
          <SlideThumb key={o} layout={layouts[o]} photoUrl={photoUrl} active={tab === o} dirty={isDirty(o)}
                      label={`${n + 1}　${o === "landscape" ? "横向きの写真" : "縦向きの写真"}`} onClick={() => setTab(o)} />
        ))} />
    </div>
  );
}
