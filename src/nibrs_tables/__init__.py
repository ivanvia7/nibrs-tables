import argparse
from importlib.util import find_spec
from pathlib import Path

from nibrs_tables.download import download_zip
from nibrs_tables.export import WRITERS, export
from nibrs_tables.offenses import offenses


def main() -> None:
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
        "--cache-dir", type=Path, default=Path("cache"), help="where zips are kept"
    )

    commands.add_parser(
        "download", parents=[state_year], help="save one state-year zip"
    )
    offense_command = commands.add_parser(
        "offenses", parents=[state_year], help="write one row per offense"
    )
    offense_command.add_argument(
        "--out", type=Path, required=True, help=f"file ending in {', '.join(WRITERS)}"
    )

    args = parser.parse_args()
    if args.command == "offenses":
        check_out(parser, args.out)

    try:
        path = download_zip(args.state, args.year, args.cache_dir)
        if args.command == "download":
            print(f"{path} {path.stat().st_size / 1_000_000:.1f} MB")
            return

        count = export(offenses(path), args.out)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"{args.out} {count:,} rows")


def check_out(parser: argparse.ArgumentParser, out: Path) -> None:
    """Fail before any download, not after a long one."""
    if not out.parent.is_dir():
        parser.error(f"--out folder {out.parent} does not exist")
    if out.suffix not in WRITERS:
        parser.error(f"--out must end with one of {', '.join(WRITERS)}")
    if out.suffix == ".parquet" and find_spec("duckdb") is None:
        parser.error('.parquet needs duckdb: pip install "nibrs-tables[parquet]"')
