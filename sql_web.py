# -*- coding: utf-8 -*-
"""唐五代笔记小说 —— 浏览器 SQL 查询控制台。

启动：
    python sql_web.py            # 自动打开浏览器
    python sql_web.py --port 880 --no-browser

默认以只读方式打开 notes.db；勾选界面上的「允许写入」后才能执行
INSERT/UPDATE/DELETE（用于标注、批量归类等）。
"""
import argparse
import csv
import io
import sqlite3
import threading
import webbrowser
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "notes.db"
MAX_ROWS = 2000

app = Flask(__name__)


def connect(writable=False):
    """只读连接用 URI mode=ro，写入连接为普通连接。"""
    if writable:
        conn = sqlite3.connect(DB_PATH)
    else:
        conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def run_sql(sql, writable=False, max_rows=MAX_ROWS):
    """执行一条 SQL，返回 (columns, rows, info, error)。"""
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        return [], [], "", "请输入 SQL 语句。"
    conn = None
    try:
        conn = connect(writable)
        cur = conn.execute(sql)
        if cur.description is None:
            conn.commit()
            n = cur.rowcount
            return [], [], f"执行成功，影响 {n if n >= 0 else 0} 行。", None
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
        truncated = cur.fetchone() is not None
        data = [[r[c] for c in columns] for r in rows]
        info = f"返回 {len(data)} 行"
        if truncated:
            info += f"（已截断至前 {max_rows} 行，请加 LIMIT 缩小范围）"
        return columns, data, info, None
    except sqlite3.OperationalError as e:
        msg = str(e)
        if "readonly" in msg.lower() or "attempt to write" in msg.lower():
            msg += "  —— 该语句需要写入权限，请勾选「允许写入」后重试。"
        return [], [], "", msg
    except sqlite3.Error as e:
        return [], [], "", f"{type(e).__name__}: {e}"
    finally:
        if conn is not None:
            conn.close()


def load_schema():
    """返回表结构与行数，供侧栏展示。"""
    conn = connect(False)
    out = []
    # 隐藏 FTS5 的内部影子表（_config/_content/_data/_docsize/_idx）
    tables = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
        "AND name NOT LIKE 'sqlite_%' "
        "AND name NOT LIKE '%\\_fts\\_%' ESCAPE '\\' "
        "ORDER BY type, name").fetchall()
    for t in tables:
        name = t["name"]
        try:
            n = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        except sqlite3.Error:
            n = None
        cols = []
        for c in conn.execute(f'PRAGMA table_info("{name}")'):
            cols.append({"name": c["name"], "type": c["type"] or "", "pk": bool(c["pk"])})
        out.append({"name": name, "kind": t["type"], "rows": n, "columns": cols})
    conn.close()
    return out


SAMPLES = [
    ("全库概览",
     "SELECT b.name AS 书, COUNT(p.id) AS 段数, SUM(p.char_count) AS 总字数\n"
     "FROM books b JOIN paragraphs p ON p.book_id = b.id\n"
     "GROUP BY b.id ORDER BY b.sort_order;"),
    ("关键词检索（LIKE，任意字数，推荐）",
     "SELECT b.name AS 书, p.para_no AS 段号, p.category_main AS 类目, p.text AS 正文\n"
     "FROM paragraphs p\n"
     "JOIN books b ON b.id = p.book_id\n"
     "WHERE p.text LIKE '%则天%'\n"
     "ORDER BY b.sort_order, p.para_no\nLIMIT 50;"),
    ("全文检索（FTS trigram，关键词须≥3字）",
     "-- 注意：trigram 分词器只能匹配 3 字及以上的词，\n"
     "-- '则天'、'开元' 这类两字词请改用上面的 LIKE 查询。\n"
     "SELECT b.name AS 书, p.para_no AS 段号, p.text AS 正文\n"
     "FROM paragraphs_fts f\n"
     "JOIN paragraphs p ON p.id = f.para_id\n"
     "JOIN books b ON b.id = p.book_id\n"
     "WHERE paragraphs_fts MATCH '贞观中'\nLIMIT 50;"),
    ("按书筛选正文",
     "SELECT p.para_no AS 段号, v.name AS 卷篇, p.text AS 正文\n"
     "FROM paragraphs p\n"
     "JOIN books b ON b.id = p.book_id\n"
     "JOIN volumes v ON v.id = p.volume_id\n"
     "WHERE b.name = '朝野佥载' AND p.text LIKE '%卜%'\nLIMIT 50;"),
    ("已标注段落",
     "SELECT b.name AS 书, p.para_no AS 段号, p.category_main AS 主类目,\n"
     "       p.annotator AS 标注人, p.annotation_note AS 备注, p.text AS 正文\n"
     "FROM paragraphs p JOIN books b ON b.id = p.book_id\n"
     "WHERE p.category_main IS NOT NULL\nORDER BY p.updated_at DESC;"),
    ("各类目段数统计",
     "SELECT c.name AS 类目, COUNT(a.id) AS 段数\n"
     "FROM categories c LEFT JOIN annotations a ON a.category_id = c.id\n"
     "GROUP BY c.id ORDER BY 段数 DESC;"),
    ("标注批次明细",
     "SELECT bt.name AS 批次, bt.annotator AS 标注人, bt.para_count AS 段数,\n"
     "       bt.created_at AS 时间, bt.note AS 备注\n"
     "FROM batches bt ORDER BY bt.id DESC;"),
    ("最长的 20 段",
     "SELECT b.name AS 书, p.para_no AS 段号, p.char_count AS 字数, p.text AS 正文\n"
     "FROM paragraphs p JOIN books b ON b.id = p.book_id\n"
     "ORDER BY p.char_count DESC LIMIT 20;"),
    ("写入示例：批量归类（需勾选允许写入）",
     "UPDATE paragraphs SET category_main = '卜筮', annotator = 'lx',\n"
     "       updated_at = datetime('now','localtime')\n"
     "WHERE book_id = (SELECT id FROM books WHERE name = '朝野佥载')\n"
     "  AND para_no IN ('01-001','01-003','01-004');"),
]


@app.route("/")
def index():
    return render_template("sql_console.html",
                           db_name=DB_PATH.name,
                           samples=SAMPLES)


@app.route("/api/schema")
def api_schema():
    try:
        return jsonify({"tables": load_schema()})
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/query", methods=["POST"])
def api_query():
    payload = request.get_json(silent=True) or {}
    sql = payload.get("sql", "")
    writable = bool(payload.get("writable"))
    columns, rows, info, error = run_sql(sql, writable=writable)
    return jsonify({"columns": columns, "rows": rows, "info": info, "error": error})


@app.route("/api/export", methods=["POST"])
def api_export():
    sql = request.form.get("sql", "")
    writable = request.form.get("writable") == "1"
    columns, rows, _, error = run_sql(sql, writable=writable, max_rows=1_000_000)
    if error:
        return Response(error, status=400, mimetype="text/plain; charset=utf-8")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    w.writerows(rows)
    data = "\ufeff" + buf.getvalue()  # BOM，便于 Excel 打开
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=query_result.csv"})


def main():
    ap = argparse.ArgumentParser(description="笔记小说 SQL 查询控制台")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库 {DB_PATH}，请先运行：python notes_db.py build")

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"SQL 控制台已启动：{url}    (Ctrl+C 停止)")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
