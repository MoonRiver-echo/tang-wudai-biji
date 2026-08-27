# -*- coding: utf-8 -*-
"""志怪动物分类库 zhiguai.db —— 检索 + SQL 控制台（网页界面）。

启动：
    python zhiguai_web.py            # 自动打开浏览器
    python zhiguai_web.py --port 8766 --no-browser

三个页签：
  检索  —— 关键词命中段落的全部细节（正文、书名、卷、段号、四级标签、
           动物别名），可按书/皇帝/年号/类别/事类/动物过滤；
  SQL   —— 自由 SQL 控制台（默认只读，可勾选写入），结果可导出 CSV；
  模型  —— 数据模型画布内容：ER 图、字段映射、分布统计。

段落的每个字段都可检索：v_paragraph_full 视图把书、卷、段号、正文、
L1–L4 全部标签、动物别名与部类摊平成一行；多列 FTS5(trigram) 索引
供 >=3 字关键词使用，更短的关键词自动走 LIKE。
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


# ---------------------------------------------------------------------------
# 段落检索
# ---------------------------------------------------------------------------
SEARCH_COLUMNS = [
    "text", "source", "volume", "paragraph_id",
    "l1_all", "l3_all", "emperor", "era",
    "animals_all", "animal_aliases", "animal_groups",
]

FACETS = {
    "source": ("source = ?", "书"),
    "emperor": ("emperor = ?", "皇帝"),
    "era": ("era = ?", "年号"),
    "l1": ("EXISTS (SELECT 1 FROM paragraph_supernatural ps "
           "JOIN supernatural_types st ON st.id = ps.type_id "
           "WHERE ps.paragraph_id = v.pk AND st.name = ?)", "志怪类别"),
    "l3": ("EXISTS (SELECT 1 FROM paragraph_domain pd "
           "JOIN domains d ON d.id = pd.domain_id "
           "WHERE pd.paragraph_id = v.pk AND d.name = ?)", "事类"),
    "animal": ("EXISTS (SELECT 1 FROM paragraph_animal pa "
               "JOIN animals a ON a.id = pa.animal_id "
               "WHERE pa.paragraph_id = v.pk AND a.name = ?)", "动物"),
    "agroup": ("EXISTS (SELECT 1 FROM paragraph_animal pa "
               "JOIN animals a ON a.id = pa.animal_id "
               "JOIN animal_groups g ON g.id = a.group_id "
               "WHERE pa.paragraph_id = v.pk AND g.name = ?)", "动物部类"),
}


def search_paragraphs(q, filters, limit=200):
    where, params = [], []
    if q:
        where.append("(" + " OR ".join(
            f"v.{c} LIKE ?" for c in SEARCH_COLUMNS) + ")")
        params.extend([f"%{q}%"] * len(SEARCH_COLUMNS))
    for key, (clause, _label) in FACETS.items():
        val = filters.get(key)
        if val:
            where.append(clause)
            params.append(val)
    sql = ("SELECT v.pk, v.source, v.volume, v.paragraph_id, v.char_count, "
           "v.l1_all, v.l1_primary, v.emperor, v.era, v.l3_all, v.l3_primary, "
           "v.animals_all, v.animal_primary, v.animal_groups, v.text "
           "FROM v_paragraph_full v")
    count_sql = "SELECT COUNT(*) FROM v_paragraph_full v"
    if where:
        sql += " WHERE " + " AND ".join(where)
        count_sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY (SELECT b2.sort_order FROM books b2 "
            "WHERE b2.name = v.source), v.volume, v.paragraph_id LIMIT ?")
    conn = connect(False)
    rows = [dict(r) for r in conn.execute(sql, params + [limit]).fetchall()]
    total = conn.execute(count_sql, params).fetchone()[0]
    conn.close()
    return rows, total


# ---------------------------------------------------------------------------
# 自由 SQL
# ---------------------------------------------------------------------------
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
            cols.append({"name": c["name"], "type": c["type"] or "",
                         "pk": bool(c["pk"])})
        out.append({"name": name, "kind": t["type"], "rows": n, "columns": cols})
    conn.close()
    return out


# ---------------------------------------------------------------------------
# 模型页统计
# ---------------------------------------------------------------------------
def load_stats():
    conn = connect(False)
    s = {}
    s["paragraphs"] = conn.execute("SELECT COUNT(*) FROM paragraphs").fetchone()[0]
    s["books"] = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    s["volumes"] = conn.execute("SELECT COUNT(*) FROM volumes").fetchone()[0]
    s["animal_links"] = conn.execute(
        "SELECT COUNT(*) FROM paragraph_animal").fetchone()[0]
    s["no_era"] = conn.execute(
        "SELECT COUNT(*) FROM paragraph_reign WHERE era_id IS NULL").fetchone()[0]
    s["animals_used"] = conn.execute(
        "SELECT COUNT(DISTINCT animal_id) FROM paragraph_animal").fetchone()[0]

    s["per_book"] = [dict(r) for r in conn.execute(
        "SELECT b.name, COUNT(p.id) AS n FROM books b "
        "JOIN paragraphs p ON p.book_id = b.id "
        "GROUP BY b.id ORDER BY n DESC")]
    s["primary_animals"] = [dict(r) for r in conn.execute(
        "SELECT a.name, COUNT(*) AS n FROM paragraph_animal pa "
        "JOIN animals a ON a.id = pa.animal_id WHERE pa.rank = 1 "
        "GROUP BY a.id ORDER BY n DESC LIMIT 12")]
    s["l1_primary"] = [dict(r) for r in conn.execute(
        "SELECT st.name, COUNT(*) AS n FROM paragraph_supernatural ps "
        "JOIN supernatural_types st ON st.id = ps.type_id WHERE ps.rank = 1 "
        "GROUP BY st.id ORDER BY st.sort_order")]
    s["multi_animal"] = [dict(r) for r in conn.execute(
        "SELECT CASE WHEN cnt = 1 THEN '单一动物' ELSE '多种动物' END AS name, "
        "COUNT(*) AS n FROM (SELECT paragraph_id, COUNT(*) AS cnt "
        "FROM paragraph_animal GROUP BY paragraph_id) GROUP BY cnt = 1")]
    s["animal_groups"] = [dict(r) for r in conn.execute(
        "SELECT g.name, COUNT(*) AS n FROM paragraph_animal pa "
        "JOIN animals a ON a.id = pa.animal_id "
        "JOIN animal_groups g ON g.id = a.group_id "
        "GROUP BY g.id ORDER BY g.sort_order")]
    s["eras_top"] = [dict(r) for r in conn.execute(
        "SELECT e.name || '·' || er.name AS name, COUNT(*) AS n "
        "FROM paragraph_reign pr "
        "JOIN emperors e ON e.id = pr.emperor_id "
        "JOIN eras er ON er.id = pr.era_id WHERE pr.rank = 1 "
        "GROUP BY pr.era_id ORDER BY n DESC LIMIT 10")]
    conn.close()
    return s


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
    ("全字段摊平视图（v_paragraph_full）",
     "SELECT source, paragraph_id, l1_all, emperor, era,\n"
     "       l3_all, animals_all, animal_aliases, animal_groups\n"
     "FROM v_paragraph_full\nLIMIT 30;"),
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
    ("全文检索（多列 FTS，关键词须≥3字）",
     "SELECT f.source, f.para_no, substr(f.text, 1, 60) AS 正文开头\n"
     "FROM paragraphs_fts f\n"
     "WHERE paragraphs_fts MATCH '景龙中'\nLIMIT 30;"),
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("zhiguai_console.html",
                           db_name=DB_PATH.name,
                           samples=SAMPLES,
                           stats=load_stats())


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    filters = {k: request.args.get(k, "").strip() for k in FACETS}
    filters = {k: v for k, v in filters.items() if v}
    rows, total = search_paragraphs(q, filters)
    return jsonify({"rows": rows, "total": total, "returned": len(rows)})


@app.route("/api/facets")
def api_facets():
    conn = connect(False)
    out = {}
    out["source"] = [r[0] for r in conn.execute(
        "SELECT name FROM books ORDER BY sort_order")]
    out["emperor"] = [r[0] for r in conn.execute(
        "SELECT e.name FROM emperors e "
        "WHERE EXISTS (SELECT 1 FROM paragraph_reign pr "
        "  WHERE pr.emperor_id = e.id) ORDER BY e.sort_order")]
    out["era"] = [r[0] for r in conn.execute(
        "SELECT DISTINCT er.name FROM eras er "
        "WHERE EXISTS (SELECT 1 FROM paragraph_reign pr "
        "  WHERE pr.era_id = er.id) ORDER BY er.sort_order")]
    out["l1"] = [r[0] for r in conn.execute(
        "SELECT name FROM supernatural_types ORDER BY sort_order")]
    out["l3"] = [r[0] for r in conn.execute(
        "SELECT name FROM domains ORDER BY sort_order")]
    out["animal"] = [r[0] for r in conn.execute(
        "SELECT a.name FROM animals a "
        "WHERE EXISTS (SELECT 1 FROM paragraph_animal pa "
        "  WHERE pa.animal_id = a.id) ORDER BY a.sort_order")]
    out["agroup"] = [r[0] for r in conn.execute(
        "SELECT name FROM animal_groups ORDER BY sort_order")]
    conn.close()
    return jsonify(out)


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
    return jsonify({"columns": columns, "rows": rows, "info": info,
                    "error": error})


@app.route("/api/export", methods=["POST"])
def api_export():
    sql = request.form.get("sql", "")
    writable = request.form.get("writable") == "1"
    columns, rows, _, error = run_sql(sql, writable=writable,
                                      max_rows=1_000_000)
    if error:
        return Response(error, status=400,
                        mimetype="text/plain; charset=utf-8")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    w.writerows(rows)
    data = "\ufeff" + buf.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             "attachment; filename=query_result.csv"})


def main():
    ap = argparse.ArgumentParser(description="志怪动物分类 检索与 SQL 控制台")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(
            f"找不到数据库 {DB_PATH}，请先运行：python build_zhiguai_db.py")

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"志怪动物分类控制台已启动：{url}    (Ctrl+C 停止)")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
