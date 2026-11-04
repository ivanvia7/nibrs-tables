import * as duckdb from "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.32.0/+esm";

const TABLE = "offenses";
const FILTERS = { offense: "offense_name", county: "county", agency: "agency_name" };
const SHOWN_COLUMNS = ["incident_date", "agency_name", "county", "offense_name", "location", "attempted"];

const $ = (id) => document.getElementById(id);
let db;
let conn;
let current;  // the files.json entry on screen

async function startDuckDB() {
  const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
  // Browsers refuse a worker script from another site, so wrap it in a same-page blob.
  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" }),
  );
  db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), new Worker(workerUrl));
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  URL.revokeObjectURL(workerUrl);
  conn = await db.connect();
}

async function rows(sql, params = []) {
  const statement = await conn.prepare(sql);
  const result = await statement.query(...params);
  await statement.close();
  return result.toArray().map((row) => row.toJSON());
}

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", isError);
}

// One WHERE clause for every query; an empty filter means "all".
function where() {
  const keys = Object.keys(FILTERS);
  const conditions = keys.map((key, index) => `($${index + 1} = '' OR ${FILTERS[key]} = $${index + 1})`);
  return { sql: `WHERE ${conditions.join(" AND ")}`, params: keys.map((key) => $(key).value) };
}

async function loadFile(entry) {
  setStatus(`Loading ${entry.state} ${entry.year}…`);
  // Whole-file fetch works on any static server; range requests need server support.
  const response = await fetch(`data/${entry.file}`);
  const bytes = await response.arrayBuffer();
  await db.registerFileBuffer(entry.file, new Uint8Array(bytes));
  await conn.query(`CREATE OR REPLACE TABLE ${TABLE} AS SELECT * FROM '${entry.file}'`);
  current = entry;

  for (const [key, column] of Object.entries(FILTERS)) {
    const values = await rows(
      `SELECT DISTINCT ${column} AS value FROM ${TABLE} WHERE ${column} <> '' ORDER BY 1`,
    );
    const select = $(key);
    select.length = 1;  // keep the "All" option
    for (const { value } of values) select.add(new Option(value, value));
  }
  await refresh();
}

function bars(element, items) {
  const top = Math.max(...items.map((item) => item.n), 1);
  element.replaceChildren(...items.flatMap(({ name, n }) => {
    const label = Object.assign(document.createElement("span"), { textContent: name, title: name });
    const bar = document.createElement("i");
    bar.style.width = `${(n / top) * 100}%`;
    const count = Object.assign(document.createElement("b"), { textContent: n.toLocaleString() });
    return [label, bar, count];
  }));
}

function table(element, records) {
  element.replaceChildren();
  const head = element.createTHead().insertRow();
  for (const column of SHOWN_COLUMNS) {
    head.append(Object.assign(document.createElement("th"), { textContent: column }));
  }
  for (const record of records) {
    const tr = element.insertRow();
    for (const column of SHOWN_COLUMNS) tr.insertCell().textContent = String(record[column]);
  }
}

async function refresh() {
  const filter = where();
  const [totals] = await rows(
    `SELECT count(*)::INT AS n, count(DISTINCT incident_id)::INT AS incidents,
            count(*) FILTER (WHERE attempted)::INT AS attempted FROM ${TABLE} ${filter.sql}`,
    filter.params,
  );
  $("count").firstChild.textContent = totals.n.toLocaleString();
  $("incidents").firstChild.textContent = totals.incidents.toLocaleString();
  $("attempted").firstChild.textContent = totals.attempted.toLocaleString();
  $("download").disabled = totals.n === 0;

  const top = (column) => rows(
    `SELECT ${column} AS name, count(*)::INT AS n FROM ${TABLE} ${filter.sql}
     GROUP BY 1 ORDER BY 2 DESC LIMIT 8`,
    filter.params,
  );
  bars($("top-offenses"), await top(FILTERS.offense));
  bars($("top-locations"), await top("location"));
  table($("rows"), await rows(
    `SELECT * FROM ${TABLE} ${filter.sql} ORDER BY incident_date LIMIT 50`, filter.params,
  ));

  const picked = Object.keys(FILTERS).flatMap((key) => ($(key).value ? [$(key).value] : []));
  $("scope").textContent = [`${current.state} ${current.year}`, ...picked].join(" · ");
  $("results").hidden = false;
  setStatus(`${current.state} ${current.year}: ${current.rows.toLocaleString()} offenses loaded.`);
}

// COPY takes no parameters, so filter values are quoted as SQL text.
const sqlText = (value) => `'${value.replaceAll("'", "''")}'`;

async function downloadCsv() {
  const keys = Object.keys(FILTERS);
  const conditions = keys.filter((key) => $(key).value)
    .map((key) => `${FILTERS[key]} = ${sqlText($(key).value)}`);
  const whereSql = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  const name = `${current.state}-${current.year}-offenses.csv`;

  await conn.query(`COPY (SELECT * FROM ${TABLE} ${whereSql}) TO '${name}' (HEADER)`);
  const buffer = await db.copyFileToBuffer(name);
  await db.dropFile(name);
  const link = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(new Blob([buffer], { type: "text/csv" })),
    download: name,
  });
  link.click();
  URL.revokeObjectURL(link.href);
}

async function fetchJson(url) {
  const response = await fetch(url);
  return response.json();
}

async function main() {
  try {
    const [files] = await Promise.all([fetchJson("data/files.json"), startDuckDB()]);
    for (const entry of files) {
      $("file").add(new Option(`${entry.state} ${entry.year}`, entry.file));
    }
    $("file").addEventListener("change", () => loadFile(files.find((entry) => entry.file === $("file").value)));
    for (const key of Object.keys(FILTERS)) $(key).addEventListener("change", refresh);
    $("download").addEventListener("click", downloadCsv);
    await loadFile(files[0]);
  } catch (error) {
    setStatus(`Could not load data: ${error.message}`, true);
    throw error;
  }
}

main();
