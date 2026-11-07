# 石垣 実写サンプル集（Wikimedia Commons）

取得日: 2026-11-06 / 枚数: 240（うち石垣が主被写体の写真 220）
取得元: Wikimedia Commons の「Stone walls of ○○ Castle」系カテゴリ（熊本城・大阪城・江戸城・姫路城・金沢城・福岡城・伊賀上野城・高松城、ほか国内城郭）

## ファイル構成
- `images/<グループ>/` … 長辺 約1280px の縮小版（原寸は licenses.csv の original_url から取得可）
  - `01_kumamoto_2016quake_damaged` 熊本地震で被災した石垣（17）
  - `02_kumamoto_nagabei` 熊本城 長塀（19）
  - `03_kumamoto_other` 熊本城 その他（57）
  - `04_osaka` 〜 `10_takamatsu` 各城郭
  - `11_other_japan` その他の国内城郭（90）
- `licenses.csv` … 1画像1行。Excelで開けるUTF-8（BOM付き）
- `licenses.json` … 同内容のJSON
- `gallery.html` … ブラウザで開くサムネイル一覧
- `_check/` … 目視確認用のコンタクトシート
- `_raw/` … ダウンロード時の元データ（不要なら削除可）

## licenses.csv の主な列
| 列 | 内容 |
|---|---|
| file | 画像の相対パス |
| is_photo / wall_main_subject | 写真か / 石垣が主被写体か（目視判定） |
| damage_hint | 被災・崩落・養生シートが写っているか（目視、要確認） |
| license / license_url | ライセンス名とURL |
| share_alike | CC BY-SA系なら yes（改変物も同ライセンスで公開する義務） |
| author / attribution_text | 作者名と、そのまま使える帰属表示文 |
| commons_page | 元ページ（ライセンスの一次情報はここ） |

## ライセンス内訳（240枚）
CC BY-SA 4.0: 68 / CC BY-SA 3.0: 54 / CC BY 3.0: 40 / CC0: 36 / CC BY 4.0: 12 / CC BY 2.5: 8 / CC BY-SA 2.0: 8 / Public domain: 8 / CC BY 2.0: 5 / CC BY-SA 2.5: 1
すべて商用利用・改変可のライセンス（NC・ND は含まない）。

## 使うときの注意
- CC BY / BY-SA は帰属表示が必須。アプリ・スライド・リポジトリで `attribution_text` と `commons_page`（またはライセンスURL）を併記する。
- 縮小は「改変」に当たる場合がある。帰属表示に「縮小して使用」等を添えると安全。
- CC BY-SA の画像を加工して再配布する場合（例：アノテーション付き画像の公開）、その加工物も CC BY-SA にする必要がある。避けたい場合は CC0 / PD / CC BY のみで絞る。
- 学習データとして使うだけ・社内検証のみ、などのケースの扱いは各ライセンス条文と大会規約を確認すること。
- メタデータはCommonsの自動抽出値。最終確認は commons_page で行う。
