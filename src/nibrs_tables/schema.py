from dataclasses import dataclass


@dataclass(frozen=True)
class Offense:
    """One offense in one incident, with names in place of FBI codes."""

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
