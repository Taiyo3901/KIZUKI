# デプロイ手順（Google Cloud）

`kizuki-hackathon` プロジェクトに、実際に行った手順です（2026-11-09）。コマンドは、PowerShell か Git Bash で、リポジトリの直下から実行します。`PROJECT` は `kizuki-hackathon` です。

| 部品 | 場所 |
|---|---|
| 撮影画面 | https://kizuki-capture.web.app/capture/{撮影ポイントID} |
| 管理画面 | https://kizuki-admin.web.app |
| API（Cloud Run `api`） | https://api-210277559315.asia-northeast1.run.app |
| 解析処理（Cloud Run `analyzer`） | 非公開（Eventarc だけが呼べます） |

## 0. 前提

- リージョンは、原則 `asia-northeast1`（東京）です。Gemini 3.8 Flash は、公式ドキュメントに東京が載っていません。そのため `GOOGLE_CLOUD_LOCATION=global` で呼び出します。保存先と処理は東京ですが、Gemini に送る画像の処理場所は `global` になります。
- この PC に Docker は要りません。イメージは Cloud Build でビルドします。
- Firebase CLI は `npx firebase-tools` で使います。最初に `npx firebase-tools login` でログインします。

## 1. API を有効にする

```
gcloud services enable run.googleapis.com eventarc.googleapis.com firestore.googleapis.com storage.googleapis.com vision.googleapis.com aiplatform.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com identitytoolkit.googleapis.com --project PROJECT
```

## 2. Firestore と Cloud Storage

1. Firestore をネイティブモードで作ります（東京）。
2. バケット `kizuki-hackathon-photos` を、東京に作ります（一律のバケットレベルアクセス）。
   ```
   gcloud storage buckets create gs://kizuki-hackathon-photos --location=asia-northeast1 --uniform-bucket-level-access
   ```
3. 元画像を 1 日で消すライフサイクルを設定します。解析が失敗しても、元画像が残り続けないようにするためです。
   ```
   gcloud storage buckets update gs://kizuki-hackathon-photos --lifecycle-file=infra/storage-lifecycle.json
   ```
4. ブラウザから直接アップロードと表示をするため、CORS を設定します。`infra/storage-cors.json` の `REPLACE-capture-site`、`REPLACE-admin-site` を、Hosting のサイト ID（`kizuki-capture`、`kizuki-admin`）に置き換えたものを使います。
5. `uploadRequests` の `expireAt` に TTL を設定します。
   ```
   gcloud firestore fields ttls update expireAt --collection-group=uploadRequests --enable-ttl
   ```
6. ルールとインデックスを反映します。
   ```
   npx firebase-tools deploy --only firestore:rules,firestore:indexes --project PROJECT
   ```

## 3. サービスアカウントと権限

API 用（`kizuki-api`）と、解析用（`kizuki-analyzer`）、Eventarc 用に、別のサービスアカウントを作ります。

| 対象 | 権限 |
|---|---|
| API | Firestore の読み書き（roles/datastore.user）、バケットの読み書き（roles/storage.objectAdmin）、署名付き URL の発行（自分自身への roles/iam.serviceAccountTokenCreator） |
| 解析処理 | Firestore の読み書き、バケットの読み書き、Vertex AI の利用（roles/aiplatform.user）、Cloud Vision の利用 |
| Eventarc のトリガー | 解析処理の呼び出し（roles/run.invoker）、イベントの受信（roles/eventarc.eventReceiver） |

Cloud Storage のサービスエージェント（`service-<プロジェクト番号>@gs-project-accounts.iam.gserviceaccount.com`）には、`roles/pubsub.publisher` が必要です。付けた直後は反映されず、トリガーの作成が失敗することがあります。数分待って、やり直してください。

署名付き URL は、IAM の署名 API を使うため、Storage のクライアントは `cloud-platform` の権限範囲で作ります（`shared/adapters/gcp.py`）。

## 4. イメージのビルドと Cloud Run へのデプロイ

Dockerfile は、どちらも `shared/` を取り込むので、リポジトリの直下をビルドの対象にします。設定は `infra/cloudbuild-api.yaml` と `infra/cloudbuild-analyzer.yaml` です。

```
gcloud artifacts repositories create kizuki --repository-format=docker --location=asia-northeast1 --project PROJECT
gcloud builds submit . --config infra/cloudbuild-analyzer.yaml --substitutions _IMAGE=asia-northeast1-docker.pkg.dev/PROJECT/kizuki/analyzer:v1 --project PROJECT
gcloud builds submit . --config infra/cloudbuild-api.yaml --substitutions _IMAGE=asia-northeast1-docker.pkg.dev/PROJECT/kizuki/api:v1 --project PROJECT
```

**解析処理**（認証なしの呼び出しを許可しません）:

```
gcloud run deploy analyzer --image <イメージ> --region asia-northeast1 --project PROJECT --service-account kizuki-analyzer@PROJECT.iam.gserviceaccount.com --no-allow-unauthenticated --cpu 1 --memory 1536Mi --concurrency 1 --timeout 300 --min-instances 0 --max-instances 3 --set-env-vars "BACKEND=gcp,JUDGE_MODE=vertex,FACE_MODE=vision,OBJECT_MODE=vision,STORAGE_BUCKET=kizuki-hackathon-photos,GOOGLE_CLOUD_PROJECT=PROJECT,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL_FAST=gemini-3.8-flash"
```

**API**（観光客が使うので、Cloud Run としては公開します。認証は API の中で、Firebase のトークンを検証します）:

```
gcloud run deploy api --image <イメージ> --region asia-northeast1 --project PROJECT --service-account kizuki-api@PROJECT.iam.gserviceaccount.com --allow-unauthenticated --cpu 1 --memory 512Mi --timeout 120 --min-instances 1 --max-instances 5 --set-env-vars "^@^BACKEND=gcp@AUTH_MODE=firebase@APP_CHECK=off@STORAGE_BUCKET=kizuki-hackathon-photos@GOOGLE_CLOUD_PROJECT=PROJECT@CAPTURE_BASE_URL=https://kizuki-capture.web.app@CORS_ORIGINS=https://kizuki-capture.web.app,https://kizuki-admin.web.app"
```

- `^@^` は、環境変数の区切りを `@` にするためです（`CORS_ORIGINS` にカンマが入るので）。
- API は、Cloud Run 上で `AUTH_MODE=firebase` と `BACKEND=gcp` が揃っていないと起動しません（付け忘れで、開発用の管理者ヘッダーが本番で通るのを防ぐため）。
- Cloud Run は `/healthz` を予約していて、Google の 404 が返ります。アプリの不具合ではありません。

## 5. Eventarc

```
gcloud eventarc triggers create analyzer-trigger --location=asia-northeast1 --event-filters="type=google.cloud.storage.object.v1.finalized" --event-filters="bucket=kizuki-hackathon-photos" --destination-run-service=analyzer --destination-run-region=asia-northeast1 --service-account=kizuki-eventarc@PROJECT.iam.gserviceaccount.com
```

トリガーは `uploads/` 以外にも反応しますが、解析処理は `uploads/{spotId}/{uuid}.jpg` 以外を無視します。イベントは再配信されることがあり、その場合は「処理済み」として扱います。

## 6. Firebase（認証と画面）

1. Firebase を、既存のプロジェクトに追加します。
   ```
   npx firebase-tools projects:addfirebase PROJECT
   npx firebase-tools hosting:sites:create kizuki-capture --project PROJECT
   npx firebase-tools hosting:sites:create kizuki-admin --project PROJECT
   npx firebase-tools apps:create WEB kizuki-web --project PROJECT
   npx firebase-tools apps:sdkconfig WEB <アプリID> --project PROJECT
   ```
2. 認証を初期化し、匿名ログインを有効にします（REST。`gcloud auth print-access-token` のトークンを使います）。
   - `POST https://identitytoolkit.googleapis.com/v2/projects/PROJECT/identityPlatform:initializeAuth`
   - `PATCH https://identitytoolkit.googleapis.com/admin/v2/projects/PROJECT/config?updateMask=signIn.anonymous.enabled`（本文 `{"signIn":{"anonymous":{"enabled":true}}}`）
3. Google ログインは、コンソール（Authentication → Sign-in method → Google）で有効にします。
4. **承認済みドメイン**に、2 つの画面のドメインを足します。これを忘れると、Google ログインのポップアップが、開いてすぐ閉じます。
   `PATCH .../admin/v2/projects/PROJECT/config?updateMask=authorizedDomains`（`localhost`、`PROJECT.firebaseapp.com`、`PROJECT.web.app`、`kizuki-capture.web.app`、`kizuki-admin.web.app`）
5. 管理者の権限と、テンプレート・文化財を作ります。管理画面で、いちど Google ログインしてから行います。
   ```
   set PYTHONPATH=.
   python infra/seed_firestore.py --site <siteId> <名前> <adminUid>
   python infra/set_admin_claims.py <uid> <siteId>
   ```
   権限は、ログインし直すと反映されます。`sites` の `adminUids` にも、同じ uid を入れます。
6. 画面をビルドして公開します。環境変数は、ビルド時に渡します。
   ```
   VITE_AUTH_MODE=firebase  VITE_API_BASE=<API の URL>
   VITE_FIREBASE_API_KEY  VITE_FIREBASE_AUTH_DOMAIN  VITE_FIREBASE_PROJECT_ID  VITE_FIREBASE_APP_ID
   VITE_GOOGLE_MAPS_API_KEY   （管理画面のみ。HTTP リファラーで制限する）
   ```
   ```
   cd apps/capture && npm run build
   cd ../admin && npm run build
   cd ../..
   npx firebase-tools target:apply hosting capture kizuki-capture --project PROJECT
   npx firebase-tools target:apply hosting admin kizuki-admin --project PROJECT
   npx firebase-tools deploy --only hosting --project PROJECT
   ```

## App Check（現状は切ってあります）

`APP_CHECK=off` で動かしています。reCAPTCHA Enterprise の準備をしていないためです。**切っている間は、匿名ログインを作り直すと、投稿の回数制限（1 人 10 回／時間）を回避できます。** 公開を続けるなら、reCAPTCHA Enterprise のサイトキーを作り、撮影画面の `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY` に入れて、API を `APP_CHECK=on` にします（撮影画面は、サイトキーがあるときだけ App Check を使います）。

## 確認できたこと・できていないこと

| 項目 | 状況 |
|---|---|
| 撮影 → アップロード（署名付き URL）→ Eventarc → 解析 → Firestore | 動作を確認（クラウド上） |
| 顔のぼかし（Vision）、元画像の削除、品質チェック（Gemini） | 動作を確認 |
| 匿名ログインでの API 呼び出し、管理者の権限の分離 | 動作を確認 |
| 管理者の Google ログイン、撮影ポイントの登録 | 動作を確認 |
| 変化の検出（差分 → Gemini の判定）の精度 | 未検証。細い線と小さな四角を足した画像は「変化なし」でした |
| App Check | 切っています |
| Firestore のルールとインデックス | 反映済み。エミュレータでの検証は未実施 |
| iPhone 実機でのレイアウト付き保存画像 | 未確認 |

## 使うリソースを増やさない設定（実施済み）

| 対象 | 設定 | ファイル／コマンド |
|---|---|---|
| Artifact Registry | 各イメージの新しい 3 版だけ残し、古いものは自動削除 | `infra/artifact-cleanup.json`（`gcloud artifacts repositories set-cleanup-policies kizuki --location asia-northeast1 --policy infra/artifact-cleanup.json --no-dry-run`） |
| ビルド用バケット（`<project>_cloudbuild`） | 3 日たったソースを自動削除 | `infra/cloudbuild-bucket-lifecycle.json`（`gcloud storage buckets update gs://<project>_cloudbuild --lifecycle-file=...`） |
| 写真バケットの `uploads/` | 1 日で自動削除（元画像） | `infra/storage-lifecycle.json` |
| Firestore `uploadRequests`（回数制限の記録） | `expireAt`（作成の 1 日後）で自動削除 | 上の 2.5 |
| 品質チェックで不合格の写真 | 画像は保存しない（理由だけ記録） | 解析処理のコード |
| Cloud Run | `analyzer` は使わないときは 0 台。`api` は動作を速くするため常時 1 台（デモ後は 0 に戻す） | `gcloud run services update api --min-instances 0 --region asia-northeast1 --project PROJECT` |

### Cloud Run の大きさ（実測にもとづく）

名古屋城の写真（2048×1536）で測ったピークは、`analyzer` が約 850MB（CPU 時間 約 5.6 秒）、`api` が約 170MB です。

| サービス | 変更前 | 変更後 |
|---|---|---|
| analyzer | 2Gi／2 CPU | 1.5Gi／1 CPU |
| api | 1Gi／1 CPU | 512Mi／1 CPU |

メモリ不足（`Memory limit exceeded`）がログに出たら、analyzer を 2Gi に戻してください。

## 後片付け

デモが終わったら、費用と公開範囲を減らします。

1. `api` を常時 1 台から 0 台に戻します（上のコマンド）。
2. 使わないなら、`api` を非公開に戻します。`gcloud run services remove-iam-policy-binding api --member=allUsers --role=roles/run.invoker --region asia-northeast1 --project PROJECT`
3. プロジェクトごと消すときは、`gcloud projects delete PROJECT` です（元に戻せません）。
