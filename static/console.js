"use strict";

const $ = (id) => document.getElementById(id);
const sqlBox = $("sql");
const statusEl = $("status");
const resultEl = $("result");

function setStatus(msg, kind) {
  statusEl.className = "status" + (kind ? " " + kind : "");
  statusEl.textContent = msg;
}

function insertAtCursor(text) {
  const s = sqlBox.selectionStart, e = sqlBox.selectionEnd;
  sqlBox.value = sqlBox.value.slice(0, s) + text + sqlBox.value.slice(e);
  sqlBox.selectionStart = sqlBox.selectionEnd = s + text.length;
  sqlBox.focus();
}

// ── 侧栏：表结构 ──
async function loadSchema() {
  const host = $("schema");
  try {
    const res = await fetch("/api/schema");
    const data = await res.json();
    if (data.error) { host.textContent = data.error; return; }
    host.innerHTML = "";
    data.tables.forEach((t) => {
      const box = document.createElement("div");
      box.className = "tbl";

      const head = document.createElement("div");
      head.className = "tbl-head";
      const rows = t.rows === null ? "" : t.rows.toLocaleString();
      head.innerHTML =
        '<span class="tbl-name">' + t.name + "</span>" +
        '<span class="tbl-rows">' + rows + "</span>";

      const cols = document.createElement("div");
      cols.className = "cols";
      t.columns.forEach((c) => {
        const row = document.createElement("div");
        row.className = "col";
        row.innerHTML =
          "<span>" + c.name + (c.pk ? ' <span class="pk">PK</span>' : "") + "</span>" +
          '<span class="t">' + c.type + "</span>";
        row.title = "点击插入字段名";
        row.onclick = (ev) => { ev.stopPropagation(); insertAtCursor(c.name); };
        cols.appendChild(row);
      });

      head.onclick = () => cols.classList.toggle("open");
      head.ondblclick = () => insertAtCursor(t.name);
      box.appendChild(head);
      box.appendChild(cols);
      host.appendChild(box);
    });
  } catch (err) {
    host.textContent = "表结构加载失败：" + err;
  }
}

// ── 结果渲染 ──
function renderRows(columns, rows) {
  if (!columns.length) {
    resultEl.innerHTML = '<div class="empty">该语句没有返回结果集。</div>';
    return;
  }
  if (!rows.length) {
    resultEl.innerHTML = '<div class="empty">查询成功，但没有匹配的行。</div>';
    return;
  }
  const table = document.createElement("table");

  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  const corner = document.createElement("th");
  corner.textContent = "#";
  htr.appendChild(corner);
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    htr.appendChild(th);
  });
  thead.appendChild(htr);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((r, i) => {
    const tr = document.createElement("tr");
    const no = document.createElement("td");
    no.className = "rowno";
    no.textContent = i + 1;
    tr.appendChild(no);
    r.forEach((v) => {
      const td = document.createElement("td");
      if (v === null) { td.className = "null"; td.textContent = "NULL"; }
      else if (typeof v === "number") { td.className = "num"; td.textContent = v; }
      else { td.textContent = v; }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  resultEl.innerHTML = "";
  resultEl.appendChild(table);
  resultEl.scrollTop = 0;
}

// ── 执行 ──
async function runQuery() {
  const sql = sqlBox.value.trim();
  if (!sql) { setStatus("请输入 SQL 语句。", "err"); return; }
  const btn = $("run");
  btn.disabled = true;
  setStatus("执行中…");
  const t0 = performance.now();
  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql, writable: $("writable").checked }),
    });
    const data = await res.json();
    const ms = Math.round(performance.now() - t0);
    if (data.error) {
      setStatus("错误：" + data.error, "err");
      resultEl.innerHTML = '<div class="empty">执行失败。</div>';
    } else {
      setStatus(data.info + "，耗时 " + ms + " ms。", "ok");
      renderRows(data.columns, data.rows);
    }
  } catch (err) {
    setStatus("请求失败：" + err, "err");
  } finally {
    btn.disabled = false;
  }
}

// ── 导出 CSV：用隐藏表单触发下载 ──
function exportCsv() {
  const sql = sqlBox.value.trim();
  if (!sql) { setStatus("请先输入 SQL。", "err"); return; }
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/api/export";
  form.style.display = "none";
  const add = (name, value) => {
    const i = document.createElement("input");
    i.name = name; i.value = value;
    form.appendChild(i);
  };
  add("sql", sql);
  add("writable", $("writable").checked ? "1" : "0");
  document.body.appendChild(form);
  form.submit();
  setTimeout(() => form.remove(), 1000);
  setStatus("已请求导出 CSV（完整结果，不受 2000 行限制）。", "ok");
}

// ── 事件绑定 ──
$("run").onclick = runQuery;
$("export").onclick = exportCsv;
$("clear").onclick = () => {
  sqlBox.value = "";
  resultEl.innerHTML = '<div class="empty">执行查询后，结果会显示在这里。</div>';
  setStatus("已清空。");
  sqlBox.focus();
};

sqlBox.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); runQuery(); }
  if (e.key === "Tab") {
    e.preventDefault();
    insertAtCursor("  ");
  }
});

document.querySelectorAll(".sample").forEach((b) => {
  b.onclick = () => {
    sqlBox.value = b.dataset.sql;
    sqlBox.focus();
    runQuery();
  };
});

const DB_NAME = document.body.dataset.db || "数据库";

$("writable").addEventListener("change", (e) => {
  setStatus(e.target.checked
    ? "已开启写入模式，UPDATE / INSERT / DELETE 将直接修改 " + DB_NAME + "，请谨慎操作。"
    : "已切回只读模式。", e.target.checked ? "err" : "ok");
});

// 记住上次的 SQL
sqlBox.value = localStorage.getItem("lastSql") || "SELECT b.name AS 书, COUNT(p.id) AS 段数\nFROM books b JOIN paragraphs p ON p.book_id = b.id\nGROUP BY b.id ORDER BY b.sort_order;";
setInterval(() => localStorage.setItem("lastSql", sqlBox.value), 2000);

loadSchema();
sqlBox.focus();
