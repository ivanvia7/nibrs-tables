import argparse
from importlib.util import find_spec
from pathlib import Path

import httpx

from nibrs_tables.download import CACHE_DIR, download_zip
from nibrs_tables.export import WRITERS, check_suffix, export
from nibrs_tables.offenses import offenses
from nibrs_tables.people import arrestees, offenders, properties, victims
from nibrs_tables.schema import Arrestee, Offender, Offense, Property, Victim

# Command name: what it writes, the function that reads it, and its row shape.
TABLES = {
    "offenses": ("one row per offense", offenses, Offense),
    "victims": ("one row per victim", victims, Victim),
    "offenders": ("one row per offender", offenders, Offender),
    "arrestees": ("one row per arrest", arrestees, Arrestee),
    "property": ("one row per item stolen, seized or recovered", properties, Property),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nibrs-tables", description="FBI NIBRS crime files as flat tables"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    # Arguments every command takes, declared once.
    state_year = argparse.ArgumentParser(add_help=False)
    state_year.add_argument(
        "state", type=str.upper, help="two-letter state code, like DE"
    )
    state_year.add_argument("year", type=int, help="data year, like 2023")
    state_year.add_argument(
        "--cache-dir", type=Path, default=CACHE_DIR, help="where zips are kept"
    )

    commands.add_parser(
        "download", parents=[state_year], help="save one state-year zip"
    )
    for name, (help_text, _, _) in TABLES.items():
        table_command = commands.add_parser(name, parents=[state_year], help=help_text)
        table_command.add_argument(
            "--out",
            type=Path,
            required=True,
            help=f"file ending in {', '.join(WRITERS)}",
        )

    args = parser.parse_args(argv)
    if args.command in TABLES:
        check_out(parser, args.out)

    try:
        path = download_zip(args.state, args.year, args.cache_dir)
        if args.command == "download":
            print(f"{path} {path.stat().st_size / 1_000_000:.1f} MB")
            return

        _, read_rows, row_type = TABLES[args.command]
        count = export(read_rows(path), args.out, row_type)
    except (ValueError, httpx.HTTPError) as error:
        raise SystemExit(str(error)) from error
    print(f"{args.out} {count:,} rows")


def check_out(parser: argparse.ArgumentParser, out: Path) -> None:
    """Fail before any download, not after a long one."""
    if not out.parent.is_dir():
        parser.error(f"--out folder {out.parent} does not exist")
    try:
        check_suffix(out)
    except ValueError as error:
        parser.error(str(error))
    if out.suffix == ".parquet" and find_spec("duckdb") is None:
        parser.error('.parquet needs duckdb: pip install "nibrs-tables[parquet]"')
