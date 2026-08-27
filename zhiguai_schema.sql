-- 志怪动物分类 · SQLite schema
-- Source: 志怪动物分类-汇总.csv / .json / .md  (359 rows, 17 books)
--
-- The CSV is a denormalized *faceted* record, not a tree.
-- Markdown nests L1→L2→L3→L4 using only the *primary* tag at each
-- facet; semicolon-separated fields hold the remaining tags.
-- This schema stores every tag, keeps rank=1 as the primary, and
-- leaves room for later vocabularies (places, persons, motifs, roles).

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------------
-- 0. Provenance
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS import_batches (
    id          INTEGER PRIMARY KEY,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    row_count   INTEGER NOT NULL,
    note        TEXT
);

-- ---------------------------------------------------------------------------
-- 1. Bibliographic core  (join key to notes.db: books.name + paragraphs.para_no)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS volumes (
    id          INTEGER PRIMARY KEY,
    book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,          -- e.g. 01-朝野佥载卷一 / 01-敬元颖
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (book_id, name)
);

CREATE TABLE IF NOT EXISTS paragraphs (
    id          INTEGER PRIMARY KEY,
    book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    volume_id   INTEGER NOT NULL REFERENCES volumes(id) ON DELETE CASCADE,
    para_no     TEXT NOT NULL,          -- e.g. 01-002  (unique only within a book)
    text        TEXT NOT NULL,
    char_count  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (book_id, para_no)
);

CREATE INDEX IF NOT EXISTS idx_para_volume ON paragraphs(volume_id);
CREATE INDEX IF NOT EXISTS idx_para_book   ON paragraphs(book_id);

-- ---------------------------------------------------------------------------
-- 2. Reign bibliography  (seed from 唐年号.xls; 未系年 is a placeholder emperor)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS emperors (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,   -- 玄宗李隆基
    temple_name    TEXT,                   -- 玄宗
    personal_name  TEXT,                   -- 李隆基
    sort_order     INTEGER NOT NULL DEFAULT 0,
    is_placeholder INTEGER NOT NULL DEFAULT 0 CHECK (is_placeholder IN (0, 1))
);

CREATE TABLE IF NOT EXISTS eras (
    id          INTEGER PRIMARY KEY,
    emperor_id  INTEGER NOT NULL REFERENCES emperors(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,             -- 开元
    start_year  INTEGER,
    end_year    INTEGER,
    duration    TEXT,
    ganzhi      TEXT,
    note        TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (emperor_id, name)
);

CREATE INDEX IF NOT EXISTS idx_era_name ON eras(name);

-- Currently 1 row per paragraph; rank lets a later pass attach extra reigns.
CREATE TABLE IF NOT EXISTS paragraph_reign (
    paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
    emperor_id   INTEGER NOT NULL REFERENCES emperors(id),
    era_id       INTEGER REFERENCES eras(id),
    rank         INTEGER NOT NULL DEFAULT 1 CHECK (rank >= 1),
    PRIMARY KEY (paragraph_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_reign_emp ON paragraph_reign(emperor_id);
CREATE INDEX IF NOT EXISTS idx_reign_era ON paragraph_reign(era_id);

-- ---------------------------------------------------------------------------
-- 3. Facet vocabularies  (L1 志怪类别, L3 事类)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS supernatural_types (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS domains (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    is_placeholder INTEGER NOT NULL DEFAULT 0 CHECK (is_placeholder IN (0, 1))
);

CREATE TABLE IF NOT EXISTS paragraph_supernatural (
    paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
    type_id      INTEGER NOT NULL REFERENCES supernatural_types(id),
    rank         INTEGER NOT NULL DEFAULT 1 CHECK (rank >= 1),
    PRIMARY KEY (paragraph_id, type_id),
    UNIQUE (paragraph_id, rank)
);

CREATE TABLE IF NOT EXISTS paragraph_domain (
    paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
    domain_id    INTEGER NOT NULL REFERENCES domains(id),
    rank         INTEGER NOT NULL DEFAULT 1 CHECK (rank >= 1),
    PRIMARY KEY (paragraph_id, domain_id),
    UNIQUE (paragraph_id, rank)
);

-- ---------------------------------------------------------------------------
-- 4. Animals  (L4)  — canonical name + aliases + optional traditional group
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS animal_groups (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,      -- 瑞兽 / 走兽 / 飞禽 / 鳞介 / 昆虫
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS animals (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,      -- canonical, e.g. 龙
    group_id    INTEGER REFERENCES animal_groups(id),
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS animal_aliases (
    animal_id      INTEGER NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
    alias          TEXT NOT NULL,          -- 凤凰 / 麒麟 / 犬
    match_pattern  TEXT,                   -- regex used by classify_animals.py
    PRIMARY KEY (animal_id, alias)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alias_unique ON animal_aliases(alias);

-- role: many CSV hits are titles/names (凤阁, 司马, 马知己), not creatures.
-- Leave NULL until a later disambiguation pass.
CREATE TABLE IF NOT EXISTS animal_roles (
    id   INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,             -- actual / omen / metaphor / title / person / unspecified
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paragraph_animal (
    paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
    animal_id    INTEGER NOT NULL REFERENCES animals(id),
    rank         INTEGER NOT NULL DEFAULT 1 CHECK (rank >= 1),
    role_id      INTEGER REFERENCES animal_roles(id),
    PRIMARY KEY (paragraph_id, animal_id),
    UNIQUE (paragraph_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_para_animal_animal ON paragraph_animal(animal_id);

-- ---------------------------------------------------------------------------
-- 5. Generic vocabularies  — future facets (place, person, motif, object…)
--    Do not migrate L1–L4 here; typed tables stay query-friendly.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vocabularies (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,      -- place / person / motif
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS terms (
    id             INTEGER PRIMARY KEY,
    vocabulary_id  INTEGER NOT NULL REFERENCES vocabularies(id) ON DELETE CASCADE,
    parent_id      INTEGER REFERENCES terms(id) ON DELETE SET NULL,
    name           TEXT NOT NULL,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (vocabulary_id, parent_id, name)
);

CREATE INDEX IF NOT EXISTS idx_terms_vocab ON terms(vocabulary_id);

CREATE TABLE IF NOT EXISTS paragraph_terms (
    paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
    term_id      INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    rank         INTEGER NOT NULL DEFAULT 1 CHECK (rank >= 1),
    note         TEXT,
    PRIMARY KEY (paragraph_id, term_id)
);

-- ---------------------------------------------------------------------------
-- 6. Views  — reconstruct CSV shape / Markdown primary-tag tree
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_paragraph_csv AS
SELECT
    b.name                                              AS source,
    p.para_no                                           AS paragraph_id,
    v.name                                              AS volume,
    (SELECT group_concat(x.name, ';')
       FROM (SELECT st.name
               FROM paragraph_supernatural ps
               JOIN supernatural_types st ON st.id = ps.type_id
              WHERE ps.paragraph_id = p.id
              ORDER BY ps.rank) x)                      AS level1_supernatural,
    e.name                                              AS level2_emperor,
    er.name                                             AS level2_era,
    (SELECT group_concat(x.name, ';')
       FROM (SELECT d.name
               FROM paragraph_domain pd
               JOIN domains d ON d.id = pd.domain_id
              WHERE pd.paragraph_id = p.id
              ORDER BY pd.rank) x)                      AS level3_domain,
    a_pri.name                                          AS level4_animal,
    (SELECT group_concat(x.name, ';')
       FROM (SELECT an.name
               FROM paragraph_animal pa
               JOIN animals an ON an.id = pa.animal_id
              WHERE pa.paragraph_id = p.id
              ORDER BY pa.rank) x)                      AS level4_animals_all,
    p.text                                              AS text
FROM paragraphs p
JOIN books b     ON b.id = p.book_id
JOIN volumes v   ON v.id = p.volume_id
LEFT JOIN paragraph_reign pr
       ON pr.paragraph_id = p.id AND pr.rank = 1
LEFT JOIN emperors e ON e.id = pr.emperor_id
LEFT JOIN eras er    ON er.id = pr.era_id
LEFT JOIN paragraph_animal pa_pri
       ON pa_pri.paragraph_id = p.id AND pa_pri.rank = 1
LEFT JOIN animals a_pri ON a_pri.id = pa_pri.animal_id;

-- Primary-tag slice used by the Markdown hierarchy
-- (L1 first, L2 emperor·era, L3 first, L4 first).
CREATE VIEW IF NOT EXISTS v_hierarchy_primary AS
SELECT
    b.name AS source,
    p.para_no,
    st.name AS l1,
    e.name  AS emperor,
    er.name AS era,
    CASE
        WHEN er.name IS NULL OR er.name = '' THEN e.name
        ELSE e.name || '·' || er.name
    END AS l2,
    d.name  AS l3,
    a.name  AS l4,
    p.text
FROM paragraphs p
JOIN books b ON b.id = p.book_id
JOIN paragraph_supernatural ps ON ps.paragraph_id = p.id AND ps.rank = 1
JOIN supernatural_types st ON st.id = ps.type_id
JOIN paragraph_reign pr ON pr.paragraph_id = p.id AND pr.rank = 1
JOIN emperors e ON e.id = pr.emperor_id
LEFT JOIN eras er ON er.id = pr.era_id
JOIN paragraph_domain pd ON pd.paragraph_id = p.id AND pd.rank = 1
JOIN domains d ON d.id = pd.domain_id
JOIN paragraph_animal pa ON pa.paragraph_id = p.id AND pa.rank = 1
JOIN animals a ON a.id = pa.animal_id;
