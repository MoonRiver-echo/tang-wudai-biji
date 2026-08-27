# -*- coding: utf-8 -*-
"""Add a 4th classification level by ANIMAL.

Reads each work's *志怪三级分类.csv* (which already carries L1 志怪类别,
L2 皇帝/年号, L3 事类 plus the full paragraph text), detects the animals
mentioned in each paragraph, keeps ONLY the paragraphs that contain at least
one animal, and writes:

  * {work}-志怪动物分类.csv   (flat, with level4_animal / level4_animals_all)
  * {work}-志怪动物层级.md     (nested L1 -> L2 -> L3 -> L4[animal])

Each paragraph appears exactly once in the hierarchy, placed by its PRIMARY
(first) tag at every level.
"""
import re
import sys
import pandas as pd
from pathlib import Path
from collections import OrderedDict, Counter

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent

WORKS = ["朝野佥载", "大唐传载", "大唐新语", "唐国史补", "刘宾客嘉话录",
         "博异志", "因话录", "教坊记", "明皇杂录", "次柳氏旧闻", "独异志",
         "玄怪录", "甘泽谣", "纂异记", "续玄怪录", "隋唐嘉话", "龙城录"]

# ---------- canonical ordering (mirrors classify_hierarchy.py) ----------
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


# ---------- animal dictionary ----------
# canonical name -> list of regex alternatives (longer compounds first so the
# canonical name itself stays stable). 马 excludes the 马 inside 司马 (a
# surname / official title) via a negative look-behind.
ANIMALS = OrderedDict([
    ("龙", [r"龙"]),
    ("凤", [r"凤凰", r"凤", r"鸾"]),
    ("麟", [r"麒麟", r"麟"]),
    ("驺虞", [r"驺虞"]),
    ("蛟", [r"蛟龙", r"蛟"]),
    ("虎", [r"猛虎", r"白虎", r"虎"]),
    ("蛇", [r"蟒", r"蚺", r"蛇"]),
    ("龟", [r"鼋", r"鳖", r"龟"]),
    ("鱼", [r"鲤鱼", r"鱼"]),
    ("蛙", [r"蛤蟆", r"蛙"]),
    ("蜈蚣", [r"蜈蚣"]),
    ("蜘蛛", [r"蜘蛛"]),
    ("蚕", [r"蚕"]),
    ("蜂", [r"蜂"]),
    ("蝉", [r"蝉"]),
    ("蝇", [r"蝇"]),
    ("蚊", [r"蚊"]),
    ("蚁", [r"蚁"]),
    ("蝗", [r"蝗"]),
    ("蝙蝠", [r"蝙蝠"]),
    ("马", [r"(?<!司)马"]),
    ("牛", [r"水牛", r"牯牛", r"牛"]),
    ("羊", [r"羔", r"羊"]),
    ("狗", [r"恶犬", r"犬", r"狗"]),
    ("猪", [r"豕", r"豚", r"猪"]),
    ("猫", [r"猫"]),
    ("鼠", [r"鼷鼠", r"鼠"]),
    ("兔", [r"白兔", r"兔"]),
    ("鹿", [r"白鹿", r"麋", r"鹿"]),
    ("猿", [r"猕猴", r"猴", r"猿"]),
    ("狐", [r"狐狸", r"狐"]),
    ("狼", [r"狼"]),
    ("豹", [r"豹"]),
    ("象", [r"大象", r"象"]),
    ("骆驼", [r"骆驼", r"驼"]),
    ("驴", [r"驴"]),
    ("骡", [r"骡"]),
    ("鸡", [r"牝鸡", r"雄鸡", r"鸡"]),
    ("雉", [r"雉"]),
    ("雁", [r"雁"]),
    ("鹅", [r"鹅"]),
    ("鸭", [r"鸭"]),
    ("鹤", [r"白鹤", r"鹤"]),
    ("鸳鸯", [r"鸳鸯"]),
    ("鹰", [r"鹗", r"鹰"]),
    ("鸱", [r"鸱"]),
    ("鸦", [r"乌鸦", r"鸦"]),
    ("雀", [r"麻雀", r"雀"]),
    ("鸟", [r"飞鸟", r"众鸟", r"鸟"]),
    ("鼍", [r"鼍"]),
])

# pre-compile one regex per animal
ANIMAL_RE = OrderedDict(
    (name, re.compile("|".join(alts))) for name, alts in ANIMALS.items()
)


def detect_animals(text):
    """Return the ordered, de-duplicated list of canonical animal names found."""
    hits = []
    for name, rx in ANIMAL_RE.items():
        if rx.search(text) and name not in hits:
            hits.append(name)
    return hits


def process(work):
    root = BASE / work
    src = None
    for cand in (f"{work}-志怪三级分类.csv", f"{work}-志怪三级层级.csv"):
        p = root / cand
        if p.exists():
            src = p
            break
    if src is None:
        print(f"[skip] {work} 无志怪三级源文件")
        return None
    df = pd.read_csv(src)
    df["text"] = df["text"].astype(str)

    anim_lists = [detect_animals(t) for t in df["text"]]
    df["_animals"] = anim_lists
    df = df[[len(a) > 0 for a in df["_animals"]]].reset_index(drop=True)
    df["level4_animal"] = [a[0] for a in df["_animals"]]
    df["level4_animals_all"] = [";".join(a) for a in df["_animals"]]
    df.insert(0, "source", work)

    out_cols = ["source", "paragraph_id", "volume", "level1_supernatural",
                "level2_emperor", "level2_era", "level3_domain",
                "level4_animal", "level4_animals_all", "text"]
    out_csv = root / f"{work}-志怪动物分类.csv"
    df[out_cols].to_csv(out_csv, index=False, encoding="utf-8-sig")

    tree = OrderedDict()
    for _, r in df.iterrows():
        l1 = str(r["level1_supernatural"]).split(";")[0]
        l2 = str(r["level2_emperor"]) if pd.notna(r["level2_emperor"]) else "未系年"
        era = str(r["level2_era"]) if pd.notna(r["level2_era"]) else ""
        l2key = l2 + (("·" + era) if era and era != "nan" else "")
        l3 = str(r["level3_domain"]).split(";")[0] if pd.notna(r["level3_domain"]) else "未明"
        l4 = str(r["level4_animal"])
        tree.setdefault(l1, OrderedDict())
        tree[l1].setdefault(l2key, OrderedDict())
        tree[l1][l2key].setdefault(l3, OrderedDict())
        tree[l1][l2key][l3].setdefault(l4, []).append(r)

    lines = [f"# {work} · 志怪动物层级分类\n",
             f"仅收录提及动物的段落，按【一级：志怪类别】→【二级：皇帝·年号】"
             f"→【三级：事类】→【四级：动物】层级排列。\n",
             f"共 {len(df)} 段（每段按主标签归入一处，不重复）。\n"]
    for l1 in sorted(tree.keys(), key=l1_rank):
        lines.append(f"# 一级：【{l1}】\n")
        for l2 in sorted(tree[l1].keys(), key=lambda k: (emp_rank(k.split("·")[0]), k)):
            lines.append(f"## 二级：【{l2}】\n")
            for l3 in sorted(tree[l1][l2].keys(), key=l3_rank):
                lines.append(f"### 三级：【{l3}】\n")
                for l4 in sorted(tree[l1][l2][l3].keys(),
                                  key=lambda a: list(ANIMALS).index(a)
                                  if a in ANIMALS else len(ANIMALS)):
                    rows = tree[l1][l2][l3][l4]
                    lines.append(f"#### 四级：【{l4}】（{len(rows)} 段）\n")
                    for r in rows:
                        lines.append(r["text"] + "\n")
                    lines.append("")
                lines.append("")
            lines.append("")
        lines.append("")
    out_md = root / f"{work}-志怪动物层级.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    ac = Counter(df["level4_animal"])
    print(f"[{work}] 志怪段落 {len(pd.read_csv(src))} 段 -> 含动物 {len(df)} 段")
    print(f"  动物分布: {dict(ac)}")
    print(f"  CSV -> {out_csv}")
    print(f"  MD  -> {out_md}")
    return df[out_cols]


if __name__ == "__main__":
    combined = []
    for w in WORKS:
        d = process(w)
        if d is not None and len(d):
            combined.append(d)
    if combined:
        import json
        all_df = pd.concat(combined, ignore_index=True)

        combo_csv = BASE / "志怪动物分类-汇总.csv"
        all_df.to_csv(combo_csv, index=False, encoding="utf-8-sig")

        # ---- combined JSON (flat array of records, source-annotated) ----
        combo_json = BASE / "志怪动物分类-汇总.json"
        records = all_df.where(pd.notnull(all_df), None).to_dict(orient="records")
        with open(combo_json, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        # ---- combined Markdown : L1 -> L2 -> L3 -> L4, paragraphs tagged
        #      with their source work so origins are visible inline ----
        tree = OrderedDict()
        for _, r in all_df.iterrows():
            l1 = str(r["level1_supernatural"]).split(";")[0]
            l2 = str(r["level2_emperor"]) if pd.notna(r["level2_emperor"]) else "未系年"
            era = str(r["level2_era"]) if pd.notna(r["level2_era"]) else ""
            l2key = l2 + (("·" + era) if era and era != "nan" else "")
            l3 = str(r["level3_domain"]).split(";")[0] if pd.notna(r["level3_domain"]) else "未明"
            l4 = str(r["level4_animal"])
            tree.setdefault(l1, OrderedDict())
            tree[l1].setdefault(l2key, OrderedDict())
            tree[l1][l2key].setdefault(l3, OrderedDict())
            tree[l1][l2key][l3].setdefault(l4, []).append(r)

        lines = ["# 志怪动物分类 · 汇总\n",
                 "仅收录提及动物的段落，跨各书合并，按"
                 "【一级：志怪类别】→【二级：皇帝·年号】→【三级：事类】"
                 "→【四级：动物】层级排列。\n",
                 f"共 {len(all_df)} 段，来自 {all_df['source'].nunique()} 部书"
                 "（每段按主标签归入一处，不重复；段首标注来源书名）。\n"]
        for l1 in sorted(tree.keys(), key=l1_rank):
            lines.append(f"# 一级：【{l1}】\n")
            for l2 in sorted(tree[l1].keys(),
                             key=lambda k: (emp_rank(k.split("·")[0]), k)):
                lines.append(f"## 二级：【{l2}】\n")
                for l3 in sorted(tree[l1][l2].keys(), key=l3_rank):
                    lines.append(f"### 三级：【{l3}】\n")
                    for l4 in sorted(tree[l1][l2][l3].keys(),
                                     key=lambda a: list(ANIMALS).index(a)
                                     if a in ANIMALS else len(ANIMALS)):
                        rows = tree[l1][l2][l3][l4]
                        lines.append(f"#### 四级：【{l4}】（{len(rows)} 段）\n")
                        for r in rows:
                            lines.append(f"【{r['source']}·{r['paragraph_id']}】"
                                         + str(r["text"]) + "\n")
                        lines.append("")
                    lines.append("")
                lines.append("")
            lines.append("")
        combo_md = BASE / "志怪动物分类-汇总.md"
        combo_md.write_text("\n".join(lines), encoding="utf-8")

        print(f"\n汇总 CSV  -> {combo_csv}  （共 {len(all_df)} 段，"
              f"来自 {all_df['source'].nunique()} 部）")
        print(f"汇总 JSON -> {combo_json}")
        print(f"汇总 MD   -> {combo_md}")
        print("各书条目数：")
        for src, n in all_df["source"].value_counts().items():
            print(f"  {src}: {n}")
