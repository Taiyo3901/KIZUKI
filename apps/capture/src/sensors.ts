/**
 * Position check (CLAUDE.md section 4, P1). The visitor's position is compared with the spot's position on the
 * phone and then dropped; it is never sent or stored.
 */
export interface LatLng {
  lat: number;
  lng: number;
}

/** Great-circle distance in metres (haversine). */
export function distanceM(a: LatLng, b: LatLng): number {
  const R = 6371008.8;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** "約 35 m" / "約 1.2 km", for the notice shown to the visitor. */
export function formatDistance(m: number): string {
  return m < 1000 ? `約${Math.max(10, Math.round(m / 10) * 10)}m` : `約${(m / 1000).toFixed(1)}km`;
}

/** One position reading, kept in memory only. Rejects when the visitor declines or the phone cannot tell. */
export function currentPosition(timeoutMs = 8000): Promise<LatLng> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("unsupported"));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      reject,
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 30_000 },
    );
  });
}
