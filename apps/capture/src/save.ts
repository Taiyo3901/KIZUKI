/**
 * Saves a photo on the phone itself. A web page cannot write to the photo library silently: on iPhone the share
 * sheet's "画像を保存" is the way in, so this opens it (it needs a tap). Where sharing files is not supported
 * (most desktop browsers) it falls back to a normal download.
 */
export async function saveToPhone(blob: Blob, name: string): Promise<void> {
  const file = new File([blob], name, { type: "image/jpeg" });
  if (typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file] });
      return;
    } catch (e) {
      if ((e as DOMException).name === "AbortError") return; // the visitor closed the sheet
    }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
}

export function photoFileName(spotId: string, at: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `kizuki-${spotId}-${at.getFullYear()}${p(at.getMonth() + 1)}${p(at.getDate())}-${p(at.getHours())}${p(at.getMinutes())}${p(at.getSeconds())}.jpg`;
}
