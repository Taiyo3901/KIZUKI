/**
 * Layout of the picture a visitor saves: the photo plus the explanation, arranged by an administrator.
 *
 * The picture is a fixed canvas, 2048x1536 for a landscape photo or 1536x2048 for a portrait one (see canvasSize).
 * An administrator makes one layout for each; the phone uses the one that matches the photo it took. Every item sits in a box given as fractions of the
 * canvas (x, y, w, h in 0..1), so the same layout draws identically in the admin editor and on the phone.
 * Font sizes, stroke widths and radii are in canvas pixels. Only the saved copy carries this; the photo sent
 * for analysis is never altered.
 */

export type Orientation = "landscape" | "portrait";
/** Canvas size in px: 2048x1536 for landscape photos, 1536x2048 for portrait photos. */
export function canvasSize(o?: Orientation): { w: number; h: number } {
  return o === "portrait" ? { w: 1536, h: 2048 } : { w: 2048, h: 1536 };
}

export type Fit = "cover" | "contain";
export type Align = "start" | "center" | "end";

interface Box {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface PhotoItem extends Box { type: "photo"; fit: Fit }
export interface TextItem extends Box {
  type: "text";
  text: string;
  vertical: boolean;
  /** canvas px; null = the largest size at which the text fits the box */
  fontSize: number | null;
  color: string;
  background: string | null;
  bold: boolean;
  /** horizontal text: left / centre / right. Vertical text: top / middle / bottom. */
  align: Align;
}
export interface RectItem extends Box { type: "rect"; fill: string | null; stroke: string | null; strokeWidth: number; radius: number }
export interface ImageItem extends Box { type: "image"; src: string; fit: Fit }
export type GuideItem = PhotoItem | TextItem | RectItem | ImageItem;

export interface GuideLayout {
  version: 1;
  /** which photo orientation this layout is for; missing = landscape */
  orientation?: Orientation;
  background: string;
  items: GuideItem[];
}

export const MIN_BOX = 0.03;
export const FONT = '"Hiragino Sans", "Yu Gothic UI", "Noto Sans JP", sans-serif';

export function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function newPhoto(): PhotoItem {
  return { id: newId(), type: "photo", x: 0.03, y: 0.05, w: 0.56, h: 0.56, fit: "cover" };
}
export function newText(text = "ここに案内文を入力"): TextItem {
  return { id: newId(), type: "text", x: 0.64, y: 0.05, w: 0.33, h: 0.9, text, vertical: false, fontSize: null, color: "#1d2430", background: null, bold: false, align: "start" };
}
export function newRect(): RectItem {
  return { id: newId(), type: "rect", x: 0.1, y: 0.7, w: 0.3, h: 0.2, fill: "#e8eef7", stroke: null, strokeWidth: 4, radius: 0 };
}
export function newImage(src: string): ImageItem {
  return { id: newId(), type: "image", x: 0.1, y: 0.7, w: 0.2, h: 0.2, src, fit: "contain" };
}

/** Photo on the left, the text beside it. Used when an administrator has not made a layout yet. */
export function defaultLayout(text = "", orientation: Orientation = "landscape"): GuideLayout {
  const t = newText(text);
  if (orientation === "portrait") Object.assign(t, { x: 0.05, y: 0.66, w: 0.9, h: 0.31 }); // text under the photo
  return { version: 1, orientation, background: "#ffffff", items: [newPhoto(), t] };
}

/** All the text of a layout's text boxes, used to start the other orientation's layout from the same words. */
export function textOf(l: GuideLayout | null | undefined): string {
  return (l?.items ?? []).flatMap((i) => (i.type === "text" && i.text.trim() ? [i.text.trim()] : [])).join("\n\n");
}

/** Copy of a layout with fresh ids, for "copy from another spot". */
export function cloneLayout(l: GuideLayout): GuideLayout {
  return { ...structuredClone(l), items: l.items.map((i) => ({ ...structuredClone(i), id: newId() })) };
}

// ---------------------------------------------------------------- text layout

/** Characters that must not start a line (Japanese line-breaking rule, simplified). */
const NO_LINE_START = new Set("、。，．,.）」』】〕！？!?ー・：；々ゝゞ".split(""));
/** Drawn turned 90 degrees clockwise in vertical text. */
const VERT_ROTATE = new Set("ー—―…～〜（）()「」『』【】〔〕［］[]〈〉《》:：;；=＝-".split(""));
/** Drawn in the upper right of their cell in vertical text. */
const VERT_CORNER = new Set("、。，．".split(""));

/** Breaks `text` into lines no wider than `maxWidth`. Explicit newlines are kept; blank lines stay as gaps. */
export function wrapText(measure: (s: string) => number, text: string, maxWidth: number): string[] {
  const lines: string[] = [];
  for (const para of text.replace(/\r\n?/g, "\n").split("\n")) {
    if (para === "") {
      lines.push("");
      continue;
    }
    let line = "";
    for (const ch of para) {
      if (line !== "" && measure(line + ch) > maxWidth && !NO_LINE_START.has(ch)) {
        lines.push(line);
        line = ch;
      } else line += ch;
    }
    lines.push(line);
  }
  return lines;
}

/** Vertical text: columns of at most `perColumn` characters, read from the right. A closing mark stays with the column before it. */
export function splitColumns(text: string, perColumn: number): string[][] {
  const cols: string[][] = [];
  for (const para of text.replace(/\r\n?/g, "\n").split("\n")) {
    if (para === "") {
      cols.push([]);
      continue;
    }
    let col: string[] = [];
    for (const ch of para) {
      if (col.length >= perColumn && !NO_LINE_START.has(ch)) {
        cols.push(col);
        col = [];
      }
      col.push(ch);
    }
    cols.push(col);
  }
  return cols;
}

const LINE_HEIGHT = 1.6;
const MIN_FONT = 14;

export interface TextPlan {
  fontPx: number;
  /** horizontal: the lines; vertical: the columns (each a list of characters) */
  lines: string[];
  columns: string[][];
}

/** Decides font size and line breaks for a text item inside an inner box of `w` x `h` px. */
export function planText(
  measureAt: (px: number, bold: boolean) => (s: string) => number,
  it: Pick<TextItem, "text" | "vertical" | "fontSize" | "bold">, w: number, h: number,
): TextPlan {
  const text = it.text.trim();
  const fits = (px: number): TextPlan | null => {
    if (it.vertical) {
      const columns = splitColumns(text, Math.max(1, Math.floor(h / px)));
      return columns.length * Math.round(px * LINE_HEIGHT) <= w ? { fontPx: px, lines: [], columns } : null;
    }
    const lines = wrapText(measureAt(px, it.bold), text, w);
    return lines.length * Math.round(px * LINE_HEIGHT) <= h ? { fontPx: px, lines, columns: [] } : null;
  };
  if (it.fontSize) {
    const px = Math.max(MIN_FONT / 2, it.fontSize);
    return fits(px) ?? (it.vertical
      ? { fontPx: px, lines: [], columns: splitColumns(text, Math.max(1, Math.floor(h / px))) }
      : { fontPx: px, lines: wrapText(measureAt(px, it.bold), text, w), columns: [] });
  }
  for (let px = Math.min(Math.round(Math.min(w, h) / 2), 110); px >= MIN_FONT; px--) {
    const p = fits(px);
    if (p) return p;
  }
  const px = MIN_FONT; // does not fit even at the smallest size: draw it anyway, the box clips the overflow
  return it.vertical
    ? { fontPx: px, lines: [], columns: splitColumns(text, Math.max(1, Math.floor(h / px))) }
    : { fontPx: px, lines: wrapText(measureAt(px, it.bold), text, w), columns: [] };
}

// ---------------------------------------------------------------- drawing

export interface Drawable {
  src: CanvasImageSource;
  w: number;
  h: number;
}

function drawFit(g: CanvasRenderingContext2D, d: Drawable, x: number, y: number, w: number, h: number, fit: Fit) {
  const k = fit === "cover" ? Math.max(w / d.w, h / d.h) : Math.min(w / d.w, h / d.h);
  const dw = d.w * k, dh = d.h * k;
  g.save();
  g.beginPath();
  g.rect(x, y, w, h);
  g.clip();
  g.drawImage(d.src, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
  g.restore();
}

function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.max(0, Math.min(r, w / 2, h / 2));
  g.beginPath();
  g.moveTo(x + rr, y);
  g.arcTo(x + w, y, x + w, y + h, rr);
  g.arcTo(x + w, y + h, x, y + h, rr);
  g.arcTo(x, y + h, x, y, rr);
  g.arcTo(x, y, x + w, y, rr);
  g.closePath();
}

function drawTextItem(g: CanvasRenderingContext2D, it: TextItem, x: number, y: number, w: number, h: number) {
  if (it.background) {
    g.fillStyle = it.background;
    g.fillRect(x, y, w, h);
  }
  if (!it.text.trim()) return;
  const pad = Math.round(Math.min(w, h) * 0.05);
  const ix = x + pad, iy = y + pad, iw = w - pad * 2, ih = h - pad * 2;
  const font = (px: number, bold: boolean) => `${bold ? "700 " : ""}${px}px ${FONT}`;
  const plan = planText((px, bold) => { g.font = font(px, bold); return (s) => g.measureText(s).width; }, it, iw, ih);
  const px = plan.fontPx, lh = Math.round(px * LINE_HEIGHT);

  g.save();
  g.beginPath();
  g.rect(x, y, w, h);
  g.clip();
  g.font = font(px, it.bold);
  g.fillStyle = it.color;
  if (!it.vertical) {
    g.textBaseline = "alphabetic";
    g.textAlign = it.align === "start" ? "left" : it.align === "center" ? "center" : "right";
    const ax = it.align === "start" ? ix : it.align === "center" ? ix + iw / 2 : ix + iw;
    plan.lines.forEach((l, k) => g.fillText(l, ax, iy + k * lh + px));
  } else {
    g.textBaseline = "middle";
    g.textAlign = "center";
    plan.columns.forEach((col, k) => {
      const cx = ix + iw - lh * (k + 0.5);
      const used = col.length * px;
      const top = it.align === "start" ? iy : it.align === "center" ? iy + (ih - used) / 2 : iy + ih - used;
      col.forEach((ch, i) => {
        const cy = top + px * (i + 0.5);
        g.save();
        if (VERT_ROTATE.has(ch)) {
          g.translate(cx, cy);
          g.rotate(Math.PI / 2);
          g.fillText(ch, 0, 0);
        } else if (VERT_CORNER.has(ch)) {
          g.fillText(ch, cx + px * 0.45, cy - px * 0.45);
        } else g.fillText(ch, cx, cy);
        g.restore();
      });
    });
  }
  g.restore();
}

/** Paints the whole layout. `photo` null leaves photo frames as a grey placeholder. */
export function drawLayout(g: CanvasRenderingContext2D, layout: GuideLayout, photo: Drawable | null, images: Map<string, Drawable>) {
  const { w: CW, h: CH } = canvasSize(layout.orientation);
  g.fillStyle = layout.background;
  g.fillRect(0, 0, CW, CH);
  for (const it of layout.items) {
    const x = it.x * CW, y = it.y * CH, w = it.w * CW, h = it.h * CH;
    if (it.type === "photo") {
      if (photo) drawFit(g, photo, x, y, w, h, it.fit);
      else {
        g.fillStyle = "#d5dae1";
        g.fillRect(x, y, w, h);
      }
    } else if (it.type === "text") drawTextItem(g, it, x, y, w, h);
    else if (it.type === "rect") {
      roundRect(g, x, y, w, h, it.radius);
      if (it.fill) {
        g.fillStyle = it.fill;
        g.fill();
      }
      if (it.stroke && it.strokeWidth > 0) {
        g.strokeStyle = it.stroke;
        g.lineWidth = it.strokeWidth;
        g.stroke();
      }
    } else {
      const d = images.get(it.id);
      if (d) drawFit(g, d, x, y, w, h, it.fit);
    }
  }
}

/** Decodes the logo/picture items of a layout (they are stored as data URLs). */
export async function loadLayoutImages(layout: GuideLayout): Promise<Map<string, Drawable>> {
  const out = new Map<string, Drawable>();
  await Promise.all(layout.items.map(async (it) => {
    if (it.type !== "image") return;
    try {
      const img = new Image();
      img.src = it.src;
      await img.decode();
      out.set(it.id, { src: img, w: img.naturalWidth, h: img.naturalHeight });
    } catch {
      /* a broken picture is simply not drawn */
    }
  }));
  return out;
}
