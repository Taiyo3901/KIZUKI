# ローカルで動かす

クラウドを使わずに、撮影から管理画面での確認までの流れをパソコン1台で試せます。データは API のメモリ上にあり、プロセスを止めると消えます。

## 準備（最初の1回）

PowerShell または Git Bash を開き、先にリポジトリの直下へ移動します（`cd C:\Users\haruk\Documents\KIZUKI`）。ホームフォルダのまま実行すると、`requirements.txt` が見つからずに失敗します。

```
python -m venv .venv
.venv\Scripts\python -m pip install -r services/api/requirements.txt -r services/analyzer/requirements.txt pytest httpx
cd apps/capture && npm install
cd ../admin && npm install
```

仮想環境（.venv）は API と解析処理で共有します。画面は、それぞれのフォルダで npm install が要ります。

## 起動

ターミナルを3つ開きます。

1. API（ポート 8080）
   ```
   cd services/api
   ..\..\.venv\Scripts\python -m uvicorn app.main:app --port 8080
   ```
   起動すると、デモ用の撮影ポイントと「要確認」の判定が1件入ります。
2. 管理画面（ポート 5174）: `cd apps/admin && npm run dev`
3. 撮影画面（ポート 5173）: `cd apps/capture && npm run dev`

管理画面は http://localhost:5174 を開き、「開発用ログイン」を押します。撮影画面の URL は `http://localhost:5173/capture/<spotId>` です。spotId は管理画面の撮影ポイントの登録後に表示される URL で確認できます。デモデータの ID は `spot0001` です。

## 開発モードの仕組み

- 認証は `X-Dev-User` ヘッダーで代用します（`anon:<id>` は観光客、`admin:<id>:<siteId>` は管理者）。本番では Firebase Authentication に切り替わります。
- 撮影した写真は、API の `/dev-files` に送られます。保存と同時に、解析処理が同じプロセスの中で動き、結果が管理画面に出ます。
- Gemini と顔検出はモックです。モックの判定は、差分のある範囲をすべて「変化あり（確信度 0.7）」として返すので、判定の精度は確かめられません。

## 本物の Gemini を使う

API を起動する前に、次の環境変数を設定します。モデル名は公式ドキュメントで確認した値を使います。

```
$env:JUDGE_MODE = "vertex"
$env:GOOGLE_CLOUD_PROJECT = "kizuki-hackathon"
$env:GOOGLE_CLOUD_LOCATION = "global"
$env:GEMINI_MODEL_FAST = "gemini-3.8-flash"
```

認証は `gcloud auth application-default login` で保存した認証情報を使い、API キーは使いません。

## テスト

```
cd services/analyzer && ..\..\.venv\Scripts\python -m pytest
cd ../api && ..\..\.venv\Scripts\python -m pytest
cd ../../apps/capture && npm test
cd ../admin && npm test
```

## iPhone で撮影画面を開く

iPhone のカメラは、https のページでしか使えません。そこで、撮影画面を自己署名の証明書つきの https で公開し、API への通信も同じ入口（`/api`）に集めます。PC と iPhone を、同じ Wi-Fi につないでおきます。

1. PC の IP アドレスを調べます（PowerShell で `ipconfig`。Wi-Fi の「IPv4 アドレス」。ここでは `192.168.3.3` とします。Wi-Fi をつなぎ直すと変わることがあります）。
2. API を、次の環境変数つきで起動します（すでに動いている API は、Ctrl+C で止めてから）。`CAPTURE_BASE_URL` は、管理画面が発行する QR コードの行き先です。
   ```
   cd services/api
   $env:CAPTURE_BASE_URL = "https://192.168.3.3:5173"
   ..\..\.venv\Scripts\python -m uvicorn app.main:app --port 8080
   ```
3. 撮影画面を、スマホ用のモードで起動します（通常の `npm run dev` の代わり）。
   ```
   cd apps/capture
   npm run dev:phone
   ```
   Windows のファイアウォールの確認が出たら、「プライベート ネットワーク」を許可します。
4. iPhone の Safari で `https://192.168.3.3:5173/capture/spot0001` を開きます。
5. 「この接続ではプライバシーが保護されません」と出ます。証明書が自己署名のためで、自分の PC なので問題ありません。「詳細を表示」→「このWebサイトを閲覧」を選びます。
6. 撮影の注意で「撮影を始める」を押すと、カメラの許可を聞かれます。

画像のリンクは、API にアクセスした側のアドレスで作られます。PC の管理画面には `http://localhost:8080`、iPhone には `https://192.168.3.3:5173/api` が使われるので、PC 側で証明書の警告を許可する必要はありません。

iPhone で画面が開かないときは、次を確認します。
- PC と iPhone が同じ Wi-Fi か（ゲスト用 Wi-Fi は、端末どうしの通信を禁じていることがあります）。
- ファイアウォールの許可（ポート 5173）。
- IP アドレスが変わっていないか。

実機での動作は、まだ確認していません。

## 撮影画面について

PC のブラウザでもカメラは使えます（http://localhost だけは、https でなくても使えます）。
