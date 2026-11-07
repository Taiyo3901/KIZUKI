"""Stage 4: align a target photo onto the reference photo (SIFT + RANSAC homography)."""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class AlignResult:
    ok: bool
    aligned: np.ndarray | None   # target warped into reference pixel coordinates
    valid_mask: np.ndarray | None  # 255 where the warped target has real pixels
    inliers: int
    reason: str = ""


def resize_long_edge(img: np.ndarray, max_edge: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = max_edge / max(h, w)
    if scale >= 1.0:
        return img
    return cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)


def align(reference: np.ndarray, target: np.ndarray, min_inliers: int = 30) -> AlignResult:
    gray_r = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    gray_t = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    # CLAHE reduces sensitivity to lighting before feature detection.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_r, gray_t = clahe.apply(gray_r), clahe.apply(gray_t)

    sift = cv2.SIFT_create(nfeatures=4000)
    kp_r, des_r = sift.detectAndCompute(gray_r, None)
    kp_t, des_t = sift.detectAndCompute(gray_t, None)
    if des_r is None or des_t is None or len(kp_r) < 8 or len(kp_t) < 8:
        return AlignResult(False, None, None, 0, "too few features")

    matcher = cv2.BFMatcher(cv2.NORM_L2)
    good = [m for m, n in matcher.knnMatch(des_t, des_r, k=2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return AlignResult(False, None, None, len(good), "too few matches")

    src = np.float32([kp_t[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_r[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, inlier_mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None:
        return AlignResult(False, None, None, 0, "homography failed")
    inliers = int(inlier_mask.sum())
    if inliers < min_inliers:
        return AlignResult(False, None, None, inliers, f"inliers {inliers} < {min_inliers}")

    h, w = reference.shape[:2]
    aligned = cv2.warpPerspective(target, H, (w, h), flags=cv2.INTER_LINEAR)
    valid = cv2.warpPerspective(np.full(gray_t.shape, 255, np.uint8), H, (w, h), flags=cv2.INTER_NEAREST)
    return AlignResult(True, aligned, valid, inliers)
