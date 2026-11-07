/** Pinch-to-zoom helpers. Kept free of the DOM so they can be unit tested. */
export const MAX_DIGITAL_ZOOM = 3;

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** New zoom after the two fingers moved from `startDist` to `dist` apart (spreading = zooming in). */
export function pinchZoom(startZoom: number, startDist: number, dist: number, min: number, max: number): number {
  if (startDist <= 0) return startZoom;
  return clamp((startZoom * dist) / startDist, min, max);
}

export interface ZoomRange {
  min: number;
  max: number;
  /** true: the camera itself zooms (Android Chrome). false: the picture is enlarged and cropped on the phone. */
  hardware: boolean;
}

type ZoomCaps = { zoom?: { min: number; max: number } };

/** Reads what the camera offers. iPhone Safari does not expose a zoom control, so it gets digital zoom. */
export function zoomRangeOf(track: MediaStreamTrack): ZoomRange {
  const caps = (typeof track.getCapabilities === "function" ? track.getCapabilities() : {}) as ZoomCaps;
  if (caps.zoom && caps.zoom.max > caps.zoom.min) return { min: caps.zoom.min, max: Math.min(caps.zoom.max, 8), hardware: true };
  return { min: 1, max: MAX_DIGITAL_ZOOM, hardware: false };
}
