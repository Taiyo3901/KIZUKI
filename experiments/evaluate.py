"""Compare results.json with labels.json and print a table of hits / false alarms / misses.

Labels: expected boxes are normalized (0-1) against the reference image.
A predicted box counts as a hit when its center lies inside an expected box grown by 50%.
Usage: .venv\\Scripts\\python evaluate.py [labels.json] [results.json]
"""
import json
import sys
from pathlib import Path


def _center_hit(pred: dict, exp: dict, w: int, h: int, grow: float = 0.5) -> bool:
    cx, cy = pred["x"] + pred["width"] / 2, pred["y"] + pred["height"] / 2
    ex, ey, ew, eh = exp["x"] * w, exp["y"] * h, exp["width"] * w, exp["height"] * h
    gx, gy = ew * grow / 2, eh * grow / 2
    return ex - gx <= cx <= ex + ew + gx and ey - gy <= cy <= ey + eh + gy


def evaluate(labels: dict, results: list[dict], threshold: float) -> tuple[list[dict], dict]:
    by_id = {r["id"]: r for r in results}
    rows, tot = [], dict(tp=0, cat_ok=0, fn=0, fp_boxes=0, neg_cases=0, neg_false_alarm=0, align_fail=0, api_calls=0)
    for case in labels["cases"]:
        r = by_id[case["id"]]
        w, h = r["image_size"]["width"], r["image_size"]["height"]
        expected = case.get("expected", [])
        preds = [c for c in r["changes"] if c["confidence"] >= threshold]
        tot["api_calls"] += r["api_calls"]
        if r["status"] == "alignment_failed":
            tot["align_fail"] += 1

        matched_pred = set()
        hits = cat_ok = 0
        for e in expected:
            m = next((i for i, p in enumerate(preds) if i not in matched_pred and _center_hit(p["box"], e["box"], w, h)), None)
            if m is not None:
                matched_pred.add(m)
                hits += 1
                accept = e.get("acceptable_categories", [e["category"]])
                cat_ok += preds[m]["category"] in accept
        fn = len(expected) - hits
        fp = len(preds) - len(matched_pred)
        tot["tp"] += hits; tot["cat_ok"] += cat_ok; tot["fn"] += fn; tot["fp_boxes"] += fp
        if not expected:
            tot["neg_cases"] += 1
            tot["neg_false_alarm"] += bool(preds)
        rows.append({"id": case["id"], "expected": len(expected), "predicted": len(preds), "hit": hits,
                     "category_ok": cat_ok, "miss": fn, "false_alarm": fp, "status": r["status"]})
    return rows, tot


def render(rows: list[dict], tot: dict) -> str:
    out = ["| 画像 | 正解の数 | 検出の数 | 位置が合った | 種類も合った | 見逃し | 誤検知 | 判定 |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['id']} | {r['expected']} | {r['predicted']} | {r['hit']} | {r['category_ok']} | "
                   f"{r['miss']} | {r['false_alarm']} | {r['status']} |")
    exp = tot["tp"] + tot["fn"]
    prec = tot["tp"] / (tot["tp"] + tot["fp_boxes"]) if tot["tp"] + tot["fp_boxes"] else float("nan")
    rec = tot["tp"] / exp if exp else float("nan")
    out += ["", "## 集計",
            f"- 変化の総数（正解）: {exp} / 位置が合った: {tot['tp']} / 種類も合った: {tot['cat_ok']}",
            f"- 見逃し: {tot['fn']} / 誤検知（枠の数）: {tot['fp_boxes']}",
            f"- 再現率: {rec:.2f} / 適合率: {prec:.2f}",
            f"- 変化なしの画像: {tot['neg_cases']} 枚中、誤って要確認になったもの: {tot['neg_false_alarm']} 枚",
            f"- 位置合わせに失敗した画像: {tot['align_fail']} 枚 / Gemini 呼び出し回数: {tot['api_calls']}"]
    return "\n".join(out)


def main() -> None:
    labels_path = Path(sys.argv[1] if len(sys.argv) > 1 else "samples/labels.json")
    results_path = Path(sys.argv[2] if len(sys.argv) > 2 else "out/results.json")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    results = json.loads(results_path.read_text(encoding="utf-8"))
    from config import SETTINGS
    rows, tot = evaluate(labels, results, SETTINGS.needs_review_threshold)
    print(render(rows, tot))


if __name__ == "__main__":
    main()
