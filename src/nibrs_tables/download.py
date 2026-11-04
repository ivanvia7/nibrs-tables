import sys
import time
import zipfile
from pathlib import Path

import httpx

SIGNED_URL_API = "https://cde.ucr.cjis.gov/LATEST/s3/signedurl"
CACHE_DIR = Path("cache")
ATTEMPTS = 4
RETRY_WAIT_S = 10  # grows 10, 20, 30 s; the FBI API drops connections under load


class NoFileError(ValueError):
    """The FBI publishes no file, or an empty one, for this state and year."""


def get_with_retries(url: str, params: dict[str, str]) -> httpx.Response:
    for attempt in range(1, ATTEMPTS):
        try:
            return httpx.get(url, params=params, timeout=30)
        except httpx.TransportError:
            time.sleep(RETRY_WAIT_S * attempt)
    return httpx.get(url, params=params, timeout=30)  # last try raises to the caller


def signed_url(state: str, year: int) -> str:
    key = f"nibrs/incident/{year}/{state}-{year}.zip"
    response = get_with_retries(SIGNED_URL_API, params={"key": key})
    response.raise_for_status()

    urls = response.json()
    if key not in urls:
        raise NoFileError(f"FBI has no NIBRS file for {state} {year}")
    return urls[key]


def download_zip(state: str, year: int, cache_dir: Path) -> Path:
    path = cache_dir / f"{state}-{year}.zip"
    # A broken cached zip is fetched again instead of failing on every run.
    if zipfile.is_zipfile(path):
        return path

    url = signed_url(state, year)
    print(f"Downloading {path.name}", file=sys.stderr)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Write to .part first, so a broken download never looks like a finished zip.
    partial = path.with_suffix(".part")
    try:
        with httpx.stream("GET", url, timeout=120) as response:
            response.raise_for_status()
            with partial.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)  # a failed download leaves no big .part file
    return path
