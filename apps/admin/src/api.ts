import type { Box, DetectionStatus, ReviewDecision, SpotStatus } from "@shared/types";
import { authHeaders } from "./auth";
import { config } from "./config";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${config.apiBase}${path}`, { ...init, headers: { ...(await authHeaders()), ...init.headers } });
  if (!res.ok) throw new ApiError(res.status, `${res.status}`);
  return res.json() as Promise<T>;
}

export interface SpotRow {
  spotId: string;
  siteId: string;
  name: string;
  standingNote: string;
  templateId: string;
  groupId?: string | null;
  status: SpotStatus;
  captureUrl: string;
  location: { lat: number; lng: number };
}

export interface DetectionRow {
  id: string;
  spotId: string;
  spotName: string;
  siteId: string;
  status: DetectionStatus;
  maxConfidence: number;
  categories: string[];
  createdAt: string | null;
}

export interface ChangeRow {
  category: string;
  box: Box;
  confidence: number;
  reason: string;
}

export interface DetectionDetail extends DetectionRow {
  changes: ChangeRow[];
  model: string;
  reviewedBy: string | null;
  reviewedAt: string | null;
  capturedAt: string | null;
  photoUrl: string | null;
  referenceUrl: string | null;
  disclaimer: string;
}

export interface TemplateRow {
  templateId: string;
  name: string;
  observationItems: string[];
}

export interface GroupRow {
  groupId: string;
  siteId: string;
  name: string;
}

export interface NewSpot {
  siteId: string;
  name: string;
  groupId?: string | null;
  standingNote: string;
  templateId: string;
  location: { lat: number; lng: number };
}

const json = { "Content-Type": "application/json" };

export const listSpots = () => request<SpotRow[]>("/admin/spots");
export const listGroups = () => request<GroupRow[]>("/admin/groups");
export const createGroup = (siteId: string, name: string) =>
  request<GroupRow>("/admin/groups", { method: "POST", headers: json, body: JSON.stringify({ siteId, name }) });
export const setSpotGroup = (spotId: string, groupId: string | null) =>
  request<{ spotId: string; groupId: string | null }>(`/admin/spots/${encodeURIComponent(spotId)}`, {
    method: "PATCH", headers: json, body: JSON.stringify({ groupId }),
  });
export const listTemplates = () => request<TemplateRow[]>("/admin/templates");

export function listDetections(o: { status?: string; sort?: "newest" | "confidence" } = {}) {
  const q = new URLSearchParams();
  if (o.status) q.set("status", o.status);
  if (o.sort) q.set("sort", o.sort);
  return request<DetectionRow[]>(`/admin/detections?${q}`);
}

export const getDetection = (id: string) => request<DetectionDetail>(`/admin/detections/${encodeURIComponent(id)}`);

export const decide = (id: string, status: ReviewDecision) =>
  request<{ id: string; status: string }>(`/admin/detections/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: json,
    body: JSON.stringify({ status }),
  });

export const createSpot = (s: NewSpot) =>
  request<{ spotId: string; captureUrl: string }>("/admin/spots", { method: "POST", headers: json, body: JSON.stringify(s) });

export interface ReferenceRow {
  referenceId: string;
  season: string | null;
  timeOfDay: string | null;
  active: boolean;
  url: string;
}

export const listReferences = (spotId: string) =>
  request<ReferenceRow[]>(`/admin/spots/${encodeURIComponent(spotId)}/references`);

export const setReferenceActive = (spotId: string, referenceId: string, active: boolean) =>
  request<{ referenceId: string; active: boolean }>(
    `/admin/spots/${encodeURIComponent(spotId)}/references/${encodeURIComponent(referenceId)}`,
    { method: "PATCH", headers: json, body: JSON.stringify({ active }) },
  );

export function addReference(spotId: string, file: File, season: string, timeOfDay: string) {
  const f = new FormData();
  f.append("file", file);
  if (season) f.append("season", season);
  if (timeOfDay) f.append("timeOfDay", timeOfDay);
  return request<{ referenceId: string; width: number; height: number }>(
    `/admin/spots/${encodeURIComponent(spotId)}/references`,
    { method: "POST", body: f },
  );
}
