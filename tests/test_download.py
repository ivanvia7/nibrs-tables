import httpx
import pytest
import respx

from nibrs_tables.download import SIGNED_URL_API, download_zip

KEY = "nibrs/incident/2023/DE-2023.zip"
SIGNED = "https://files.example/DE-2023.zip?signature=abc"


@respx.mock
def test_download_saves_zip_then_skips(tmp_path):
    api = respx.get(SIGNED_URL_API).mock(
        return_value=httpx.Response(200, json={KEY: SIGNED})
    )
    respx.get(SIGNED).mock(return_value=httpx.Response(200, content=b"zip bytes"))

    path = download_zip("DE", 2023, tmp_path)
    assert path.read_bytes() == b"zip bytes"
    assert not path.with_suffix(".part").exists()

    assert download_zip("DE", 2023, tmp_path) == path
    assert api.call_count == 1


@respx.mock
def test_unknown_state_year_raises_and_saves_nothing(tmp_path):
    respx.get(SIGNED_URL_API).mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(ValueError, match="FBI has no NIBRS file for XX 2023"):
        download_zip("XX", 2023, tmp_path)
    assert list(tmp_path.iterdir()) == []
