import type { GuideLayout } from "./guideLayout";
// Shared data model (TypeScript side). Mirror of models.py — keep both in sync (CLAUDE.md section 7).

/** ok = no change / needs_review = waiting for a human / confirmed_change = a human confirmed a change */
export type SpotStatus = "ok" | "needs_review" | "confirmed_change";
export type DetectionStatus =
  | "no_change"
  | "needs_review"
  | "confirmed_change"
  | "false_positive"
  | "monitoring";
export type Season = "spring" | "summer" | "autumn" | "winter";
export type TimeOfDay = "morning" | "day" | "evening";

/** Statuses an admin may set when reviewing. */
export const REVIEW_DECISIONS = ["confirmed_change", "false_positive", "monitoring"] as const;
export type ReviewDecision = (typeof REVIEW_DECISIONS)[number];

/** UI labels (all UI text is Japanese). */
export const DETECTION_STATUS_LABEL: Record<DetectionStatus, string> = {
  no_change: "変化なし",
  needs_review: "要確認",
  confirmed_change: "変化あり",
  false_positive: "誤検知",
  monitoring: "経過観察",
};

export interface LatLng { lat: number; lng: number }
/** Pixel coordinates in the aligned reference photo. */
export interface Box { x: number; y: number; width: number; height: number }

export interface Change {
  category: string; // one of the template's observationItems
  box: Box;
  confidence: number; // 0..1
  reason: string;
}

export interface Site { name: string; address: string; adminUids: string[] }

export interface Group {
  siteId: string;
  name: string;
  createdAt?: string;
}

export interface Spot {
  siteId: string;
  name: string;
  groupId?: string | null;
  location: LatLng;
  standingNote: string;
  guideText?: string;
  guideLayout?: GuideLayout | null;
  guideLayoutPortrait?: GuideLayout | null;
  templateId: string;
  status: SpotStatus;
  captureUrl: string;
  createdAt?: string;
}

export interface Reference {
  spotId: string;
  storagePath: string;
  season?: Season | null;
  timeOfDay?: TimeOfDay | null;
  active: boolean;
}

export interface Photo {
  siteId: string; // denormalized from the spot (for security rules)
  spotId: string;
  storagePath: string; // blurred image only
  capturedAt: string;
  quality: { passed: boolean; reasons: string[] };
  uploaderUid: string; // anonymous uid
}

export interface Detection {
  siteId: string; // denormalized from the spot (for security rules)
  photoId: string;
  spotId: string;
  referenceId: string;
  changes: Change[];
  maxConfidence: number;
  status: DetectionStatus;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
  model: string;
  createdAt?: string;
}

export interface Template { name: string; observationItems: string[]; promptInstruction: string }

/** Public spot info returned to tourists by GET /spots/{spotId}. */
export interface PublicSpot {
  spotId: string;
  name: string;
  standingNote: string;
  guideText: string;
  guideLayout?: GuideLayout | null;
  guideLayoutPortrait?: GuideLayout | null;
  references: { referenceId: string; url: string; season?: Season | null; timeOfDay?: TimeOfDay | null }[];
}
