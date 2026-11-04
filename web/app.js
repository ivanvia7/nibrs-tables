import * as duckdb from "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.32.0/+esm";

const TABLE = "offenses";
const FILTERS = { offense: "offense_name", county: "county", agency: "agency_name" };
const SHOWN_COLUMNS = ["incident_date", "agency_name", "county", "offense_name", "location", "attempted"];

const $ = (id) => document.getElementById(id);
let db;
let conn;
let current;  // the files.json entry on screen
let queue = Promise.resolve();  // loads, filters and downloads run one at a time

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

async function rows(sql) {
  const result = await conn.query(sql);
  return result.toArray().map((row) => row.toJSON());
}

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", isError);
}

function run(task) {
  queue = queue.then(task).catch((error) => setStatus(`Error: ${error.message}`, true));
  return queue;
}

// COPY takes no parameters, so every query quotes filter values as SQL text.
const sqlText = (value) => `'${value.replaceAll("'", "''")}'`;

// One WHERE clause for every query; an empty filter means "all".
function where() {
  const conditions = Object.keys(FILTERS).filter((key) => $(key).value)
    .map((key) => `${FILTERS[key]} = ${sqlText($(key).value)}`);
  return conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
}

async function fetchOk(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response;
}

async function loadFile(entry) {
  setStatus(`Loading ${entry.state} ${entry.year}…`);
  // Whole-file fetch works on any static server; range requests need server support.
  const response = await fetchOk(`data/${entry.file}`);
  const bytes = await response.arrayBuffer();
  await db.registerFileBuffer(entry.file, new Uint8Array(bytes));
  await conn.query(`CREATE OR REPLACE TABLE ${TABLE} AS SELECT * FROM ${sqlText(entry.file)}`);
  await db.dropFile(entry.file);  // the table holds a copy; free the raw file
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
            count(*) FILTER (WHERE attempted)::INT AS attempted FROM ${TABLE} ${filter}`,
  );
  $("count").firstChild.textContent = totals.n.toLocaleString();
  $("incidents").firstChild.textContent = totals.incidents.toLocaleString();
  $("attempted").firstChild.textContent = totals.attempted.toLocaleString();
  $("download").disabled = totals.n === 0;

  const top = (column) => rows(
    `SELECT ${column} AS name, count(*)::INT AS n FROM ${TABLE} ${filter}
     GROUP BY 1 ORDER BY 2 DESC LIMIT 8`,
  );
  bars($("top-offenses"), await top(FILTERS.offense));
  bars($("top-locations"), await top("location"));
  table($("rows"), await rows(
    `SELECT * FROM ${TABLE} ${filter} ORDER BY incident_date LIMIT 50`,
  ));

  const picked = Object.keys(FILTERS).flatMap((key) => ($(key).value ? [$(key).value] : []));
  $("scope").textContent = [`${current.state} ${current.year}`, ...picked].join(" · ");
  $("results").hidden = false;
  setStatus(`${current.state} ${current.year}: ${current.rows.toLocaleString()} offenses loaded.`);
}

async function downloadCsv() {
  const name = `${current.state}-${current.year}-offenses.csv`;
  let buffer;
  try {
    await conn.query(`COPY (SELECT * FROM ${TABLE} ${where()}) TO ${sqlText(name)} (HEADER)`);
    buffer = await db.copyFileToBuffer(name);
  } finally {
    await db.dropFile(name);
  }
  // The byte-order mark makes Excel read accented names as UTF-8.
  const href = URL.createObjectURL(new Blob(["\ufeff", buffer], { type: "text/csv" }));
  Object.assign(document.createElement("a"), { href, download: name }).click();
  // Revoke later: some browsers start the download after click() returns.
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}

async function main() {
  try {
    const [response] = await Promise.all([fetchOk("data/files.json"), startDuckDB()]);
    const files = await response.json();
    for (const entry of files) {
      $("file").add(new Option(`${entry.state} ${entry.year}`, entry.file));
    }
    $("file").addEventListener("change", () => {
      const entry = files.find(({ file }) => file === $("file").value);
      run(() => loadFile(entry).catch((error) => {
        $("file").value = current.file;  // keep the menu on the state still shown
        throw error;
      }));
    });
    for (const key of Object.keys(FILTERS)) $(key).addEventListener("change", () => run(refresh));
    $("download").addEventListener("click", () => run(downloadCsv));
    await run(() => loadFile(files[0]));
  } catch (error) {
    setStatus(`Could not load data: ${error.message}`, true);
    throw error;
  }
}

main();
