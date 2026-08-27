import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  PieChart,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  useHostTheme,
} from "cursor/canvas";

const BOOKS = [
  { name: "朝野佥载", n: 88 },
  { name: "玄怪录", n: 48 },
  { name: "大唐新语", n: 41 },
  { name: "续玄怪录", n: 27 },
  { name: "独异志", n: 25 },
  { name: "唐国史补", n: 20 },
  { name: "纂异记", n: 18 },
  { name: "因话录", n: 16 },
  { name: "明皇杂录", n: 15 },
  { name: "大唐传载", n: 10 },
  { name: "隋唐嘉话", n: 10 },
  { name: "龙城录", n: 10 },
  { name: "刘宾客嘉话录", n: 9 },
  { name: "博异志", n: 9 },
  { name: "甘泽谣", n: 7 },
  { name: "教坊记", n: 4 },
  { name: "次柳氏旧闻", n: 2 },
];

const PRIMARY_ANIMALS = [
  { name: "马", n: 78 },
  { name: "龙", n: 65 },
  { name: "凤", n: 25 },
  { name: "牛", n: 25 },
  { name: "鱼", n: 14 },
  { name: "鸟", n: 14 },
  { name: "虎", n: 13 },
  { name: "麟", n: 10 },
  { name: "狗", n: 10 },
  { name: "象", n: 9 },
  { name: "龟", n: 9 },
  { name: "蛇", n: 8 },
];

const L1_PRIMARY = [
  { name: "鬼怪妖魅", n: 136 },
  { name: "神仙佛道", n: 115 },
  { name: "卜筮占相", n: 29 },
  { name: "谶谣征应", n: 27 },
  { name: "巫术厌胜", n: 21 },
  { name: "冥报报应", n: 18 },
  { name: "神梦感应", n: 6 },
  { name: "死而复生", n: 4 },
  { name: "灵异神异", n: 3 },
];

function ErBox({
  x,
  y,
  w,
  h,
  label,
  sub,
  accent,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  sub?: string;
  accent?: boolean;
}) {
  const theme = useHostTheme();
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={4}
        fill={accent ? theme.fill.tertiary : theme.bg.elevated}
        stroke={accent ? theme.accent.primary : theme.stroke.secondary}
        strokeWidth={accent ? 1.5 : 1}
      />
      <text
        x={x + w / 2}
        y={sub ? y + h / 2 - 5 : y + h / 2 + 4}
        textAnchor="middle"
        fill={theme.text.primary}
        fontSize={12}
        fontFamily="inherit"
      >
        {label}
      </text>
      {sub ? (
        <text
          x={x + w / 2}
          y={y + h / 2 + 11}
          textAnchor="middle"
          fill={theme.text.tertiary}
          fontSize={10}
          fontFamily="inherit"
        >
          {sub}
        </text>
      ) : null}
    </g>
  );
}

function ErEdge({
  x1,
  y1,
  x2,
  y2,
  label,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label?: string;
}) {
  const theme = useHostTheme();
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={theme.stroke.primary}
        strokeWidth={1}
      />
      {label ? (
        <text
          x={midX + 6}
          y={midY - 4}
          fill={theme.text.tertiary}
          fontSize={10}
          fontFamily="inherit"
        >
          {label}
        </text>
      ) : null}
    </g>
  );
}

function ErDiagram() {
  const theme = useHostTheme();
  const W = 920;
  const H = 420;
  return (
    <svg
      width="100%"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Entity-relationship diagram for the zhiguai animal classification database"
      style={{ display: "block" }}
    >
      <text x={16} y={22} fill={theme.text.tertiary} fontSize={11} fontFamily="inherit">
        bibliographic core
      </text>
      <ErBox x={16} y={36} w={120} h={44} label="books" sub="17 works" />
      <ErEdge x1={136} y1={58} x2={168} y2={58} label="1:N" />
      <ErBox x={168} y={36} w={130} h={44} label="volumes" sub="84 juan / pian" />
      <ErEdge x1={298} y1={58} x2={330} y2={58} label="1:N" />
      <ErBox
        x={330}
        y={32}
        w={160}
        h={52}
        label="paragraphs"
        sub="359 · unique (book, para_no)"
        accent
      />

      <text x={16} y={118} fill={theme.text.tertiary} fontSize={11} fontFamily="inherit">
        facet junctions · rank 1 = primary tag used by the Markdown tree
      </text>

      <ErBox x={16} y={136} w={168} h={44} label="paragraph_supernatural" sub="L1 · 488 links" />
      <ErBox x={200} y={136} w={150} h={44} label="paragraph_reign" sub="L2 · 359 rows" />
      <ErBox x={366} y={136} w={150} h={44} label="paragraph_domain" sub="L3 · 620 links" />
      <ErBox x={532} y={136} w={150} h={44} label="paragraph_animal" sub="L4 · 610 links" />
      <ErBox x={698} y={136} w={150} h={44} label="paragraph_terms" sub="future facets" />

      <line x1={410} y1={84} x2={410} y2={100} stroke={theme.stroke.primary} strokeWidth={1} />
      <line x1={100} y1={100} x2={773} y2={100} stroke={theme.stroke.primary} strokeWidth={1} />
      <line x1={100} y1={100} x2={100} y2={136} stroke={theme.stroke.primary} strokeWidth={1} />
      <line x1={275} y1={100} x2={275} y2={136} stroke={theme.stroke.primary} strokeWidth={1} />
      <line x1={441} y1={100} x2={441} y2={136} stroke={theme.stroke.primary} strokeWidth={1} />
      <line x1={607} y1={100} x2={607} y2={136} stroke={theme.stroke.primary} strokeWidth={1} />
      <line x1={773} y1={100} x2={773} y2={136} stroke={theme.stroke.primary} strokeWidth={1} />

      <text x={16} y={212} fill={theme.text.tertiary} fontSize={11} fontFamily="inherit">
        controlled vocabularies
      </text>
      <ErBox x={16} y={228} w={168} h={44} label="supernatural_types" sub="9 L1 labels" />
      <ErBox x={200} y={228} w={150} h={44} label="emperors" sub="22 + 未系年" />
      <ErBox x={366} y={228} w={150} h={44} label="domains" sub="11 L3 labels" />
      <ErBox x={532} y={228} w={150} h={44} label="animals" sub="50 canonical" />
      <ErBox x={698} y={228} w={150} h={44} label="terms" sub="hierarchical" />

      <ErEdge x1={100} y1={180} x2={100} y2={228} />
      <ErEdge x1={275} y1={180} x2={275} y2={228} />
      <ErEdge x1={441} y1={180} x2={441} y2={228} />
      <ErEdge x1={607} y1={180} x2={607} y2={228} />
      <ErEdge x1={773} y1={180} x2={773} y2={228} />

      <ErBox x={200} y={300} w={150} h={44} label="eras" sub="76 from 唐年号.xls" />
      <ErEdge x1={275} y1={272} x2={275} y2={300} label="1:N" />

      <ErBox x={454} y={300} w={130} h={44} label="animal_groups" sub="瑞兽…昆虫" />
      <ErBox x={598} y={300} w={130} h={44} label="animal_aliases" sub="凤凰 / 犬 / 豕" />
      <ErBox x={742} y={300} w={106} h={44} label="animal_roles" sub="nullable" />
      <ErEdge x1={580} y1={272} x2={519} y2={300} />
      <ErEdge x1={607} y1={272} x2={663} y2={300} />
      <ErEdge x1={640} y1={180} x2={795} y2={300} />

      <ErBox x={698} y={364} w={150} h={40} label="vocabularies" sub="place / person / motif" />
      <ErEdge x1={773} y1={272} x2={773} y2={364} />

      <text x={16} y={408} fill={theme.text.quaternary} fontSize={10} fontFamily="inherit">
        Source: 志怪动物分类-汇总.csv · 359 paragraphs · rebuilt into zhiguai.db
      </text>
    </svg>
  );
}

export default function ZhiguaiAnimalSchema() {
  return (
    <Stack gap={24}>
      <Stack gap={8}>
        <H1>志怪动物分类 · relational model</H1>
        <Text tone="secondary">
          The CSV, JSON, and Markdown are three serializations of the same 359
          paragraphs. Semicolon fields are multi-valued tags; the Markdown tree
          keeps only the first tag at each facet. The SQLite schema stores every
          tag, keeps rank 1 as the primary, and leaves typed tables plus a
          generic vocabulary for later work.
        </Text>
      </Stack>

      <Row gap={24} wrap>
        <Stat value="359" label="paragraphs" />
        <Stat value="17" label="books" />
        <Stat value="84" label="volumes / pian" />
        <Stat value="610" label="animal links" />
        <Stat value="265" label="no era (74%)" tone="warning" />
      </Row>

      <Callout tone="info" title="Faceted record, not a hierarchy">
        level1_supernatural, level2_emperor/era, level3_domain, and
        level4_animal are independent dimensions. Nesting them L1→L2→L3→L4 in
        Markdown is a browse order. Encoding that tree as parent/child rows
        would block queries such as “all 龙, any emperor” and would break when
        a new facet (place, person, motif) is added.
      </Callout>

      <H2>Entity-relationship diagram</H2>
      <Card>
        <CardHeader>zhiguai.db</CardHeader>
        <CardBody>
          <ErDiagram />
        </CardBody>
      </Card>

      <H2>CSV column → tables</H2>
      <Table
        headers={["CSV / JSON field", "Cardinality in source", "Relational mapping"]}
        columnAlign={["left", "left", "left"]}
        rows={[
          [
            "source",
            "17 distinct",
            "books.name",
          ],
          [
            "volume",
            "84 distinct; name need not contain the book title (e.g. 01-敬元颖)",
            "volumes(book_id, name)",
          ],
          [
            "paragraph_id",
            "265 distinct; 94 collide across books. Unique only as (source, paragraph_id)",
            "paragraphs.para_no with UNIQUE(book_id, para_no)",
          ],
          [
            "text",
            "359 unique; 23–15,943 characters, mean 304",
            "paragraphs.text + FTS5 trigram",
          ],
          [
            "level1_supernatural",
            "9 labels; 98 rows multi-tag (max 5); 488 links after split",
            "paragraph_supernatural.rank + supernatural_types",
          ],
          [
            "level2_emperor",
            "16 values in this extract; 210 = 未系年 (58%)",
            "paragraph_reign.emperor_id; 未系年 is a placeholder emperor",
          ],
          [
            "level2_era",
            "29 names, 265 NULL; never present without an emperor; 29 emperor–era pairs",
            "paragraph_reign.era_id → eras (seeded from 唐年号.xls, 76 rows)",
          ],
          [
            "level3_domain",
            "11 labels; 160 rows multi-tag (max 7); 620 links",
            "paragraph_domain.rank + domains; 未明 is a placeholder",
          ],
          [
            "level4_animal",
            "36 primary names; always equal to the first of level4_animals_all",
            "paragraph_animal WHERE rank = 1",
          ],
          [
            "level4_animals_all",
            "46 distinct; 127 rows multi-animal (max 18); 610 links",
            "paragraph_animal (all ranks) + animals + animal_aliases",
          ],
        ]}
        striped
        stickyHeader
      />

      <H2>Distribution in the source extract</H2>
      <Grid columns={2} gap={16}>
        <Stack gap={8}>
          <H3>Paragraphs per book</H3>
          <BarChart
            horizontal
            height={340}
            categories={BOOKS.map((b) => b.name)}
            series={[{ name: "Paragraphs", data: BOOKS.map((b) => b.n) }]}
            showValues
          />
          <Text size="small" tone="tertiary">
            Source: 志怪动物分类-汇总.csv · 359 animal-tagged supernatural paragraphs
          </Text>
        </Stack>
        <Stack gap={8}>
          <H3>Primary animal (rank 1)</H3>
          <BarChart
            horizontal
            height={340}
            categories={PRIMARY_ANIMALS.map((a) => a.name)}
            series={[{ name: "Paragraphs", data: PRIMARY_ANIMALS.map((a) => a.n) }]}
            showValues
          />
          <Text size="small" tone="tertiary">
            Top 12 of 36 primary animals · remaining 24 names share 79 paragraphs
          </Text>
        </Stack>
      </Grid>

      <Grid columns="1.2fr 1fr" gap={16}>
        <Stack gap={8}>
          <H3>Primary supernatural type (L1)</H3>
          <BarChart
            horizontal
            height={260}
            categories={L1_PRIMARY.map((x) => x.name)}
            series={[{ name: "Paragraphs", data: L1_PRIMARY.map((x) => x.n) }]}
            showValues
          />
          <Text size="small" tone="tertiary">
            Rank-1 L1 only · 98 paragraphs also carry secondary L1 tags
          </Text>
        </Stack>
        <Stack gap={8}>
          <H3>Multi-tag density</H3>
          <PieChart
            donut
            size={220}
            data={[
              { label: "Single animal", value: 232 },
              { label: "2+ animals", value: 127 },
            ]}
          />
          <Text size="small" tone="tertiary">
            Animal facet · 127 / 359 paragraphs mention more than one canonical animal
          </Text>
        </Stack>
      </Grid>

      <H2>Design rules for later extension</H2>
      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>Keep L1–L4 typed</CardHeader>
          <CardBody>
            <Text>
              Query paths such as “龙 in 开元 under 神仙佛道” need real foreign
              keys, not a generic tag bag. Typed junction tables stay. New
              unknown facets (place, person, motif) go through
              vocabularies / terms / paragraph_terms.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Rank, not a second is_primary column</CardHeader>
          <CardBody>
            <Text>
              CSV order is meaningful: the first token is the primary used by
              the Markdown tree. rank = 1 is primary; UNIQUE(paragraph_id, rank)
              preserves order without a redundant boolean.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Join key to notes.db</CardHeader>
          <CardBody>
            <Text>
              notes.db already holds the full corpus. Do not duplicate the
              whole text collection here. Join on books.name +
              paragraphs.para_no when you want search, annotation history, or
              non-animal paragraphs.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Animal role is deferred</CardHeader>
          <CardBody>
            <Text>
              Detector hits include 凤阁, 司马, 马知己. paragraph_animal.role_id
              is seeded as 未辨析. Later passes can set 实物 / 征兆 / 隐喻 /
              官署/名号 / 人名 without changing the table shape. Dictionary
              leftovers 蛙, 蝇, 蝗, 驺虞 stay in animals for the next scan.
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <H2>Tables to create later (no migration of L1–L4)</H2>
      <Table
        headers={["Table", "When", "Purpose"]}
        rows={[
          [
            "vocabularies / terms / paragraph_terms",
            "next classification pass",
            "Places, persons, motifs, objects — same rank pattern as animals",
          ],
          [
            "animal_roles (already present)",
            "disambiguation",
            "Mark false-positive detections without deleting the link",
          ],
          [
            "paragraph_reign extra ranks",
            "if a paragraph names two reigns",
            "UNIQUE is on (paragraph_id, rank), not on emperor; extra rows are allowed",
          ],
          [
            "notes.db paragraphs",
            "full-corpus work",
            "This DB is the animal-zhiguai subset; notes.db remains the text warehouse",
          ],
        ]}
        striped
      />

      <Divider />

      <H2>Queries the schema is built for</H2>
      <Table
        headers={["Question", "SQL sketch"]}
        rows={[
          [
            "All 龙, including secondary mentions",
            "JOIN paragraph_animal · animals.name = '龙'",
          ],
          [
            "Primary-tag Markdown slice",
            "SELECT * FROM v_hierarchy_primary",
          ],
          [
            "Rebuild the CSV",
            "SELECT * FROM v_paragraph_csv",
          ],
          [
            "开元-era 医疗 with any bird",
            "reign.era = 开元 ∧ domain = 医疗 ∧ animal_groups = 飞禽",
          ],
          [
            "Books that mention 狐 as primary",
            "paragraph_animal.rank = 1 AND animals.name = '狐' GROUP BY books",
          ],
        ]}
      />

      <Callout tone="neutral" title="Build">
        python build_zhiguai_db.py writes zhiguai.db from zhiguai_schema.sql and
        志怪动物分类-汇总.csv. Lookup tables are seeded from the animal
        dictionary and 唐年号.xls. Re-run replaces the file.
      </Callout>
    </Stack>
  );
}
