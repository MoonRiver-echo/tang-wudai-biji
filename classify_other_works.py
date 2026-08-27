# -*- coding: utf-8 -*-
"""Apply the full classification pipeline to 大唐传载 / 大唐新语 / 唐国史补:
  1. Emperor/era classification (all paragraphs)
  2. Supernatural scan (志怪 paragraphs)
  3. Three-level hierarchy (L1 志怪类别 -> L2 皇帝/年号 -> L3 事类)
Uses 唐年号.xls as bibliography.
"""
import re, json
import pandas as pd
from pathlib import Path
from collections import OrderedDict, Counter

BASE = Path(__file__).parent
XLS = BASE / "唐年号.xls"
WORKS = ["大唐传载", "大唐新语", "唐国史补", "刘宾客嘉话录", "博异志",
         "因话录", "教坊记", "明皇杂录", "次柳氏旧闻", "独异志", "玄怪录",
         "甘泽谣", "纂异记", "续玄怪录", "隋唐嘉话", "龙城录"]

# ===== bibliography =====
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

# ===== supernatural (L1) + domain (L3) categories =====
L1_CATS = OrderedDict([
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
L3_CATS = OrderedDict([
    ("医疗", ["医", "药", "病", "疗", "疾", "痊", "愈", "疮", "肿", "痛",
            "盲", "失明", "灸", "解毒", "医人", "善医", "疗病", "平复",
            "病卒", "患", "疯", "咳", "喘", "本草", "蛇胆", "蛇肉", "蛇骨",
            "杀鬼丸", "铜末", "雄黄", "地黄", "旋复", "甲虫", "刀割",
            "折足", "坠马", "应语病", "虫蚀", "守宫", "染大疯", "鼻根"]),
    ("官运仕途", ["迁", "除", "授", "贬", "降", "罢", "选", "举", "进士",
                "擢第", "应举", "掌选", "铨", "左授", "左降", "配流", "秩",
                "禄", "禄尽", "品", "阶", "得官", "失官", "方伯", "京官",
                "当迁", "何当迁", "官职", "补阙", "城门郎", "拾遗",
                "司户", "主簿", "县丞"]),
    ("命运寿夭", ["寿", "寿命", "夭", "死期", "活几时", "厄", "大厄",
                "命禄", "算年命", "卜年命", "年命", "不救法", "病当死",
                "当死", "必死", "无救", "救法", "十余日活"]),
    ("婚姻家庭", ["婚", "嫁", "娶", "妻", "妾", "姻", "配", "纳妾",
                "夫妇", "夫妻", "家口", "家属"]),
    ("报应惩恶", ["报应", "冥报", "业报", "冥罚", "报焉", "报之",
                "冥司", "见王", "下状", "追至", "冥吏", "鬼使", "受报",
                "恶报", "善报", "冤", "枉"]),
    ("军事战争", ["叛", "反叛", "谋反", "作逆", "作乱", "征讨", "征伐",
                "讨伐", "北征", "征兵", "军没", "兵革", "入贼", "击贼",
                "破贼", "破营", "陷没", "没于", "没贼", "突厥", "契丹",
                "营府", "反贼", "叛乱", "起兵", "举兵", "入寇", "战于",
                "交战", "战败", "破阵", "阵亡", "寇贼", "欲反", "兵起",
                "起事", "同起事"]),
    ("政治征兆", ["即位", "践祚", "改元", "革命", "禅位", "禅让", "废帝",
                "废为", "立太子", "立为", "中兴", "易主", "逊位", "登极",
                "龙飞", "篡", "复辟", "践阼", "太上皇", "践阼"]),
    ("巫蛊害人", ["蛊", "蛊毒", "诅咒", "咒人", "厌咒", "诅", "厌魅",
                "毒药", "冶葛", "鸩", "妖术", "妖道", "猫鬼", "害人",
                "厌胜", "巫蛊", "蛊毒"]),
    ("禳灾祈福", ["禳", "崇福", "压", "厌", "祭", "祈", "设斋", "造像",
                "修造", "祠", "祀", "斋", "醮", "祈雨", "祈福", "诵经",
                "诵咒", "经咒", "设坛", "坛场", "止雨", "祈请", "祈晴"]),
    ("风俗信仰", ["风俗", "俗", "忌", "忌讳", "俗谚", "谚", "谚云",
                "俗语", "谣曰", "童谣", "唱歌", "唱", "俗云"]),
])
def l1_tags(body):
    return [c for c, kws in L1_CATS.items() if any(k in body for k in kws)]
def l3_tags(body):
    return [c for c, kws in L3_CATS.items() if any(k in body for k in kws)]

# ===== ordering helpers =====
L1_ORDER = list(L1_CATS.keys())
L3_ORDER = list(L3_CATS.keys()) + ["未明"]
EMP_ORDER = emperor_order + ["未系年"]
def rank(x, order):
    return order.index(x) if x in order else len(order)

# ===== read paragraphs from a work =====
para_re = re.compile(r"^(【(\d{2}-\d{3})】)(.*)$", re.S)
def read_work(root):
    out = []
    for src in sorted(root.rglob("00-*全卷*.md")):
        vol = src.parent.name
        for line in src.read_text(encoding="utf-8").splitlines():
            m = para_re.match(line.strip())
            if m:
                out.append({"id": m.group(2), "vol": vol,
                            "head": m.group(1), "body": m.group(3).strip()})
    return out

def era_rank(e):
    return era_order.index(e) if e in era_order else len(era_order)

# ===== grouped MD writers =====
def write_emperor_md(rows, out, title):
    groups = OrderedDict((emp, OrderedDict()) for emp in emperor_order)
    indep = []
    for r in rows:
        if r["classification_type"] == "independent":
            indep.append(r); continue
        emp = r["main_emperor"]
        era = r["main_era"] if r["main_era"] else "（仅称皇帝·未系年号）"
        groups[emp].setdefault(era, []).append(r)
    lines = [f"# {title}\n"]
    for emp in emperor_order:
        em = groups[emp]
        if not em:
            continue
        lines.append(f"# 皇帝：{emp}\n")
        for era in sorted(em.keys(), key=lambda e: (e.startswith("（"), era_rank(e))):
            lines.append(f"## 年号：{era}\n")
            for r in em[era]:
                lines.append(r["text"] + "\n")
            lines.append("")
    lines.append("# 未系年（未提及年号或皇帝）\n")
    for r in indep:
        lines.append(r["text"] + "\n")
    out.write_text("\n".join(lines), encoding="utf-8")

def write_hierarchy_md(rows, out, title):
    tree = OrderedDict()
    for r in rows:
        l1 = r["level1_supernatural"].split(";")[0]
        l2 = r["level2_emperor"] + (("·" + r["level2_era"]) if r["level2_era"] else "")
        l3 = r["level3_domain"].split(";")[0] if r["level3_domain"] else "未明"
        tree.setdefault(l1, OrderedDict())
        tree[l1].setdefault(l2, OrderedDict())
        tree[l1][l2].setdefault(l3, []).append(r)
    lines = [f"# {title}\n",
             "段落按【一级：志怪类别】→【二级：皇帝·年号】→【三级：事类】层级排列。\n",
             f"共 {len(rows)} 段志怪段落（每段按主标签归入一处）。\n"]
    for l1 in sorted(tree.keys(), key=lambda x: rank(x, L1_ORDER)):
        lines.append(f"# 一级：【{l1}】\n")
        for l2 in sorted(tree[l1].keys(), key=lambda k: (rank(k.split("·")[0], EMP_ORDER), k)):
            lines.append(f"## 二级：【{l2}】\n")
            for l3 in sorted(tree[l1][l2].keys(), key=lambda x: rank(x, L3_ORDER)):
                rs = tree[l1][l2][l3]
                lines.append(f"### 三级：【{l3}】（{len(rs)} 段）\n")
                for r in rs:
                    lines.append(r["text"] + "\n")
                lines.append("")
            lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")

# ===== process each work =====
for work in WORKS:
    root = BASE / work
    paras = read_work(root)
    all_rows = []
    super_rows = []
    for p in paras:
        emp, era, all_emp, all_era = time_tag(p["body"])
        l1 = l1_tags(p["body"])
        full = p["head"] + p["body"]
        row = {
            "paragraph_id": p["id"], "volume": p["vol"],
            "main_emperor": emp, "main_era": era,
            "all_emperors": all_emp, "all_eras": all_era,
            "classification_type": "era" if era else ("emperor" if emp else "independent"),
            "text": full,
        }
        all_rows.append(row)
        if l1:
            l3 = l3_tags(p["body"])
            super_rows.append({
                "paragraph_id": p["id"], "volume": p["vol"],
                "level1_supernatural": ";".join(l1),
                "level2_emperor": emp or "未系年",
                "level2_era": era,
                "level3_domain": ";".join(l3) if l3 else "未明",
                "text": full,
            })

    ec = root / f"{work}-按皇帝分类.csv"
    ej = root / f"{work}-按皇帝分类.json"
    em = root / f"{work}-按皇帝分类.md"
    pd.DataFrame(all_rows).to_csv(ec, index=False, encoding="utf-8-sig")
    with open(ej, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    write_emperor_md(all_rows, em, f"{work} · 按皇帝→年号分类")

    sc = root / f"{work}-志怪异事.csv"
    sj = root / f"{work}-志怪异事.json"
    sm = root / f"{work}-志怪异事.md"
    pd.DataFrame(super_rows).to_csv(sc, index=False, encoding="utf-8-sig")
    with open(sj, "w", encoding="utf-8") as f:
        json.dump(super_rows, f, ensure_ascii=False, indent=2)
    lines = [f"# {work} · 志怪异事汇编\n", f"共 {len(super_rows)} 段提及超自然内容。\n"]
    for cat in L1_CATS:
        sub = [r for r in super_rows if cat in r["level1_supernatural"]]
        if not sub:
            continue
        lines.append(f"## 【{cat}】（{len(sub)} 段）\n")
        for r in sub:
            lines.append(r["text"] + "\n")
        lines.append("")
    sm.write_text("\n".join(lines), encoding="utf-8")

    hc = root / f"{work}-志怪三级层级.csv"
    hm = root / f"{work}-志怪三级层级.md"
    pd.DataFrame(super_rows).to_csv(hc, index=False, encoding="utf-8-sig")
    write_hierarchy_md(super_rows, hm, f"{work} · 志怪三级层级分类")

    cc = Counter(r["main_emperor"] or "未系年" for r in all_rows)
    print(f"[{work}] 全{len(all_rows)}段  志怪{len(super_rows)}段")
    print(f"  皇帝分布: {dict(cc)}")
    sc_count = Counter(r["level1_supernatural"].split(';')[0] for r in super_rows)
    print(f"  志怪一级: {dict(sc_count)}")
