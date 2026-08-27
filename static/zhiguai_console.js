"use strict";

const $ = (id) => document.getElementById(id);

// ═══════════════════════ 页签 ═══════════════════════
document.querySelectorAll(".tab").forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
    document.querySelectorAll(".page").forEach((p) =>
      p.classList.toggle("active", p.id === "page-" + t.dataset.page));
    if (t.dataset.page === "model" && !window._modelDrawn) {
      drawModel();
      window._modelDrawn = true;
    }
  };
});

// ═══════════════════════ 检索 ═══════════════════════
const FACET_DEFS = [
  ["source", "书"], ["emperor", "皇帝"], ["era", "年号"],
  ["l1", "志怪类别"], ["l3", "事类"], ["animal", "动物"], ["agroup", "部类"],
];
const facetState = {};

async function initFacets() {
  const host = $("facets");
  const res = await fetch("/api/facets");
  const data = await res.json();
  FACET_DEFS.forEach(([key, label]) => {
    const wrap = document.createElement("div");
    wrap.className = "facet";
    const sel = document.createElement("select");
    sel.dataset.key = key;
    const head = document.createElement("option");
    head.value = "";
    head.textContent = label + "：全部";
    sel.appendChild(head);
    (data[key] || []).forEach((v) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = v;
      sel.appendChild(o);
    });
    sel.onchange = () => {
      facetState[key] = sel.value;
      sel.classList.toggle("on", !!sel.value);
      doSearch();
    };
    wrap.appendChild(sel);
    host.appendChild(wrap);
  });
  const clear = document.createElement("button");
  clear.className = "facet-clear";
  clear.textContent = "清除过滤";
  clear.onclick = () => {
    Object.keys(facetState).forEach((k) => delete facetState[k]);
    host.querySelectorAll("select").forEach((s) => {
      s.value = "";
      s.classList.remove("on");
    });
    doSearch();
  };
  host.appendChild(clear);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function highlight(text, q) {
  let h = esc(text);
  if (q) {
    const qh = esc(q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    h = h.replace(new RegExp(qh, "g"), (m) => "<mark>" + m + "</mark>");
  }
  return h;
}

function tagList(allStr, primary, cls) {
  if (!allStr) return "";
  return allStr.split(";").filter(Boolean).map((t) =>
    `<span class="tag ${cls}${t === primary ? " pri" : ""}">${esc(t)}</span>`).join("");
}

function renderCards(rows, q) {
  const host = $("cards");
  if (!rows.length) {
    host.innerHTML = '<div class="empty">没有匹配的段落。</div>';
    return;
  }
  host.innerHTML = "";
  rows.forEach((r) => {
    const card = document.createElement("div");
    card.className = "card";
    const reign = r.emperor
      ? `<span class="tag reign${r.emperor !== "未系年" ? "" : ""}">${esc(r.emperor)}${r.era ? "·" + esc(r.era) : ""}</span>` : "";
    const groups = r.animal_groups
      ? r.animal_groups.split(",").map((g) =>
          `<span class="tag group">${esc(g)}</span>`).join("") : "";
    card.innerHTML =
      `<div class="card-head">
        <span class="card-title"><span class="book">${esc(r.source)}</span>
        <span class="pid">·${esc(r.paragraph_id)}</span></span>
        <span class="card-vol">${esc(r.volume)}</span>
        <span class="card-len">${r.char_count} 字</span>
      </div>
      <div class="tagrow">
        ${tagList(r.l1_all, r.l1_primary, "l1")}
        ${reign}
        ${tagList(r.l3_all, r.l3_primary, "l3")}
        ${tagList(r.animals_all, r.animal_primary, "animal")}
        ${groups}
      </div>
      <div class="card-text" title="点击展开/收起">${highlight(r.text, q)}</div>`;
    card.querySelector(".card-text").onclick = (e) =>
      e.currentTarget.classList.toggle("expanded");
    host.appendChild(card);
  });
}

async function doSearch() {
  const q = $("q").value.trim();
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  Object.entries(facetState).forEach(([k, v]) => v && params.set(k, v));
  const meta = $("meta");
  meta.textContent = "检索中…";
  try {
    const res = await fetch("/api/search?" + params.toString());
    const data = await res.json();
    const active = Object.entries(facetState)
      .filter(([, v]) => v)
      .map(([k, v]) => {
        const label = (FACET_DEFS.find(([key]) => key === k) || [])[1] || k;
        return label + "=" + v;
      });
    meta.innerHTML = `命中 <b>${data.total}</b> 段` +
      (data.total > data.returned ? `，显示前 ${data.returned} 段` : "") +
      (q ? `　关键词「${esc(q)}」` : "　（全部段落）") +
      (active.length ? `　过滤：${esc(active.join("，"))}` : "");
    renderCards(data.rows, q);
  } catch (err) {
    meta.textContent = "检索失败：" + err;
  }
}

let searchTimer = null;
$("q").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(doSearch, 250);
});
$("q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { clearTimeout(searchTimer); doSearch(); }
});
$("go").onclick = doSearch;

// ═══════════════════════ SQL 控制台 ═══════════════════════
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
        `<span class="tbl-name ${t.kind === "view" ? "view" : ""}">${t.name}</span>` +
        `<span class="tbl-rows">${rows}</span>`;
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
  if (e.key === "Tab") { e.preventDefault(); insertAtCursor("  "); }
});
document.querySelectorAll(".sample").forEach((b) => {
  b.onclick = () => { sqlBox.value = b.dataset.sql; sqlBox.focus(); runQuery(); };
});
$("writable").addEventListener("change", (e) => {
  setStatus(e.target.checked
    ? "已开启写入模式，UPDATE / INSERT / DELETE 将直接修改 zhiguai.db，请谨慎操作。"
    : "已切回只读模式。", e.target.checked ? "err" : "ok");
});
sqlBox.value = localStorage.getItem("zgLastSql") ||
  "SELECT * FROM v_paragraph_full LIMIT 5;";
setInterval(() => localStorage.setItem("zgLastSql", sqlBox.value), 2000);

// ═══════════════════════ 模型页 ═══════════════════════
function cssVar(n) {
  return getComputedStyle(document.documentElement).getPropertyValue(n).trim();
}

function drawBars(hostId, rows, fillCls) {
  const host = $(hostId);
  if (!host || !rows || !rows.length) return;
  const max = Math.max(...rows.map((r) => r.n));
  host.innerHTML = "";
  rows.forEach((r) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML =
      `<span class="bl" title="${esc(r.name)}">${esc(r.name)}</span>` +
      `<span class="track"><span class="fill ${fillCls || ""}" ` +
      `style="width:${Math.max(1.5, (r.n / max) * 100)}%"></span></span>` +
      `<span class="bv">${r.n}</span>`;
    host.appendChild(row);
  });
}

function erBox(x, y, w, h, label, sub, accent) {
  const fill = accent ? cssVar("--panel3") : cssVar("--panel2");
  const stroke = accent ? cssVar("--accent") : cssVar("--line2");
  const fg = cssVar("--fg"), dim = cssVar("--dim2");
  return (
    `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="5" fill="${fill}" stroke="${stroke}" stroke-width="${accent ? 1.6 : 1}"/>` +
    `<text x="${x + w / 2}" y="${sub ? y + h / 2 - 5 : y + h / 2 + 4}" text-anchor="middle" fill="${fg}" font-size="12">${label}</text>` +
    (sub ? `<text x="${x + w / 2}" y="${y + h / 2 + 11}" text-anchor="middle" fill="${dim}" font-size="10">${sub}</text>` : "")
  );
}

function erEdge(x1, y1, x2, y2, label) {
  const line = cssVar("--line2"), dim = cssVar("--dim2");
  let s = `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${line}" stroke-width="1"/>`;
  if (label) {
    s += `<text x="${(x1 + x2) / 2 + 6}" y="${(y1 + y2) / 2 - 4}" fill="${dim}" font-size="10">${label}</text>`;
  }
  return s;
}

function drawEr() {
  const dim = cssVar("--dim2");
  const P = [];
  P.push(`<text x="16" y="22" fill="${dim}" font-size="11">书目核心</text>`);
  P.push(erBox(16, 36, 120, 44, "books", "17 部"));
  P.push(erEdge(136, 58, 168, 58, "1:N"));
  P.push(erBox(168, 36, 130, 44, "volumes", "84 卷/篇"));
  P.push(erEdge(298, 58, 330, 58, "1:N"));
  P.push(erBox(330, 32, 170, 52, "paragraphs", "359 · UNIQUE(书,段号)", true));

  P.push(`<text x="16" y="118" fill="${dim}" font-size="11">分面连接表 · rank=1 为 Markdown 树的主标签</text>`);
  P.push(erBox(16, 136, 168, 44, "paragraph_supernatural", "L1 · 488 链"));
  P.push(erBox(200, 136, 150, 44, "paragraph_reign", "L2 · 359 行"));
  P.push(erBox(366, 136, 150, 44, "paragraph_domain", "L3 · 620 链"));
  P.push(erBox(532, 136, 150, 44, "paragraph_animal", "L4 · 610 链"));
  P.push(erBox(698, 136, 150, 44, "paragraph_terms", "未来维度"));

  const spine = cssVar("--line2");
  P.push(`<line x1="415" y1="84" x2="415" y2="100" stroke="${spine}"/>`);
  P.push(`<line x1="100" y1="100" x2="773" y2="100" stroke="${spine}"/>`);
  [100, 275, 441, 607, 773].forEach((x) =>
    P.push(`<line x1="${x}" y1="100" x2="${x}" y2="136" stroke="${spine}"/>`));

  P.push(`<text x="16" y="212" fill="${dim}" font-size="11">受控词表</text>`);
  P.push(erBox(16, 228, 168, 44, "supernatural_types", "9 个 L1"));
  P.push(erBox(200, 228, 150, 44, "emperors", "22 + 未系年"));
  P.push(erBox(366, 228, 150, 44, "domains", "11 个 L3"));
  P.push(erBox(532, 228, 150, 44, "animals", "50 正名"));
  P.push(erBox(698, 228, 150, 44, "terms", "层级词表"));
  [100, 275, 441, 607, 773].forEach((x) => P.push(erEdge(x, 180, x, 228)));

  P.push(erBox(200, 300, 150, 44, "eras", "76 · 唐年号.xls"));
  P.push(erEdge(275, 272, 275, 300, "1:N"));
  P.push(erBox(454, 300, 130, 44, "animal_groups", "瑞兽…昆虫"));
  P.push(erBox(598, 300, 130, 44, "animal_aliases", "凤凰 / 犬 / 豕"));
  P.push(erBox(742, 300, 106, 44, "animal_roles", "可回填"));
  P.push(erEdge(580, 272, 519, 300));
  P.push(erEdge(607, 272, 663, 300));
  P.push(erEdge(640, 180, 795, 300));

  P.push(erBox(698, 364, 150, 40, "vocabularies", "place/person/motif"));
  P.push(erEdge(773, 272, 773, 364));

  P.push(`<text x="16" y="408" fill="${dim}" font-size="10">检索视图 v_paragraph_full：段落全部细节摊平为一行 · 源：志怪动物分类-汇总.csv · 359 段</text>`);

  $("er").innerHTML =
    `<svg class="er-svg" width="100%" viewBox="0 0 920 420" role="img" ` +
    `aria-label="志怪动物分类数据库实体关系图">${P.join("")}</svg>`;
}

function drawModel() {
  const S = window.STATS || {};
  const sg = $("stat-grid");
  sg.innerHTML = "";
  [
    [S.paragraphs, "段落", ""],
    [S.books, "书", ""],
    [S.volumes, "卷 / 篇", ""],
    [S.animal_links, "动物链接", ""],
    [S.animals_used, "出现动物", ""],
    [S.no_era, "无年号段落", "warn"],
  ].forEach(([v, l, cls]) => {
    const d = document.createElement("div");
    d.className = "stat";
    d.innerHTML = `<div class="v ${cls}">${v ?? "—"}</div><div class="l">${l}</div>`;
    sg.appendChild(d);
  });
  drawEr();
  drawBars("chart-books", S.per_book, "");
  drawBars("chart-animals", S.primary_animals, "warn");
  drawBars("chart-l1", S.l1_primary, "a2");
  drawBars("chart-eras", S.eras_top, "ok");
  drawBars("chart-groups", S.animal_groups, "rose");
  drawBars("chart-multi", S.multi_animal, "");
}

// ═══════════════════════ 启动 ═══════════════════════
initFacets().then(doSearch);
loadSchema();
