from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from nibrs_tables.download import NoFileError
from nibrs_tables.read import read_table
from nibrs_tables.schema import Offense


class Incident(NamedTuple):
    """The incident fields every table repeats, so each row stands on its own."""

    date: str
    hour: str
    ori: str
    agency_name: str
    county: str


def iso_date(text: str) -> str:
    """Turn 09-AUG-16 (2016-2020) and 2015-08-09 00:00:00 (before 2016) into 2016-08-09."""
    if len(text) == len("09-AUG-16"):
        return datetime.strptime(text, "%d-%b-%y").date().isoformat()
    return text[: len("2023-01-01")]


def row_year(row: dict[str, str], date: str) -> int:
    # Files before 2016 have no data_year column; their dates hold the year.
    return int(row.get("data_year") or date[:4])


def lookup(zip_path: Path, table: str, key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in read_table(zip_path, table)}


def agency_table(zip_path: Path) -> dict[str, dict[str, str]]:
    """2016 on: agencies.csv. Before 2016: cde_agencies.csv, renamed to the new columns."""
    try:
        return lookup(zip_path, "agencies", "agency_id")
    except ValueError:
        old = lookup(zip_path, "cde_agencies", "agency_id")
        return {
            agency_id: {
                **row,
                "pub_agency_name": row["agency_name"],
                "county_name": row["primary_county"].upper(),
            }
            for agency_id, row in old.items()
        }


def incidents(zip_path: Path) -> tuple[str, dict[str, Incident]]:
    """The zip's state, and every incident by id with its date and agency."""
    # Codes mean different things in different years, so each zip uses its own tables.
    agencies = agency_table(zip_path)
    if not agencies:
        # AK 2020 ships a zip with no agencies: the state sent the FBI nothing that year.
        raise NoFileError(f"{zip_path.name} has an empty agencies table")
    state = next(iter(agencies.values()))["state_abbr"]  # one state per zip

    by_id = {}
    for row in read_table(zip_path, "NIBRS_incident"):
        # A few incidents point to agencies missing from the FBI table (45 in TX 2023).
        agency = agencies.get(row["agency_id"], {})
        by_id[row["incident_id"]] = Incident(
            date=iso_date(row["incident_date"]),
            hour=row["incident_hour"],
            ori=agency.get("ori", ""),
            agency_name=agency.get("pub_agency_name", ""),
            county=agency.get("county_name", ""),
        )
    return state, by_id


def offense_types(zip_path: Path) -> tuple[str, dict[str, dict[str, str]]]:
    """The column offenses link by, and the offense types keyed by it."""
    rows = list(read_table(zip_path, "NIBRS_OFFENSE_TYPE"))
    if not rows:
        raise ValueError(f"{zip_path.name} has an empty NIBRS_OFFENSE_TYPE table")
    # Before 2023 offenses point to offense_type_id, from 2023 to offense_code.
    link = "offense_type_id" if "offense_type_id" in rows[0] else "offense_code"
    return link, {row[link]: row for row in rows}


def offenses(zip_path: Path) -> Iterator[Offense]:
    state, by_id = incidents(zip_path)
    locations = lookup(zip_path, "NIBRS_LOCATION_TYPE", "location_id")
    link, types = offense_types(zip_path)

    for row in read_table(zip_path, "NIBRS_OFFENSE"):
        try:
            incident = by_id[row["incident_id"]]
            offense_type = types[row[link]]
            location = locations[row["location_id"]]["location_name"]
        except KeyError as error:
            raise ValueError(
                f"{zip_path.name}: offense {row['offense_id']} points to missing id {error}"
            ) from error
        yield Offense(
            state=state,
            year=row_year(row, incident.date),
            incident_id=row["incident_id"],
            offense_id=row["offense_id"],
            incident_date=incident.date,
            incident_hour=incident.hour,
            ori=incident.ori,
            agency_name=incident.agency_name,
            county=incident.county,
            offense_code=offense_type["offense_code"],
            offense_name=offense_type["offense_name"],
            offense_category=offense_type["offense_category_name"],
            crime_against=offense_type["crime_against"],
            attempted=row["attempt_complete_flag"] == "A",
            location=location,
        )
