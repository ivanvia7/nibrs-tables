import argparse
from pathlib import Path

from nibrs_tables.download import download_zip


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nibrs-tables", description="FBI NIBRS crime files as flat tables"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    download = commands.add_parser("download", help="save one state-year zip")
    download.add_argument(
        "state", type=str.upper, help="two-letter state code, like DE"
    )
    download.add_argument("year", type=int, help="data year, like 2023")
    download.add_argument(
        "--cache-dir", type=Path, default=Path("cache"), help="where zips are kept"
    )

    args = parser.parse_args()

    try:
        path = download_zip(args.state, args.year, args.cache_dir)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"{path} {path.stat().st_size / 1_000_000:.1f} MB")
