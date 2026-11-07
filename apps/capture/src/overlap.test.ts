import { describe, expect, it } from "vitest";
import { AutoShutter, estimateOverlap, guidance, type Gray } from "./overlap";

function noise(w: number, h: number, seed = 1): Gray {
  let s = seed >>> 0; // mulberry32: seeds that differ a little still give unrelated sequences
  const rnd = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return (((t ^ (t >>> 14)) >>> 0) / 2 ** 32) * 255;
  };
  // generate a 1px larger field and blur it, so every output pixel (borders included) has a real value
  const W = w + 2;
  const raw = new Float32Array(W * (h + 2)).map(rnd);
  const data = new Float32Array(w * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let a = 0;
      for (let j = 0; j <= 2; j++) for (let i = 0; i <= 2; i++) a += raw[(y + j) * W + x + i];
      data[y * w + x] = a / 9;
    }
  return { width: w, height: h, data };
}

/** live(x, y) = ref(x - dx, y - dy): the scene appears displaced by (dx, dy). */
function displaced(ref: Gray, dx: number, dy: number, gain = 1): Gray {
  const data = new Float32Array(ref.data.length);
  for (let y = 0; y < ref.height; y++)
    for (let x = 0; x < ref.width; x++) {
      const sx = x - dx, sy = y - dy;
      data[y * ref.width + x] = sx >= 0 && sy >= 0 && sx < ref.width && sy < ref.height ? ref.data[sy * ref.width + sx] * gain : 0;
    }
  return { width: ref.width, height: ref.height, data };
}

describe("estimateOverlap", () => {
  const ref = noise(80, 60);

  it("identical images overlap perfectly", () => {
    const o = estimateOverlap(ref, ref);
    expect(o.score).toBeCloseTo(1, 5);
    expect([o.dx, o.dy]).toEqual([0, 0]);
  });

  it("is robust to brightness changes", () => {
    expect(estimateOverlap(displaced(ref, 0, 0, 0.6), ref).score).toBeGreaterThan(0.99);
  });

  it("finds how far the scene is displaced", () => {
    const o = estimateOverlap(displaced(ref, 4, 2), ref);
    expect([o.dx, o.dy]).toEqual([4, 2]);
    expect(o.score).toBeLessThan(0.5); // not aligned yet
    expect(o.bestScore).toBeGreaterThan(0.9);
  });

  it("unrelated images have low score", () => {
    expect(estimateOverlap(noise(80, 60, 99), ref).bestScore).toBeLessThan(0.5);
  });
});

describe("guidance", () => {
  it("tells the user to pan toward the displacement (scene to the right -> point right)", () => {
    expect(guidance({ score: 0.3, dx: 5, dy: 0, bestScore: 0.9 }, 0.8)).toBe("カメラを右へ向けてください");
    expect(guidance({ score: 0.3, dx: -5, dy: 4, bestScore: 0.9 }, 0.8)).toBe("カメラを左へ・下へ向けてください");
  });
  it("says hold still when aligned, and asks to find the scene when lost", () => {
    expect(guidance({ score: 0.9, dx: 0, dy: 0, bestScore: 0.9 }, 0.8)).toContain("動かさない");
    expect(guidance({ score: 0.0, dx: 3, dy: 3, bestScore: 0.1 }, 0.8)).toContain("ガイドに合わせて");
  });
});

describe("AutoShutter", () => {
  it("fires only after the score is held long enough", () => {
    const a = new AutoShutter(0.8, 1000);
    expect(a.update(0.9, 0)).toBe(false);
    expect(a.update(0.9, 900)).toBe(false);
    expect(a.update(0.9, 1000)).toBe(true);
  });
  it("restarts the clock when the score drops", () => {
    const a = new AutoShutter(0.8, 1000);
    a.update(0.9, 0);
    a.update(0.5, 600);
    expect(a.update(0.9, 700)).toBe(false);
    expect(a.update(0.9, 1600)).toBe(false);
    expect(a.update(0.9, 1700)).toBe(true);
  });
});
