"""Write one small Parquet file per state-year into web/data/, plus files.json for the page.

Build some files:  uv run --extra parquet python scripts/build_web_data.py DE-2023 TX-2023
Rebuild the index from the files already in web/data/:  ... build_web_data.py
"""

import json
import re
import sys
import tempfile
from pathlib import Path

import duckdb

from nibrs_tables.download import CACHE_DIR, NoFileError, download_zip
from nibrs_tables.export import export, sql_text
from nibrs_tables.offenses import offenses

WEB_DATA = Path(__file__).parent.parent / "web" / "data"
FILES_JSON = WEB_DATA / "files.json"

# The page gets state and year from files.json and never shows offense_id, so the web
# copy drops them; numeric incident ids sorted in order compress to half the size.
# That half is what lets every year fit under the 1 GB GitHub Pages limit.
WEB_COPY = """
COPY (
    SELECT * EXCLUDE (state, year, offense_id)
        REPLACE (incident_id::BIGINT AS incident_id)
    FROM read_parquet({src})
    ORDER BY incident_id
) TO {dst} (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19, PARQUET_VERSION V2)
"""


def build(state: str, year: int) -> None:
    path = WEB_DATA / f"{state}-{year}.parquet"
    with tempfile.TemporaryDirectory() as folder:
        full = Path(folder) / path.name
        rows = export(offenses(download_zip(state, year, CACHE_DIR)), full)
        duckdb.execute(WEB_COPY.format(src=sql_text(full), dst=sql_text(path)))
    print(f"{path} {rows:,} rows", file=sys.stderr)


def write_index() -> None:
    files = []
    for path in sorted(WEB_DATA.glob("*.parquet")):
        state, year = path.stem.split("-")
        query = f"SELECT count(*) FROM read_parquet({sql_text(path)})"
        (rows,) = duckdb.execute(query).fetchone() or (0,)
        files.append(
            {"state": state, "year": int(year), "file": path.name, "rows": rows}
        )
    FILES_JSON.write_text(json.dumps(files, indent=1) + "\n")
    print(f"{FILES_JSON} {len(files)} files", file=sys.stderr)


def main(names: list[str]) -> None:
    bad = [name for name in names if not re.fullmatch(r"[A-Za-z]{2}-\d{4}", name)]
    if bad:
        raise SystemExit(f"give names like DE-2023; bad: {', '.join(bad)}")

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    for name in names:
        state, year = name.upper().split("-")
        try:
            build(state, int(year))
        except NoFileError as error:
            # Older years cover fewer states; a missing file is not a failed build.
            print(f"skipped: {error}", file=sys.stderr)
    write_index()


if __name__ == "__main__":
    main(sys.argv[1:])
