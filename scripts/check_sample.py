"""Check offense output against the raw FBI tables with a second, separate join.

    uv run python scripts/check_sample.py DE-2005 DE-2016 DE-2023 TX-2023

Per state-year it checks two things and exits 1 on any miss:
- one row per offense: every raw NIBRS_OFFENSE row whose incident, type and
  location exist comes out exactly once (the tool skips the rest by design,
  and more than 1% of such rows fails the check);
- a seeded sample of raw rows, decoded by hand from the zip's own tables, gives
  the same ori, codes, names, location and attempted flag as the tool.
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
MAX_DANGLING = 0.01  # share of rows with a missing id before the year fails
OFFENSES = "nibrs_offense.csv"


def raw_rows(zip_path: Path, table: str) -> Iterator[dict[str, str]]:
    """Stream one table with plain csv; TX holds 1.6 million offense rows."""
    with zipfile.ZipFile(zip_path) as archive:
        name = next(
            n for n in archive.namelist() if n.lower().rsplit("/", 1)[-1] == table
        )
        with archive.open(name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
            reader = csv.DictReader(text)
            # Lower-case the header, not each row: a long row adds a None key.
            reader.fieldnames = [field.lower() for field in reader.fieldnames or []]
            yield from reader


def agency_rows(zip_path: Path) -> Iterator[dict[str, str]]:
    """agencies.csv from 2016 on, cde_agencies.csv before."""
    with zipfile.ZipFile(zip_path) as archive:
        names = {n.lower().rsplit("/", 1)[-1] for n in archive.namelist()}
    table = "agencies.csv" if "agencies.csv" in names else "cde_agencies.csv"
    yield from raw_rows(zip_path, table)


def check(zip_path: Path, sample: int = SAMPLE, seed: int = SEED) -> dict:
    """Counts and the problems found, one line each."""
    oris = {row["agency_id"]: row["ori"] for row in agency_rows(zip_path)}
    incident_agency = {
        row["incident_id"]: row["agency_id"]
        for row in raw_rows(zip_path, "nibrs_incident.csv")
    }
    first = next(raw_rows(zip_path, OFFENSES), {})
    # Before 2023 an offense names its type by offense_type_id, from 2023 by code.
    key = "offense_type_id" if "offense_type_id" in first else "offense_code"
    types = {row[key]: row for row in raw_rows(zip_path, "nibrs_offense_type.csv")}
    places = {
        row["location_id"]: row for row in raw_rows(zip_path, "nibrs_location_type.csv")
    }

    # Reservoir sample over the rows the tool keeps, so every pick gets compared.
    rng = random.Random(seed)
    raw_ids: Counter[str] = Counter()
    total = dangling = kept = 0
    reservoir: list[tuple[str, dict[str, str]]] = []
    for row in raw_rows(zip_path, OFFENSES):
        total += 1
        kind = types.get(row[key])
        place = places.get(row["location_id"])
        if row["incident_id"] not in incident_agency or kind is None or place is None:
            dangling += 1
            continue
        raw_ids[row["offense_id"]] += 1
        kept += 1
        slot = len(reservoir) if len(reservoir) < sample else rng.randrange(kept)
        if slot >= sample:
            continue
        decoded = {
            "incident_id": row["incident_id"],
            "ori": oris.get(incident_agency[row["incident_id"]], ""),
            "offense_code": kind["offense_code"],
            "offense_name": kind["offense_name"],
            "offense_category": kind["offense_category_name"],
            "crime_against": kind["crime_against"],
            "attempted": str(row["attempt_complete_flag"] == "A"),
            "location_code": place["location_code"],
            "location": place["location_name"],
        }
        if slot == len(reservoir):
            reservoir.append((row["offense_id"], decoded))
        else:
            reservoir[slot] = (row["offense_id"], decoded)
    picked = dict(reservoir)

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
    # A few dangling rows are normal FBI noise; many mean the codes changed.
    if dangling > total * MAX_DANGLING:
        problems.append(f"rows: {dangling:,} of {total:,} point to a missing id")
    unchecked = picked.keys() - seen.keys()
    problems += [f"offense {oid} sampled but not in the output" for oid in unchecked]
    return {
        "total": total,
        "dangling": dangling,
        "sampled": len(picked),
        "problems": problems,
    }


def main(names: list[str]) -> None:
    failed = False
    for name in names:
        state, year = name.upper().split("-")
        try:
            path = download_zip(state, int(year), CACHE_DIR)
        except NoFileError as error:
            # Older years cover fewer states; the web build skips these too.
            print(f"{name}: skipped, {error}")
            continue
        try:
            result = check(path)
        except NoFileError as error:
            print(f"{name}: skipped, {error}")
            continue
        except ValueError as error:
            # The tool refused the file, e.g. every offense points to a missing id;
            # report it and go on, so later state-years still get checked.
            print(f"{name}: tool failed, {error}")
            failed = True
            continue
        print(
            f"{name}: {result['total']:,} raw offenses, {result['dangling']:,} with a "
            f"missing id, {result['sampled']} sampled, {len(result['problems'])} problems"
        )
        for problem in result["problems"]:
            print(f"  {problem}")
        failed = failed or bool(result["problems"])
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
