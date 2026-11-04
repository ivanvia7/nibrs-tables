import argparse


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

    args = parser.parse_args()
    print(args)
