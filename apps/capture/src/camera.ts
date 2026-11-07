import type { Gray } from "./overlap";

export const SMALL_W = 80;
export const SMALL_H = 60;

/** Draw `src` into ctx like CSS object-fit: cover (what the user sees), at size dw x dh. `zoom` > 1 crops the centre. */
export function drawCover(ctx: CanvasRenderingContext2D, src: CanvasImageSource, sw: number, sh: number, dw: number, dh: number, zoom = 1) {
  const scale = Math.max(dw / sw, dh / sh) * zoom;
  const w = sw * scale, h = sh * scale;
  ctx.drawImage(src, (dw - w) / 2, (dh - h) / 2, w, h);
}

export function toGray(ctx: CanvasRenderingContext2D, w: number, h: number): Gray {
  const px = ctx.getImageData(0, 0, w, h).data;
  const data = new Float32Array(w * h);
  for (let i = 0; i < data.length; i++) data[i] = 0.299 * px[i * 4] + 0.587 * px[i * 4 + 1] + 0.114 * px[i * 4 + 2];
  return { width: w, height: h, data };
}

/** Scale so the long edge is at most maxEdge, encode as JPEG. `zoom` > 1 keeps only the centre, as shown on screen. */
export function captureJpeg(video: HTMLVideoElement, maxEdge: number, zoom = 1): Promise<Blob> {
  const sw = video.videoWidth / zoom, sh = video.videoHeight / zoom;
  const scale = Math.min(1, maxEdge / Math.max(sw, sh));
  const c = document.createElement("canvas");
  c.width = Math.round(sw * scale);
  c.height = Math.round(sh * scale);
  c.getContext("2d")!.drawImage(video, (video.videoWidth - sw) / 2, (video.videoHeight - sh) / 2, sw, sh, 0, 0, c.width, c.height);
  return new Promise((resolve, reject) => c.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), "image/jpeg", 0.9));
}
