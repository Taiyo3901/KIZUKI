import { config } from "./config";

let loading: Promise<void> | null = null;

export const hasMaps = Boolean(config.mapsKey);

/** Loads the Maps JavaScript API once (script tag, so no extra dependency). */
export function loadMaps(): Promise<void> {
  loading ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(config.mapsKey)}&v=weekly&loading=async&libraries=marker&language=ja&region=JP`;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("maps failed to load"));
    document.head.appendChild(s);
  });
  return loading;
}

/** Marker positions come back as a LatLng object or a plain literal depending on the call. */
export function toLiteral(p: google.maps.LatLng | google.maps.LatLngLiteral | null | undefined): { lat: number; lng: number } | null {
  if (!p) return null;
  return typeof p.lat === "function"
    ? { lat: p.lat(), lng: (p as google.maps.LatLng).lng() }
    : { lat: p.lat as number, lng: (p as google.maps.LatLngLiteral).lng };
}
