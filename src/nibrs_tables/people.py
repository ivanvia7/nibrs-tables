"""Victims, offenders, arrestees and property, each joined to its incident and agency."""

from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from nibrs_tables.offenses import (
    Incident,
    incidents,
    iso_date,
    lookup,
    offense_types,
    row_year,
)
from nibrs_tables.read import read_table
from nibrs_tables.schema import Arrestee, Offender, Property, Victim

SEX = {"M": "Male", "F": "Female", "U": "Unknown"}  # X: not a person, left blank
RESIDENT = {"R": "Resident", "N": "Nonresident", "U": "Unknown"}


class Names:
    """Code tables of one zip: id to name, blank when the id is blank or unknown."""

    def __init__(self, zip_path: Path) -> None:
        self.zip_path = zip_path
        self.tables: dict[str, dict[str, str]] = {}

    def __call__(self, table: str, key: str, name: str, value: str) -> str:
        if table not in self.tables:
            rows = read_table(self.zip_path, table)
            self.tables[table] = {row[key]: row[name] for row in rows}
        return self.tables[table].get(value, "")

    def age(self, row: dict[str, str]) -> str:
        # age_num holds years; 00 means Unknown, and babies and blanks use the age table.
        if row["age_num"].isdigit() and int(row["age_num"]) > 0:
            return str(int(row["age_num"]))
        return self("NIBRS_AGE", "age_id", "age_name", row["age_id"])

    def race(self, row: dict[str, str]) -> str:
        return self("REF_RACE", "race_id", "race_desc", row["race_id"])

    def ethnicity(self, row: dict[str, str]) -> str:
        return self(
            "NIBRS_ETHNICITY", "ethnicity_id", "ethnicity_name", row["ethnicity_id"]
        )


def incident_of(
    by_id: dict[str, Incident], zip_path: Path, table: str, row: dict[str, str]
) -> Incident:
    try:
        return by_id[row["incident_id"]]
    except KeyError as error:
        raise ValueError(
            f"{zip_path.name}: {table} row points to missing incident {error}"
        ) from error


def grouped(pairs: Iterator[tuple[str, str]]) -> dict[str, str]:
    """Join every name per id with "; ", first seen first, no repeats."""
    names: dict[str, dict[str, None]] = defaultdict(dict)
    for key, name in pairs:
        if name:
            names[key][name] = None
    return {key: "; ".join(values) for key, values in names.items()}


def victims(zip_path: Path) -> Iterator[Victim]:
    state, by_id = incidents(zip_path)
    names = Names(zip_path)
    link, types = offense_types(zip_path)
    offense_names = {
        row["offense_id"]: types.get(row[link], {}).get("offense_name", "")
        for row in read_table(zip_path, "NIBRS_OFFENSE")
    }
    victim_offenses = grouped(
        (row["victim_id"], offense_names.get(row["offense_id"], ""))
        for row in read_table(zip_path, "NIBRS_VICTIM_OFFENSE")
    )
    injuries = grouped(
        (
            row["victim_id"],
            names("NIBRS_INJURY", "injury_id", "injury_name", row["injury_id"]),
        )
        for row in read_table(zip_path, "NIBRS_VICTIM_INJURY")
    )
    relationships = grouped(
        (
            row["victim_id"],
            names(
                "NIBRS_RELATIONSHIP",
                "relationship_id",
                "relationship_name",
                row["relationship_id"],
            ),
        )
        for row in read_table(zip_path, "NIBRS_VICTIM_OFFENDER_REL")
    )

    for row in read_table(zip_path, "NIBRS_VICTIM"):
        incident = incident_of(by_id, zip_path, "victim", row)
        victim_id = row["victim_id"]
        yield Victim(
            state=state,
            year=row_year(row, incident.date),
            incident_id=row["incident_id"],
            victim_id=victim_id,
            incident_date=incident.date,
            ori=incident.ori,
            agency_name=incident.agency_name,
            county=incident.county,
            victim_type=names(
                "NIBRS_VICTIM_TYPE",
                "victim_type_id",
                "victim_type_name",
                row["victim_type_id"],
            ),
            age=names.age(row),
            sex=SEX.get(row["sex_code"], ""),
            race=names.race(row),
            ethnicity=names.ethnicity(row),
            resident_status=RESIDENT.get(row["resident_status_code"], ""),
            offenses=victim_offenses.get(victim_id, ""),
            injuries=injuries.get(victim_id, ""),
            relationships=relationships.get(victim_id, ""),
        )


def offenders(zip_path: Path) -> Iterator[Offender]:
    state, by_id = incidents(zip_path)
    names = Names(zip_path)
    for row in read_table(zip_path, "NIBRS_OFFENDER"):
        incident = incident_of(by_id, zip_path, "offender", row)
        yield Offender(
            state=state,
            year=row_year(row, incident.date),
            incident_id=row["incident_id"],
            offender_id=row["offender_id"],
            incident_date=incident.date,
            ori=incident.ori,
            agency_name=incident.agency_name,
            county=incident.county,
            age=names.age(row),
            sex=SEX.get(row["sex_code"], ""),
            race=names.race(row),
            ethnicity=names.ethnicity(row),
        )


def arrestees(zip_path: Path) -> Iterator[Arrestee]:
    state, by_id = incidents(zip_path)
    names = Names(zip_path)
    link, types = offense_types(zip_path)
    for row in read_table(zip_path, "NIBRS_ARRESTEE"):
        incident = incident_of(by_id, zip_path, "arrestee", row)
        yield Arrestee(
            state=state,
            year=row_year(row, incident.date),
            incident_id=row["incident_id"],
            arrestee_id=row["arrestee_id"],
            arrest_date=iso_date(row["arrest_date"]),
            ori=incident.ori,
            agency_name=incident.agency_name,
            county=incident.county,
            arrest_type=names(
                "NIBRS_ARREST_TYPE",
                "arrest_type_id",
                "arrest_type_name",
                row["arrest_type_id"],
            ),
            offense_name=types.get(row[link], {}).get("offense_name", ""),
            age=names.age(row),
            sex=SEX.get(row["sex_code"], ""),
            race=names.race(row),
            ethnicity=names.ethnicity(row),
        )


def properties(zip_path: Path) -> Iterator[Property]:
    state, by_id = incidents(zip_path)
    names = Names(zip_path)
    items = lookup(zip_path, "NIBRS_PROPERTY", "property_id")
    for row in read_table(zip_path, "NIBRS_PROPERTY_DESC"):
        try:
            item = items[row["property_id"]]
        except KeyError as error:
            raise ValueError(
                f"{zip_path.name}: property row points to missing property {error}"
            ) from error
        incident = incident_of(by_id, zip_path, "property", item)
        value = row["property_value"]
        yield Property(
            state=state,
            year=row_year(row, incident.date),
            incident_id=item["incident_id"],
            property_id=row["property_id"],
            incident_date=incident.date,
            ori=incident.ori,
            agency_name=incident.agency_name,
            county=incident.county,
            loss_type=names(
                "NIBRS_PROP_LOSS_TYPE",
                "prop_loss_id",
                "prop_loss_name",
                item["prop_loss_id"],
            ),
            description=names(
                "NIBRS_PROP_DESC_TYPE",
                "prop_desc_id",
                "prop_desc_name",
                row["prop_desc_id"],
            ),
            value=int(value) if value.isdigit() else None,
            date_recovered=iso_date(row["date_recovered"]),
        )
