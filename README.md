# KIZUKI（文化財見守り）

観光客が撮る「同じ角度の1枚」を積み重ねて、文化財（城の石垣など）の小さな変化に早く気づくシステムです。
AI は「要確認」を出すまでで、「変化あり」を確定するのは管理者です。

- 設計の前提: [CLAUDE.md](CLAUDE.md)
- 構成の全体像: [docs/architecture.md](docs/architecture.md)
- ローカルでの動かし方（iPhone の実機を含む）: [docs/local-dev.md](docs/local-dev.md)
- デモの流れ: [docs/demo.md](docs/demo.md)
- デプロイ手順（案）: [infra/DEPLOY.md](infra/DEPLOY.md)

| フォルダ | 内容 |
|---|---|
| `apps/capture` | 観光客の撮影画面（React + Vite、PWA） |
| `apps/admin` | 管理画面（React + Vite） |
| `services/api` | API（FastAPI） |
| `services/analyzer` | 解析処理（OpenCV + Gemini） |
| `shared` | データ型と、保存先・DB の差し替え口 |
| `infra` | Firestore と Storage のルール、デプロイ手順 |
| `experiments` | 精度検証のスクリプト |

## このリポジトリに含まれないもの
- 秘密情報（`.env`、`.env.local`。API キーなど）。
- サンプル写真（`ishigaki_samples/images`、`ishigaki_change_pairs/photos`）。Wikimedia Commons などの写真で、サイズが大きく、写真ごとにライセンスが異なるためです。出典とライセンスの一覧（`licenses.csv`）だけを含めています。
- 仮想環境、`node_modules`、実験の出力。
