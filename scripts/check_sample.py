"""Check offense output against the raw FBI tables with a second, separate join.

    uv run python scripts/check_sample.py DE-2005 DE-2016 DE-2023 TX-2023

Per state-year it checks two things and exits 1 on any miss:
- one row per offense: every raw NIBRS_OFFENSE row comes out exactly once;
- a seeded sample of raw rows, decoded by hand from the zip's own code tables,
  gives the same codes, names, location and attempted flag as the tool.
The join here reads the zip with plain csv on purpose, so a bug in read.py or
offenses.py cannot hide itself.
"""

import csv
import io
import random
import sys
import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from nibrs_tables.download import CACHE_DIR, NoFileError, download_zip
from nibrs_tables.offenses import offenses

SEED = 7
SAMPLE = 20


def raw_rows(zip_path: Path, table: str) -> Iterator[dict[str, str]]:
    """Stream one table with plain csv; TX holds 1.6 million offense rows."""
    with zipfile.ZipFile(zip_path) as archive:
        name = next(
            n for n in archive.namelist() if n.lower().rsplit("/", 1)[-1] == table
        )
        with archive.open(name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
            for row in csv.DictReader(text):
                yield {key.lower(): value for key, value in row.items()}


def decode(row: dict[str, str], types: dict, places: dict, key: str) -> dict[str, str]:
    """One raw offense row decoded by hand from the zip's own code tables."""
    kind = types.get(row[key], {})
    place = places.get(row["location_id"], {})
    return {
        "incident_id": row["incident_id"],
        "offense_code": kind.get("offense_code", ""),
        "offense_name": kind.get("offense_name", ""),
        "offense_category": kind.get("offense_category_name", ""),
        "crime_against": kind.get("crime_against", ""),
        "attempted": str(row["attempt_complete_flag"] == "A"),
        "location_code": place.get("location_code", ""),
        "location": place.get("location_name", ""),
    }


def check(
    zip_path: Path, sample: int = SAMPLE, seed: int = SEED
) -> tuple[int, list[str]]:
    """Raw offense count and the problems found, one line each."""
    table = "nibrs_offense.csv"
    total = sum(1 for _ in raw_rows(zip_path, table))
    chosen = set(random.Random(seed).sample(range(total), min(sample, total)))

    types_rows = list(raw_rows(zip_path, "nibrs_offense_type.csv"))
    # Before 2023 an offense names its type by offense_type_id, from 2023 by code.
    first = next(raw_rows(zip_path, table), {})
    key = "offense_type_id" if "offense_type_id" in first else "offense_code"
    types = {row[key]: row for row in types_rows}
    places = {
        row["location_id"]: row for row in raw_rows(zip_path, "nibrs_location_type.csv")
    }
    raw_ids: Counter[str] = Counter()
    picked = {}
    for index, row in enumerate(raw_rows(zip_path, table)):
        raw_ids[row["offense_id"]] += 1
        if index in chosen:
            picked[row["offense_id"]] = decode(row, types, places, key)

    seen: Counter[str] = Counter()
    problems = []
    for offense in offenses(zip_path):
        seen[offense.offense_id] += 1
        for field, value in picked.get(offense.offense_id, {}).items():
            got = str(getattr(offense, field))
            if got != value:
                problems.append(
                    f"offense {offense.offense_id} {field}: tool {got!r}, raw {value!r}"
                )

    if seen != raw_ids:
        missing = sum((raw_ids - seen).values())
        extra = sum((seen - raw_ids).values())
        problems.append(f"rows: {missing:,} raw offenses missing, {extra:,} extra")
    unchecked = picked.keys() - seen.keys()
    problems += [f"offense {oid} sampled but not in the output" for oid in unchecked]
    return total, problems


def main(names: list[str]) -> None:
    failed = False
    for name in names:
        state, year = name.upper().split("-")
        try:
            rows, problems = check(download_zip(state, int(year), CACHE_DIR))
        except NoFileError as error:
            # Older years cover fewer states; the web build skips these too.
            print(f"{name}: skipped, {error}")
            continue
        print(
            f"{name}: {rows:,} raw offenses, {min(SAMPLE, rows)} sampled, "
            f"{len(problems)} problems"
        )
        for problem in problems:
            print(f"  {problem}")
        failed = failed or bool(problems)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
