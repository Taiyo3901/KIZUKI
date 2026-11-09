# デプロイ手順（案）

この手順は一度も実行していません。コマンドは公式ドキュメントで確認する前の案なので、実行前にそれぞれ確かめてください。`PROJECT`、`REGION`、`BUCKET` は自分の値に置き換えます。

## 0. 前提

- プロジェクト: `kizuki-hackathon`（Vertex AI の API は有効にしてあります）
- リージョン: 原則 `asia-northeast1`。Gemini 3.8 Flash は、公式ドキュメントに東京が載っていません。`GOOGLE_CLOUD_LOCATION=global` で呼び出す方針です。保存先と処理は東京に置けますが、Gemini に送る画像の処理場所は `global` になるため、本番のリージョンはフェーズ1の結果を見て決め直します。

## 1. API を有効にする

```
gcloud services enable run.googleapis.com eventarc.googleapis.com firestore.googleapis.com storage.googleapis.com vision.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
```

## 2. Firestore と Cloud Storage

1. Firestore をネイティブモードで作成します（コンソールまたは `gcloud firestore databases create`）。
2. バケットを作ります。
   ```
   gcloud storage buckets create gs://BUCKET --location=asia-northeast1 --uniform-bucket-level-access
   ```
3. 元画像を1日で消すライフサイクルを設定します。解析が失敗しても、アップロードされた元画像が残り続けないようにするためです。
   ```
   gcloud storage buckets update gs://BUCKET --lifecycle-file=infra/storage-lifecycle.json
   ```
4. ブラウザから直接アップロードと表示をするため、CORS を設定します。先に `infra/storage-cors.json` の `REPLACE-...` を、Hosting の実際の URL に置き換えます。
   ```
   gcloud storage buckets update gs://BUCKET --cors-file=infra/storage-cors.json
   ```
5. `uploadRequests` の `expireAt` に TTL ポリシーを設定します（Firestore のコンソールまたは `gcloud firestore fields ttls update`）。
6. ルールとインデックスを反映します（Firebase CLI が必要です）。
   ```
   firebase deploy --only firestore,storage
   ```

## 3. サービスアカウントと権限

API 用と解析用に別のサービスアカウントを作ります。必要な権限の目安です。

| 対象 | 権限 |
|---|---|
| API | Firestore の読み書き（roles/datastore.user）、バケットの読み書き（roles/storage.objectAdmin）、署名付きURLの発行（自分自身への roles/iam.serviceAccountTokenCreator） |
| 解析処理 | Firestore の読み書き、バケットの読み書き、Vertex AI の利用（roles/aiplatform.user）、Cloud Vision の利用 |
| Eventarc のトリガー | 解析処理の呼び出し（roles/run.invoker）、イベントの受信（roles/eventarc.eventReceiver） |

Cloud Storage のイベントを受けるには、Cloud Storage のサービスエージェントに `roles/pubsub.publisher` が必要です。

## 4. Cloud Run へのデプロイ

API と解析処理の Dockerfile は、どちらも `shared/` を取り込むため、リポジトリの直下をビルドの対象にします（`docker build -f services/api/Dockerfile .` の形）。Cloud Build で行う場合は、Dockerfile を指定できる設定ファイルが要ります。書き方は公式ドキュメントで確認してください。イメージは Artifact Registry に置き、Cloud Run のサービスとして `api` と `analyzer` をデプロイします。

環境変数の例は次のとおりです。

| サービス | 環境変数 |
|---|---|
| API | `BACKEND=gcp` `AUTH_MODE=firebase` `APP_CHECK=on` `STORAGE_BUCKET` `GOOGLE_CLOUD_PROJECT` `CAPTURE_BASE_URL` `CORS_ORIGINS` |
| 解析処理 | `BACKEND=gcp` `JUDGE_MODE=vertex` `FACE_MODE=vision` `STORAGE_BUCKET` `GOOGLE_CLOUD_PROJECT` `GOOGLE_CLOUD_LOCATION=global` `GEMINI_MODEL_FAST` `GEMINI_MODEL_PRO`（任意） |

安全のための決まり:

- API は、Cloud Run 上で `AUTH_MODE=firebase` と `BACKEND=gcp` が揃っていないと起動しません（環境変数の付け忘れで、開発用の管理者ヘッダーが本番で通ってしまうのを防ぐため）。
- 解析処理は認証なしの呼び出しを許可しません（デプロイ時に未認証を許可しない設定にする。公式ドキュメントで該当のフラグを確認）。呼び出せるのは Eventarc のサービスアカウントだけにします。

## 5. Eventarc

アップロードの完了を、解析処理に知らせます。

```
gcloud eventarc triggers create analyzer-trigger --location=asia-northeast1 --event-filters="type=google.cloud.storage.object.v1.finalized" --event-filters="bucket=BUCKET" --destination-run-service=analyzer --destination-run-region=asia-northeast1 --service-account=EVENTARC_SA
```

トリガーは `uploads/` 以外のオブジェクトにも反応します。解析処理は `uploads/{spotId}/{uuid}.jpg` 以外を無視するので、ぼかし済みの写真を保存しても再び解析されることはありません。

## 6. 認証

1. Firebase Authentication で、匿名ログインと Google ログインを有効にします。
2. 管理者に権限を付けます。
   ```
   set PYTHONPATH=.
   python infra/set_admin_claims.py <uid> <siteId>
   ```
3. App Check（reCAPTCHA Enterprise）を設定し、撮影画面の `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY` に入れます。
4. テンプレートと文化財を作ります。
   ```
   python infra/seed_firestore.py --site <siteId> <名前> <adminUid>
   ```

## 7. 画面（Firebase Hosting）

```
cd apps/capture && npm run build
cd ../admin && npm run build
firebase target:apply hosting capture <撮影画面のサイトID>
firebase target:apply hosting admin <管理画面のサイトID>
firebase deploy --only hosting
```

画面の環境変数（`VITE_API_BASE`、`VITE_AUTH_MODE=firebase`、Firebase の設定値、Maps の API キー）は、ビルド時に `.env.production` へ書きます。Maps の API キーは、HTTP リファラーで制限します。

## まだ確認していないこと

- Firestore のルールとインデックス（エミュレータには Java が必要で、未導入です）
- 署名付き URL の発行と、ブラウザからの PUT
- Eventarc から解析処理への呼び出し
- Cloud Vision による顔のぼかし
- App Check と匿名ログインの組み合わせ

## 使うリソースを増やさない設定（実施済み）

| 対象 | 設定 | ファイル／コマンド |
|---|---|---|
| Artifact Registry | 各イメージの新しい 3 版だけ残し、古いものは自動削除 | `infra/artifact-cleanup.json`（`gcloud artifacts repositories set-cleanup-policies kizuki --location asia-northeast1 --policy infra/artifact-cleanup.json --no-dry-run`） |
| ビルド用バケット（`<project>_cloudbuild`） | 3 日たったソースを自動削除 | `infra/cloudbuild-bucket-lifecycle.json`（`gcloud storage buckets update gs://<project>_cloudbuild --lifecycle-file=...`） |
| 写真バケットの `uploads/` | 1 日で自動削除（元画像） | `infra/storage-lifecycle.json` |
| Firestore `uploadRequests`（回数制限の記録） | `expireAt`（作成の 1 日後）で自動削除 | `gcloud firestore fields ttls update expireAt --collection-group=uploadRequests --enable-ttl` |
| Cloud Run | 使わないときは 0 台へ縮む（`analyzer`）。`api` は動作を速くするため常時 1 台。デモ後は 0 に戻す | `gcloud run services update api --min-instances 0 ...` |

### Cloud Run の大きさ（実測にもとづく）

名古屋城の写真（2048×1536）で測ったピークは、`analyzer` が約 850MB（CPU 時間 約 5.6 秒）、`api` が約 170MB です。

| サービス | 変更前 | 変更後 |
|---|---|---|
| analyzer | 2Gi／2 CPU | 1.5Gi／1 CPU |
| api | 1Gi／1 CPU | 512Mi／1 CPU |

変更コマンド：`gcloud run deploy <service> --image <image> --cpu 1 --memory 1536Mi`（analyzer）／`--memory 512Mi`（api）。
メモリ不足（`Memory limit exceeded`）がログに出たら、analyzer を 2Gi に戻してください。
