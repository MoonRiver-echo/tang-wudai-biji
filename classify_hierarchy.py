# -*- coding: utf-8 -*-
"""Re-classify the supernatural paragraphs into a hierarchical file ordered by
Level 1 (志怪类别) -> Level 2 (皇帝/年号) -> Level 3 (事类).
Reads 朝野佥载-志怪三级分类.csv and writes a nested Markdown + a flat ordered CSV.
"""
import pandas as pd
from pathlib import Path
from collections import OrderedDict

BASE = Path(__file__).parent
ROOT = BASE / "朝野佥载"
SRC = ROOT / "朝野佥载-志怪三级分类.csv"

# canonical ordering
L1_ORDER = ["卜筮占相", "鬼怪妖魅", "神仙佛道", "谶谣征应", "冥报报应",
            "死而复生", "巫术厌胜", "灵异神异", "神梦感应"]
L3_ORDER = ["医疗", "官运仕途", "命运寿夭", "婚姻家庭", "报应惩恶",
            "军事战争", "政治征兆", "巫蛊害人", "禳灾祈福", "风俗信仰", "未明"]
EMP_ORDER = ["太宗李世民", "高宗李治", "中宗李显", "睿宗李旦", "武则天",
             "殇帝李重茂", "玄宗李隆基", "肃宗李亨", "代宗李豫", "德宗李适",
             "顺宗李诵", "宪宗李纯", "穆宗李恒", "敬宗李湛", "文宗李昂",
             "武宗李炎", "宣宗李忱", "懿宗李漼", "僖宗李儇", "昭宗李晔",
             "哀帝李柷", "未系年"]

def l1_rank(x):
    return L1_ORDER.index(x) if x in L1_ORDER else len(L1_ORDER)
def l3_rank(x):
    return L3_ORDER.index(x) if x in L3_ORDER else len(L3_ORDER)
def emp_rank(x):
    return EMP_ORDER.index(x) if x in EMP_ORDER else len(EMP_ORDER)

df = pd.read_csv(SRC)

# build nested dict using PRIMARY (first) tag at each level -> no duplication
tree = OrderedDict()
for _, r in df.iterrows():
    l1 = str(r["level1_supernatural"]).split(";")[0]
    l2 = str(r["level2_emperor"]) if pd.notna(r["level2_emperor"]) else "未系年"
    era = str(r["level2_era"]) if pd.notna(r["level2_era"]) else ""
    l2key = l2 + (("·" + era) if era and era != "nan" else "")
    l3 = str(r["level3_domain"]).split(";")[0] if pd.notna(r["level3_domain"]) else "未明"
    tree.setdefault(l1, OrderedDict())
    tree[l1].setdefault(l2key, OrderedDict())
    tree[l1][l2key].setdefault(l3, []).append(r)

# nested markdown
lines = ["# 朝野佥载 · 志怪三级层级分类\n",
         "段落按【一级：志怪类别】→【二级：皇帝·年号】→【三级：事类】层级排列。\n",
         f"共 {len(df)} 段志怪段落（每段按主标签归入一处，不重复）。\n"]
for l1 in sorted(tree.keys(), key=l1_rank):
    lines.append(f"# 一级：【{l1}】\n")
    for l2 in sorted(tree[l1].keys(), key=lambda k: (emp_rank(k.split("·")[0]), k)):
        lines.append(f"## 二级：【{l2}】\n")
        for l3 in sorted(tree[l1][l2].keys(), key=l3_rank):
            rows = tree[l1][l2][l3]
            lines.append(f"### 三级：【{l3}】（{len(rows)} 段）\n")
            for r in rows:
                lines.append(r["text"] + "\n")
            lines.append("")
        lines.append("")
    lines.append("")
out_md = ROOT / "朝野佥载-志怪三级层级.md"
out_md.write_text("\n".join(lines), encoding="utf-8")

# flat ordered CSV: sort by L1, L2(emperor), L2(era), L3
df["l1_first"] = df["level1_supernatural"].str.split(";").str[0]
df["l2_emp"] = df["level2_emperor"].fillna("未系年")
df["l2_era"] = df["level2_era"].fillna("")
df["l3_first"] = df["level3_domain"].str.split(";").str[0]
df["_r1"] = df["l1_first"].map(l1_rank)
df["_re"] = df["l2_emp"].map(emp_rank)
df["_r3"] = df["l3_first"].map(l3_rank)
ordered = df.sort_values(["_r1", "_re", "l2_era", "_r3", "paragraph_id"])
out_cols = ["paragraph_id", "volume", "l1_first", "l2_emp", "l2_era",
            "level1_supernatural", "level2_emperor", "level2_era",
            "l3_first", "level3_domain", "text"]
ordered_csv = ROOT / "朝野佥载-志怪三级层级.csv"
ordered[out_cols].to_csv(ordered_csv, index=False, encoding="utf-8-sig")

print(f"层级文件已生成：{len(df)} 段")
print(f"MD  -> {out_md}")
print(f"CSV -> {ordered_csv}")
print("\n一级类别顺序：")
for l1 in sorted(tree.keys(), key=l1_rank):
    n = sum(len(rows) for l2m in tree[l1].values() for rows in l2m.values())
    print(f"  {l1}: {n} 段")
