import pytest
from conftest import TABLES_2023, build_zip

from nibrs_tables.offenses import iso_date, offenses
from nibrs_tables.schema import Offense


def test_iso_date_reads_both_layouts():
    assert iso_date("09-AUG-16") == "2016-08-09"
    assert iso_date("2023-01-01") == "2023-01-01"
    assert iso_date("2015-08-09 00:00:00") == "2015-08-09"


def test_pre_2016_layout_reads_cde_agencies(zip_2015):
    (offense,) = offenses(zip_2015)
    assert (offense.year, offense.incident_date) == (2015, "2015-08-09")
    assert (offense.agency_name, offense.county, offense.state) == (
        "Dover",
        "KENT",
        "DE",
    )
    assert offense.location == "Parking/Drop Lot/Garage"


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


def test_dangling_ids_are_skipped_and_counted(tmp_path, capsys):
    tables = {
        **TABLES_2023,
        "NIBRS_OFFENSE": TABLES_2023["NIBRS_OFFENSE"]
        + "2023,22,1,99Z,C,35\n"  # offense type missing
        + "2023,23,999,13B,C,35\n"  # incident missing
        + "2023,24,1,13B,C,999\n",  # location missing
    }
    path = build_zip(tmp_path / "DE-2023.zip", "DE", tables)
    good = list(offenses(build_zip(tmp_path / "good.zip", "DE", TABLES_2023)))
    assert list(offenses(path)) == good
    assert (
        "skipped 3 offenses with a missing id, first: "
        "offense 22 points to missing offense_code '99Z'"
    ) in capsys.readouterr().err


def test_skip_count_is_printed_when_reading_stops_early(tmp_path, capsys):
    tables = {
        **TABLES_2023,
        "NIBRS_OFFENSE": "data_year,offense_id,incident_id,offense_code,"
        "attempt_complete_flag,location_id\n"
        "2023,22,1,99Z,C,35\n"
        "2023,20,1,13B,C,35\n"
        "2023,21,2,13B,C,35\n",
    }
    rows = offenses(build_zip(tmp_path / "DE-2023.zip", "DE", tables))
    next(rows)
    rows.close()
    assert "skipped 1 offenses" in capsys.readouterr().err


def test_missing_column_fails_loudly(tmp_path):
    tables = {
        **TABLES_2023,
        "NIBRS_OFFENSE": "data_year,offense_id,incident_id,offense_code,"
        "attempt_complete_flag\n2023,20,1,13B,C\n",
    }
    path = build_zip(tmp_path / "DE-2023.zip", "DE", tables)
    with pytest.raises(
        ValueError, match="a table read for offenses has no column 'location_id'"
    ):
        list(offenses(path))


def test_empty_agencies_raises_clean_error(tmp_path):
    tables = {
        **TABLES_2023,
        "agencies": "agency_id,ori,pub_agency_name,county_name,state_abbr\n",
    }
    path = build_zip(tmp_path / "DE-2023.zip", "DE", tables)
    with pytest.raises(ValueError, match="empty agencies table"):
        list(offenses(path))


def test_missing_column_in_a_code_table_fails_loudly(tmp_path):
    tables = {
        **TABLES_2023,
        "NIBRS_LOCATION_TYPE": "location_id,location_code,place\n35,20,Residence/Home\n",
    }
    path = build_zip(tmp_path / "DE-2023.zip", "DE", tables)
    with pytest.raises(ValueError, match="has no column 'location_name'"):
        list(offenses(path))
