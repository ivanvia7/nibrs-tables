import zipfile

import pytest
from conftest import TABLES_2015, TABLES_2023, build_zip

from nibrs_tables.export import export
from nibrs_tables.people import arrestees, offenders, properties, victims
from nibrs_tables.schema import Arrestee, Offender, Property, Victim

# Incident 1 (Dover, 2023-01-01) from TABLES_2023, with one victim, offender, arrest and item.
CODES = {
    "NIBRS_VICTIM_TYPE": "victim_type_id,victim_type_code,victim_type_name\n"
    "4,I,Individual\n8,S,Society/Public\n",
    "NIBRS_AGE": "age_id,age_code,age_name\n103,00,Unknown\n1,NN,Under 24 Hours\n",
    "REF_RACE": "race_id,race_code,race_desc\n1,W,White\n",
    "NIBRS_ETHNICITY": "ethnicity_id,ethnicity_code,ethnicity_name\n"
    "2,N,Not Hispanic or Latino\n",
    "NIBRS_INJURY": "injury_id,injury_code,injury_name\n1,N,None\n2,M,Apparent Minor Injury\n",
    "NIBRS_RELATIONSHIP": "relationship_id,relationship_code,relationship_name\n"
    "5,AQ,Acquaintance\n",
    "NIBRS_ARREST_TYPE": "arrest_type_id,arrest_type_code,arrest_type_name\n1,O,On View\n",
    "NIBRS_PROP_LOSS_TYPE": "prop_loss_id,prop_loss_name\n7,Stolen/Etc\n",
    "NIBRS_PROP_DESC_TYPE": "prop_desc_id,prop_desc_code,prop_desc_name\n20,20,Money\n",
}
PEOPLE_2023 = {
    **TABLES_2023,
    **CODES,
    "NIBRS_VICTIM": "data_year,victim_id,incident_id,victim_type_id,age_id,age_num,"
    "sex_code,race_id,ethnicity_id,resident_status_code\n"
    "2023,100,1,4,,34,F,1,2,R\n"
    "2023,101,1,8,,NS,X,,,\n",
    "NIBRS_VICTIM_OFFENSE": "data_year,victim_id,offense_id\n2023,100,20\n2023,100,20\n",
    "NIBRS_VICTIM_INJURY": "data_year,victim_id,injury_id\n2023,100,2\n2023,100,1\n",
    "NIBRS_VICTIM_OFFENDER_REL": "data_year,victim_id,offender_id,relationship_id\n"
    "2023,100,200,5\n",
    "NIBRS_OFFENDER": "data_year,offender_id,incident_id,age_id,age_num,sex_code,"
    "race_id,ethnicity_id\n"
    "2023,200,1,103,00,M,1,\n",
    "NIBRS_ARRESTEE": "data_year,arrestee_id,incident_id,arrest_date,arrest_type_id,"
    "offense_code,age_id,age_num,sex_code,race_id,ethnicity_id\n"
    "2023,300,1,2023-01-02,1,13B,,19,M,1,2\n",
    "NIBRS_PROPERTY": "data_year,property_id,incident_id,prop_loss_id\n2023,400,1,7\n",
    "NIBRS_PROPERTY_DESC": "data_year,property_id,prop_desc_id,property_value,"
    "date_recovered\n"
    "2023,400,20,250,\n2023,400,20,,\n",
}
INCIDENT = {
    "state": "DE",
    "year": 2023,
    "incident_id": "1",
    "incident_date": "2023-01-01",
    "ori": "DE0010100",
    "agency_name": "Dover",
    "county": "KENT",
}


@pytest.fixture
def zip_people(tmp_path):
    return build_zip(tmp_path / "DE-2023.zip", "DE-2023/DE", PEOPLE_2023)


def test_victims_list_offenses_injuries_and_relationships(zip_people):
    person, society = victims(zip_people)
    assert person == Victim(
        **INCIDENT,
        victim_id="100",
        victim_type="Individual",
        age="34",
        sex="Female",
        race="White",
        ethnicity="Not Hispanic or Latino",
        resident_status="Resident",
        offenses="Simple Assault",  # listed twice in the file, once here
        injuries="Apparent Minor Injury; None",
        relationships="Acquaintance",
    )
    # Society as a victim has no age, sex or race.
    assert (society.victim_type, society.age, society.sex, society.race) == (
        "Society/Public",
        "",
        "",
        "",
    )


def test_offender_age_from_age_table_when_not_a_number(zip_people):
    assert list(offenders(zip_people)) == [
        Offender(
            **INCIDENT,
            offender_id="200",
            age="Unknown",  # the file says 00
            sex="Male",
            race="White",
            ethnicity="",
        )
    ]


def test_arrestee_gets_arrest_offense_name(zip_people):
    (arrest,) = arrestees(zip_people)
    no_incident_date = {
        key: value for key, value in INCIDENT.items() if key != "incident_date"
    }
    assert arrest == Arrestee(
        **no_incident_date,
        arrestee_id="300",
        arrest_date="2023-01-02",
        arrest_type="On View",
        offense_name="Simple Assault",
        age="19",
        sex="Male",
        race="White",
        ethnicity="Not Hispanic or Latino",
    )


def test_property_value_is_a_number_or_empty(zip_people):
    reported, blank = properties(zip_people)
    assert reported == Property(
        **INCIDENT,
        property_id="400",
        loss_type="Stolen/Etc",
        description="Money",
        value=250,
        date_recovered="",
    )
    assert blank.value is None


def test_pre_2016_arrestee_links_by_offense_type_id(tmp_path):
    tables = {
        **TABLES_2015,
        "nibrs_arrest_type": "arrest_type_id,arrest_type_code,arrest_type_name\n"
        "3,T,Taken INTO Custody\n",
        "nibrs_age": "age_id,age_code,age_name\n",
        "ref_race": "race_id,race_code,race_desc\n",
        "nibrs_ethnicity": "ethnicity_id,ethnicity_code,ethnicity_name\n",
        "nibrs_arrestee": "arrestee_id,incident_id,arrest_date,arrest_type_id,"
        "offense_type_id,age_id,age_num,sex_code,race_id,ethnicity_id\n"
        "500,83088265,2015-08-10 00:00:00,3,39,,30,F,,\n",
    }
    path = tmp_path / "DE-2015.zip"
    with zipfile.ZipFile(path, "w") as archive:  # files before 2016 sit in no folder
        for table, text in tables.items():
            archive.writestr(f"{table}.csv", text)
    (arrest,) = arrestees(path)
    assert (
        arrest.year,
        arrest.arrest_date,
        arrest.arrest_type,
        arrest.offense_name,
    ) == (
        2015,
        "2015-08-10",
        "Taken INTO Custody",
        "Destruction/Damage/Vandalism of Property",
    )


@pytest.mark.parametrize(
    ("read_rows", "row_type"),
    [
        (victims, Victim),
        (offenders, Offender),
        (arrestees, Arrestee),
        (properties, Property),
    ],
)
def test_every_table_exports_to_sqlite_and_parquet(
    zip_people, tmp_path, read_rows, row_type
):
    for suffix in (".db", ".parquet"):
        path = tmp_path / f"{row_type.TABLE}{suffix}"
        assert export(read_rows(zip_people), path, row_type) > 0
