/**
 * Overlap between the live camera frame and the reference photo, computed on the phone.
 * Both are tiny grayscale images (e.g. 80x60). We search small shifts and use zero-mean normalized
 * cross-correlation (robust to brightness changes). CLAUDE.md names OpenCV.js for this; the interface
 * here is what OpenCV.js can later be dropped behind.
 */
export interface Gray {
  width: number;
  height: number;
  data: Float32Array; // 0..255, row-major
}

export interface Overlap {
  /** NCC with no shift, -1..1. This is what auto-shutter compares to its threshold. */
  score: number;
  /** How far the live content is displaced from the reference, in small-image pixels (+x = right, +y = down). */
  dx: number;
  dy: number;
  /** NCC at that best shift. */
  bestScore: number;
}

function ncc(a: Gray, b: Gray, dx: number, dy: number): number {
  // compare a(x, y) with b(x - dx, y - dy) on the overlapping area
  const x0 = Math.max(0, dx), x1 = Math.min(a.width, b.width + dx);
  const y0 = Math.max(0, dy), y1 = Math.min(a.height, b.height + dy);
  const n = (x1 - x0) * (y1 - y0);
  if (n < 16) return -1;
  let sa = 0, sb = 0;
  for (let y = y0; y < y1; y++)
    for (let x = x0; x < x1; x++) {
      sa += a.data[y * a.width + x];
      sb += b.data[(y - dy) * b.width + (x - dx)];
    }
  const ma = sa / n, mb = sb / n;
  let num = 0, da = 0, db = 0;
  for (let y = y0; y < y1; y++)
    for (let x = x0; x < x1; x++) {
      const va = a.data[y * a.width + x] - ma;
      const vb = b.data[(y - dy) * b.width + (x - dx)] - mb;
      num += va * vb; da += va * va; db += vb * vb;
    }
  const den = Math.sqrt(da * db);
  return den < 1e-6 ? -1 : num / den;
}

export function estimateOverlap(live: Gray, reference: Gray, maxShift = 10): Overlap {
  const score = ncc(live, reference, 0, 0);
  let best = { dx: 0, dy: 0, s: score };
  for (let dy = -maxShift; dy <= maxShift; dy++)
    for (let dx = -maxShift; dx <= maxShift; dx++) {
      if (dx === 0 && dy === 0) continue;
      const s = ncc(live, reference, dx, dy);
      if (s > best.s) best = { dx, dy, s };
    }
  return { score, dx: best.dx, dy: best.dy, bestScore: best.s };
}

/** Japanese guidance text. Content displaced to the right means the camera points too far left: pan right. */
export function guidance(o: Overlap, okScore: number, deadZone = 1): string {
  if (o.score >= okScore) return "そのまま動かさないでください";
  if (o.bestScore < 0.2) return "ガイドに合わせてください";
  const parts: string[] = [];
  if (o.dx > deadZone) parts.push("右へ");
  if (o.dx < -deadZone) parts.push("左へ");
  if (o.dy > deadZone) parts.push("下へ");
  if (o.dy < -deadZone) parts.push("上へ");
  return parts.length ? `カメラを${parts.join("・")}向けてください` : "もう少しで重なります";
}

/** Decides when to release the shutter: score must stay >= threshold for holdMs without a break. */
export class AutoShutter {
  private since: number | null = null;
  constructor(private threshold: number, private holdMs: number) {}

  /** Returns true exactly when the shutter should fire. */
  update(score: number, nowMs: number): boolean {
    if (score < this.threshold) {
      this.since = null;
      return false;
    }
    if (this.since === null) this.since = nowMs;
    return nowMs - this.since >= this.holdMs;
  }

  /** 0..1, for a progress ring. */
  progress(nowMs: number): number {
    return this.since === null ? 0 : Math.min(1, (nowMs - this.since) / this.holdMs);
  }

  reset(): void {
    this.since = null;
  }
}
