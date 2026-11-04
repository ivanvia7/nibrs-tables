from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from nibrs_tables.read import read_table
from nibrs_tables.schema import Offense


def iso_date(text: str) -> str:
    """Turn 09-AUG-16 from 2016-2020 files into 2016-08-09, the form 2023 files use."""
    if len(text) == len("09-AUG-16"):
        return datetime.strptime(text, "%d-%b-%y").date().isoformat()
    return text


def lookup(zip_path: Path, table: str, key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in read_table(zip_path, table)}


def offenses(zip_path: Path) -> Iterator[Offense]:
    # Codes mean different things in different years, so each zip uses its own tables.
    agencies = lookup(zip_path, "agencies", "agency_id")
    locations = lookup(zip_path, "NIBRS_LOCATION_TYPE", "location_id")
    # ponytail: every incident sits in memory; fine for DE (51k), a big state may need a SQLite join.
    incidents = lookup(zip_path, "NIBRS_incident", "incident_id")

    offense_types = list(read_table(zip_path, "NIBRS_OFFENSE_TYPE"))
    # 2016-2020 offenses point to offense_type_id, 2023 offenses to offense_code.
    link = (
        "offense_type_id" if "offense_type_id" in offense_types[0] else "offense_code"
    )
    types = {row[link]: row for row in offense_types}

    for row in read_table(zip_path, "NIBRS_OFFENSE"):
        incident = incidents[row["incident_id"]]
        agency = agencies[incident["agency_id"]]
        offense_type = types[row[link]]
        yield Offense(
            state=agency["state_abbr"],
            year=int(row["data_year"]),
            incident_id=row["incident_id"],
            offense_id=row["offense_id"],
            incident_date=iso_date(incident["incident_date"]),
            incident_hour=incident["incident_hour"],
            ori=agency["ori"],
            agency_name=agency["pub_agency_name"],
            county=agency["county_name"],
            offense_code=offense_type["offense_code"],
            offense_name=offense_type["offense_name"],
            offense_category=offense_type["offense_category_name"],
            crime_against=offense_type["crime_against"],
            attempted=row["attempt_complete_flag"] == "A",
            location=locations[row["location_id"]]["location_name"],
        )
