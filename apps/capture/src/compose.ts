/**
 * The picture a visitor saves on the phone: the photo plus the guide, arranged as the administrator laid it out
 * (see shared/schemas/guideLayout.ts). The administrator makes one layout for landscape photos and one for portrait
 * photos; the one matching the photo that was taken is used. Only this saved copy carries the guide. The photo sent
 * for analysis is left untouched.
 */
import { canvasSize, defaultLayout, drawLayout, loadLayoutImages, textOf, type GuideLayout } from "@shared/guideLayout";

export interface GuideSource {
  guideLayout?: GuideLayout | null;
  guideLayoutPortrait?: GuideLayout | null;
  guideText?: string;
}

/** True when the administrator set anything to add to the saved picture. */
export function hasGuide(spot: GuideSource): boolean {
  return Boolean(spot.guideLayout?.items?.length || spot.guideLayoutPortrait?.items?.length || spot.guideText?.trim());
}

/**
 * The layout for a photo of the given orientation: the administrator's own, else the default arrangement around the
 * same words (taken from the other orientation's layout if need be), else none.
 */
export function layoutFor(spot: GuideSource, portrait: boolean): GuideLayout | null {
  const own = portrait ? spot.guideLayoutPortrait : spot.guideLayout;
  if (own?.items?.length) return own;
  const words = spot.guideText?.trim() || textOf(portrait ? spot.guideLayout : spot.guideLayoutPortrait);
  return words ? defaultLayout(words, portrait ? "portrait" : "landscape") : null;
}

export async function composeGuideImage(photo: Blob, spot: GuideSource): Promise<Blob> {
  const bmp = await createImageBitmap(photo);
  const layout = layoutFor(spot, bmp.height > bmp.width);
  if (!layout) {
    bmp.close();
    return photo;
  }
  const { w, h } = canvasSize(layout.orientation);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const images = await loadLayoutImages(layout);
  drawLayout(c.getContext("2d")!, layout, { src: bmp, w: bmp.width, h: bmp.height }, images);
  bmp.close();
  return new Promise((resolve, reject) => c.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), "image/jpeg", 0.92));
}
