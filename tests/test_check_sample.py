import dataclasses
import importlib.util
from pathlib import Path

import pytest
from conftest import TABLES_2023, build_zip

from nibrs_tables.offenses import offenses

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_sample.py"
spec = importlib.util.spec_from_file_location("check_sample", SCRIPT)
assert spec and spec.loader
check_sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_sample)


def test_good_output_has_no_problems(zip_2023, zip_2016, zip_2015):
    for path, rows in ((zip_2023, 2), (zip_2016, 1), (zip_2015, 1)):
        result = check_sample.check(path)
        assert (result["total"], result["sampled"], result["problems"]) == (
            rows,
            rows,
            [],
        )


def test_a_wrong_name_is_caught(zip_2023, monkeypatch):
    def wrong(path):
        for offense in offenses(path):
            yield dataclasses.replace(offense, offense_name="Intimidation")

    monkeypatch.setattr(check_sample, "offenses", wrong)
    problems = check_sample.check(zip_2023)["problems"]
    assert "offense_name: tool 'Intimidation', raw 'Simple Assault'" in problems[0]


def test_a_lost_row_is_caught(zip_2023, monkeypatch):
    monkeypatch.setattr(check_sample, "offenses", lambda path: list(offenses(path))[1:])
    problems = check_sample.check(zip_2023)["problems"]
    assert "rows: 1 raw offenses missing, 0 extra" in problems


def test_rows_the_tool_skips_by_design_are_not_problems(tmp_path, monkeypatch):
    # 1 of 3 rows here; real files have far more rows, so allow a high share.
    monkeypatch.setattr(check_sample, "MAX_DANGLING", 0.5)
    tables = {
        **TABLES_2023,
        "NIBRS_OFFENSE": TABLES_2023["NIBRS_OFFENSE"] + "2023,22,1,99Z,C,35\n",
    }
    result = check_sample.check(build_zip(tmp_path / "DE-2023.zip", "DE", tables))
    assert (result["dangling"], result["problems"]) == (1, [])


def test_a_wrong_ori_is_caught(zip_2023, monkeypatch):
    def wrong(path):
        for offense in offenses(path):
            yield dataclasses.replace(offense, ori="DE9999999")

    monkeypatch.setattr(check_sample, "offenses", wrong)
    assert "ori: tool 'DE9999999'" in check_sample.check(zip_2023)["problems"][0]


def test_a_row_longer_than_its_header_is_read(tmp_path):
    tables = {
        **TABLES_2023,
        "NIBRS_OFFENSE": TABLES_2023["NIBRS_OFFENSE"] + "2023,22,1,13B,C,35,extra\n",
    }
    result = check_sample.check(build_zip(tmp_path / "DE-2023.zip", "DE", tables))
    assert result["problems"] == []


def test_many_dangling_rows_fail_and_sampling_skips_them(tmp_path):
    rows = "".join(f"2023,{30 + i},1,99Z,C,35\n" for i in range(5))
    tables = {**TABLES_2023, "NIBRS_OFFENSE": TABLES_2023["NIBRS_OFFENSE"] + rows}
    result = check_sample.check(build_zip(tmp_path / "DE-2023.zip", "DE", tables))
    assert result["sampled"] == 2  # both good rows, none of the 5 dangling ones
    assert result["problems"] == ["rows: 5 of 7 point to a missing id"]


def test_a_refused_file_fails_but_later_files_are_checked(
    tmp_path, monkeypatch, capsys
):
    bad = {
        **TABLES_2023,
        "NIBRS_OFFENSE": TABLES_2023["NIBRS_OFFENSE"].replace(",13B,", ",X13B,"),
    }
    zips = {
        ("DE", 2023): build_zip(tmp_path / "DE-2023.zip", "DE", bad),
        ("MD", 2023): build_zip(tmp_path / "MD-2023.zip", "DE", TABLES_2023),
    }
    monkeypatch.setattr(check_sample, "download_zip", lambda s, y, _: zips[(s, y)])
    with pytest.raises(SystemExit) as stop:
        check_sample.main(["DE-2023", "MD-2023"])
    assert stop.value.code == 1
    out = capsys.readouterr().out
    assert "DE-2023: tool failed" in out
    assert "MD-2023: 2 raw offenses, 0 with a missing id, 2 sampled, 0 problems" in out


def test_a_bad_name_is_not_called_a_tool_failure():
    with pytest.raises(ValueError, match="invalid literal"):
        check_sample.main(["DE-20x3"])


def test_a_bare_value_error_from_the_tool_is_a_tool_failure(
    tmp_path, monkeypatch, capsys
):
    # A bad date cell raises a strptime ValueError with no zip name in it.
    path = build_zip(tmp_path / "DE-2023.zip", "DE", TABLES_2023)
    monkeypatch.setattr(check_sample, "download_zip", lambda *_: path)

    def bad_cell(_):
        raise ValueError("time data '31-FOO-16' does not match format")

    monkeypatch.setattr(check_sample, "check", bad_cell)
    with pytest.raises(SystemExit) as stop:
        check_sample.main(["DE-2023"])
    assert stop.value.code == 1
    assert "DE-2023: tool failed" in capsys.readouterr().out
