"""Stage 5: find candidate regions where the aligned photo differs from the reference."""
from dataclasses import dataclass

import cv2
import numpy as np
from skimage.metrics import structural_similarity


@dataclass
class Candidate:
    x: int
    y: int
    width: int
    height: int
    score: float  # mean dissimilarity (0-1) inside the region

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height,
                "score": round(self.score, 3)}


def normalize_lighting(reference_gray: np.ndarray, target_gray: np.ndarray) -> np.ndarray:
    """Match brightness/contrast of the target to the reference using blurred local statistics."""
    def local(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        f = img.astype(np.float32)
        mean = cv2.GaussianBlur(f, (0, 0), 25)
        var = cv2.GaussianBlur((f - mean) ** 2, (0, 0), 25)
        return mean, np.sqrt(var) + 1e-3

    mr, sr = local(reference_gray)
    mt, st = local(target_gray)
    out = (target_gray.astype(np.float32) - mt) / st * sr + mr
    return np.clip(out, 0, 255).astype(np.uint8)


def dissimilarity_map(reference: np.ndarray, aligned: np.ndarray) -> np.ndarray:
    gr = cv2.GaussianBlur(cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), (0, 0), 1.5)
    gt = cv2.GaussianBlur(cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY), (0, 0), 1.5)
    gt = normalize_lighting(gr, gt)
    _, ssim_map = structural_similarity(gr, gt, full=True, win_size=11, data_range=255)
    return np.clip(1.0 - ssim_map, 0.0, 1.0)  # 0 = same, 1 = totally different


def find_candidates(reference: np.ndarray, aligned: np.ndarray, valid_mask: np.ndarray, *,
                    dissim_threshold: float, min_area_ratio: float, max_candidates: int,
                    ignore_mask: np.ndarray | None = None) -> tuple[list[Candidate], np.ndarray]:
    """`ignore_mask` (255 = leave out, same size as the reference) hides things that move, e.g. people."""
    dis = dissimilarity_map(reference, aligned)
    if ignore_mask is not None:
        dis = np.where(ignore_mask > 0, 0.0, dis)
    # Ignore the border where the warped target has no pixels.
    safe = cv2.erode(valid_mask, np.ones((25, 25), np.uint8)) > 0
    dis = np.where(safe, dis, 0.0)

    binary = (dis >= dissim_threshold).astype(np.uint8) * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))

    h, w = binary.shape
    min_area = min_area_ratio * h * w
    n, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    cands: list[Candidate] = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        score = float(dis[y:y + bh, x:x + bw].mean())
        cands.append(Candidate(int(x), int(y), int(bw), int(bh), score))
    cands.sort(key=lambda c: c.score * c.width * c.height, reverse=True)
    return cands[:max_candidates], dis
