# 唐五代笔记小说

《唐五代笔记小说大观》（上海古籍出版社）上册的整理成果：OCR 初校文本、逐书逐卷逐段切分的 Markdown、
一个带全文检索与分类标注的 SQLite 数据库，以及一个浏览器端 SQL 查询控制台。

## 规模

| 项目 | 数量 |
| --- | --- |
| 书 | 18 |
| 卷/篇 | 160 |
| 段落 | 4,204 |
| 正文字数 | 532,878 |

收录：朝野佥载、隋唐嘉话、教坊记、龙城录、唐国史补、大唐新语、玄怪录、续玄怪录、次柳氏旧闻、
博异志、纂异记、甘泽谣、酉阳杂俎、刘宾客嘉话录、因话录、大唐传载、独异志、明皇杂录。

## 目录结构

```
<书名>/
  00-前言/            题署、校点说明、目录
  01-<卷名>/
    00-<卷名>-全卷.md  整卷合并本
    001.md 002.md ...  逐段单文件，含「全书序号」等元信息
  _切分核对单.md       切分结果的人工核对清单
  <书名>-校订全本.md   全书校订本
唐五代上-初校.md        OCR 全文初校稿（切分的输入）
notes.db               SQLite 库：全文检索 + 分类标注
notes_db.py            建库、检索、标注命令行工具
sql_web.py             浏览器 SQL 控制台（Flask）
split_books.py         按总目把初校稿切分为单书文件
```

段号形如 `01-001`，即「卷序-段序」；每段另有跨全书唯一的「全书序号」。

## 数据库

`notes.db` 由 `notes_db.py` 从上述 Markdown 生成，可随时重建。核心表：

- `books` / `volumes` / `paragraphs` —— 书、卷、段三级正文
- `paragraphs_fts` —— FTS5 全文索引，使用 trigram 分词器
- `categories` / `annotations` / `batches` —— 分类体系、段↔类目多对多标注、批量标注记录

`paragraphs` 上另有 `category_main`、`annotator` 等软字段，作为单段快速标注的后门；
`annotations` 表保留完整的标注历史。

> FTS5 的 trigram 分词器只能匹配 3 字及以上的词。「则天」「开元」这类双字词请改用 `LIKE` 查询。

## 使用

```bash
pip install -r requirements.txt

python notes_db.py build            # 从 Markdown 重建 notes.db
python notes_db.py stats
python notes_db.py search 贞观中 -b 大唐新语
python notes_db.py annotate 01-003 -c 卜筮 --by lx

python sql_web.py                   # 浏览器 SQL 控制台，默认 http://127.0.0.1:8765/
```

控制台默认以只读方式打开数据库，勾选「允许写入」后才能执行 `INSERT`/`UPDATE`/`DELETE`。

## 底本与版权

底本为上海古籍出版社《唐五代笔记小说大观》。该书的校点、注释等整理成果仍在版权保护期内，
本仓库仅供个人研究与检索之用，未收录原书扫描件（见 `.gitignore`），请勿再行传播。
笔记小说原文本身属公有领域。
