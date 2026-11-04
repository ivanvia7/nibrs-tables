from dataclasses import dataclass
from typing import ClassVar

# Every table starts with the same incident columns, so they join on incident_id.


@dataclass(frozen=True)
class Offense:
    """One offense in one incident, with names in place of FBI codes."""

    TABLE: ClassVar[str] = "offenses"

    state: str
    year: int
    incident_id: str
    offense_id: str
    incident_date: str  # ISO, like 2023-01-31
    incident_hour: str  # 0 to 23, empty when unknown
    ori: str  # FBI agency id, like DE0010100
    agency_name: str
    county: str
    offense_code: str
    offense_name: str
    offense_category: str
    crime_against: str
    attempted: bool
    location: str


@dataclass(frozen=True)
class Victim:
    """One victim in one incident; lists hold every match, joined by "; "."""

    TABLE: ClassVar[str] = "victims"

    state: str
    year: int
    incident_id: str
    victim_id: str
    incident_date: str
    ori: str
    agency_name: str
    county: str
    victim_type: str  # Individual, Business, Society/Public and so on
    age: str  # years, or a name like "Under 24 Hours" or "Unknown"
    sex: str
    race: str
    ethnicity: str
    resident_status: str
    offenses: str  # offense names this victim suffered
    injuries: str
    relationships: str  # victim's relationship to each offender, like "Acquaintance"


@dataclass(frozen=True)
class Offender:
    """One offender in one incident, as the victim or witness described them."""

    TABLE: ClassVar[str] = "offenders"

    state: str
    year: int
    incident_id: str
    offender_id: str
    incident_date: str
    ori: str
    agency_name: str
    county: str
    age: str
    sex: str
    race: str
    ethnicity: str


@dataclass(frozen=True)
class Arrestee:
    """One arrest tied to an incident."""

    TABLE: ClassVar[str] = "arrestees"

    state: str
    year: int
    incident_id: str
    arrestee_id: str
    arrest_date: str
    ori: str
    agency_name: str
    county: str
    arrest_type: str  # On-View Arrest, Summoned/Cited or Taken Into Custody
    offense_name: str  # the offense the person was arrested for
    age: str
    sex: str
    race: str
    ethnicity: str


@dataclass(frozen=True)
class Property:
    """One item of property in one incident: stolen, recovered, seized and so on."""

    TABLE: ClassVar[str] = "property"

    state: str
    year: int
    incident_id: str
    property_id: str
    incident_date: str
    ori: str
    agency_name: str
    county: str
    loss_type: str  # Stolen, Recovered, Seized, Destroyed/Damaged/Vandalized ...
    description: str  # Money, Automobiles, Drugs/Narcotics ...
    value: int | None  # US dollars, empty when not reported
    date_recovered: str


Row = Offense | Victim | Offender | Arrestee | Property
