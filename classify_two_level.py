# -*- coding: utf-8 -*-
"""Two-level classification of 朝野佥载 paragraphs:
  Level 1 tag = supernatural type (志怪类别)
  Level 2 tag = emperor / era (时序, from 唐年号.xls)
Keep only paragraphs that have supernatural content; output a new CSV/JSON/MD.
"""
import re, json
import pandas as pd
from pathlib import Path
from collections import OrderedDict

BASE = Path(__file__).parent
ROOT = BASE / "朝野佥载"
XLS = BASE / "唐年号.xls"

# ---------- bibliography (emperor/era) ----------
df = pd.read_excel(XLS)
df.columns = [c.strip() for c in df.columns]
df["皇帝"] = df["皇帝"].ffill()
df["年号"] = df["年号"].astype(str).str.strip()
era_to_emps = OrderedDict()
emperor_order, era_order = [], []
for _, r in df.iterrows():
    era, emp = str(r["年号"]).strip(), str(r["皇帝"]).strip()
    era_to_emps.setdefault(era, [])
    if emp not in era_to_emps[era]:
        era_to_emps[era].append(emp)
    if emp not in emperor_order:
        emperor_order.append(emp)
    if era not in era_order:
        era_order.append(era)
EMP_ALIASES = {
    "武则天": ["天后"],
    "玄宗李隆基": ["神武皇帝"],
}
emp_keywords = {}
for emp in emperor_order:
    kws = {emp}
    if emp.startswith("武则天"):
        kws |= {"武则天", "则天"}
    else:
        m = re.match(r"(\S+?)(李\S+)", emp)
        if m:
            kws |= {m.group(1), m.group(2)}
    kws |= set(EMP_ALIASES.get(emp, []))
    emp_keywords[emp] = sorted(kws, key=len, reverse=True)

TEMPORAL = r"(?:[一二三四五六七八九十百千零]+年|年中|中|初|后|已来|以来|以后|之后|之季|以前|年)"
era_re = re.compile("(" + "|".join(re.escape(e) for e in era_to_emps) + ")" + TEMPORAL)

def match_eras(body):
    hits = []
    for m in re.finditer(era_re, body):
        if m.group(1) not in hits:
            hits.append(m.group(1))
    return hits

def match_emperors(body):
    hits = []
    for emp in emperor_order:
        for k in emp_keywords[emp]:
            if k in body and emp not in hits:
                hits.append(emp); break
    return hits

def time_tag(body):
    eras = match_eras(body)
    direct = match_emperors(body)
    implied = []
    for e in eras:
        for em in era_to_emps[e]:
            if em not in implied:
                implied.append(em)
    all_emps = implied + [e for e in direct if e not in implied]
    if eras:
        return era_to_emps[eras[0]][0], eras[0], ";".join(all_emps), ";".join(eras)
    if direct:
        return direct[0], "", ";".join(direct), ""
    return "", "", "", ""

# ---------- supernatural categories (level 1) ----------
CATEGORIES = OrderedDict([
    ("卜筮占相", ["卜", "筮", "占", "推算", "卦", "转式", "式讫", "相书", "相者",
                "看相", "算命", "推之", "卜之", "筮之", "九宫"]),
    ("鬼怪妖魅", ["鬼", "妖", "怪", "魅", "精", "魔", "魑", "见鬼", "鬼神",
                "鬼物", "妖怪", "狐妖", "蛇精", "邪鬼", "恶鬼"]),
    ("神仙佛道", ["天尊", "菩萨", "神仙", "神人", "禅师", "道士", "法师",
                "沙门", "佛", "僧", "尼", "仙", "神鼎", "空如", "神通"]),
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
def super_types(body):
    return [c for c, kws in CATEGORIES.items() if any(k in body for k in kws)]

# ---------- scan all paragraphs ----------
para_re = re.compile(r"^(【(\d{2}-\d{3})】)(.*)$", re.S)
records = []
vol_dirs = sorted([d for d in ROOT.iterdir()
                  if d.is_dir() and d.name[:2].isdigit() and d.name[:2] != "00"])
for vd in vol_dirs:
    vol = vd.name
    src = next(vd.glob("00-*全卷*.md"))
    for line in src.read_text(encoding="utf-8").splitlines():
        m = para_re.match(line.strip())
        if not m:
            continue
        body = m.group(3)
        l1 = super_types(body)
        if not l1:
            continue  # only supernatural paragraphs
        emp, era, all_emp, all_era = time_tag(body)
        records.append({
            "paragraph_id": m.group(2),
            "volume": vol,
            "level1_supernatural": ";".join(l1),
            "level2_emperor": emp or "未系年",
            "level2_era": era,
            "all_emperors": all_emp,
            "all_eras": all_era,
            "text": m.group(1) + body,
        })

out_csv = ROOT / "朝野佥载-志怪二级分类.csv"
out_json = ROOT / "朝野佥载-志怪二级分类.json"
out_md = ROOT / "朝野佥载-志怪二级分类.md"
pd.DataFrame(records).to_csv(out_csv, index=False, encoding="utf-8-sig")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

# grouped md: by level1 -> level2
lines = ["# 朝野佥载 · 志怪二级分类（类别→皇帝/年号）\n",
         f"共 {len(records)} 段志怪段落，按【一级：志怪类别】→【二级：皇帝/年号】归类。\n"]
for cat in CATEGORIES:
    sub = [r for r in records if cat in r["level1_supernatural"]]
    if not sub:
        continue
    lines.append(f"## 一级：【{cat}】（{len(sub)} 段）\n")
    by_emp = OrderedDict()
    for r in sub:
        key = r["level2_emperor"] + ("·" + r["level2_era"] if r["level2_era"] else "")
        by_emp.setdefault(key, []).append(r)
    for key in sorted(by_emp.keys(), key=lambda k: (k.startswith("未"), k)):
        paras = by_emp[key]
        lines.append(f"### 二级：【{key}】（{len(paras)} 段）\n")
        for r in paras:
            others = [c for c in r["level1_supernatural"].split(";") if c != cat]
            note = f"  〔兼涉：{'、'.join(others)}〕" if others else ""
            lines.append(r["text"] + note + "\n")
        lines.append("")
    lines.append("")
out_md.write_text("\n".join(lines), encoding="utf-8")

print(f"志怪段落二级分类：{len(records)} 段")
print("\n一级类别 × 二级皇帝 交叉表：")
from collections import Counter
for cat in CATEGORIES:
    sub = [r for r in records if cat in r["level1_supernatural"]]
    cc = Counter(r["level2_emperor"] for r in sub)
    print(f"  {cat}: {dict(cc)}")
print(f"\nCSV  -> {out_csv}")
print(f"JSON -> {out_json}")
print(f"MD   -> {out_md}")
