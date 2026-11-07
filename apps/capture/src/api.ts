import type { PublicSpot } from "@shared/types";
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

export const getSpot = (spotId: string) => request<PublicSpot>(`/spots/${encodeURIComponent(spotId)}`);

interface UploadTicket {
  uploadUrl: string;
  path: string;
  headers: Record<string, string>;
}

/** Ask for a short-lived URL, then PUT the JPEG straight to storage. */
export async function uploadPhoto(spotId: string, jpeg: Blob): Promise<void> {
  const t = await request<UploadTicket>(`/spots/${encodeURIComponent(spotId)}/upload-url`, { method: "POST" });
  const res = await fetch(t.uploadUrl, { method: "PUT", headers: t.headers, body: jpeg });
  if (!res.ok) throw new ApiError(res.status, "upload failed");
}
