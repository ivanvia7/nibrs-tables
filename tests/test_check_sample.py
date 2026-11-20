import dataclasses
import importlib.util
from pathlib import Path

from nibrs_tables.offenses import offenses

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_sample.py"
spec = importlib.util.spec_from_file_location("check_sample", SCRIPT)
assert spec and spec.loader
check_sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_sample)


def test_good_output_has_no_problems(zip_2023, zip_2016, zip_2015):
    assert check_sample.check(zip_2023) == (2, [])
    assert check_sample.check(zip_2016) == (1, [])
    assert check_sample.check(zip_2015) == (1, [])


def test_a_wrong_name_is_caught(zip_2023, monkeypatch):
    def wrong(path):
        for offense in offenses(path):
            yield dataclasses.replace(offense, offense_name="Intimidation")

    monkeypatch.setattr(check_sample, "offenses", wrong)
    _, problems = check_sample.check(zip_2023)
    assert "offense_name: tool 'Intimidation', raw 'Simple Assault'" in problems[0]


def test_a_lost_row_is_caught(zip_2023, monkeypatch):
    monkeypatch.setattr(check_sample, "offenses", lambda path: list(offenses(path))[1:])
    _, problems = check_sample.check(zip_2023)
    assert "rows: 1 raw offenses missing, 0 extra" in problems
