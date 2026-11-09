"""Built-in target templates (CLAUDE.md section 2). Seeded into the `templates` collection."""
from shared.schemas.models import Template

STONE_WALL = Template(
    name="石垣",
    observationItems=["緩み", "割れ", "表面劣化", "孕み出し", "前倒れ", "崩れ", "樹木", "落書き・汚損"],
    promptInstruction=(
        "あなたは城の石垣を点検する専門家の補助をしています。"
        "同じ場所を撮った『前（基準写真）』と『後（投稿写真）』の切り抜きを比べ、"
        "石垣の状態が悪くなる方向の変化だけを報告してください。"
        "石垣の面に貼られた物（シール、貼り紙）、描かれた物（落書き）、付着した汚れは、"
        "石垣の汚損として『落書き・汚損』で報告してください。"
        "光の当たり方、影、天候、植物の季節による色の違いは『変化』に含めないでください。"
        "歩いている人、乗り物、荷物など、石垣の面に付いていない、一時的に手前を通っただけのものは変化ではありません。"
        "変化が見つからなければ noChange を true にし、changes は空にしてください。"
    ),
)

BUILTIN_TEMPLATES: dict[str, Template] = {"stone_wall": STONE_WALL}
