import csv
import sqlite3

import pytest

from nibrs_tables.export import COLUMNS, export
from nibrs_tables.offenses import offenses


@pytest.mark.parametrize("suffix", [".csv", ".jsonl", ".db", ".parquet"])
def test_every_format_writes_every_row(zip_2023, tmp_path, suffix):
    path = tmp_path / f"out{suffix}"
    assert export(offenses(zip_2023), path) == 2
    assert path.stat().st_size > 0


def test_csv_has_header_and_excel_mark(zip_2023, tmp_path):
    path = tmp_path / "out.csv"
    export(offenses(zip_2023), path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open(encoding="utf-8-sig", newline="") as file:
        header, *rows = csv.reader(file)
    assert header == COLUMNS
    assert len(rows) == 2


def test_sqlite_keeps_numbers_and_flags(zip_2016, tmp_path):
    path = tmp_path / "out.db"
    export(offenses(zip_2016), path)

    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT year, attempted FROM offenses").fetchone()
    assert row == (2016, 1)


def test_unknown_ending_is_refused(zip_2023, tmp_path):
    with pytest.raises(ValueError, match="--out must end with"):
        export(offenses(zip_2023), tmp_path / "out.txt")


def test_failed_export_keeps_the_old_file(zip_2023, tmp_path):
    path = tmp_path / "out.csv"
    path.write_text("old")

    def broken():
        yield from offenses(zip_2023)
        raise RuntimeError("cut")

    with pytest.raises(RuntimeError):
        export(broken(), path)
    assert path.read_text() == "old"
    assert list(tmp_path.glob(".*.part")) == []
