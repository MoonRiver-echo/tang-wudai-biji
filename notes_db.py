# -*- coding: utf-8 -*-
"""唐五代笔记小说 SQLite 全文检索与分类标注数据库。

实体：books / volumes / paragraphs / categories / annotations / batches。
段落表同时保留 category_main 等软字段作为单段快速标注后门，
annotations 表保留段↔类目多对多全部历史。

用法：
    python notes_db.py build
    python notes_db.py stats
    python notes_db.py search <关键词> [-b 书名] [-v 卷名] [--limit N] [--no-fts]
    python notes_db.py show <段号|全书序号>
    python notes_db.py cat-add <名称> [-p 父类] [--desc 描述]
    python notes_db.py cat-list
    python notes_db.py annotate <段号> -c <类目> [--by 标注人] [--note 备注] [--batch 批次名]
    python notes_db.py batch <类目> -i <段号1,段号2,...> [--by 标注人] [--name 批次名] [--note 备注]
    python notes_db.py batch-file <类目> -f <段号清单文件>
    python notes_db.py tags <段号>
    python notes_db.py export [输出文件]
"""
import argparse
import csv
import re
import sqlite3
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "notes.db"

TITLE_RE = re.compile(r"^#\s+(.+?)\s*\u00b7\s*(.+?)\s*$")  # # 书 · 卷
PARA_RE = re.compile(r"^\u3010(\d{1,2})-(\d{3})\u3011")     # 【01-001】
SEQ_RE = re.compile(r"\u5168\u4e66\u5e8f\u53f7\uff1a\s*(\d+)")  # 全书序号：
BOOK_META_RE = re.compile(r"\u4e66\u540d\uff1a\s*(.+)")        # 书名：
VOL_META_RE = re.compile(r"\u5377/\u7bc7\uff1a\s*(.+)")        # 卷/篇：


def find_quanjuan_files():
    files = [p for p in ROOT.rglob("*\u5168\u5377*.md")]
    files.sort(key=lambda p: p.parts)
    return files


def read_paragraph_seq_map(quanjuan_path):
    """从同目录 001.md/002.md ... 读取 段号→全书序号 映射；缺失返回空 dict。
    段号由「目录前缀数字-文件名」拼成，如 01-001。"""
    seq_map = {}
    d = quanjuan_path.parent
    m = re.match(r"(\d+)-", d.name)
    prefix = f"{int(m.group(1)):02d}" if m else ""
    for f in d.glob("*.md"):
        if f.name.startswith("00-") or not f.stem.isdigit():
            continue
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:
            continue
        sm = SEQ_RE.search(txt)
        if sm:
            para_no = f"{prefix}-{int(f.stem):03d}" if prefix else f.stem
            seq_map[para_no] = int(sm.group(1))
    return seq_map


def parse_quanjuan(path):
    """解析单个全卷文件 → (book, volume, [paragraphs])。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    book = volume = None
    body_start = 0
    for i, ln in enumerate(lines):
        m = TITLE_RE.match(ln.strip())
        if m:
            book, volume = m.group(1).strip(), m.group(2).strip()
            body_start = i + 1
            break
    if book is None:
        book = path.parent.parent.name
        volume = path.stem.replace("-\u5168\u5377", "")
    paras = []
    cur_no = None
    cur_lines = []
    for ln in lines[body_start:]:
        s = ln.strip()
        if not s:
            continue
        m = PARA_RE.match(s)
        if m:
            if cur_no is not None:
                paras.append({"para_no": cur_no, "text": "".join(cur_lines).strip()})
            cur_no = f"{int(m.group(1)):02d}-{m.group(2)}"
            rest = s[m.end():].strip()
            cur_lines = [rest] if rest else []
        else:
            if cur_no is None:
                continue
            cur_lines.append(s)
    if cur_no is not None:
        paras.append({"para_no": cur_no, "text": "".join(cur_lines).strip()})
    return book, volume, paras


SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
    author TEXT, dynasty TEXT, sort_order INTEGER NOT NULL DEFAULT 0,
    para_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS volumes (
    id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    name TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0,
    para_count INTEGER NOT NULL DEFAULT 0, source_file TEXT,
    UNIQUE(book_id, sort_order)
);
CREATE TABLE IF NOT EXISTS paragraphs (
    id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    volume_id INTEGER NOT NULL REFERENCES volumes(id) ON DELETE CASCADE,
    para_no TEXT NOT NULL, seq_no INTEGER, text TEXT NOT NULL,
    char_count INTEGER NOT NULL DEFAULT 0, source_file TEXT,
    category_main TEXT, category_tags TEXT, annotator TEXT,
    annotation_note TEXT, batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    updated_at TEXT, UNIQUE(volume_id, para_no)
);
CREATE INDEX IF NOT EXISTS idx_para_book ON paragraphs(book_id);
CREATE INDEX IF NOT EXISTS idx_para_seq  ON paragraphs(seq_no);
CREATE INDEX IF NOT EXISTS idx_para_cat  ON paragraphs(category_main);
CREATE INDEX IF NOT EXISTS idx_para_text ON paragraphs(text COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
    parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    description TEXT, sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT,
    UNIQUE(parent_id, name)
);
CREATE INDEX IF NOT EXISTS idx_cat_parent ON categories(parent_id);
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, annotator TEXT,
    note TEXT, created_at TEXT, para_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY, paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    annotator TEXT, note TEXT, batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    created_at TEXT, UNIQUE(paragraph_id, category_id, batch_id)
);
CREATE INDEX IF NOT EXISTS idx_ann_para ON annotations(paragraph_id);
CREATE INDEX IF NOT EXISTS idx_ann_cat  ON annotations(category_id);
"""


def get_tokenizer(conn):
    for tok in ("trigram", "unicode61"):
        try:
            conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS __p USING fts5(x, tokenize={tok})")
            conn.execute("DROP TABLE __p")
            return tok
        except sqlite3.OperationalError:
            continue
    return None


def rebuild_fts(conn):
    tok = get_tokenizer(conn)
    if not tok:
        return None
    conn.execute("DROP TABLE IF EXISTS paragraphs_fts")
    conn.execute(f"CREATE VIRTUAL TABLE paragraphs_fts USING fts5(para_id UNINDEXED, text, tokenize={tok})")
    rows = conn.execute("SELECT id, text FROM paragraphs").fetchall()
    conn.executemany("INSERT INTO paragraphs_fts(para_id, text) VALUES (?,?)", rows)
    return tok


def build(force=True):
    if force and DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    files = find_quanjuan_files()
    book_order, book_ids, total_paras = {}, {}, 0
    for path in files:
        book_name, vol_name, paras = parse_quanjuan(path)
        if not paras:
            continue
        vol_dir = path.parent.name
        m = re.match(r"(\d+)-", vol_dir)
        vol_sort = int(m.group(1)) if m else 0
        if book_name not in book_order:
            book_order[book_name] = len(book_order)
        if book_name not in book_ids:
            cur = conn.execute("INSERT INTO books(name, sort_order) VALUES (?,?)",
                               (book_name, book_order[book_name]))
            book_ids[book_name] = cur.lastrowid
        bid = book_ids[book_name]
        cur = conn.execute(
            "INSERT INTO volumes(book_id, name, sort_order, source_file) VALUES (?,?,?,?)",
            (bid, vol_name, vol_sort, str(path.relative_to(ROOT))))
        vid = cur.lastrowid
        seq_map = read_paragraph_seq_map(path)
        rows = []
        for p in paras:
            seq = seq_map.get(p["para_no"])
            rows.append((bid, vid, p["para_no"], seq, p["text"], len(p["text"]),
                         str(path.relative_to(ROOT))))
        conn.executemany(
            "INSERT INTO paragraphs(book_id, volume_id, para_no, seq_no, text, char_count, source_file) "
            "VALUES (?,?,?,?,?,?,?)", rows)
        conn.execute("UPDATE volumes SET para_count=? WHERE id=?", (len(paras), vid))
        total_paras += len(paras)

    for bn, bid in book_ids.items():
        n = conn.execute("SELECT COUNT(*) FROM paragraphs WHERE book_id=?", (bid,)).fetchone()[0]
        conn.execute("UPDATE books SET para_count=? WHERE id=?", (n, bid))

    tok = rebuild_fts(conn)
    conn.commit()
    conn.close()
    print(f"已建库：{DB_PATH}")
    print(f"  全卷文件：{len(files)}")
    print(f"  书：{len(book_ids)}")
    print(f"  段落：{total_paras}")
    print(f"  FTS5 分词器：{tok or '不可用（将使用 LIKE 检索）'}")


def stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    nb = conn.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
    nv = conn.execute("SELECT COUNT(*) c FROM volumes").fetchone()["c"]
    np_ = conn.execute("SELECT COUNT(*) c FROM paragraphs").fetchone()["c"]
    nc = conn.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"]
    na = conn.execute("SELECT COUNT(*) c FROM annotations").fetchone()["c"]
    nb_ = conn.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"]
    print(f"书 {nb}  卷 {nv}  段 {np_}  类目 {nc}  标注 {na}  批次 {nb_}\n")
    print("各书段数：")
    for r in conn.execute("SELECT name, para_count, sort_order FROM books ORDER BY sort_order"):
        print(f"  {r['sort_order']:>2}. {r['name']:<10} {r['para_count']} 段")
    conn.close()


def _resolve_para(conn, key):
    """解析段标识 → paragraph row。
    支持格式：
      123            段落主键 id
      01-002         卷内段号（若全书唯一则直接命中，否则报歧义）
      朝野佥载:01-002   书名:段号（推荐，无歧义）
      0001           全书序号（每书各自从 1 起，歧义时需用 书名:序号）
      朝野佥载:0001     书名:全书序号
    """
    key = key.strip()
    # 1) 纯数字 → 先试主键 id，再试 seq_no
    if key.isdigit():
        row = conn.execute("SELECT * FROM paragraphs WHERE id=?", (int(key),)).fetchone()
        if row:
            return row
        rows = conn.execute("SELECT * FROM paragraphs WHERE seq_no=?", (int(key),)).fetchall()
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            names = [f"{conn.execute('SELECT name FROM books WHERE id=?',(r['book_id'],)).fetchone()[0]}:{r['para_no']}" for r in rows]
            print(f"序号 {key} 在 {len(rows)} 个书中都存在，请用「书名:序号」指定其一：{names}")
            return None
        return None
    # 2) 含分隔符 → 书名:段号 或 书名:序号
    if ":" in key:
        book_part, no_part = key.split(":", 1)
        book_part, no_part = book_part.strip(), no_part.strip()
        brow = conn.execute("SELECT id FROM books WHERE name=?", (book_part,)).fetchone()
        if not brow:
            return None
        bid = brow["id"]
        row = conn.execute("SELECT * FROM paragraphs WHERE book_id=? AND para_no=?", (bid, no_part)).fetchone()
        if row:
            return row
        if no_part.isdigit():
            row = conn.execute("SELECT * FROM paragraphs WHERE book_id=? AND seq_no=?", (bid, int(no_part))).fetchone()
            if row:
                return row
        return None
    # 3) 形如 01-002 的卷内段号
    if "-" in key:
        rows = conn.execute("SELECT * FROM paragraphs WHERE para_no=?", (key,)).fetchall()
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            names = [f"{conn.execute('SELECT name FROM books WHERE id=?',(r['book_id'],)).fetchone()[0]}:{r['para_no']}" for r in rows]
            print(f"段号 {key} 在 {len(rows)} 个书中都存在，请用「书名:段号」指定其一：{names}")
            return None
    return None


def search(kw, book=None, volume=None, limit=50, use_fts=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    where, params = [], []
    if book:
        where.append("b.name=?"); params.append(book)
    if volume:
        where.append("v.name=?"); params.append(volume)
    rows = None
    if use_fts:
        try:
            sql = ("SELECT p.id, b.name book, v.name volume, p.para_no, p.text, p.category_main "
                   "FROM paragraphs_fts f JOIN paragraphs p ON p.id=f.para_id "
                   "JOIN books b ON b.id=p.book_id JOIN volumes v ON v.id=p.volume_id "
                   "WHERE paragraphs_fts MATCH ?")
            if where:
                sql += " AND " + " AND ".join(where)
            sql += " LIMIT ?"
            rows = conn.execute(sql, [kw] + params + [limit]).fetchall()
        except sqlite3.OperationalError:
            rows = None
    if not rows:
        sql = ("SELECT p.id, b.name book, v.name volume, p.para_no, p.text, p.category_main "
               "FROM paragraphs p JOIN books b ON b.id=p.book_id JOIN volumes v ON v.id=p.volume_id "
               "WHERE p.text LIKE ?")
        if where:
            sql += " AND " + " AND ".join(where)
        sql += " ORDER BY b.sort_order, v.sort_order, p.para_no LIMIT ?"
        rows = conn.execute(sql, [f"%{kw}%"] + params + [limit]).fetchall()
    if not rows:
        print(f"未找到含「{kw}」的段落")
        return
    print(f"命中 {len(rows)} 段（关键词：{kw}）：\n")
    for r in rows:
        cat = f"  \u3010类目:{r['category_main']}\u3011" if r["category_main"] else ""
        print(f"【{r['book']}:{r['para_no']}】 ({r['volume']}){cat}")
        t = r["text"]
        i = t.find(kw)
        if 0 <= i:
            lo, hi = max(0, i - 25), min(len(t), i + len(kw) + 40)
            snippet = ("…" if lo else "") + t[lo:hi] + ("…" if hi < len(t) else "")
        else:
            snippet = t[:60] + ("…" if len(t) > 60 else "")
        print(f"  {snippet}\n")
    conn.close()


def show(key):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = _resolve_para(conn, key)
    if not row:
        print(f"找不到段号/序号：{key}"); return
    b = conn.execute("SELECT name FROM books WHERE id=?", (row["book_id"],)).fetchone()
    v = conn.execute("SELECT name FROM volumes WHERE id=?", (row["volume_id"],)).fetchone()
    print(f"【{b['name']}:{row['para_no']}】 ({v['name']})  全书序号:{row['seq_no']}  字数:{row['char_count']}  id={row['id']}")
    print(f"源文件：{row['source_file']}")
    if row["category_main"]:
        print(f"主类目：{row['category_main']}  次标签：{row['category_tags'] or ''}")
        print(f"标注人：{row['annotator'] or ''}  备注：{row['annotation_note'] or ''}")
    print("\n" + row["text"])
    conn.close()


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_or_create_category(conn, name, parent_name=None):
    parent_id = None
    if parent_name:
        prow = conn.execute("SELECT id FROM categories WHERE name=?", (parent_name,)).fetchone()
        if not prow:
            print(f"父类目「{parent_name}」不存在，已自动创建。")
            prow = conn.execute("INSERT INTO categories(name, parent_id, created_at) VALUES (?,NULL,?)",
                                (parent_name, _now())).lastrowid
            prow = conn.execute("SELECT id FROM categories WHERE name=?", (parent_name,)).fetchone()
        parent_id = prow["id"] if hasattr(prow, "keys") else prow[0]
    row = conn.execute("SELECT id FROM categories WHERE name=? AND parent_id IS ?",
                      (name, parent_id)).fetchone()
    if row:
        return row["id"] if hasattr(row, "keys") else row[0]
    cur = conn.execute("INSERT INTO categories(name, parent_id, created_at) VALUES (?,?,?)",
                      (name, parent_id, _now()))
    return cur.lastrowid


def cat_add(name, parent=None, desc=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cid = _get_or_create_category(conn, name, parent)
    if desc:
        conn.execute("UPDATE categories SET description=? WHERE id=?", (desc, cid))
    conn.commit()
    conn.close()
    print(f"类目「{name}」id={cid}")


def cat_list():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, name, parent_id, description FROM categories ORDER BY parent_id IS NULL DESC, parent_id, sort_order, id").fetchall()
    conn.close()
    if not rows:
        print("尚无类目。用 cat-add 创建。"); return
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r[2], []).append(r)
    def walk(pid, depth):
        for r in by_parent.get(pid, []):
            print("  " * depth + f"- {r[1]}  (id={r[0]})" + (f"  {r[3]}" if r[3] else ""))
            walk(r[0], depth + 1)
    walk(None, 0)


def _resolve_keys(conn, keys):
    """把一批段号/全书序号解析为 paragraph id 列表；报告未找到项。"""
    ids, missing = [], []
    for k in keys:
        row = _resolve_para(conn, k.strip())
        if row:
            ids.append(row["id"])
        else:
            missing.append(k)
    return ids, missing


def _apply_annotation(conn, pid, cid, annotator, note, batch_id):
    now = _now()
    conn.execute(
        "INSERT OR IGNORE INTO annotations(paragraph_id, category_id, annotator, note, batch_id, created_at) "
        "VALUES (?,?,?,?,?,?)", (pid, cid, annotator, note, batch_id, now))
    cname = conn.execute("SELECT name FROM categories WHERE id=?", (cid,)).fetchone()[0]
    conn.execute(
        "UPDATE paragraphs SET category_main=?, annotator=?, annotation_note=?, batch_id=?, updated_at=? "
        "WHERE id=?", (cname, annotator, note, batch_id, now, pid))


def annotate(key, category, annotator=None, note=None, batch_name=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = _resolve_para(conn, key)
    if not row:
        print(f"找不到段号/序号：{key}"); conn.close(); return
    crow = conn.execute("SELECT id FROM categories WHERE name=?", (category,)).fetchone()
    if not crow:
        print(f"类目「{category}」不存在，请先用 cat-add 创建。"); conn.close(); return
    cid = crow["id"]
    batch_id = None
    if batch_name:
        batch_id = conn.execute(
            "INSERT INTO batches(name, annotator, note, created_at) VALUES (?,?,?,?)",
            (batch_name, annotator, note, _now())).lastrowid
    _apply_annotation(conn, row["id"], cid, annotator, note, batch_id)
    if batch_id:
        conn.execute("UPDATE batches SET para_count=1 WHERE id=?", (batch_id,))
    conn.commit()
    conn.close()
    print(f"已标注：【{key}】→ 类目「{category}」" + (f"  批次={batch_name}" if batch_name else ""))


def batch_annotate(category, keys, annotator=None, note=None, name=None):
    """批量归类：把多个段号一次性归入同一类目，记为一个批次。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    crow = conn.execute("SELECT id FROM categories WHERE name=?", (category,)).fetchone()
    if not crow:
        print(f"类目「{category}」不存在，请先用 cat-add 创建。"); conn.close(); return
    cid = crow["id"]
    ids, missing = _resolve_keys(conn, keys)
    if missing:
        print(f"警告：未找到 {len(missing)} 个段号，已跳过：{missing}")
    if not ids:
        print("没有可标注的段落。"); conn.close(); return
    bname = name or f"batch-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    batch_id = conn.execute(
        "INSERT INTO batches(name, annotator, note, created_at) VALUES (?,?,?,?)",
        (bname, annotator, note, _now())).lastrowid
    for pid in ids:
        _apply_annotation(conn, pid, cid, annotator, note, batch_id)
    conn.execute("UPDATE batches SET para_count=? WHERE id=?", (len(ids), batch_id))
    conn.commit()
    conn.close()
    print(f"已批量归类 {len(ids)} 段 → 类目「{category}」  批次={bname} (id={batch_id})")


def batch_file(category, file_path, annotator=None, note=None, name=None):
    keys = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                keys.append(s)
    batch_annotate(category, keys, annotator=annotator, note=note, name=name)


def tags(key):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = _resolve_para(conn, key)
    if not row:
        print(f"找不到段号/序号：{key}"); conn.close(); return
    b = conn.execute("SELECT name FROM books WHERE id=?", (row["book_id"],)).fetchone()
    v = conn.execute("SELECT name FROM volumes WHERE id=?", (row["volume_id"],)).fetchone()
    print(f"【{b['name']}:{row['para_no']}】 ({v['name']})")
    print(f"  主类目：{row['category_main'] or '（未标）'}")
    print(f"  次标签：{row['category_tags'] or ''}")
    print(f"  标注人：{row['annotator'] or ''}  备注：{row['annotation_note'] or ''}")
    rows = conn.execute(
        "SELECT c.name, a.annotator, a.note, b.name batch, a.created_at "
        "FROM annotations a JOIN categories c ON c.id=a.category_id "
        "LEFT JOIN batches b ON b.id=a.batch_id WHERE a.paragraph_id=? "
        "ORDER BY a.created_at", (row["id"],)).fetchall()
    print(f"  历史标注 {len(rows)} 条：")
    for r in rows:
        print(f"    - {r['name']}  by={r['annotator'] or ''}  batch={r['batch'] or ''}  {r['created_at']}"
              + (f"  备注:{r['note']}" if r["note"] else ""))
    conn.close()


def export(out_path=None):
    out = out_path or (str(ROOT / "notes_export.csv"))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT b.name book, v.name volume, p.para_no, p.seq_no, p.char_count, "
        "p.text, p.category_main, p.category_tags, p.annotator, p.annotation_note "
        "FROM paragraphs p JOIN books b ON b.id=p.book_id JOIN volumes v ON v.id=p.volume_id "
        "ORDER BY b.sort_order, v.sort_order, p.para_no")
    n = 0
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["书", "卷/篇", "段号", "全书序号", "字数", "正文", "主类目", "次标签", "标注人", "备注"])
        for r in rows:
            w.writerow([r["book"], r["volume"], r["para_no"], r["seq_no"], r["char_count"],
                        r["text"], r["category_main"], r["category_tags"], r["annotator"], r["annotation_note"]])
            n += 1
    conn.close()
    print(f"已导出 {n} 段 → {out}")


def main():
    ap = argparse.ArgumentParser(description="唐五代笔记小说 检索与标注库")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build").add_argument("--keep", action="store_true", help="不重建，仅补 FTS")
    sub.add_parser("stats")
    s = sub.add_parser("search")
    s.add_argument("keyword"); s.add_argument("-b", "--book"); s.add_argument("-v", "--volume")
    s.add_argument("--limit", type=int, default=50); s.add_argument("--no-fts", action="store_true")

    sh = sub.add_parser("show"); sh.add_argument("key")

    ca = sub.add_parser("cat-add"); ca.add_argument("name")
    ca.add_argument("-p", "--parent"); ca.add_argument("--desc")

    sub.add_parser("cat-list")

    an = sub.add_parser("annotate"); an.add_argument("key")
    an.add_argument("-c", "--category", required=True)
    an.add_argument("--by"); an.add_argument("--note"); an.add_argument("--batch")

    ba = sub.add_parser("batch")
    ba.add_argument("category"); ba.add_argument("-i", "--items", required=True,
        help="逗号分隔的段号列表，如 01-001,01-002,0003")
    ba.add_argument("--by"); ba.add_argument("--note"); ba.add_argument("--name")

    bf = sub.add_parser("batch-file")
    bf.add_argument("category"); bf.add_argument("-f", "--file", required=True)
    bf.add_argument("--by"); bf.add_argument("--note"); bf.add_argument("--name")

    tg = sub.add_parser("tags"); tg.add_argument("key")

    ex = sub.add_parser("export"); ex.add_argument("out", nargs="?")

    args = ap.parse_args()

    if args.cmd == "build":
        if args.keep and DB_PATH.exists():
            conn = sqlite3.connect(DB_PATH); tok = rebuild_fts(conn); conn.commit(); conn.close()
            print(f"FTS 已刷新，分词器={tok}")
        else:
            build(force=not args.keep)
    elif args.cmd == "stats":
        stats()
    elif args.cmd == "search":
        search(args.keyword, book=args.book, volume=args.volume, limit=args.limit, use_fts=not args.no_fts)
    elif args.cmd == "show":
        show(args.key)
    elif args.cmd == "cat-add":
        cat_add(args.name, parent=args.parent, desc=args.desc)
    elif args.cmd == "cat-list":
        cat_list()
    elif args.cmd == "annotate":
        annotate(args.key, args.category, annotator=args.by, note=args.note, batch_name=args.batch)
    elif args.cmd == "batch":
        keys = [k.strip() for k in args.items.split(",") if k.strip()]
        batch_annotate(args.category, keys, annotator=args.by, note=args.note, name=args.name)
    elif args.cmd == "batch-file":
        batch_file(args.category, args.file, annotator=args.by, note=args.note, name=args.name)
    elif args.cmd == "tags":
        tags(args.key)
    elif args.cmd == "export":
        export(args.out)


if __name__ == "__main__":
    main()
