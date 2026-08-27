# -*- coding: utf-8 -*-
"""
Classify paragraphs of 朝野佥载卷一 by Era name / Emperor mentioned in 唐年号.xls.
Output a database-mergeable CSV + a human-readable grouped Markdown file.
"""
import re
import json
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent
SRC = BASE / "朝野佥载" / "01-朝野佥载卷一" / "00-朝野佥载卷一-全卷.md"
XLS = BASE / "唐年号.xls"

# ---------- 1. Load bibliography ----------
df = pd.read_excel(XLS)
df.columns = [c.strip() for c in df.columns]
df["皇帝"] = df["皇帝"].ffill()          # forward-fill emperor name
df["年号"] = df["年号"].astype(str).str.strip()

# era_name -> list of emperors (some era names repeat, e.g. 上元)
era_to_emps = {}
for _, r in df.iterrows():
    era_to_emps.setdefault(r["年号"], []).append(str(r["皇帝"]).strip())

# emperor keywords (temple name + personal name + full name)
EMP_ALIASES = {
    "武则天": ["天后"],
    "玄宗李隆基": ["神武皇帝"],
}
emp_keywords = {}
for emp in df["皇帝"].unique():
    emp = str(emp).strip()
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
# era name must be followed by a temporal marker to avoid false positives
TEMPORAL = r"(?:[一二三四五六七八九十百千零]+年|年中|中|初|后|已来|以来|以后|之后|之季|以前|年)"
era_re = re.compile("(" + "|".join(re.escape(e) for e in era_to_emps) + ")" + TEMPORAL)

def match_era(body):
    hits = []
    for m in re.finditer(era_re, body):
        hits.append(m.group(1))
    return list(dict.fromkeys(hits))  # unique, keep order

def match_emperor(body):
    hits = []
    for emp, kws in emp_keywords.items():
        if any(k in body for k in kws):
            hits.append(emp)
    return hits

results = []
for p in paragraphs:
    eras = match_era(p["body"])
    emps = match_emperor(p["body"])
    # emperors implied by matched era names
    implied_emps = []
    for e in eras:
        for em in era_to_emps[e]:
            if em not in implied_emps:
                implied_emps.append(em)
    all_emps = implied_emps + [e for e in emps if e not in implied_emps]

    if eras or emps:
        kind = "era" if eras else "emperor"
        tag = "/".join(eras) if eras else "/".join(emps)
    else:
        kind = "independent"
        tag = "未系年"
    results.append({
        "paragraph_id": p["id"],
        "classification_type": kind,
        "era_name": ";".join(eras),
        "emperor": ";".join(all_emps),
        "tag": tag,
        "text": p["head"] + p["body"],
    })

# ---------- 4. Output ----------
out_csv = BASE / "朝野佥载" / "01-朝野佥载卷一" / "01-朝野佥载卷一-分类.csv"
out_json = BASE / "朝野佥载" / "01-朝野佥载卷一" / "01-朝野佥载卷一-分类.json"
out_md = BASE / "朝野佥载" / "01-朝野佥载卷一" / "01-朝野佥载卷一-分类.md"

pd.DataFrame(results).to_csv(out_csv, index=False, encoding="utf-8-sig")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# grouped markdown
groups = {}
for r in results:
    groups.setdefault(r["tag"], []).append(r)
order = sorted(groups.keys(), key=lambda t: (t == "未系年", t))
lines = ["# 朝野佥载 · 朝野佥载卷一 · 段落时序分类\n"]
for tag in order:
    emps_for_tag = "; ".join(sorted({r["emperor"] for r in groups[tag] if r["emperor"]}))
    lines.append(f"## 【{tag}】" + (f"  （皇帝：{emps_for_tag}）" if emps_for_tag else "") + "\n")
    for r in groups[tag]:
        lines.append(r["text"] + "\n")
    lines.append("")
out_md.write_text("\n".join(lines), encoding="utf-8")

# ---------- 5. Summary ----------
print(f"共 {len(results)} 段")
from collections import Counter
c = Counter(r["tag"] for r in results)
for t, n in c.most_common():
    print(f"  {t}: {n}")
print(f"\nCSV  -> {out_csv}")
print(f"JSON -> {out_json}")
print(f"MD   -> {out_md}")
