from nibrs_tables.offenses import iso_date, offenses
from nibrs_tables.schema import Offense


def test_iso_date_reads_both_layouts():
    assert iso_date("09-AUG-16") == "2016-08-09"
    assert iso_date("2023-01-01") == "2023-01-01"


def test_2016_layout_joins_by_offense_type_id(zip_2016):
    assert list(offenses(zip_2016)) == [
        Offense(
            state="DE",
            year=2016,
            incident_id="1",
            offense_id="10",
            incident_date="2016-08-09",
            incident_hour="15",
            ori="DE0010800",
            agency_name="Frederica",
            county="KENT",
            offense_code="23C",
            offense_name="Shoplifting",
            offense_category="Larceny/Theft Offenses",
            crime_against="Property",
            attempted=True,
            location="Department/Discount Store",
        )
    ]


def test_2023_layout_joins_by_offense_code(zip_2023):
    first = next(offenses(zip_2023))
    assert (first.agency_name, first.offense_name, first.location) == (
        "Dover",
        "Simple Assault",
        "Residence/Home",
    )
    assert first.attempted is False


def test_unknown_agency_keeps_the_offense_with_blank_agency(zip_2023):
    second = list(offenses(zip_2023))[1]
    assert (second.state, second.ori, second.agency_name, second.county) == (
        "DE",
        "",
        "",
        "",
    )
    assert second.offense_name == "Simple Assault"
