import { describe, expect, it } from "vitest";
import { distanceM, formatDistance } from "./sensors";

describe("distanceM", () => {
  it("is zero for the same point and about 111 m per 0.001 degree of latitude", () => {
    const p = { lat: 35.1856, lng: 136.8993 };
    expect(distanceM(p, p)).toBe(0);
    expect(distanceM(p, { lat: p.lat + 0.001, lng: p.lng })).toBeGreaterThan(110);
    expect(distanceM(p, { lat: p.lat + 0.001, lng: p.lng })).toBeLessThan(112);
  });
  it("shrinks east-west distances with latitude", () => {
    const eq = distanceM({ lat: 0, lng: 0 }, { lat: 0, lng: 0.01 });
    const tokyo = distanceM({ lat: 35, lng: 0 }, { lat: 35, lng: 0.01 });
    expect(tokyo / eq).toBeCloseTo(Math.cos((35 * Math.PI) / 180), 2);
  });
});

describe("formatDistance", () => {
  it("rounds to 10 m below 1 km and shows km above", () => {
    expect(formatDistance(3)).toBe("約10m");
    expect(formatDistance(124)).toBe("約120m");
    expect(formatDistance(1250)).toBe("約1.3km");
  });
});
