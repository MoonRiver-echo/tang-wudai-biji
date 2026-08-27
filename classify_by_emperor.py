# -*- coding: utf-8 -*-
"""Further classification of 朝野佥载卷一 paragraphs:
  Primary tag  = Emperor (first emperor if a paragraph matches several)
  Secondary tag = Era name (first era matched) within each emperor
  Paragraphs matching no emperor/era -> 未系年 (independent)
Outputs: a database-mergeable CSV/JSON + a grouped Markdown.
"""
import re, json
import pandas as pd
from pathlib import Path
from collections import OrderedDict

BASE = Path(__file__).parent
SRC = BASE / "朝野佥载" / "01-朝野佥载卷一" / "00-朝野佥载卷一-全卷.md"
XLS = BASE / "唐年号.xls"
OUTDIR = BASE / "朝野佥载" / "01-朝野佥载卷一"

# ---------- 1. Load bibliography ----------
df = pd.read_excel(XLS)
df.columns = [c.strip() for c in df.columns]
df["皇帝"] = df["皇帝"].ffill()
df["年号"] = df["年号"].astype(str).str.strip()

era_to_emps = OrderedDict()
emperor_order = []
era_order = []
for _, r in df.iterrows():
    era = str(r["年号"]).strip()
    emp = str(r["皇帝"]).strip()
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

# ---------- 2. Read paragraphs ----------
text = SRC.read_text(encoding="utf-8")
para_re = re.compile(r"^(【(\d{2}-\d{3})】)(.*)$", re.S)
paragraphs = []
for line in text.splitlines():
    m = para_re.match(line.strip())
    if m:
        paragraphs.append({"id": m.group(2), "head": m.group(1), "body": m.group(3).strip()})

# ---------- 3. Matching ----------
TEMPORAL = r"(?:[一二三四五六七八九十百千零]+年|年中|中|初|后|已来|以来|以后|之后|之季|以前|年)"
era_re = re.compile("(" + "|".join(re.escape(e) for e in era_to_emps) + ")" + TEMPORAL)

def match_eras_in_order(body):
    hits = []
    for m in re.finditer(era_re, body):
        if m.group(1) not in hits:
            hits.append(m.group(1))
    return hits

def match_emperors_in_order(body):
    hits = []
    for emp in emperor_order:
        for k in emp_keywords[emp]:
            if k in body and emp not in hits:
                hits.append(emp)
                break
    return hits

results = []
for p in paragraphs:
    eras = match_eras_in_order(p["body"])
    direct_emps = match_emperors_in_order(p["body"])
    implied = []
    for e in eras:
        for em in era_to_emps[e]:
            if em not in implied:
                implied.append(em)
    all_emps = implied + [e for e in direct_emps if e not in implied]
    if eras:
        main_emperor = era_to_emps[eras[0]][0]
        main_era = eras[0]
        kind = "era"
    elif direct_emps:
        main_emperor = direct_emps[0]
        main_era = ""
        kind = "emperor"
    else:
        main_emperor = ""
        main_era = ""
        kind = "independent"
    results.append({
        "paragraph_id": p["id"],
        "main_emperor": main_emperor,
        "main_era": main_era,
        "all_emperors": ";".join(all_emps),
        "all_eras": ";".join(eras),
        "classification_type": kind,
        "text": p["head"] + p["body"],
    })

# ---------- 4. Output CSV/JSON ----------
out_csv = OUTDIR / "02-朝野佥载卷一-按皇帝分类.csv"
out_json = OUTDIR / "02-朝野佥载卷一-按皇帝分类.json"
out_md = OUTDIR / "02-朝野佥载卷一-按皇帝分类.md"
pd.DataFrame(results).to_csv(out_csv, index=False, encoding="utf-8-sig")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# ---------- 5. Grouped Markdown : Emperor -> Era ----------
emp_groups = OrderedDict((emp, OrderedDict()) for emp in emperor_order)
indep = []
for r in results:
    if r["classification_type"] == "independent":
        indep.append(r)
        continue
    emp = r["main_emperor"]
    era = r["main_era"] if r["main_era"] else "（仅称皇帝·未系年号）"
    emp_groups[emp].setdefault(era, []).append(r)

def era_rank(era):
    return era_order.index(era) if era in era_order else len(era_order)

lines = ["# 朝野佥载 · 朝野佥载卷一 · 按皇帝→年号分类\n"]
for emp in emperor_order:
    era_map = emp_groups[emp]
    if not era_map:
        continue
    lines.append(f"# 皇帝：{emp}\n")
    keys = sorted(era_map.keys(), key=lambda e: (e.startswith("（"), era_rank(e)))
    for era in keys:
        paras = era_map[era]
        all_emp_set = ";".join(sorted({r["all_emperors"] for r in paras if r["all_emperors"]}))
        head = f"## 年号：{era}"
        if all_emp_set and ";" in all_emp_set:
            head += f"  （兼涉皇帝：{all_emp_set}）"
        lines.append(head + "\n")
        for r in paras:
            note = ""
            if r["all_eras"] and ";" in r["all_eras"]:
                note = f"  〔兼涉年号：{r['all_eras']}〕"
            lines.append(r["text"] + note + "\n")
        lines.append("")
lines.append("# 未系年（未提及年号或皇帝）\n")
for r in indep:
    lines.append(r["text"] + "\n")
out_md.write_text("\n".join(lines), encoding="utf-8")

# ---------- 6. Summary ----------
print(f"共 {len(results)} 段")
from collections import Counter
c = Counter(r["main_emperor"] or "未系年" for r in results)
for t, n in c.most_common():
    print(f"  {t}: {n}")
print(f"\nCSV  -> {out_csv}")
print(f"JSON -> {out_json}")
print(f"MD   -> {out_md}")
