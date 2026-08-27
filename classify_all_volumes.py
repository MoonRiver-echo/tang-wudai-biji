# -*- coding: utf-8 -*-
"""Classify all volumes of 朝野佥载 by Emperor (primary) -> Era (secondary),
using 唐年号.xls as bibliography. Outputs CSV/JSON/MD per volume + a combined set.
"""
import re, json
import pandas as pd
from pathlib import Path
from collections import OrderedDict

BASE = Path(__file__).parent
ROOT = BASE / "朝野佥载"
XLS = BASE / "唐年号.xls"

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

def classify_paragraph(p):
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
    return {
        "paragraph_id": p["id"],
        "volume": p["vol"],
        "main_emperor": main_emperor,
        "main_era": main_era,
        "all_emperors": ";".join(all_emps),
        "all_eras": ";".join(eras),
        "classification_type": kind,
        "text": p["head"] + p["body"],
    }

def read_paragraphs(vol_dir, vol_name):
    src = next(vol_dir.glob("00-*全卷*.md"))
    text = src.read_text(encoding="utf-8")
    para_re = re.compile(r"^(【(\d{2}-\d{3})】)(.*)$", re.S)
    paras = []
    for line in text.splitlines():
        m = para_re.match(line.strip())
        if m:
            paras.append({"id": m.group(2), "head": m.group(1),
                          "body": m.group(3).strip(), "vol": vol_name})
    return paras

def era_rank(era):
    return era_order.index(era) if era in era_order else len(era_order)

def write_grouped_md(results, out_md, title):
    emp_groups = OrderedDict((emp, OrderedDict()) for emp in emperor_order)
    indep = []
    for r in results:
        if r["classification_type"] == "independent":
            indep.append(r); continue
        emp = r["main_emperor"]
        era = r["main_era"] if r["main_era"] else "（仅称皇帝·未系年号）"
        emp_groups[emp].setdefault(era, []).append(r)
    lines = [f"# {title}\n"]
    for emp in emperor_order:
        era_map = emp_groups[emp]
        if not era_map:
            continue
        lines.append(f"# 皇帝：{emp}\n")
        for era in sorted(era_map.keys(), key=lambda e: (e.startswith("（"), era_rank(e))):
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

# ---------- 2. Process every volume ----------
all_results = []
vol_dirs = sorted([d for d in ROOT.iterdir() if d.is_dir() and d.name[:2].isdigit() and d.name[:2] != "00"])
for vd in vol_dirs:
    vol_name = vd.name
    vol_short = vol_name.split("-", 1)[1] if vol_name[:2].isdigit() else vol_name
    paras = read_paragraphs(vd, vol_name)
    res = [classify_paragraph(p) for p in paras]
    all_results.extend(res)
    out_csv = vd / f"02-{vol_short}-按皇帝分类.csv"
    out_json = vd / f"02-{vol_short}-按皇帝分类.json"
    out_md = vd / f"02-{vol_short}-按皇帝分类.md"
    pd.DataFrame(res).to_csv(out_csv, index=False, encoding="utf-8-sig")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    write_grouped_md(res, out_md, f"朝野佥载 · {vol_short} · 按皇帝→年号分类")
    n = len(res)
    from collections import Counter
    c = Counter(r["main_emperor"] or "未系年" for r in res)
    print(f"[{vol_name}] {n} 段  ->  {dict(c)}")

# ---------- 3. Combined output ----------
comb_csv = ROOT / "朝野佥载-全卷-按皇帝分类.csv"
comb_json = ROOT / "朝野佥载-全卷-按皇帝分类.json"
comb_md = ROOT / "朝野佥载-全卷-按皇帝分类.md"
pd.DataFrame(all_results).to_csv(comb_csv, index=False, encoding="utf-8-sig")
with open(comb_json, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
write_grouped_md(all_results, comb_md, "朝野佥载 · 全卷 · 按皇帝→年号分类")
print(f"\n合计 {len(all_results)} 段")
print(f"合并CSV  -> {comb_csv}")
print(f"合并JSON -> {comb_json}")
print(f"合并MD   -> {comb_md}")
