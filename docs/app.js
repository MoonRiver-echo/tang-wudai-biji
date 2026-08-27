"use strict";

const $ = (id) => document.getElementById(id);
const SQL_JS_BASE = "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.13.0/";
const SEARCH_COLUMNS = [
  "text", "source", "volume", "paragraph_id", "l1_all", "l3_all",
  "emperor", "era", "animals_all", "animal_aliases", "animal_groups",
];
const FACETS = [
  ["source", "书", "SELECT name FROM books ORDER BY sort_order"],
  ["emperor", "皇帝", `SELECT e.name FROM emperors e
    WHERE EXISTS (SELECT 1 FROM paragraph_reign pr WHERE pr.emperor_id=e.id)
    ORDER BY e.sort_order`],
  ["era", "年号", `SELECT DISTINCT er.name FROM eras er
    WHERE EXISTS (SELECT 1 FROM paragraph_reign pr WHERE pr.era_id=er.id)
    ORDER BY er.sort_order`],
  ["l1", "志怪类别", "SELECT name FROM supernatural_types ORDER BY sort_order"],
  ["l3", "事类", "SELECT name FROM domains ORDER BY sort_order"],
  ["animal", "动物", `SELECT a.name FROM animals a
    WHERE EXISTS (SELECT 1 FROM paragraph_animal pa WHERE pa.animal_id=a.id)
    ORDER BY a.sort_order`],
  ["agroup", "部类", "SELECT name FROM animal_groups ORDER BY sort_order"],
];

let database = null;
let searchTimer = null;
let lastSqlResult = null;
const facetState = {};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
  })[character]);
}

function highlight(value, term) {
  let html = escapeHtml(value);
  if (term) {
    const pattern = escapeHtml(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    html = html.replace(new RegExp(pattern, "gi"), (match) => `<mark>${match}</mark>`);
  }
  return html;
}

function query(sql, parameters = []) {
  const statement = database.prepare(sql);
  try {
    if (parameters.length) statement.bind(parameters);
    const columns = statement.getColumnNames();
    const rows = [];
    while (statement.step()) rows.push(statement.get());
    return { columns, rows };
  } finally {
    statement.free();
  }
}

function queryObjects(sql, parameters = []) {
  const result = query(sql, parameters);
  return result.rows.map((row) =>
    Object.fromEntries(result.columns.map((column, index) => [column, row[index]])));
}

function scalar(sql, parameters = []) {
  const result = query(sql, parameters);
  return result.rows.length ? result.rows[0][0] : null;
}

function setLoadingState(ready, message, kind = "") {
  const status = $("db-status");
  status.textContent = message;
  status.className = `status ${kind}`.trim();
  ["query", "search-button", "sql", "run-sql", "export-csv"].forEach((id) => {
    $(id).disabled = !ready;
  });
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) =>
      item.classList.toggle("active", item === tab));
    document.querySelectorAll(".page").forEach((page) =>
      page.classList.toggle("active", page.id === `page-${tab.dataset.page}`));
  });
});

function addFacet(key, label, values) {
  const select = document.createElement("select");
  select.dataset.key = key;
  select.disabled = !database;
  const all = document.createElement("option");
  all.value = "";
  all.textContent = `${label}：全部`;
  select.appendChild(all);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  select.addEventListener("change", () => {
    facetState[key] = select.value;
    runSearch();
  });
  $("facets").appendChild(select);
}

function initializeFacets() {
  $("facets").innerHTML = "";
  FACETS.forEach(([key, label, sql]) => {
    addFacet(key, label, query(sql).rows.map((row) => row[0]));
  });
  const clear = document.createElement("button");
  clear.className = "ghost";
  clear.textContent = "清除过滤";
  clear.addEventListener("click", () => {
    Object.keys(facetState).forEach((key) => delete facetState[key]);
    $("facets").querySelectorAll("select").forEach((select) => { select.value = ""; });
    runSearch();
  });
  $("facets").appendChild(clear);
}

function facetClause(key) {
  const clauses = {
    source: "v.source = ?",
    emperor: "v.emperor = ?",
    era: "v.era = ?",
    l1: `EXISTS (SELECT 1 FROM paragraph_supernatural ps
      JOIN supernatural_types st ON st.id=ps.type_id
      WHERE ps.paragraph_id=v.pk AND st.name=?)`,
    l3: `EXISTS (SELECT 1 FROM paragraph_domain pd
      JOIN domains d ON d.id=pd.domain_id
      WHERE pd.paragraph_id=v.pk AND d.name=?)`,
    animal: `EXISTS (SELECT 1 FROM paragraph_animal pa
      JOIN animals a ON a.id=pa.animal_id
      WHERE pa.paragraph_id=v.pk AND a.name=?)`,
    agroup: `EXISTS (SELECT 1 FROM paragraph_animal pa
      JOIN animals a ON a.id=pa.animal_id
      JOIN animal_groups g ON g.id=a.group_id
      WHERE pa.paragraph_id=v.pk AND g.name=?)`,
  };
  return clauses[key];
}

function splitTags(value) {
  return String(value || "").split(/[;,]/).map((tag) => tag.trim()).filter(Boolean);
}

function renderCards(rows, term) {
  const host = $("cards");
  if (!rows.length) {
    host.innerHTML = '<div class="empty">没有匹配的段落。</div>';
    return;
  }
  host.innerHTML = "";
  rows.forEach((row) => {
    const card = document.createElement("article");
    card.className = "card";
    const regularTags = [
      ...splitTags(row.l1_all),
      row.emperor && row.era ? `${row.emperor}·${row.era}` : row.emperor,
      ...splitTags(row.l3_all),
    ].filter(Boolean);
    const animalTags = [
      ...splitTags(row.animals_all),
      ...splitTags(row.animal_groups),
    ];
    card.innerHTML = `
      <div class="card-head">
        <span class="book">${escapeHtml(row.source)}</span>
        <span class="para">· ${escapeHtml(row.paragraph_id)}</span>
        <span class="volume">${escapeHtml(row.volume)}</span>
        <span class="length">${Number(row.char_count).toLocaleString()} 字</span>
      </div>
      <div class="tags">
        ${regularTags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}
        ${animalTags.map((tag) => `<span class="tag animal">${escapeHtml(tag)}</span>`).join("")}
      </div>
      <div class="text" title="点击展开或收起">${highlight(row.text, term)}</div>`;
    card.querySelector(".text").addEventListener("click", (event) =>
      event.currentTarget.classList.toggle("expanded"));
    host.appendChild(card);
  });
}

function runSearch() {
  if (!database) return;
  const term = $("query").value.trim();
  const where = [];
  const parameters = [];
  if (term) {
    where.push(`(${SEARCH_COLUMNS.map((column) => `v.${column} LIKE ?`).join(" OR ")})`);
    SEARCH_COLUMNS.forEach(() => parameters.push(`%${term}%`));
  }
  Object.entries(facetState).forEach(([key, value]) => {
    if (value) {
      where.push(facetClause(key));
      parameters.push(value);
    }
  });
  const suffix = where.length ? ` WHERE ${where.join(" AND ")}` : "";
  const total = scalar(`SELECT COUNT(*) FROM v_paragraph_full v${suffix}`, parameters);
  const rows = queryObjects(`SELECT v.pk, v.source, v.volume, v.paragraph_id,
      v.char_count, v.l1_all, v.emperor, v.era, v.l3_all, v.animals_all,
      v.animal_groups, v.text
    FROM v_paragraph_full v${suffix}
    ORDER BY (SELECT sort_order FROM books WHERE name=v.source),
      v.volume, v.paragraph_id
    LIMIT 200`, parameters);
  $("search-meta").innerHTML = `命中 <b>${Number(total).toLocaleString()}</b> 段` +
    (total > rows.length ? `，显示前 ${rows.length} 段` : "");
  renderCards(rows, term);
}

$("query").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 220);
});
$("query").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    clearTimeout(searchTimer);
    runSearch();
  }
});
$("search-button").addEventListener("click", runSearch);

function renderSqlResult(result) {
  const host = $("sql-result");
  if (!result.columns.length) {
    host.innerHTML = '<div class="empty">语句执行成功，但没有结果集。</div>';
    return;
  }
  if (!result.rows.length) {
    host.innerHTML = '<div class="empty">查询成功，没有匹配的数据。</div>';
    return;
  }
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  result.columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column;
    headRow.appendChild(cell);
  });
  head.appendChild(headRow);
  table.appendChild(head);
  const body = document.createElement("tbody");
  result.rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value === null ? "NULL" : String(value);
      tr.appendChild(cell);
    });
    body.appendChild(tr);
  });
  table.appendChild(body);
  host.innerHTML = "";
  host.appendChild(table);
}

function runSql() {
  if (!database) return;
  const sql = $("sql").value.trim();
  if (!sql) return;
  const status = $("sql-status");
  const started = performance.now();
  try {
    lastSqlResult = query(sql);
    renderSqlResult(lastSqlResult);
    status.textContent = `返回 ${lastSqlResult.rows.length.toLocaleString()} 行，${Math.round(performance.now() - started)} ms`;
    status.style.color = "var(--ok)";
  } catch (error) {
    lastSqlResult = null;
    status.textContent = `错误：${error.message || error}`;
    status.style.color = "var(--error)";
  }
}

$("run-sql").addEventListener("click", runSql);
$("sql").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    runSql();
  }
});

function csvCell(value) {
  if (value === null) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

$("export-csv").addEventListener("click", () => {
  if (!lastSqlResult) {
    $("sql-status").textContent = "请先执行查询。";
    return;
  }
  const lines = [
    lastSqlResult.columns.map(csvCell).join(","),
    ...lastSqlResult.rows.map((row) => row.map(csvCell).join(",")),
  ];
  const blob = new Blob(["\ufeff", lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "zhiguai-query.csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
});

async function start() {
  try {
    const [SQL, response] = await Promise.all([
      initSqlJs({ locateFile: (file) => `${SQL_JS_BASE}${file}` }),
      fetch("./zhiguai.db"),
    ]);
    if (!response.ok) throw new Error(`数据库下载失败（HTTP ${response.status}）`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    database = new SQL.Database(bytes);
    database.run("PRAGMA query_only = ON");
    initializeFacets();
    const paragraphs = scalar("SELECT COUNT(*) FROM paragraphs");
    const books = scalar("SELECT COUNT(*) FROM books");
    const animals = scalar("SELECT COUNT(DISTINCT animal_id) FROM paragraph_animal");
    $("db-summary").textContent =
      `当前收录 ${paragraphs.toLocaleString()} 个段落、${books.toLocaleString()} 部书、` +
      `${animals.toLocaleString()} 种已出现动物。`;
    setLoadingState(
      true,
      `已加载 zhiguai.db · ${(bytes.byteLength / 1024 / 1024).toFixed(2)} MB · 只读`,
      "ok",
    );
    $("sql-status").textContent = "就绪；Ctrl+Enter 执行";
    runSearch();
  } catch (error) {
    console.error(error);
    setLoadingState(false, `加载失败：${error.message || error}`, "error");
    $("cards").innerHTML =
      '<div class="empty">无法打开在线数据库，请刷新页面或使用上方链接下载数据库。</div>';
  }
}

start();
