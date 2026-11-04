"""Write one Parquet file per state-year into web/data/, plus files.json for the page.

Run: uv run --extra parquet python scripts/build_web_data.py DE-2023 TX-2023
"""

import json
import re
import sys
from pathlib import Path

from nibrs_tables.download import CACHE_DIR, download_zip
from nibrs_tables.export import export
from nibrs_tables.offenses import offenses

WEB_DATA = Path(__file__).parent.parent / "web" / "data"
FILES_JSON = WEB_DATA / "files.json"


def main(names: list[str]) -> None:
    bad = [name for name in names if not re.fullmatch(r"[A-Za-z]{2}-\d{4}", name)]
    if not names or bad:
        raise SystemExit(
            f"give names like DE-2023; bad: {', '.join(bad) or 'none given'}"
        )

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    # Merge with earlier runs, so states built before stay in the page menu.
    old = json.loads(FILES_JSON.read_text()) if FILES_JSON.exists() else []
    files = {entry["file"]: entry for entry in old}

    for name in names:
        state, year = name.upper().split("-")
        path = WEB_DATA / f"{state}-{year}.parquet"
        rows = export(offenses(download_zip(state, int(year), CACHE_DIR)), path)
        files[path.name] = {
            "state": state,
            "year": int(year),
            "file": path.name,
            "rows": rows,
        }
        print(f"{path} {rows:,} rows", file=sys.stderr)

    FILES_JSON.write_text(json.dumps(list(files.values()), indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
