import { describe, expect, it } from "vitest";
import { clamp, pinchZoom } from "./zoom";

describe("pinchZoom", () => {
  it("zooms in when the fingers spread and out when they close", () => {
    expect(pinchZoom(1, 100, 200, 1, 3)).toBe(2);
    expect(pinchZoom(2, 200, 100, 1, 3)).toBe(1);
  });
  it("stays inside the range", () => {
    expect(pinchZoom(1, 100, 1000, 1, 3)).toBe(3);
    expect(pinchZoom(1, 100, 10, 1, 3)).toBe(1);
  });
  it("ignores a zero start distance", () => {
    expect(pinchZoom(1.5, 0, 50, 1, 3)).toBe(1.5);
  });
  it("clamp", () => expect(clamp(5, 0, 3)).toBe(3));
});
