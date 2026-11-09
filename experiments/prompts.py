"""The stone-wall template as it was BEFORE "落書き・汚損" was added, so the two wordings can be compared on the same images."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.schemas.models import Template  # noqa: E402
from shared.schemas.templates import BUILTIN_TEMPLATES  # noqa: E402

OLD = Template(
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
NEW = BUILTIN_TEMPLATES["stone_wall"]

# B: NEW plus a true statement about production photos (they come straight from the phone camera). Aim: stop Gemini
# from dismissing a real displacement as "a stitching / editing artefact".
_FACT = "2枚とも、スマホのカメラで撮った実際の写真で、合成や画像加工は行われていません。"
B = NEW.model_copy(update={"promptInstruction": NEW.promptInstruction.replace(
    "あなたは城の石垣を点検する専門家の補助をしています。", "あなたは城の石垣を点検する専門家の補助をしています。" + _FACT, 1)})
assert B.promptInstruction != NEW.promptInstruction


def template_for(name: str) -> Template:
    return {"old": OLD, "new": NEW, "b": B}[name]
