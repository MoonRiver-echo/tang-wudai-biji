# -*- coding: utf-8 -*-
"""按目录切分唐五代笔记小说：卷 -> 篇 -> 段，并核对目录。"""
import os
import re
import shutil

ROOT = r"c:\Users\lx\Desktop\笔记小说"
HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
WS = re.compile(r"[\s\u3000]+")


def nows(s):
    return WS.sub("", s)


# ---------------------------------------------------------------- 修复操作表
# ("promote", 行号, 期望原文)            普通行升为标题
# ("demote",  行号, 期望原文)            标题降为普通行
# ("delete",  行号, 期望原文)            删行
# ("retitle", 行号, 期望原文, 新标题)     改标题文字
# ("split",   行号, 期望原文, 标题, 正文) 一行拆为标题＋正文
REPAIRS = {
    "朝野佥载": [
        ("retitle", 1, "# 朝野僉載", "朝野佥载"),
    ],
    "大唐新语": [
        ("promote", 81, "匡赞第一"),
        ("promote", 137, "极谏第三"),
        ("promote", 211, "公直第五"),
        ("split", 351, None, "忠烈第九", None),
        ("promote", 483, "识量第十四"),
        ("promote", 649, "著述第十九"),
        ("promote", 717, "厘革第二十二"),
        ("promote", 775, "褒锡第二十四"),
        ("promote", 835, "劝励第二十六"),
        ("promote", 879, "谐谑第二十八"),
    ],
    "酉阳杂俎": [
        ("delete", 88, "##### 酉阳杂俎目录"),
        ("promote", 208, "玉格"),
        ("demote", 250, "##### 图籍有符图七千章"),
        ("promote", 506, "诡习"),
        ("retitle", 1148, "##### 尸 穷", "尸穸"),
        ("promote", 1214, "诺皋记上"),
        ("promote", 1302, "诺皋记下"),
        ("promote", 1362, "广动植之一 并序"),
        ("promote", 1510, "广动植之二"),
        ("promote", 1512, "鳞介篇"),
        ("promote", 1654, "广动植之三"),
        ("promote", 1656, "木篇"),
        ("promote", 1784, "广动植之四"),
        ("promote", 1786, "草篇"),
        ("promote", 1910, "肉攫部"),
        ("promote", 1984, "支诺皋上"),
        ("promote", 2022, "支诺皋中"),
        ("promote", 2090, "支诺皋下"),
        ("promote", 2242, "寺塔记上"),
        ("promote", 2268, "寺塔记下"),
        ("promote", 2300, "金刚经鸠异"),
    ],
    "玄怪录": [
        ("promote", 133, "尼妙寂"),
        ("promote", 565, "张宠奴"),
    ],
    "续玄怪录": [
        ("promote", 177, "苏州客"),
    ],
    "因话录": [
        ("split", 84, None, "商部上", "商为臣，凡自王公至有秩已上，皆入此部。"),
        ("promote", 130, "商部下"),
        ("split", 190, None, "角部", "角，为人凡不仕者，皆以此部。"),
        ("split", 234, None, "徵部", "徵为事，凡不为其人与物而泛说者，皆入此部。"),
    ],
    "纂异记": [
        ("demote", 383, "##### 鸱夷君衔杯作歌曰："),
        ("demote", 481, "##### 少年神貌扬扬者诗云："),
        ("delete", 483, "现场扬者诗云："),
        ("demote", 493, "##### 短小器宇落落者诗云："),
        ("delete", 495, "器宇落落者诗云："),
        ("demote", 505, "##### 清瘦及瞻视疾速者诗云："),
    ],
}

# 《大唐新语》忠烈第九：篇题与正文黏连，正文自「李玄通」起
SPLIT_BODY = {("大唐新语", 351): ("忠烈第九", "李玄通刺定州")}

# ------------------------------------------------------------------ 结构配置
# mode: 卷=一级；两级=卷下分篇；篇=丢弃与书名同名的外壳，其下各篇即为章
FRONT = {"校点说明", "目录", "原序", "序"}

BOOKS = {
    "朝野佥载":   {"mode": "卷"},
    "隋唐嘉话":   {"mode": "卷"},
    "教坊记":     {"mode": "两级", "卷": ["教坊记", "教坊记补遗"]},
    "龙城录":     {"mode": "篇"},
    "唐国史补":   {"mode": "卷"},
    "大唐新语":   {"mode": "两级", "extra卷": ["总论"]},
    "玄怪录":     {"mode": "两级"},
    "续玄怪录":   {"mode": "两级"},
    "次柳氏旧闻": {"mode": "卷", "卷": ["次柳氏旧闻", "补遗"]},
    "博异志":     {"mode": "篇"},
    "纂异记":     {"mode": "篇"},
    "甘泽谣":     {"mode": "篇"},
    "酉阳杂俎":   {"mode": "两级"},
    "刘宾客嘉话录": {"mode": "卷", "卷": ["刘宾客嘉话录", "补遗"]},
    "因话录":     {"mode": "两级"},
    "大唐传载":   {"mode": "卷", "卷": ["大唐传载"]},
    "独异志":     {"mode": "卷"},
    "明皇杂录":   {"mode": "卷", "卷": ["明皇杂录卷上", "明皇杂录卷下", "明皇杂录补遗",
                                    "明皇杂录逸文", "补遗四则"]},
}

BAD = re.compile(r'[\\/:*?"<>|]')


def safe(name):
    return BAD.sub("_", name).strip() or "无题"


def apply_repairs(book, lines):
    """按行号倒序施工，避免行号漂移。返回 (新行表, 日志)。"""
    log = []
    ops = sorted(REPAIRS.get(book, []), key=lambda o: o[1], reverse=True)
    for op in ops:
        kind, ln = op[0], op[1]
        i = ln - 1
        cur = lines[i]
        if kind == "promote":
            assert nows(cur) == nows(op[2]), f"{book} L{ln} 期望「{op[2]}」实为「{cur}」"
            lines[i] = "### " + nows(cur)
            log.append(f"L{ln} 普通行升为篇题：{nows(cur)}")
        elif kind == "demote":
            assert nows(cur) == nows(op[2]), f"{book} L{ln} 期望「{op[2]}」实为「{cur}」"
            t = HEAD.match(cur).group(2)
            lines[i] = t
            log.append(f"L{ln} 标题降为正文：{t}")
        elif kind == "delete":
            assert nows(cur) == nows(op[2]), f"{book} L{ln} 期望「{op[2]}」实为「{cur}」"
            end = i + 1
            while end < len(lines) and not lines[end].strip():
                end += 1
            del lines[i:end]
            log.append(f"L{ln} 删除：{op[2]}")
        elif kind == "retitle":
            assert nows(cur) == nows(op[2]), f"{book} L{ln} 期望「{op[2]}」实为「{cur}」"
            hashes = HEAD.match(cur).group(1)
            lines[i] = f"{hashes} {op[3]}"
            log.append(f"L{ln} 改题：{HEAD.match(cur).group(2)} → {op[3]}")
        elif kind == "split":
            title, body = op[3], op[4]
            if body is None:
                t, anchor = SPLIT_BODY[(book, ln)]
                pos = cur.find(anchor)
                assert pos > 0, f"{book} L{ln} 未找到锚点「{anchor}」"
                body = cur[pos:]
                title = t
            else:
                assert nows(cur).startswith(nows(title)), f"{book} L{ln} 行首非「{title}」"
                assert nows(cur) == nows(title) + nows(body), f"{book} L{ln} 拆分后文字不符"
            lines[i:i + 1] = ["### " + title, "", body]
            log.append(f"L{ln} 拆分：标题「{title}」＋正文「{body[:20]}…」")
    return lines, list(reversed(log))


def normalize_levels(book, lines):
    """书名 #，卷/前言 ##，篇 ###；标题内空格一律删去。"""
    cfg = BOOKS[book]
    juan = set(cfg.get("卷", []))
    juan |= set(cfg.get("extra卷", []))
    out = []
    for idx, l in enumerate(lines):
        m = HEAD.match(l)
        if not m:
            out.append(l)
            continue
        t = nows(m.group(2))
        if idx == 0:
            out.append("# " + book)
        elif t in FRONT or t.endswith("序") and len(t) <= len(book) + 1:
            out.append("## " + t)
        elif "卷" in t and t.startswith(book) or t in juan:
            out.append("## " + t)
        else:
            out.append("### " + t)
    return out


def parse(lines):
    """切成 [(级别, 标题, [段落])]，段落为空行分隔的文本块。"""
    nodes, cur = [], None
    buf = []

    def flush():
        if cur is not None:
            text = "\n".join(buf).strip("\n")
            paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            cur[2].extend(paras)

    for l in lines:
        m = HEAD.match(l)
        if m:
            flush()
            buf = []
            cur = (len(m.group(1)), m.group(2), [])
            nodes.append(cur)
        else:
            buf.append(l)
    flush()
    return nodes


def build_tree(book, nodes):
    """返回 (前言列表, 章列表)。章 = {title, paras, sections:[{title,paras}]}"""
    cfg = BOOKS[book]
    front, chapters, titlepage = [], [], []
    for lvl, title, paras in nodes:
        if lvl == 1:
            titlepage = paras
            continue
        if lvl == 2 and nows(title) in FRONT or (lvl == 2 and title.endswith("序")):
            front.append({"title": title, "paras": paras})
        elif lvl == 2:
            chapters.append({"title": title, "paras": paras, "sections": []})
        else:
            if chapters:
                chapters[-1]["sections"].append({"title": title, "paras": paras})
            else:
                chapters.append({"title": title, "paras": paras, "sections": []})

    if cfg["mode"] == "篇":
        merged = []
        for ch in chapters:
            if nows(ch["title"]) == nows(book):
                for s in ch["sections"]:
                    merged.append({"title": s["title"], "paras": s["paras"], "sections": []})
            else:
                merged.append(ch)
        chapters = merged
    return titlepage, front, chapters


def export(book):
    src = os.path.join(ROOT, book, book + ".md")
    lines = open(src, encoding="utf-8").read().splitlines()
    orig_chars = sum(len(nows(l)) for l in lines)

    lines, log = apply_repairs(book, lines)
    lines = normalize_levels(book, lines)
    fixed = "\n".join(lines).rstrip("\n") + "\n"
    open(os.path.join(ROOT, book, f"{book}-校订全本.md"), "w", encoding="utf-8").write(fixed)

    titlepage, front, chapters = build_tree(book, parse(lines))

    bookdir = os.path.join(ROOT, book)
    for d in os.listdir(bookdir):
        p = os.path.join(bookdir, d)
        if os.path.isdir(p) and re.match(r"^\d\d-", d):
            shutil.rmtree(p)

    # ---- 前言
    if front or titlepage:
        fd = os.path.join(bookdir, "00-前言")
        os.makedirs(fd, exist_ok=True)
        if titlepage:
            body = f"# {book}\n\n" + "\n\n".join(titlepage) + "\n"
            open(os.path.join(fd, "00-题署.md"), "w", encoding="utf-8").write(body)
        for n, f in enumerate(front, 1):
            body = f"# {f['title']}\n\n" + "\n\n".join(f["paras"]) + "\n"
            open(os.path.join(fd, f"{n:02d}-{safe(f['title'])}.md"), "w",
                 encoding="utf-8").write(body)

    # ---- 正文
    total = 0
    stats = []
    for ci, ch in enumerate(chapters, 1):
        cdir = os.path.join(bookdir, f"{ci:02d}-{safe(ch['title'])}")
        os.makedirs(cdir, exist_ok=True)
        whole = [f"# {book} · {ch['title']}", ""]
        cpara = 0

        def dump(paras, sec_title, outdir, prefix):
            nonlocal total, cpara
            files = []
            for p in paras:
                cpara += 1
                total += 1
                pid = f"{ci:02d}-{cpara:03d}"
                meta = [f"书名：{book}", f"卷/篇：{ch['title']}"]
                if sec_title:
                    meta.append(f"子篇：{sec_title}")
                meta += [f"段号：{pid}", f"全书序号：{total:04d}"]
                body = "<!--\n" + "\n".join(meta) + "\n-->\n\n" + p + "\n"
                fn = f"{cpara:03d}.md"
                open(os.path.join(outdir, fn), "w", encoding="utf-8").write(body)
                files.append(f"【{pid}】" + p)
            return files

        if ch["paras"]:
            whole += dump(ch["paras"], None, cdir, "")
            whole.append("")
        for si, sec in enumerate(ch["sections"], 1):
            sdir = os.path.join(cdir, f"{si:02d}-{safe(sec['title'])}")
            os.makedirs(sdir, exist_ok=True)
            got = dump(sec["paras"], sec["title"], sdir, "")
            whole.append(f"## {sec['title']}")
            whole.append("")
            whole += got
            whole.append("")
            sbody = f"# {sec['title']}\n\n" + "\n\n".join(got) + "\n"
            open(os.path.join(sdir, f"00-{safe(sec['title'])}-全篇.md"), "w",
                 encoding="utf-8").write(sbody)

        open(os.path.join(cdir, f"00-{safe(ch['title'])}-全卷.md"), "w",
             encoding="utf-8").write("\n\n".join(x for x in whole if x != "") + "\n")
        stats.append((ch["title"], [s["title"] for s in ch["sections"]], cpara))

    # ---- 字数核对
    got_chars = 0
    for f in front:
        got_chars += sum(len(nows(p)) for p in f["paras"]) + len(nows(f["title"]))
    for ch in chapters:
        got_chars += len(nows(ch["title"])) + sum(len(nows(p)) for p in ch["paras"])
        for s in ch["sections"]:
            got_chars += len(nows(s["title"])) + sum(len(nows(p)) for p in s["paras"])
    got_chars += len(nows(book))
    return log, stats, total, orig_chars, got_chars


if __name__ == "__main__":
    summary = []
    for book in BOOKS:
        log, stats, total, oc, gc = export(book)
        summary.append((book, log, stats, total, oc, gc))
        print(f"{book:8s} 章{len(stats):>3}  段{total:>4}  原字{oc:>6} 出字{gc:>6} "
              f"{'OK' if abs(oc-gc) < 60 else '差' + str(oc-gc)}")

    import json
    with open(os.path.join(ROOT, "_export_stats.json"), "w", encoding="utf-8") as f:
        json.dump([{"book": b, "log": l, "chapters": [(t, s, n) for t, s, n in st],
                    "paras": tt, "orig": oc, "out": gc}
                   for b, l, st, tt, oc, gc in summary], f, ensure_ascii=False, indent=1)
