"""Built-in target templates (CLAUDE.md section 2). Seeded into the `templates` collection."""
from shared.schemas.models import Template

STONE_WALL = Template(
    name="石垣",
    observationItems=["緩み", "割れ", "表面劣化", "孕み出し", "前倒れ", "崩れ", "樹木"],
    promptInstruction=(
        "あなたは城の石垣を点検する専門家の補助をしています。"
        "同じ場所を撮った『前（基準写真）』と『後（投稿写真）』の切り抜きを比べ、"
        "石垣の状態が悪くなる方向の変化だけを報告してください。"
        "光の当たり方、影、天候、植物の季節による色の違いは『変化』に含めないでください。"
        "人や物が一時的に写り込んだだけのものも変化ではありません。"
        "変化が見つからなければ noChange を true にし、changes は空にしてください。"
    ),
)

BUILTIN_TEMPLATES: dict[str, Template] = {"stone_wall": STONE_WALL}
