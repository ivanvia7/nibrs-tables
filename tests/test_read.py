import pytest

from nibrs_tables.read import read_table


def test_upper_case_headers_become_lower_case(zip_2016):
    row = next(read_table(zip_2016, "NIBRS_incident"))
    assert row["incident_date"] == "09-AUG-16"


def test_table_is_found_in_any_folder(zip_2016, zip_2023):
    assert next(read_table(zip_2016, "agencies"))["ori"] == "DE0010800"
    assert next(read_table(zip_2023, "agencies"))["ori"] == "DE0010100"


def test_table_name_ignores_case(zip_2023):
    assert len(list(read_table(zip_2023, "nibrs_offense"))) == 2


def test_broken_byte_is_replaced_not_fatal(zip_2016):
    row = next(read_table(zip_2016, "NIBRS_BIAS_LIST"))
    assert row["bias_desc"] == "offender�s motive"


def test_missing_table_names_the_zip(zip_2023):
    with pytest.raises(ValueError, match=r"DE-2023\.zip has no NOPE\.csv"):
        list(read_table(zip_2023, "NOPE"))
