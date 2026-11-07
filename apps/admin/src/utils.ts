import { DETECTION_STATUS_LABEL, type DetectionStatus, type SpotStatus } from "@shared/types";

export const DETECTION_LABEL = DETECTION_STATUS_LABEL;

/** Map pin / dot colors: ok = green, needs_review = red, confirmed_change = orange (CLAUDE.md screen 4). */
export const SPOT_COLOR: Record<SpotStatus, string> = { ok: "#2e9e5b", needs_review: "#d93025", confirmed_change: "#f29900" };
export const SPOT_LABEL: Record<SpotStatus, string> = { ok: "変化なし", needs_review: "要確認", confirmed_change: "変化あり（確定）" };

/** Order used for the legend. */
export const SPOT_STATUSES: SpotStatus[] = ["ok", "needs_review", "confirmed_change"];

export const SEASON_LABEL: Record<string, string> = { spring: "春", summer: "夏", autumn: "秋", winter: "冬" };
export const TIME_LABEL: Record<string, string> = { morning: "朝", day: "昼", evening: "夕" };

export const percent = (confidence: number): string => `${Math.round(confidence * 100)}%`;

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("ja-JP", { dateStyle: "short", timeStyle: "short" });
}

export const STATUS_FILTERS: { value: DetectionStatus | ""; label: string }[] = [
  { value: "needs_review", label: "要確認" },
  { value: "monitoring", label: "経過観察" },
  { value: "confirmed_change", label: "変化あり" },
  { value: "false_positive", label: "誤検知" },
  { value: "", label: "すべて" },
];

/** Rectangle for a change box, clamped inside the image. */
export function clampBox(b: { x: number; y: number; width: number; height: number }, w: number, h: number) {
  const x = Math.max(0, Math.min(b.x, w));
  const y = Math.max(0, Math.min(b.y, h));
  return { x, y, width: Math.max(0, Math.min(b.width, w - x)), height: Math.max(0, Math.min(b.height, h - y)) };
}
