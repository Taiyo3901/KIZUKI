import { defaultLayout, planText, splitColumns, textOf, wrapText } from "@shared/guideLayout";
import { describe, expect, it } from "vitest";
import { hasGuide, layoutFor } from "./compose";

const widthOf = (px: number) => (s: string) => [...s].length * px; // every character is one em wide
const measureAt = (px: number) => widthOf(px);
const text = (t: string, o: object = {}) => ({ text: t, vertical: false, fontSize: null, bold: false, ...o });

describe("wrapText", () => {
  it("breaks at the width and keeps explicit newlines", () => {
    expect(wrapText(widthOf(10), "あいうえおかきくけこ", 50)).toEqual(["あいうえお", "かきくけこ"]);
    expect(wrapText(widthOf(10), "あい\nうえ", 100)).toEqual(["あい", "うえ"]);
    expect(wrapText(widthOf(10), "あい\n\nうえ", 100)).toEqual(["あい", "", "うえ"]);
  });
  it("does not start a line with a closing punctuation mark", () => {
    expect(wrapText(widthOf(10), "あいうえお。かき", 50)).toEqual(["あいうえお。", "かき"]);
  });
});

describe("splitColumns", () => {
  it("fills columns top to bottom and keeps a closing mark with its column", () => {
    expect(splitColumns("あいうえおかき", 3)).toEqual([["あ", "い", "う"], ["え", "お", "か"], ["き"]]);
    expect(splitColumns("あいう。え", 3)).toEqual([["あ", "い", "う", "。"], ["え"]]);
    expect(splitColumns("あ\n\nい", 3)).toEqual([["あ"], [], ["い"]]);
  });
});

describe("planText", () => {
  it("auto size picks the largest size that fits", () => {
    const small = planText(measureAt, text("あ".repeat(200)), 200, 200);
    const big = planText(measureAt, text("あ".repeat(8)), 200, 200);
    expect(big.fontPx).toBeGreaterThan(small.fontPx);
    expect(small.lines.join("")).toBe("あ".repeat(200));
  });
  it("uses a fixed size as given", () => {
    expect(planText(measureAt, text("あいう", { fontSize: 40 }), 400, 400).fontPx).toBe(40);
  });
  it("lays vertical text out in columns", () => {
    const p = planText(measureAt, text("あ".repeat(30), { vertical: true }), 300, 200);
    expect(p.columns.length).toBeGreaterThan(1);
    expect(p.columns.flat().join("")).toBe("あ".repeat(30));
    expect(p.lines).toEqual([]);
  });
});

describe("layoutFor", () => {
  it("uses the layout of the photo's orientation, else the default around the same words, else none", () => {
    const land = defaultLayout("横", "landscape");
    const port = defaultLayout("縦", "portrait");
    expect(layoutFor({ guideLayout: land, guideLayoutPortrait: port }, false)).toBe(land);
    expect(layoutFor({ guideLayout: land, guideLayoutPortrait: port }, true)).toBe(port);
    // only a landscape layout was made: a portrait photo gets a portrait arrangement of the same words
    const fallback = layoutFor({ guideLayout: land }, true);
    expect(fallback?.orientation).toBe("portrait");
    expect(textOf(fallback)).toBe("横");
    expect(layoutFor({ guideText: "x" }, false)?.orientation).toBe("landscape");
    expect(layoutFor({ guideText: "  " }, false)).toBeNull();
    expect(hasGuide({ guideLayoutPortrait: port })).toBe(true);
    expect(hasGuide({})).toBe(false);
  });
});
