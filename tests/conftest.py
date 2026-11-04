import zipfile
from pathlib import Path

import pytest

from nibrs_tables import main

# Two tiny zips, one per FBI layout. Values copy real Delaware rows.
TABLES_2016 = {
    "agencies": '"AGENCY_ID","ORI","PUB_AGENCY_NAME","COUNTY_NAME","STATE_ABBR"\n'
    '"2254","DE0010800","Frederica","KENT","DE"\n',
    "NIBRS_LOCATION_TYPE": '"LOCATION_ID","LOCATION_CODE","LOCATION_NAME"\n'
    '"8","08","Department/Discount Store"\n',
    "NIBRS_incident": '"DATA_YEAR","AGENCY_ID","INCIDENT_ID","INCIDENT_DATE","INCIDENT_HOUR"\n'
    '"2016","2254","1","09-AUG-16","15"\n',
    "NIBRS_OFFENSE_TYPE": '"OFFENSE_TYPE_ID","OFFENSE_CODE","OFFENSE_NAME",'
    '"CRIME_AGAINST","OFFENSE_CATEGORY_NAME"\n'
    '"35","23C","Shoplifting","Property","Larceny/Theft Offenses"\n',
    "NIBRS_OFFENSE": '"DATA_YEAR","OFFENSE_ID","INCIDENT_ID","OFFENSE_TYPE_ID",'
    '"ATTEMPT_COMPLETE_FLAG","LOCATION_ID"\n'
    '"2016","10","1","35","A","8"\n',
}

TABLES_2023 = {
    "agencies": "agency_id,ori,pub_agency_name,county_name,state_abbr\n"
    "2247,DE0010100,Dover,KENT,DE\n",
    "NIBRS_LOCATION_TYPE": "location_id,location_code,location_name\n"
    "35,20,Residence/Home\n",
    # Incident 2 points to agency 99999, missing from agencies, as happens in TX 2023.
    "NIBRS_incident": "data_year,agency_id,incident_id,incident_date,incident_hour\n"
    "2023,2247,1,2023-01-01,2\n"
    "2023,99999,2,2023-02-01,\n",
    "NIBRS_OFFENSE_TYPE": "offense_code,offense_name,crime_against,offense_category_name\n"
    "13B,Simple Assault,Person,Assault Offenses\n",
    "NIBRS_OFFENSE": "data_year,offense_id,incident_id,offense_code,"
    "attempt_complete_flag,location_id\n"
    "2023,20,1,13B,C,35\n"
    "2023,21,2,13B,C,35\n",
}


def build_zip(path: Path, folder: str, tables: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for table, text in tables.items():
            archive.writestr(f"{folder}/{table}.csv", text)
    return path


@pytest.fixture
def zip_2016(tmp_path):
    """2016 layout: DE/ folder, upper-case headers, offense_type_id link, 09-AUG-16 dates."""
    path = build_zip(tmp_path / "DE-2016.zip", "DE", TABLES_2016)
    # The real 2016 bias list holds this broken byte.
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(
            "DE/NIBRS_BIAS_LIST.csv", b'"BIAS_DESC"\n"offender\xbfs motive"\n'
        )
    return path


@pytest.fixture
def zip_2023(tmp_path):
    """2023 layout: DE-2023/DE/ folder, lower-case headers, offense_code link."""
    return build_zip(tmp_path / "DE-2023.zip", "DE-2023/DE", TABLES_2023)


@pytest.fixture
def run_cli(capsys):
    """Run the CLI in-process; returns exit code, stdout and stderr."""

    def run(*args: str) -> tuple[int | str | None, str, str]:
        try:
            main(list(args))
            code = 0
        except SystemExit as error:
            code = error.code
        out = capsys.readouterr()
        return code, out.out, out.err

    return run
