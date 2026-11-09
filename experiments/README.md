# experiments — フェーズ1：精度検証

前後の写真を「位置合わせ → 差分 → Gemini 判定」に通し、変化の位置と種類を JSON で出して、誤検知と見逃しを表にします。

## 準備（コマンドプロンプトまたは PowerShell。`experiments` フォルダで実行）
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## 動作確認（合成画像・モック。費用なし）
```
.venv\Scripts\python make_synthetic_samples.py
.venv\Scripts\python run_experiment.py samples_synthetic\labels.json out
.venv\Scripts\python evaluate.py samples_synthetic\labels.json out\results.json
```
合成画像は動作確認用です。実際の精度は分かりません。

## 実写の石垣に変化を合成して試す（`../ishigaki_samples` を使用）
```
.venv\Scripts\python make_derived_samples.py 20
.venv\Scripts\python run_experiment.py samples_derived\labels.json out_derived
.venv\Scripts\python evaluate.py samples_derived\labels.json out_derived\results.json
```
- 基準＝実写。投稿写真＝同じ写真に「明るさ・色・ノイズ・小さな視点のずれ」を加え、変化ありは「ひび」か「石の局所的なずれ」を足したもの。変化の位置が分かっている。
- ShareAlike（CC BY-SA）の写真は使わない。生成物は手元のみ（`.gitignore` 済み）。出典は `samples_derived/sources.json`。
- 本物のダメージの検出精度は測れない。測れるのは「位置合わせ」と「差分による候補抽出」の段階。

## 熊本城の実際の前後ペアで試す（`../ishigaki_change_pairs` を使用）
同じ場所を別の日に撮った写真6組（崩落、復旧、変化の少ないもの）です。撮影位置と角度が前後で違うため、本番の撮影（QRコードで同じ位置へ誘導する）より位置合わせが難しい条件です。
```
.venv\Scripts\python run_experiment.py pairs_real\labels.json out_pairs_real
```
`pairs_real/labels.json` は前（A）を基準写真、後（B）を投稿写真として組んであります。変化の位置の正解は付けていないので、`evaluate.py` は使えません。結果は `out_pairs_real/results.json` と、赤枠つきの `*_overlay.jpg` で確かめます。

## 本番と同じ処理で試す（費用あり）
`miss_check.py`（足した変化がどの段階で落ちるか）と `regress_prod.py`（実写の「変化なし」の組で誤検知が出ないか）は、解析処理（`services/analyzer`）の本物の部品を使います。Gemini と、`--objects` を付けたときは Vision を呼びます。
```
set JUDGE_MODE=vertex & set GOOGLE_CLOUD_PROJECT=<プロジェクト ID> & set GEMINI_MODEL_FAST=<モデル名>
python miss_check.py <基準写真.jpg> --judge
python regress_prod.py samples\labels.json --objects
```

## 実写のサンプルで試す
1. `samples/` に基準写真と投稿写真を置き、`samples/labels.json` を書く（形式は `samples_synthetic/labels.json` と同じ）。
   - `expected` の `box` は基準写真に対する割合（0〜1）の `x, y, width, height`。変化なしの画像は `"expected": []`。
   - 種類に幅を持たせたいときは `"acceptable_categories": ["割れ", "緩み"]` を足す。
2. `run_experiment.py samples\labels.json out` → `evaluate.py samples\labels.json out\results.json`
3. `out\<id>_overlay.jpg`：橙の枠＝差分の候補、赤の枠＝Gemini が示した変化。

## 本物の Gemini を使う（費用がかかる）
```
set JUDGE_MODE=vertex
set GOOGLE_CLOUD_PROJECT=<プロジェクトID>
set GEMINI_MODEL_FAST=<公式ドキュメントで確認したモデルID>
set GEMINI_MODEL_PRO=<同上（任意。確信度 0.4〜0.6 の再判定用）>
gcloud auth application-default login
```
APIキーは使いません。リージョンの初期値は `asia-northeast1` です（モデルが使えるかは未確認）。

## 調整できる値（環境変数）
`NEEDS_REVIEW_THRESHOLD`(0.6) / `RECHECK_LOW`(0.4) / `RECHECK_HIGH`(0.6) / `DIFF_DISSIM_THRESHOLD`(0.55) / `DIFF_MIN_AREA_RATIO` / `DIFF_MAX_CANDIDATES` / `CROP_MARGIN` / `ALIGN_MIN_INLIERS`
