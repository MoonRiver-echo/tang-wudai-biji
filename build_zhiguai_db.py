# -*- coding: utf-8 -*-
"""Build zhiguai.db from 志怪动物分类-汇总.csv + zhiguai_schema.sql.

    python build_zhiguai_db.py
    python build_zhiguai_db.py --db path/to/out.db

Replaces the target database each run.
"""
import argparse
import datetime
import re
import sqlite3
from collections import OrderedDict
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
SCHEMA = BASE / "zhiguai_schema.sql"
CSV = BASE / "志怪动物分类-汇总.csv"
XLS = BASE / "唐年号.xls"
DEFAULT_DB = BASE / "zhiguai.db"

L1_ORDER = [
    "卜筮占相", "鬼怪妖魅", "神仙佛道", "谶谣征应", "冥报报应",
    "死而复生", "巫术厌胜", "灵异神异", "神梦感应",
]
L3_ORDER = [
    "医疗", "官运仕途", "命运寿夭", "婚姻家庭", "报应惩恶",
    "军事战争", "政治征兆", "巫蛊害人", "禳灾祈福", "风俗信仰", "未明",
]
EMP_ORDER = [
    "高祖李渊", "太宗李世民", "高宗李治", "中宗李显", "睿宗李旦", "武则天",
    "殇帝李重茂", "玄宗李隆基", "肃宗李亨", "代宗李豫", "德宗李适",
    "顺宗李诵", "宪宗李纯", "穆宗李恒", "敬宗李湛", "文宗李昂",
    "武宗李炎", "宣宗李忱", "懿宗李漼", "僖宗李儇", "昭宗李晔",
    "哀帝李柷", "未系年",
]

ANIMAL_GROUPS = OrderedDict([
    ("瑞兽", ["龙", "凤", "麟", "驺虞", "蛟"]),
    ("走兽", ["虎", "马", "牛", "羊", "狗", "猪", "猫", "鼠", "兔",
              "鹿", "猿", "狐", "狼", "豹", "象", "骆驼", "驴", "骡"]),
    ("飞禽", ["鸡", "雉", "雁", "鹅", "鸭", "鹤", "鸳鸯", "鹰", "鸱",
              "鸦", "雀", "鸟"]),
    ("鳞介", ["蛇", "龟", "鱼", "蛙", "鼍"]),
    ("昆虫", ["蜈蚣", "蜘蛛", "蚕", "蜂", "蝉", "蝇", "蚊", "蚁", "蝗", "蝙蝠"]),
])

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

ANIMAL_TO_GROUP = {
    animal: group
    for group, members in ANIMAL_GROUPS.items()
    for animal in members
}

ROLES = [
    ("unspecified", "未辨析"),
    ("actual", "实物"),
    ("omen", "征兆"),
    ("metaphor", "隐喻"),
    ("title", "官署/名号"),
    ("person", "人名"),
]


def split_tags(value):
    if pd.isna(value) or str(value).strip() == "":
        return []
    return [part for part in str(value).split(";") if part]


def parse_emperor_parts(name):
    if name == "武则天":
        return "则天皇后", "武曌"
    if name == "未系年":
        return None, None
    m = re.match(r"(\S+?)(李\S+)", name)
    if m:
        return m.group(1), m.group(2)
    return None, None


def seed_lookups(conn):
    for i, name in enumerate(L1_ORDER):
        conn.execute(
            "INSERT INTO supernatural_types(name, sort_order) VALUES (?,?)",
            (name, i),
        )
    for i, name in enumerate(L3_ORDER):
        conn.execute(
            "INSERT INTO domains(name, sort_order, is_placeholder) VALUES (?,?,?)",
            (name, i, 1 if name == "未明" else 0),
        )
    for i, name in enumerate(ANIMAL_GROUPS):
        conn.execute(
            "INSERT INTO animal_groups(name, sort_order) VALUES (?,?)",
            (name, i),
        )
    group_ids = {r[0]: r[1] for r in conn.execute("SELECT name, id FROM animal_groups")}
    for i, (name, aliases) in enumerate(ANIMALS.items()):
        gid = group_ids.get(ANIMAL_TO_GROUP.get(name))
        conn.execute(
            "INSERT INTO animals(name, group_id, sort_order) VALUES (?,?,?)",
            (name, gid, i),
        )
        aid = conn.execute("SELECT id FROM animals WHERE name=?", (name,)).fetchone()[0]
        for alias in aliases:
            literal = alias.replace(r"(?<!司)", "")
            conn.execute(
                "INSERT INTO animal_aliases(animal_id, alias, match_pattern) VALUES (?,?,?)",
                (aid, literal, alias),
            )
    for code, name in ROLES:
        conn.execute("INSERT INTO animal_roles(code, name) VALUES (?,?)", (code, name))

    emp_ids = {}
    for i, name in enumerate(EMP_ORDER):
        temple, personal = parse_emperor_parts(name)
        conn.execute(
            "INSERT INTO emperors(name, temple_name, personal_name, sort_order, is_placeholder) "
            "VALUES (?,?,?,?,?)",
            (name, temple, personal, i, 1 if name == "未系年" else 0),
        )
        emp_ids[name] = conn.execute(
            "SELECT id FROM emperors WHERE name=?", (name,)
        ).fetchone()[0]

    if XLS.exists():
        xdf = pd.read_excel(XLS)
        xdf.columns = [c.strip() for c in xdf.columns]
        xdf["皇帝"] = xdf["皇帝"].ffill()
        for i, row in xdf.iterrows():
            emp = str(row["皇帝"]).strip()
            era = str(row["年号"]).strip()
            if emp not in emp_ids or not era or era == "nan":
                continue
            conn.execute(
                "INSERT OR IGNORE INTO eras"
                "(emperor_id, name, duration, ganzhi, note, sort_order) "
                "VALUES (?,?,?,?,?,?)",
                (
                    emp_ids[emp],
                    era,
                    None if pd.isna(row.get("时长")) else str(row["时长"]),
                    None if pd.isna(row.get("干支")) else str(row["干支"]),
                    None if pd.isna(row.get("备注")) or str(row["备注"]).strip() in ("-", "nan")
                    else str(row["备注"]),
                    int(i),
                ),
            )
    return emp_ids


def get_or_create_era(conn, emp_ids, emperor, era_name, extra_sort):
    if not era_name:
        return None
    eid = emp_ids[emperor]
    row = conn.execute(
        "SELECT id FROM eras WHERE emperor_id=? AND name=?", (eid, era_name)
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO eras(emperor_id, name, sort_order) VALUES (?,?,?)",
        (eid, era_name, extra_sort),
    )
    return cur.lastrowid


def get_or_create_emperor(conn, emp_ids, name):
    if name in emp_ids:
        return emp_ids[name]
    sort = len(emp_ids)
    conn.execute(
        "INSERT INTO emperors(name, sort_order, is_placeholder) VALUES (?,?,0)",
        (name, sort),
    )
    emp_ids[name] = conn.execute(
        "SELECT id FROM emperors WHERE name=?", (name,)
    ).fetchone()[0]
    return emp_ids[name]


def get_or_create_animal(conn, name):
    row = conn.execute("SELECT id FROM animals WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO animals(name, sort_order) VALUES (?,?)",
        (name, 1000),
    )
    return cur.lastrowid


def get_or_create_type(conn, name):
    row = conn.execute("SELECT id FROM supernatural_types WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO supernatural_types(name, sort_order) VALUES (?,?)",
        (name, 1000),
    )
    return cur.lastrowid


def get_or_create_domain(conn, name):
    row = conn.execute("SELECT id FROM domains WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO domains(name, sort_order) VALUES (?,?)",
        (name, 1000),
    )
    return cur.lastrowid


def load_csv(conn, emp_ids):
    df = pd.read_csv(CSV)
    book_ids, vol_ids = {}, {}
    unspecified = conn.execute(
        "SELECT id FROM animal_roles WHERE code='unspecified'"
    ).fetchone()[0]

    for _, row in df.iterrows():
        source = str(row["source"])
        volume = str(row["volume"])
        para_no = str(row["paragraph_id"])
        text = str(row["text"])

        if source not in book_ids:
            cur = conn.execute(
                "INSERT INTO books(name, sort_order) VALUES (?,?)",
                (source, len(book_ids)),
            )
            book_ids[source] = cur.lastrowid
        bid = book_ids[source]

        vkey = (bid, volume)
        if vkey not in vol_ids:
            m = re.match(r"^(\d+)-", volume)
            sort = int(m.group(1)) if m else len(vol_ids)
            cur = conn.execute(
                "INSERT INTO volumes(book_id, name, sort_order) VALUES (?,?,?)",
                (bid, volume, sort),
            )
            vol_ids[vkey] = cur.lastrowid
        vid = vol_ids[vkey]

        cur = conn.execute(
            "INSERT INTO paragraphs(book_id, volume_id, para_no, text, char_count) "
            "VALUES (?,?,?,?,?)",
            (bid, vid, para_no, text, len(text)),
        )
        pid = cur.lastrowid

        for rank, name in enumerate(split_tags(row["level1_supernatural"]), start=1):
            conn.execute(
                "INSERT INTO paragraph_supernatural(paragraph_id, type_id, rank) "
                "VALUES (?,?,?)",
                (pid, get_or_create_type(conn, name), rank),
            )

        emperor = str(row["level2_emperor"]) if pd.notna(row["level2_emperor"]) else "未系年"
        era_name = str(row["level2_era"]).strip() if pd.notna(row["level2_era"]) else ""
        if era_name in ("nan",):
            era_name = ""
        emp_id = get_or_create_emperor(conn, emp_ids, emperor)
        era_id = get_or_create_era(conn, emp_ids, emperor, era_name, 9000 + pid) if era_name else None
        conn.execute(
            "INSERT INTO paragraph_reign(paragraph_id, emperor_id, era_id, rank) "
            "VALUES (?,?,?,1)",
            (pid, emp_id, era_id),
        )

        for rank, name in enumerate(split_tags(row["level3_domain"]), start=1):
            conn.execute(
                "INSERT INTO paragraph_domain(paragraph_id, domain_id, rank) "
                "VALUES (?,?,?)",
                (pid, get_or_create_domain(conn, name), rank),
            )

        for rank, name in enumerate(split_tags(row["level4_animals_all"]), start=1):
            conn.execute(
                "INSERT INTO paragraph_animal(paragraph_id, animal_id, rank, role_id) "
                "VALUES (?,?,?,?)",
                (pid, get_or_create_animal(conn, name), rank, unspecified),
            )

    conn.execute(
        "INSERT INTO import_batches(source_file, imported_at, row_count, note) "
        "VALUES (?,?,?,?)",
        (
            CSV.name,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            len(df),
            "animal-classified supernatural paragraphs; primary tag = rank 1",
        ),
    )
    return len(df)


def rebuild_fts(conn):
    tok = None
    for candidate in ("trigram", "unicode61"):
        try:
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS __p USING fts5(x, tokenize={candidate})"
            )
            conn.execute("DROP TABLE __p")
            tok = candidate
            break
        except sqlite3.OperationalError:
            continue
    if not tok:
        return None
    conn.execute("DROP TABLE IF EXISTS paragraphs_fts")
    conn.execute(
        f"CREATE VIRTUAL TABLE paragraphs_fts "
        f"USING fts5(para_id UNINDEXED, text, tokenize={tok})"
    )
    rows = conn.execute("SELECT id, text FROM paragraphs").fetchall()
    conn.executemany(
        "INSERT INTO paragraphs_fts(para_id, text) VALUES (?,?)", rows
    )
    return tok


def print_stats(conn):
    n_books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    n_vols = conn.execute("SELECT COUNT(*) FROM volumes").fetchone()[0]
    n_paras = conn.execute("SELECT COUNT(*) FROM paragraphs").fetchone()[0]
    n_anim = conn.execute("SELECT COUNT(*) FROM paragraph_animal").fetchone()[0]
    n_l1 = conn.execute("SELECT COUNT(*) FROM paragraph_supernatural").fetchone()[0]
    n_l3 = conn.execute("SELECT COUNT(*) FROM paragraph_domain").fetchone()[0]
    print(f"books {n_books}  volumes {n_vols}  paragraphs {n_paras}")
    print(f"tags  L1 {n_l1}  L3 {n_l3}  animals {n_anim}")
    print("paragraphs per book:")
    for name, n in conn.execute(
        "SELECT b.name, COUNT(p.id) FROM books b "
        "JOIN paragraphs p ON p.book_id=b.id "
        "GROUP BY b.id ORDER BY b.sort_order"
    ):
        print(f"  {name}: {n}")
    print("primary animals:")
    for name, n in conn.execute(
        "SELECT a.name, COUNT(*) FROM paragraph_animal pa "
        "JOIN animals a ON a.id=pa.animal_id "
        "WHERE pa.rank=1 GROUP BY a.id ORDER BY COUNT(*) DESC"
    ):
        print(f"  {name}: {n}")


def build(db_path):
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    emp_ids = seed_lookups(conn)
    n = load_csv(conn, emp_ids)
    tok = rebuild_fts(conn)
    conn.commit()
    print(f"built {db_path}  ({n} paragraphs)")
    print(f"FTS tokenizer: {tok or 'unavailable'}")
    print_stats(conn)
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Build zhiguai.db from the animal CSV")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    build(args.db)


if __name__ == "__main__":
    main()
