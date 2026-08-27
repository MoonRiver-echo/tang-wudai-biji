# -*- coding: utf-8 -*-
"""志怪动物分类库 zhiguai.db —— 浏览器 SQL 查询控制台。

启动：
    python zhiguai_web.py            # 自动打开浏览器
    python zhiguai_web.py --port 8766 --no-browser

默认以只读方式打开 zhiguai.db；勾选界面上的「允许写入」后才能执行
INSERT/UPDATE/DELETE（例如回填 paragraph_animal.role_id）。
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
DB_PATH = ROOT / "zhiguai.db"
MAX_ROWS = 2000

app = Flask(__name__)


def connect(writable=False):
    if writable:
        conn = sqlite3.connect(DB_PATH)
    else:
        conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def run_sql(sql, writable=False, max_rows=MAX_ROWS):
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
    conn = connect(False)
    out = []
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
     "SELECT b.name AS 书, COUNT(p.id) AS 段数\n"
     "FROM books b JOIN paragraphs p ON p.book_id = b.id\n"
     "GROUP BY b.id ORDER BY b.sort_order;"),
    ("主动物分布（rank=1）",
     "SELECT a.name AS 动物, COUNT(*) AS 段数\n"
     "FROM paragraph_animal pa JOIN animals a ON a.id = pa.animal_id\n"
     "WHERE pa.rank = 1\n"
     "GROUP BY a.id ORDER BY 段数 DESC;"),
    ("某动物的全部段落（含次要提及）",
     "SELECT b.name AS 书, p.para_no AS 段号, substr(p.text, 1, 60) AS 正文开头\n"
     "FROM paragraph_animal pa\n"
     "JOIN animals a   ON a.id = pa.animal_id\n"
     "JOIN paragraphs p ON p.id = pa.paragraph_id\n"
     "JOIN books b     ON b.id = p.book_id\n"
     "WHERE a.name = '龙'\n"
     "ORDER BY b.sort_order, p.para_no\nLIMIT 50;"),
    ("皇帝 × 主动物 交叉",
     "SELECT e.name AS 皇帝, a.name AS 主动物, COUNT(*) AS 段数\n"
     "FROM paragraph_reign pr\n"
     "JOIN emperors e ON e.id = pr.emperor_id AND pr.rank = 1\n"
     "JOIN paragraph_animal pa ON pa.paragraph_id = pr.paragraph_id AND pa.rank = 1\n"
     "JOIN animals a ON a.id = pa.animal_id\n"
     "GROUP BY e.id, a.id\n"
     "HAVING 段数 >= 2\n"
     "ORDER BY e.sort_order, 段数 DESC;"),
    ("年号 + 事类 + 动物 三级检索",
     "SELECT er.name AS 年号, d.name AS 事类, a.name AS 动物, COUNT(*) AS 段数\n"
     "FROM paragraph_reign pr\n"
     "JOIN eras er ON er.id = pr.era_id AND pr.rank = 1\n"
     "JOIN paragraph_domain pd ON pd.paragraph_id = pr.paragraph_id AND pd.rank = 1\n"
     "JOIN domains d ON d.id = pd.domain_id\n"
     "JOIN paragraph_animal pa ON pa.paragraph_id = pr.paragraph_id AND pa.rank = 1\n"
     "JOIN animals a ON a.id = pa.animal_id\n"
     "GROUP BY er.name, d.name, a.name\n"
     "ORDER BY er.sort_order, 段数 DESC\nLIMIT 50;"),
    ("重建原始 CSV（v_paragraph_csv 视图）",
     "SELECT source, paragraph_id, level1_supernatural, level2_emperor,\n"
     "       level2_era, level3_domain, level4_animal, level4_animals_all\n"
     "FROM v_paragraph_csv\nLIMIT 30;"),
    ("Markdown 层级切片（v_hierarchy_primary）",
     "SELECT l1, l2, l3, l4, source, para_no\n"
     "FROM v_hierarchy_primary\nLIMIT 30;"),
    ("多动物段落（一段多兽）",
     "SELECT b.name AS 书, p.para_no AS 段号, COUNT(*) AS 动物数,\n"
     "       group_concat(a.name, '、') AS 动物\n"
     "FROM paragraph_animal pa\n"
     "JOIN animals a   ON a.id = pa.animal_id\n"
     "JOIN paragraphs p ON p.id = pa.paragraph_id\n"
     "JOIN books b     ON b.id = p.book_id\n"
     "GROUP BY p.id HAVING 动物数 >= 4\n"
     "ORDER BY 动物数 DESC;"),
    ("动物别名词典",
     "SELECT a.name AS 正名, aa.alias AS 别名, aa.match_pattern AS 匹配式\n"
     "FROM animal_aliases aa JOIN animals a ON a.id = aa.animal_id\n"
     "ORDER BY a.sort_order, aa.alias;"),
    ("写入示例：标记「凤阁」为名号而非实物（需勾选允许写入）",
     "UPDATE paragraph_animal SET role_id =\n"
     "  (SELECT id FROM animal_roles WHERE code = 'title')\n"
     "WHERE animal_id = (SELECT id FROM animals WHERE name = '凤')\n"
     "  AND paragraph_id IN (\n"
     "    SELECT p.id FROM paragraphs p JOIN books b ON b.id = p.book_id\n"
     "    WHERE b.name = '朝野佥载' AND p.para_no IN ('01-003', '01-007'))\n"
     "  AND paragraph_id IN (\n"
     "    SELECT id FROM paragraphs WHERE text LIKE '%凤阁%');"),
]


@app.route("/")
def index():
    return render_template("sql_console.html",
                           title="志怪动物分类 SQL 控制台",
                           db_name=DB_PATH.name,
                           hint="本库为志怪动物分类子集（359 段）。标签用连接表存储："
                                "rank=1 为主标签；v_paragraph_csv 视图可还原原 CSV。",
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
    data = "\ufeff" + buf.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=query_result.csv"})


def main():
    ap = argparse.ArgumentParser(description="志怪动物分类 SQL 查询控制台")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库 {DB_PATH}，请先运行：python build_zhiguai_db.py")

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"SQL 控制台已启动：{url}    (Ctrl+C 停止)")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
