import csv
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing
from dataclasses import astuple, fields
from pathlib import Path

from nibrs_tables.schema import Offense, Row

TYPES = {
    "year": "INTEGER",
    "attempted": "BOOLEAN",
    "value": "BIGINT",
}  # the rest is text


def columns(row_type: type[Row]) -> list[str]:
    return [field.name for field in fields(row_type)]


def to_csv(rows: Iterator[Row], path: Path, row_type: type[Row]) -> int:
    count = 0

    # utf-8-sig adds the byte-order mark Excel needs to read UTF-8.
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(columns(row_type))
        for row in rows:
            # Lower-case true/false, as in the JSONL file and the web page CSV.
            writer.writerow(
                [str(v).lower() if isinstance(v, bool) else v for v in astuple(row)]
            )
            count += 1
    return count


def to_jsonl(rows: Iterator[Row], path: Path, row_type: type[Row]) -> int:
    names = columns(row_type)
    count = 0

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            record = dict(zip(names, astuple(row), strict=True))
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def to_sqlite(rows: Iterator[Row], path: Path, row_type: type[Row]) -> int:
    names = columns(row_type)
    declared = ", ".join(f"{name} {TYPES.get(name, 'TEXT')}" for name in names)
    marks = ", ".join("?" for _ in names)
    path.unlink(missing_ok=True)
    # closing() shuts the file on errors too; "with out" only commits or rolls back.
    with closing(sqlite3.connect(path)) as out, out:
        out.execute(f"CREATE TABLE {row_type.TABLE} ({declared})")
        return out.executemany(
            f"INSERT INTO {row_type.TABLE} VALUES ({marks})",
            (astuple(row) for row in rows),
        ).rowcount


def to_parquet(rows: Iterator[Row], path: Path, row_type: type[Row]) -> int:
    import duckdb  # only needed here; plain installs skip it

    types = {name: TYPES.get(name, "VARCHAR") for name in columns(row_type)}
    # Stage beside the output: /tmp can be too small for a big state.
    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        staged = Path(tmp) / "rows.jsonl"
        count = to_jsonl(rows, staged, row_type)
        duckdb.sql(
            f"COPY (SELECT * FROM read_json({sql_text(staged)}, columns={types}))"
            f" TO {sql_text(path)} (FORMAT parquet, COMPRESSION zstd)"
        )
    return count


def sql_text(path: Path) -> str:
    """Quote a path for duckdb SQL, which takes no parameters in COPY."""
    return "'" + str(path).replace("'", "''") + "'"


WRITERS = {".csv": to_csv, ".jsonl": to_jsonl, ".db": to_sqlite, ".parquet": to_parquet}


def check_suffix(path: Path) -> None:
    if path.suffix not in WRITERS:
        raise ValueError(f"--out must end with one of {', '.join(WRITERS)}")


def export(rows: Iterator[Row], path: Path, row_type: type[Row] = Offense) -> int:
    check_suffix(path)
    # Write beside the target, then swap, so a failed run keeps the old file.
    staged = path.with_name(f".{path.name}.part")
    try:
        count = WRITERS[path.suffix](rows, staged, row_type)
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
    return count
