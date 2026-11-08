import {
  MIN_BOX, canvasSize, drawLayout, loadLayoutImages, newId, newImage, newRect, newText,
  type Align, type Drawable, type GuideItem, type GuideLayout, type TextItem,
} from "@shared/guideLayout";
import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Editor for the picture a visitor saves (one layout for one photo orientation), laid out like a slide editor:
 * ribbon on top, slide list on the left, the slide in the middle, format pane on the right, status bar below.
 * The slide is the real canvas, drawn by the same code the phone uses, so what you see is what is saved; the boxes
 * on top are only handles for moving and resizing.
 * `onChange(layout, push)`: push = true starts a new undo step, false replaces the current one.
 */
type Dir = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
const HANDLES: Dir[] = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
const TYPE_LABEL: Record<GuideItem["type"], string> = { photo: "写真", text: "テキスト", rect: "図形", image: "画像" };

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

// ---------------------------------------------------------------- icons (16px, thin line)
const Icon = ({ children }: { children: ReactNode }) => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{children}</svg>
);
const I = {
  photo: <Icon><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10.5" r="1.6" /><path d="m4 17 5-4.5 4 3.5 3-2.5 4 3.5" /></Icon>,
  text: <Icon><path d="M5 7V5h14v2M12 5v14M9 19h6" /></Icon>,
  rect: <Icon><rect x="4" y="6" width="16" height="12" rx="2" /></Icon>,
  image: <Icon><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M12 16V9m0 0-3 3m3-3 3 3" /></Icon>,
  front: <Icon><path d="M12 15V5m0 0L8 9m4-4 4 4M5 20h14" /></Icon>,
  back: <Icon><path d="M12 9v10m0 0-4-4m4 4 4-4M5 4h14" /></Icon>,
  copy: <Icon><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a1 1 0 0 1 1-1h9" /></Icon>,
  trash: <Icon><path d="M4 7h16M10 11v6m4-6v6M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12M9 7V4h6v3" /></Icon>,
  horiz: <Icon><path d="M4 7h16M4 12h16M4 17h10" /></Icon>,
  vert: <Icon><path d="M7 4v16M12 4v16M17 4v10" /></Icon>,
  alignStart: <Icon><path d="M4 6h16M4 11h10M4 16h14" /></Icon>,
  alignCenter: <Icon><path d="M4 6h16M7 11h10M5 16h14" /></Icon>,
  alignEnd: <Icon><path d="M4 6h16M10 11h10M6 16h14" /></Icon>,
  bold: <Icon><path d="M7 5h6a3.5 3.5 0 0 1 0 7H7zM7 12h7a3.5 3.5 0 0 1 0 7H7z" /></Icon>,
};

/** Reads an image file and shrinks it so it fits in a layout (a layout is stored in one database document). */
async function fileToDataUrl(file: File): Promise<string> {
  const img = new Image();
  img.src = URL.createObjectURL(file);
  await img.decode();
  for (const edge of [640, 480, 320, 200]) {
    const k = Math.min(1, edge / Math.max(img.naturalWidth, img.naturalHeight));
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(img.naturalWidth * k));
    c.height = Math.max(1, Math.round(img.naturalHeight * k));
    c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
    for (const [type, q] of [["image/png", undefined], ["image/jpeg", 0.85]] as const) {
      const url = c.toDataURL(type, q);
      if (url.length <= 250_000) return url;
    }
  }
  throw new Error("too large");
}

function usePhoto(photoUrl: string | null): Drawable | null {
  const [photo, setPhoto] = useState<Drawable | null>(null);
  useEffect(() => {
    setPhoto(null);
    if (!photoUrl) return;
    const img = new Image();
    img.onload = () => setPhoto({ src: img, w: img.naturalWidth, h: img.naturalHeight });
    img.src = photoUrl;
  }, [photoUrl]);
  return photo;
}

function useImages(layout: GuideLayout): Map<string, Drawable> {
  const [images, setImages] = useState<Map<string, Drawable>>(new Map());
  const ref = useRef(layout);
  ref.current = layout;
  const key = layout.items.map((i) => (i.type === "image" ? i.id + i.src.length : "")).join("|");
  useEffect(() => {
    let live = true;
    void loadLayoutImages(ref.current).then((m) => live && setImages(m));
    return () => { live = false; };
  }, [key]);
  return images;
}

/** A small live picture of a layout, for the slide list. */
export function SlideThumb({ layout, photoUrl, active, label, dirty, onClick }: {
  layout: GuideLayout; photoUrl: string | null; active: boolean; label: string; dirty: boolean; onClick: () => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const photo = usePhoto(photoUrl);
  const images = useImages(layout);
  const size = canvasSize(layout.orientation);
  useEffect(() => {
    const g = ref.current?.getContext("2d");
    if (!g) return;
    const id = requestAnimationFrame(() => drawLayout(g, layout, photo, images));
    return () => cancelAnimationFrame(id);
  }, [layout, photo, images]);
  return (
    <button className={`slide${active ? " on" : ""}`} onClick={onClick} aria-pressed={active}>
      <span className="slide-label">{label}{dirty && <i className="dot" aria-label="未保存" />}</span>
      <span className="slide-pic" style={{ aspectRatio: `${size.w} / ${size.h}`, width: layout.orientation === "portrait" ? "62%" : "100%" }}>
        <canvas ref={ref} width={size.w} height={size.h} />
      </span>
    </button>
  );
}

export default function LayoutEditor({ layout, photoUrl, onChange, slides }: {
  layout: GuideLayout; photoUrl: string | null; onChange: (l: GuideLayout, push: boolean) => void; slides: ReactNode;
}) {
  const portrait = layout.orientation === "portrait";
  const size = canvasSize(layout.orientation);
  const [sel, setSel] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const stage = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const photo = usePhoto(photoUrl);
  const images = useImages(layout);
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  useEffect(() => setSel(null), [layout.orientation]);

  useEffect(() => {
    const g = canvas.current?.getContext("2d");
    if (!g) return;
    const id = requestAnimationFrame(() => drawLayout(g, layout, photo, images));
    return () => cancelAnimationFrame(id);
  }, [layout, photo, images]);

  const item = layout.items.find((i) => i.id === sel) ?? null;
  const hasPhoto = layout.items.some((i) => i.type === "photo");

  function setItems(items: GuideItem[], push: boolean) {
    onChange({ ...layoutRef.current, items }, push);
  }
  function patch(id: string, p: Partial<GuideItem>, push = true) {
    setItems(layoutRef.current.items.map((i) => (i.id === id ? ({ ...i, ...p } as GuideItem) : i)), push);
  }
  function add(i: GuideItem) {
    setItems([...layoutRef.current.items, i], true);
    setSel(i.id);
  }
  function remove(id: string) {
    setItems(layoutRef.current.items.filter((i) => i.id !== id), true);
    setSel(null);
  }
  function duplicate(i: GuideItem) {
    add({ ...structuredClone(i), id: newId(), x: clamp(i.x + 0.03, 0, 1 - i.w), y: clamp(i.y + 0.03, 0, 1 - i.h) } as GuideItem);
  }
  function reorder(id: string, to: "front" | "back") {
    const items = layoutRef.current.items;
    const it = items.find((i) => i.id === id)!;
    const rest = items.filter((i) => i.id !== id);
    setItems(to === "front" ? [...rest, it] : [it, ...rest], true);
  }

  function startDrag(e: React.PointerEvent, it: GuideItem, dir: Dir) {
    e.preventDefault();
    e.stopPropagation();
    setSel(it.id);
    stage.current?.focus();
    const rect = stage.current!.getBoundingClientRect();
    const sx = e.clientX, sy = e.clientY, o = { x: it.x, y: it.y, w: it.w, h: it.h };
    let started = false;
    const move = (ev: PointerEvent) => {
      const dx = (ev.clientX - sx) / rect.width, dy = (ev.clientY - sy) / rect.height;
      if (!started && Math.abs(dx) + Math.abs(dy) < 0.002) return;
      let { x, y, w, h } = o;
      if (dir === "move") {
        x = clamp(o.x + dx, 0, 1 - o.w);
        y = clamp(o.y + dy, 0, 1 - o.h);
      } else {
        if (dir.includes("e")) w = clamp(o.w + dx, MIN_BOX, 1 - o.x);
        if (dir.includes("s")) h = clamp(o.h + dy, MIN_BOX, 1 - o.y);
        if (dir.includes("w")) {
          x = clamp(o.x + dx, 0, o.x + o.w - MIN_BOX);
          w = o.x + o.w - x;
        }
        if (dir.includes("n")) {
          y = clamp(o.y + dy, 0, o.y + o.h - MIN_BOX);
          h = o.y + o.h - y;
        }
      }
      patch(it.id, { x, y, w, h }, !started); // the first move opens one undo step; the rest update it
      started = true;
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function onKey(e: React.KeyboardEvent) {
    const t = e.target as HTMLElement;
    if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT") return;
    if (!item) return;
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      remove(item.id);
      return;
    }
    const step = e.shiftKey ? 0.02 : 0.005;
    const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (d) {
      e.preventDefault();
      patch(item.id, { x: clamp(item.x + d[0], 0, 1 - item.w), y: clamp(item.y + d[1], 0, 1 - item.h) }, !e.repeat);
    }
  }

  async function pickImage(file: File | undefined) {
    if (!file) return;
    setNotice("");
    try {
      add(newImage(await fileToDataUrl(file)));
    } catch {
      setNotice("画像が大きすぎるか、読み込めませんでした");
    }
  }

  const p = (q: Partial<GuideItem>, push: boolean) => item && patch(item.id, q, push);

  return (
    <div className="studio-main" onKeyDown={onKey}>
      <div className="ribbon" role="toolbar" aria-label="書式">
        <div className="rgroup" aria-label="挿入">
          <button className="rbtn" disabled={hasPhoto} title={hasPhoto ? "写真枠は1つだけ置けます" : "写真枠を挿入"}
                  onClick={() => add({ id: newId(), type: "photo", x: 0.03, y: 0.05, w: 0.56, h: 0.56, fit: "cover" })}>{I.photo}写真</button>
          <button className="rbtn" onClick={() => add(newText())}>{I.text}テキスト</button>
          <button className="rbtn" onClick={() => add(newRect())}>{I.rect}図形</button>
          <label className="rbtn" title="画像・ロゴを挿入">{I.image}画像
            <input type="file" accept="image/png,image/jpeg,image/webp" hidden
                   onChange={(e) => { void pickImage(e.target.files?.[0]); e.target.value = ""; }} />
          </label>
        </div>

        {item?.type === "text" && (
          <div className="rgroup" aria-label="文字">
            <Seg value={item.vertical ? "v" : "h"} onChange={(v) => p({ vertical: v === "v" }, true)}
                 options={[["h", I.horiz, "横書き"], ["v", I.vert, "縦書き"]]} />
            <Seg value={item.align} onChange={(v) => p({ align: v }, true)}
                 options={([["start", I.alignStart, item.vertical ? "上揃え" : "左揃え"], ["center", I.alignCenter, "中央揃え"], ["end", I.alignEnd, item.vertical ? "下揃え" : "右揃え"]] as [Align, ReactNode, string][])} />
            <button className={`rbtn sq${item.bold ? " on" : ""}`} title="太字" aria-pressed={item.bold} onClick={() => p({ bold: !item.bold }, true)}>{I.bold}</button>
            <label className="rfield" title="文字の大きさ（空欄で枠に合わせる）">大きさ
              <input type="number" min={10} max={300} placeholder="自動" value={item.fontSize ?? ""}
                     onFocus={() => p({}, true)} onChange={(e) => p({ fontSize: e.target.value === "" ? null : clamp(Number(e.target.value), 8, 400) }, false)} />
            </label>
            <MiniColor label="文字色" value={item.color} onChange={(v, push) => p({ color: v ?? "#1d2430" }, push)} />
            <MiniColor label="背景" value={item.background} optional fallback="#f3f5f8" onChange={(v, push) => p({ background: v }, push)} />
          </div>
        )}
        {item?.type === "rect" && (
          <div className="rgroup" aria-label="図形">
            <MiniColor label="塗り" value={item.fill} optional fallback="#e8eef7" onChange={(v, push) => p({ fill: v }, push)} />
            <MiniColor label="線" value={item.stroke} optional fallback="#2b4c7e" onChange={(v, push) => p({ stroke: v }, push)} />
          </div>
        )}
        {(item?.type === "photo" || item?.type === "image") && (
          <div className="rgroup" aria-label="表示">
            <Seg value={item.fit} onChange={(v) => p({ fit: v }, true)} options={[["cover", "枠いっぱい", "はみ出しを切り取る"], ["contain", "全体表示", "全体を入れる（余白あり）"]]} />
          </div>
        )}
        {item && (
          <div className="rgroup" aria-label="配置">
            <button className="rbtn sq" title="前面へ" onClick={() => reorder(item.id, "front")}>{I.front}</button>
            <button className="rbtn sq" title="背面へ" onClick={() => reorder(item.id, "back")}>{I.back}</button>
            <button className="rbtn sq" title="複製" onClick={() => duplicate(item)}>{I.copy}</button>
            <button className="rbtn sq danger" title="削除 (Delete)" onClick={() => remove(item.id)}>{I.trash}</button>
          </div>
        )}
        {!item && <span className="rhint">部品をクリックして選びます</span>}
      </div>

      <div className="studio-body">
        <aside className="slides" aria-label="スライド">{slides}</aside>

        <div className="canvasarea" onPointerDown={() => setSel(null)}>
          <div className="stage" ref={stage} tabIndex={0} aria-label="保存画像の編集領域" style={{ ["--ar" as string]: size.w / size.h }}>
            <canvas ref={canvas} width={size.w} height={size.h} />
            {layout.items.map((it) => (
              <div key={it.id} className={`box${it.id === sel ? " on" : ""}`}
                   style={{ left: `${it.x * 100}%`, top: `${it.y * 100}%`, width: `${it.w * 100}%`, height: `${it.h * 100}%` }}
                   onPointerDown={(e) => startDrag(e, it, "move")} title={TYPE_LABEL[it.type]}>
                {it.id === sel && HANDLES.map((d) => (
                  <span key={d} className={`handle ${d}`} onPointerDown={(e) => startDrag(e, it, d)} />
                ))}
              </div>
            ))}
          </div>
        </div>

        <aside className="inspector" aria-label="書式設定">
          {!item ? (
            <PagePane layout={layout} onSelect={setSel} onBackground={(v, push) => onChange({ ...layout, background: v }, push)} />
          ) : (
            <ItemPane item={item} onPatch={(q, push) => patch(item.id, q, push)} />
          )}
        </aside>
      </div>

      <footer className="statusbar">
        <span>{portrait ? "縦向きの写真" : "横向きの写真"}を撮ったときの保存画像（{size.w}×{size.h}）</span>
        <span className="grow" />
        {notice && <span className="error">{notice}</span>}
        <span>{item ? `${TYPE_LABEL[item.type]}を選択中` : `部品 ${layout.items.length} 個`}</span>
        <span className="muted">ドラッグで移動 ／ 矢印キーで微調整 ／ Delete で削除</span>
      </footer>
    </div>
  );
}

function Seg<T extends string>({ value, options, onChange }: { value: T; options: [T, ReactNode, string?][]; onChange: (v: T) => void }) {
  return (
    <div className="seg" role="group">
      {options.map(([v, label, title]) => (
        <button key={v} title={title} className={v === value ? "on" : ""} aria-pressed={v === value} onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  );
}

/** A colour swatch for the ribbon. `optional` ones can be switched off (null). */
function MiniColor({ label, value, onChange, optional, fallback = "#ffffff" }: {
  label: string; value: string | null; onChange: (v: string | null, push: boolean) => void; optional?: boolean; fallback?: string;
}) {
  return (
    <span className="mcolor" title={label}>
      <span>{label}</span>
      <label className={`swatch-sq${value === null ? " none" : ""}`}>
        <i style={{ background: value ?? "transparent" }} />
        <input type="color" value={value ?? fallback} onPointerDown={() => onChange(value ?? fallback, true)}
               onChange={(e) => onChange(e.target.value, false)} />
      </label>
      {optional && value !== null && <button className="rbtn sq tiny" title={`${label}をなしにする`} onClick={() => onChange(null, true)}>×</button>}
    </span>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="pfield"><span>{label}</span>{children}</label>;
}

function Num({ value, min = 0, max = 100, onFocus, onChange }: { value: number; min?: number; max?: number; onFocus: () => void; onChange: (v: number) => void }) {
  return <input type="number" min={min} max={max} value={Math.round(value)} onFocus={onFocus} onChange={(e) => e.target.value !== "" && onChange(clamp(Number(e.target.value), min, max))} />;
}

function PagePane({ layout, onSelect, onBackground }: {
  layout: GuideLayout; onSelect: (id: string) => void; onBackground: (v: string, push: boolean) => void;
}) {
  return (
    <>
      <h3 className="pane-title">ページの書式設定</h3>
      <section className="psec">
        <h4>背景</h4>
        <Field label="背景色">
          <label className="swatch-sq wide"><i style={{ background: layout.background }} /><code>{layout.background.toUpperCase()}</code>
            <input type="color" value={layout.background} onPointerDown={() => onBackground(layout.background, true)} onChange={(e) => onBackground(e.target.value, false)} />
          </label>
        </Field>
      </section>
      <section className="psec">
        <h4>重なり順（上が前面）</h4>
        <ol className="layers">
          {[...layout.items].reverse().map((i) => (
            <li key={i.id}>
              <button onClick={() => onSelect(i.id)}>{I[i.type]}<span>{TYPE_LABEL[i.type]}{i.type === "text" && i.text.trim() ? `　${i.text.trim().slice(0, 10)}` : ""}</span></button>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

function ItemPane({ item, onPatch }: { item: GuideItem; onPatch: (p: Partial<GuideItem>, push: boolean) => void }) {
  const geo = (k: "x" | "y" | "w" | "h", v: number) => {
    const f = v / 100;
    const next = k === "x" ? clamp(f, 0, 1 - item.w) : k === "y" ? clamp(f, 0, 1 - item.h)
      : k === "w" ? clamp(f, MIN_BOX, 1 - item.x) : clamp(f, MIN_BOX, 1 - item.y);
    onPatch({ [k]: next }, false);
  };
  const open = () => onPatch({}, true);
  return (
    <>
      <h3 className="pane-title">{TYPE_LABEL[item.type]}の書式設定</h3>
      {item.type === "text" && <TextPane item={item} onPatch={onPatch} />}
      {item.type === "rect" && (
        <section className="psec">
          <h4>図形</h4>
          <Field label={`線の太さ ${Math.round(item.strokeWidth)}`}><input type="range" min={0} max={60} value={item.strokeWidth} onPointerDown={open} onChange={(e) => onPatch({ strokeWidth: Number(e.target.value) }, false)} /></Field>
          <Field label={`角の丸み ${Math.round(item.radius)}`}><input type="range" min={0} max={300} value={item.radius} onPointerDown={open} onChange={(e) => onPatch({ radius: Number(e.target.value) }, false)} /></Field>
        </section>
      )}
      <section className="psec">
        <h4>位置とサイズ（%）</h4>
        <div className="geo">
          <Field label="左"><Num value={item.x * 100} onFocus={open} onChange={(v) => geo("x", v)} /></Field>
          <Field label="上"><Num value={item.y * 100} onFocus={open} onChange={(v) => geo("y", v)} /></Field>
          <Field label="幅"><Num value={item.w * 100} min={3} onFocus={open} onChange={(v) => geo("w", v)} /></Field>
          <Field label="高さ"><Num value={item.h * 100} min={3} onFocus={open} onChange={(v) => geo("h", v)} /></Field>
        </div>
      </section>
    </>
  );
}

function TextPane({ item, onPatch }: { item: TextItem; onPatch: (p: Partial<GuideItem>, push: boolean) => void }) {
  return (
    <section className="psec">
      <h4>案内文</h4>
      <textarea value={item.text} rows={7} onFocus={() => onPatch({}, true)} onChange={(e) => onPatch({ text: e.target.value }, false)}
                placeholder="撮影した写真と一緒に保存される案内文" />
    </section>
  );
}
