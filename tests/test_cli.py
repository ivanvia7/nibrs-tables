import httpx
import respx

from nibrs_tables.download import SIGNED_URL_API


def test_offenses_uses_cached_zip_and_writes_rows(run_cli, zip_2023, tmp_path):
    out = tmp_path / "out.csv"
    code, stdout, _ = run_cli(
        "offenses", "de", "2023", "--cache-dir", str(zip_2023.parent), "--out", str(out)
    )
    assert code == 0
    assert stdout == f"{out} 2 rows\n"


def test_bad_out_fails_before_any_download(run_cli, tmp_path):
    code, _, stderr = run_cli(
        "offenses", "DE", "2023", "--cache-dir", str(tmp_path), "--out", "x.txt"
    )
    assert code == 2
    assert "--out must end with one of .csv, .jsonl, .db, .parquet" in stderr
    assert list(tmp_path.iterdir()) == []


def test_command_is_required(run_cli):
    code, _, stderr = run_cli()
    assert code == 2
    assert "the following arguments are required: command" in stderr


@respx.mock
def test_network_error_exits_without_traceback(run_cli, tmp_path):
    respx.get(SIGNED_URL_API).mock(side_effect=httpx.ConnectError("offline"))
    code, _, _ = run_cli("download", "DE", "2023", "--cache-dir", str(tmp_path))
    assert code == "offline"
