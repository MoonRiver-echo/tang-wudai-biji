# -*- coding: utf-8 -*-
"""Scan all 朝野佥载 paragraphs for supernatural / paranormal content."""
import re, json
import pandas as pd
from pathlib import Path
from collections import OrderedDict, Counter

BASE = Path(__file__).parent
ROOT = BASE / "朝野佥载"

CATEGORIES = OrderedDict([
    ("卜筮占相", ["卜", "筮", "占", "推算", "卦", "转式", "式讫", "相书", "相者",
                "看相", "算命", "推之", "卜之", "筮之", "九宫"]),
    ("鬼怪妖魅", ["鬼", "妖", "怪", "魅", "精", "魔", "魑", "见鬼", "鬼神",
                "鬼物", "妖怪", "狐妖", "蛇精", "邪鬼", "恶鬼"]),
    ("神仙佛道", ["天尊", "菩萨", "神仙", "神人", "禅师", "道士", "法师",
                "沙门", "佛", "僧", "尼", "真人", "仙", "神鼎", "空如", "神通"]),
    ("谶谣征应", ["谶", "谣", "童谣", "祥", "征应", "妖异", "妖言", "谣曰",
                "谶曰", "其应", "之应", "之谶", "之验", "斯为验", "信有征"]),
    ("冥报报应", ["冥", "阴司", "阎", "见王", "报应", "冥报", "业报", "地狱",
                "冥司", "冥道", "见冥", "冥吏", "鬼使", "下状"]),
    ("死而复生", ["而苏", "复生", "还魂", "更苏", "乃苏", "苏醒",
                "七日而苏", "病卒五日而苏", "托梦"]),
    ("巫术厌胜", ["咒", "符", "厌魅", "巫", "蛊", "法术", "妖术", "厌胜",
                "魇", "禁咒", "猫鬼", "蛊毒"]),
    ("灵异神异", ["灵验", "神异", "奇异", "异事", "征验", "有验", "灵异",
                "显灵", "神验", "怪异", "变异", "神变"]),
    ("神梦感应", ["梦见", "梦神", "梦天尊", "梦中", "梦一", "梦僧", "梦佛",
                "梦告", "昼梦", "托梦"]),
])

def categories_for(text):
    return [c for c, kws in CATEGORIES.items() if any(k in text for k in kws)]

para_re = re.compile(r"^(【(\d{2}-\d{3})】)(.*)$", re.S)
records = []
vol_dirs = sorted([d for d in ROOT.iterdir()
                  if d.is_dir() and d.name[:2].isdigit() and d.name[:2] != "00"])
for vd in vol_dirs:
    vol = vd.name
    src = next(vd.glob("00-*全卷*.md"))
    for line in src.read_text(encoding="utf-8").splitlines():
        m = para_re.match(line.strip())
        if m:
            body = m.group(3)
            cats = categories_for(body)
            if cats:
                records.append({
                    "paragraph_id": m.group(2), "volume": vol,
                    "supernatural_types": ";".join(cats),
                    "n_types": len(cats), "text": m.group(1) + body,
                })

out_csv = ROOT / "朝野佥载-志怪异事.csv"
out_json = ROOT / "朝野佥载-志怪异事.json"
out_md = ROOT / "朝野佥载-志怪异事.md"
pd.DataFrame(records).to_csv(out_csv, index=False, encoding="utf-8-sig")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

lines = [f"# 朝野佥载 · 志怪异事汇编\n",
         f"共 {len(records)} 段提及超自然 / 志怪内容。\n"]
for cat in CATEGORIES:
    subset = [r for r in records if cat in r["supernatural_types"]]
    if not subset:
        continue
    lines.append(f"## 【{cat}】（{len(subset)} 段）\n")
    for r in subset:
        others = [c for c in r["supernatural_types"].split(";") if c != cat]
        note = f"  〔兼涉：{'、'.join(others)}〕" if others else ""
        lines.append(r["text"] + note + "\n")
    lines.append("")
out_md.write_text("\n".join(lines), encoding="utf-8")

print(f"提及超自然内容的段落：{len(records)} / 376 段")
print("\n各类目命中段数：")
for cat in CATEGORIES:
    n = sum(1 for r in records if cat in r["supernatural_types"])
    print(f"  {cat}: {n}")
print("\n各卷分布：")
for vol, n in Counter(r["volume"] for r in records).most_common():
    print(f"  {vol}: {n}")
print(f"\nCSV  -> {out_csv}")
print(f"JSON -> {out_json}")
print(f"MD   -> {out_md}")
