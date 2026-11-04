# nibrs-tables

FBI NIBRS crime files as one flat table: one row per offense, with names in place of codes.

The FBI publishes each state and year as a zip of about 40 CSV tables. An offense row says `13B` at location `35`; the names sit in other tables. This tool joins them for you.

```
$ nibrs-tables offenses TX 2023 --out tx-2023.parquet
Downloading TX-2023.zip
tx-2023.parquet 1,643,107 rows
```

That run took 29 seconds. Top Texas offenses in 2023: Simple Assault 249,745, All Other Larceny 173,999, Vandalism 167,598.

## Install

```
pip install git+https://github.com/ivanvia7/nibrs-tables
nibrs-tables offenses DE 2023 --out de-2023.csv
```

`--out` writes `.csv`, `.jsonl`, `.db` (SQLite) or `.parquet` (needs the `parquet` extra: `pip install "nibrs-tables[parquet] @ git+https://github.com/ivanvia7/nibrs-tables"`).
`nibrs-tables download DE 2023` saves only the FBI zip. Zips are kept in `cache/` inside the folder you run from, or in `--cache-dir`, so a second run skips the download.

## One row per offense

| Column | Example |
|---|---|
| `state`, `year` | `DE`, `2023` |
| `incident_id`, `offense_id` | FBI ids |
| `incident_date`, `incident_hour` | `2023-01-01`, `2` |
| `ori`, `agency_name`, `county` | `DE0010100`, `Dover`, `KENT` |
| `offense_code`, `offense_name` | `13B`, `Simple Assault` |
| `offense_category`, `crime_against` | `Assault Offenses`, `Person` |
| `attempted` | `false` |
| `location` | `Residence/Home` |

## What it handles

- Files tested on 2016, 2020 and 2023: the folder inside the zip moves, headers change case, and offenses link by `offense_type_id` before 2023 and `offense_code` after.
- Dates: `09-AUG-16` becomes `2016-08-09`.
- Codes are read from each zip's own tables, because a location id can mean a different place in another year.
- Offenses whose agency is missing from the FBI agencies table are kept with blank agency fields (45 incidents in Texas 2023).

## Web page

`web/` is a static page that filters a Parquet file in the browser with DuckDB. Build its data and serve it locally:

```
uv run --extra parquet python scripts/build_web_data.py DE-2023 TX-2023
python3 -m http.server 8765 --directory web
```

## Source

FBI Crime Data Explorer, NIBRS state-year downloads. Not affiliated with the FBI.

## License

MIT
