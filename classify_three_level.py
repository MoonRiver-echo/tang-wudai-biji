# -*- coding: utf-8 -*-
"""Third-level classification of the supernatural paragraphs.
Level 3 = subject/purpose domain (e.g. divination for illness -> 医疗).
Reads the existing two-level CSV, adds level3_domain, writes new CSV/JSON/MD.
"""
import re, json
import pandas as pd
from pathlib import Path
from collections import OrderedDict

BASE = Path(__file__).parent
ROOT = BASE / "朝野佥载"
SRC = ROOT / "朝野佥载-志怪二级分类.csv"

DOMAINS = OrderedDict([
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

def domains_for(text):
    return [d for d, kws in DOMAINS.items() if any(k in text for k in kws)]

df = pd.read_csv(SRC)
records = []
for _, row in df.iterrows():
    text = str(row["text"])
    l3 = domains_for(text)
    records.append({
        "paragraph_id": row["paragraph_id"],
        "volume": row["volume"],
        "level1_supernatural": row["level1_supernatural"],
        "level2_emperor": row["level2_emperor"],
        "level2_era": row["level2_era"],
        "level3_domain": ";".join(l3) if l3 else "未明",
        "text": text,
    })

out_csv = ROOT / "朝野佥载-志怪三级分类.csv"
out_json = ROOT / "朝野佥载-志怪三级分类.json"
out_md = ROOT / "朝野佥载-志怪三级分类.md"
pd.DataFrame(records).to_csv(out_csv, index=False, encoding="utf-8-sig")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

lines = ["# 朝野佥载 · 志怪三级分类（类别→皇帝/年号→事类）\n",
         f"共 {len(records)} 段志怪段落，三级标签：\n",
         "- 一级：志怪类别\n- 二级：皇帝/年号\n- 三级：事类（医疗/官运/报应…）\n"]
for cat in DOMAINS:
    sub = [r for r in records if cat in r["level3_domain"]]
    if not sub:
        continue
    lines.append(f"## 三级事类：【{cat}】（{len(sub)} 段）\n")
    for r in sub:
        l1 = r["level1_supernatural"]
        l2 = r["level2_emperor"] + (("·" + r["level2_era"]) if pd.notna(r["level2_era"]) and r["level2_era"] else "")
        tag = f"  〔一级：{l1}｜二级：{l2}〕"
        lines.append(r["text"] + tag + "\n")
    lines.append("")
out_md.write_text("\n".join(lines), encoding="utf-8")

print(f"三级分类：{len(records)} 段")
from collections import Counter
print("\n三级事类分布：")
for d in DOMAINS:
    n = sum(1 for r in records if d in r["level3_domain"])
    print(f"  {d}: {n}")
print(f"  未明: {sum(1 for r in records if r['level3_domain']=='未明')}")
print(f"\nCSV  -> {out_csv}")
print(f"JSON -> {out_json}")
print(f"MD   -> {out_md}")
