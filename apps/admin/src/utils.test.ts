import { describe, expect, it } from "vitest";
import { clampBox, formatDate, percent } from "./utils";

describe("utils", () => {
  it("formats confidence as a percentage", () => expect(percent(0.824)).toBe("82%"));

  it("shows a dash for missing or invalid dates", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("not a date")).toBe("—");
  });

  it("clamps boxes into the image", () => {
    expect(clampBox({ x: -5, y: 10, width: 50, height: 500 }, 100, 100)).toEqual({ x: 0, y: 10, width: 50, height: 90 });
    expect(clampBox({ x: 150, y: 0, width: 10, height: 10 }, 100, 100).width).toBe(0);
  });
});
