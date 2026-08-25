# -*- coding: utf-8 -*-
"""导出后严格核对：
1. 完整性——把各段落文件按序拼回，须与「校订全本」去标题后的正文逐字相同；
2. 目录——目录每一条目须对应一个已导出的章或篇（可处理目录连排成行的情况）;
3. 逐书写出核对单。
"""
import json
import os
import re

ROOT = r"c:\Users\lx\Desktop\笔记小说"
WS = re.compile(r"[\s\u3000]+")
HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
PAGE = re.compile(r"\s*[.．\u2026]{2,}\s*[（(]?\s*\d+\s*[)）]?\s*$")
META = re.compile(r"^<!--.*?-->\s*", re.S)


def nows(s):
    return WS.sub("", s)


def source_paras(book):
    """校订全本中的正文段落（不含标题），按文档顺序。"""
    path = os.path.join(ROOT, book, f"{book}-校订全本.md")
    text = open(path, encoding="utf-8").read()
    paras = []
    for blk in re.split(r"\n\s*\n", text):
        blk = blk.strip()
        if blk and not HEAD.match(blk):
            paras.append(blk)
    return paras


def exported_paras(book):
    """各章/篇目录下的段落文件，按 章号 -> 段号 排序。"""
    bookdir = os.path.join(ROOT, book)
    items = []
    for ch in sorted(d for d in os.listdir(bookdir)
                     if os.path.isdir(os.path.join(bookdir, d)) and re.match(r"^\d\d-", d)):
        if ch == "00-前言":
            continue
        cdir = os.path.join(bookdir, ch)
        for root, dirs, files in os.walk(cdir):
            dirs.sort()
            for f in sorted(files):
                if re.fullmatch(r"\d{3}\.md", f):
                    body = open(os.path.join(root, f), encoding="utf-8").read()
                    body = META.sub("", body).strip()
                    n = int(f[:3])
                    items.append((int(ch[:2]), n, body))
    items.sort(key=lambda x: (x[0], x[1]))
    return [b for _, _, b in items]


def front_paras(book):
    fd = os.path.join(ROOT, book, "00-前言")
    if not os.path.isdir(fd):
        return []
    out = []
    for f in sorted(os.listdir(fd)):
        text = open(os.path.join(fd, f), encoding="utf-8").read()
        for blk in re.split(r"\n\s*\n", text):
            blk = blk.strip()
            if blk and not HEAD.match(blk):
                out.append(blk)
    return out


def catalog(book):
    path = os.path.join(ROOT, book, f"{book}-校订全本.md")
    lines = open(path, encoding="utf-8").read().splitlines()
    i = next((k for k, l in enumerate(lines)
              if HEAD.match(l) and nows(HEAD.match(l).group(2)) == "目录"), None)
    if i is None:
        return []
    raw = []
    for l in lines[i + 1:]:
        if HEAD.match(l):
            break
        if l.strip():
            raw.append(l.strip())
    return raw


STRUCT = re.compile(r"^(?:[前后]集)?卷(?:第)?(?:[一二三四五六七八九十百]+|[上中下])|^[上下]册")


def match_catalog(raw_lines, names, book):
    """目录条目常连排、且会跨行断开（如「滕庭 / 俊」），故先去页码再整体拼接贪婪切分。"""
    joined = "".join(nows(PAGE.sub("", l)) for l in raw_lines)
    pool = sorted(names, key=len, reverse=True)
    unmatched = []
    s = joined
    while s:
        m = STRUCT.match(s)
        if m:
            s = s[m.end():]
            continue
        for cand in pool:
            if cand and s.startswith(cand):
                s = s[len(cand):]
                break
        else:
            unmatched.append(s[:24])
            break
    return unmatched


stats = json.load(open(os.path.join(ROOT, "_export_stats.json"), encoding="utf-8"))

rows = ["| 书 | 章 | 篇 | 段 | 正文完整性 | 目录核对 |",
        "| --- | --- | --- | --- | --- | --- |"]
problems = []
detail = []
grand = 0

for rec in stats:
    book = rec["book"]
    chapters = rec["chapters"]
    nsec = sum(len(s) for _, s, _ in chapters)
    grand += rec["paras"]

    src = source_paras(book)
    got = front_paras(book) + exported_paras(book)
    if [nows(x) for x in src] == [nows(x) for x in got]:
        integ = f"逐字相同（{len(src)} 段）"
    else:
        integ = f"**不符** 源 {len(src)} / 出 {len(got)}"
        # 找出第一处不同
        for k in range(min(len(src), len(got))):
            if nows(src[k]) != nows(got[k]):
                problems.append(f"《{book}》第 {k+1} 段起不一致：源「{src[k][:30]}」/ 出「{got[k][:30]}」")
                break
        else:
            problems.append(f"《{book}》段数不等：源 {len(src)}，出 {len(got)}")

    names = set()
    for t, secs, _ in chapters:
        names.add(nows(t))
        names.add(nows(t).replace(nows(book), ""))
        for s in secs:
            names.add(nows(s))
            names.add(nows(s).replace("并序", ""))
    fd = os.path.join(ROOT, book, "00-前言")
    if os.path.isdir(fd):
        for f in os.listdir(fd):
            names.add(nows(os.path.splitext(f)[0].split("-", 1)[-1]))
    names.discard("")

    un = match_catalog(catalog(book), names, book)
    if not un:
        cat_flag = "全部条目对应"
    else:
        cat_flag = f"**未对应**"
        for rest in un:
            problems.append(f"《{book}》目录切分中断于「{rest}」")

    rows.append(f"| {book} | {len(chapters)} | {nsec} | {rec['paras']} | {integ} | {cat_flag} |")

    block = [f"\n## 《{book}》 {len(chapters)} 章 / {nsec} 篇 / {rec['paras']} 段\n"]
    if rec["log"]:
        block.append("**修复记录**\n")
        for l in rec["log"]:
            block.append(f"- {l}")
        block.append("")
    for i, (t, secs, n) in enumerate(chapters, 1):
        if secs:
            block.append(f"- `{i:02d}` **{t}**（{n} 段）→ {len(secs)} 篇：{'、'.join(secs)}")
        else:
            block.append(f"- `{i:02d}` **{t}**（{n} 段）")
    detail += block

    own = [f"# 《{book}》切分核对单", "",
           f"- 章：{len(chapters)}　篇：{nsec}　段：{rec['paras']}",
           f"- 正文完整性：{integ}",
           f"- 目录核对：{cat_flag}", ""] + block[1:]
    open(os.path.join(ROOT, book, "_切分核对单.md"), "w", encoding="utf-8").write(
        "\n".join(own) + "\n")

head = ["# 导出核对总表", "",
        f"共 18 种、{sum(len(r['chapters']) for r in stats)} 章、"
        f"{sum(sum(len(s) for _, s, _ in r['chapters']) for r in stats)} 篇、{grand} 段。", ""]
head += rows
head.append("")
if problems:
    head.append("## 待处理")
    head += [f"- {p}" for p in problems]
else:
    head.append("## 结论")
    head.append("全部 18 种书：段落逐字回归原文，目录条目全部对应，无遗漏。")

open(os.path.join(ROOT, "_导出核对.md"), "w", encoding="utf-8").write(
    "\n".join(head) + "\n" + "\n".join(detail) + "\n")
print("\n".join(head))
