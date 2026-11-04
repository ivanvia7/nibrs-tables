import csv
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from dataclasses import astuple, fields
from pathlib import Path

from nibrs_tables.schema import Offense

COLUMNS = [field.name for field in fields(Offense)]
TYPES = {"year": "INTEGER", "attempted": "BOOLEAN"}  # every other column is text


def to_csv(rows: Iterator[Offense], path: Path) -> int:
    count = 0

    # utf-8-sig adds the byte-order mark Excel needs to read UTF-8.
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow(astuple(row))
            count += 1
    return count


def to_jsonl(rows: Iterator[Offense], path: Path) -> int:
    count = 0

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            record = dict(zip(COLUMNS, astuple(row), strict=True))
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def to_sqlite(rows: Iterator[Offense], path: Path) -> int:
    columns = ", ".join(f"{column} {TYPES.get(column, 'TEXT')}" for column in COLUMNS)
    marks = ", ".join("?" for _ in COLUMNS)
    path.unlink(missing_ok=True)
    out = sqlite3.connect(path)

    with out:
        out.execute(f"CREATE TABLE offenses ({columns})")
        count = out.executemany(
            f"INSERT INTO offenses VALUES ({marks})", (astuple(row) for row in rows)
        ).rowcount
    out.close()
    return count


def to_parquet(rows: Iterator[Offense], path: Path) -> int:
    import duckdb  # only needed here; plain installs skip it

    columns = {column: TYPES.get(column, "VARCHAR") for column in COLUMNS}
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "rows.jsonl"
        count = to_jsonl(rows, staged)
        duckdb.sql(
            f"COPY (SELECT * FROM read_json({sql_text(staged)}, columns={columns}))"
            f" TO {sql_text(path)} (FORMAT parquet, COMPRESSION zstd)"
        )
    return count


def sql_text(path: Path) -> str:
    """Quote a path for duckdb SQL, which takes no parameters in COPY."""
    return "'" + str(path).replace("'", "''") + "'"


WRITERS = {".csv": to_csv, ".jsonl": to_jsonl, ".db": to_sqlite, ".parquet": to_parquet}


def export(rows: Iterator[Offense], path: Path) -> int:
    writer = WRITERS.get(path.suffix)
    if writer is None:
        raise ValueError(f"--out must end with one of {', '.join(WRITERS)}")
    return writer(rows, path)
