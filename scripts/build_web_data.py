"""Write one Parquet file per state-year into web/data/, plus files.json for the page.

Run: uv run --extra parquet python scripts/build_web_data.py DE-2023 TX-2023
"""

import json
import sys
from pathlib import Path

from nibrs_tables.download import download_zip
from nibrs_tables.export import to_parquet
from nibrs_tables.offenses import offenses

WEB_DATA = Path(__file__).parent.parent / "web" / "data"
CACHE = Path("cache")


def main(names: list[str]) -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    files = []

    for name in names:
        state, year = name.upper().split("-")
        path = WEB_DATA / f"{state}-{year}.parquet"
        rows = to_parquet(offenses(download_zip(state, int(year), CACHE)), path)
        files.append(
            {"state": state, "year": int(year), "file": path.name, "rows": rows}
        )
        print(f"{path} {rows:,} rows", file=sys.stderr)

    (WEB_DATA / "files.json").write_text(json.dumps(files, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
