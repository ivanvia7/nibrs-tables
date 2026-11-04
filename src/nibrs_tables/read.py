import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path


def read_table(zip_path: Path, table: str) -> Iterator[dict[str, str]]:
    """Yield rows of one table, like "NIBRS_OFFENSE", keyed by lower-case column names."""
    wanted = f"{table}.csv".lower()
    with zipfile.ZipFile(zip_path) as archive:
        # The folder inside the zip changes between years, so match the file name only.
        matches = [
            name for name in archive.namelist() if Path(name).name.lower() == wanted
        ]
        if not matches:
            raise ValueError(f"{zip_path.name} has no {table}.csv")

        with archive.open(matches[0]) as raw:
            # Old files hold a few broken bytes, like "offender\xbfs" in 2016 bias list.
            text = io.TextIOWrapper(
                raw, encoding="utf-8-sig", errors="replace", newline=""
            )
            reader = csv.DictReader(text)
            # 2016-2020 headers are upper case, 2023 lower case.
            reader.fieldnames = [field.lower() for field in reader.fieldnames or []]
            yield from reader
