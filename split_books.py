"""Split 唐五代上-初校.md into one file per book, using the 总目 book list."""

import re
from pathlib import Path

SRC = Path(__file__).parent / "唐五代上-初校.md"
OUT_DIR = Path(__file__).parent / "唐五代上"

# Books of 上册, in the order given by 总目.
BOOKS = [
    "朝野佥载",
    "隋唐嘉话",
    "教坊记",
    "龙城录",
    "唐国史补",
    "大唐新语",
    "玄怪录",
    "续玄怪录",
    "次柳氏旧闻",
    "博异志",
    "纂异记",
    "甘泽谣",
    "酉阳杂俎",
    "刘宾客嘉话录",
    "因话录",
    "大唐传载",
    "独异志",
    "明皇杂录",
]

# The OCR text mixes simplified and traditional forms in some headings.
VARIANTS = {"朝野佥载": {"朝野僉載", "朝野佥載", "朝野僉载"}}

HEADING = re.compile(r"^(#{1,6})\s*(.+?)\s*$")


def normalize(text):
    return re.sub(r"[\s\u3000]+", "", text)


def main():
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    headings = []
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if m:
            headings.append((i, normalize(m.group(2))))

    starts = []
    pos = 0
    for book in BOOKS:
        names = {book} | VARIANTS.get(book, set())
        for idx, (line_no, text) in enumerate(headings[pos:], start=pos):
            if text in names:
                starts.append(line_no)
                pos = idx + 1
                break
        else:
            raise SystemExit(f"heading not found for book: {book}")

    OUT_DIR.mkdir(exist_ok=True)

    bounds = starts + [len(lines)]
    front = lines[: starts[0]]
    (OUT_DIR / "00-卷首.md").write_text("".join(front), encoding="utf-8")
    print(f"00-卷首.md  lines 1-{starts[0]}  ({len(front)} lines)")

    for n, book in enumerate(BOOKS, start=1):
        start, end = bounds[n - 1], bounds[n]
        chunk = lines[start:end]
        name = f"{n:02d}-{book}.md"
        (OUT_DIR / name).write_text("".join(chunk), encoding="utf-8")
        print(f"{name}  lines {start + 1}-{end}  ({len(chunk)} lines)")


if __name__ == "__main__":
    main()
