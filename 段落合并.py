# -*- coding: utf-8 -*-
"""
唐五代笔记小说大观 上 —— 初校第一步：合并被分页打断的段落

1. 把 OCR 生成的 .md 原样复制为「唐五代上-初校.md」；
2. 在副本上处理：凡是空行前的段落没有以中文句末标点收尾（逗号、顿号、
   或干脆没有标点），就把它与空行后的段落接成一段，直到接出句末标点为止。

标题、表格、目录、题名列表、卷次名、英文与 JSON 附注等不属于正文段落，
不参与合并；合并明细写入「唐五代上-初校_合并日志.txt」备查。
"""
import re
import shutil

SRC = ("唐五代笔记小说大观 上 (上海古籍出版社编, Ruming Ding, Zongwei Li etc.) "
       "(z-library.sk, 1lib.sk, z-lib.sk).pdf_by_PaddleOCR-VL-1.6.md")
DST = "唐五代上-初校.md"
LOG = "唐五代上-初校_合并日志.txt"

# 句末标点：以此收尾者视为完整段落
TERMINAL = set("。！？；…”’〞）)》〉」』】")
# 中文标点：一段之内完全不含这些符号，多半是题名、卷次、人名等非正文行
CJK_PUNCT = set("，。、；：！？“”‘’《》〈〉（）()【】「」『』…—·")
CJK_CHAR = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
DOTTED = re.compile(r"[.．]{3,}|……")
HEADING_LIKE_MAX = 30


def is_structural(block):
    """标题、表格、图片、公式块等结构行，不与正文合并。"""
    first = block[0].lstrip()
    return first.startswith(("#", "<", "![", "|", "$$", "---", "```"))


def is_non_paragraph(block):
    """判断整段是否不属于正文散段（不可参与合并）。"""
    if is_structural(block):
        return True
    text = "".join(line.strip() for line in block)
    if not CJK_CHAR.search(text):          # 纯英文、版权说明、JSON 附注
        return True
    if DOTTED.search(text):                # 目录行
        return True
    if len(text) < HEADING_LIKE_MAX and not (set(text) & CJK_PUNCT):
        return True                        # 题名列表、卷次名、校点者署名等
    return False


def joins_forward(block, nxt):
    """本段是否应当接上下一段。"""
    tail = block[-1].strip()
    if not tail or tail[-1] in TERMINAL:
        return False
    if is_non_paragraph(block) or is_non_paragraph(nxt):
        return False
    if len(nxt) > 1:                       # 多行段落结构不明，留待人工
        return False
    if tail[-1] in "：:":                  # 「诗曰：」下接诗行属原书格式，不并；
        head = nxt[0].strip()              # 下接引号者是被分页截断的话语，要并
        return head.startswith(("“", "「", "‘"))
    return True


def main():
    shutil.copyfile(SRC, DST)
    lines = open(DST, encoding="utf-8").read().split("\n")

    # 切分为「段落 + 其后的空行」
    units, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        start = i
        while i < len(lines) and lines[i].strip():
            i += 1
        block_end = i
        while i < len(lines) and not lines[i].strip():
            i += 1
        units.append({"lines": lines[start:block_end],
                      "gap": lines[block_end:i],
                      "first_lineno": start + 1})

    head = lines[:units[0]["first_lineno"] - 1] if units else lines

    merged, log, n_merge, n_group = [], [], 0, 0
    for unit in units:
        if merged and joins_forward(merged[-1]["lines"], unit["lines"]):
            prev = merged[-1]
            before = prev["lines"][-1].strip()
            prev["lines"][-1] = before + unit["lines"][0].strip()
            prev["gap"] = unit["gap"]
            prev["merged_from"].append(unit["first_lineno"])
            n_merge += 1
            log.append("原第 %d 行  +  原第 %d 行\n    …%s ⊕ %s…\n" % (
                prev["first_lineno"], unit["first_lineno"],
                before[-30:], unit["lines"][0].strip()[:30]))
        else:
            unit["merged_from"] = []
            merged.append(unit)

    out = list(head)
    for unit in merged:
        if unit["merged_from"]:
            n_group += 1
        out.extend(unit["lines"])
        out.extend(unit["gap"])
    open(DST, "w", encoding="utf-8", newline="\n").write("\n".join(out))

    open(LOG, "w", encoding="utf-8", newline="\n").write(
        "源文件：%s\n生成：%s\n\n段落总数：%d → %d\n"
        "合并次数：%d（并成 %d 段）\n\n%s\n" % (
            SRC, DST, len(units), len(merged), n_merge, n_group,
            "-" * 60) + "\n".join(log))

    print("blocks: %d -> %d ; merges: %d ; groups: %d" % (
        len(units), len(merged), n_merge, n_group))


if __name__ == "__main__":
    main()
