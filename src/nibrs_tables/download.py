import sys
from pathlib import Path

import httpx

SIGNED_URL_API = "https://cde.ucr.cjis.gov/LATEST/s3/signedurl"


def signed_url(state: str, year: int) -> str:
    key = f"nibrs/incident/{year}/{state}-{year}.zip"
    response = httpx.get(SIGNED_URL_API, params={"key": key}, timeout=30)
    response.raise_for_status()

    urls = response.json()
    if key not in urls:
        raise ValueError(f"FBI has no NIBRS file for {state} {year}")
    return urls[key]


def download_zip(state: str, year: int, cache_dir: Path) -> Path:
    path = cache_dir / f"{state}-{year}.zip"
    if path.exists():
        return path

    url = signed_url(state, year)
    print(f"Downloading {path.name}", file=sys.stderr)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Write to .part first, so a broken download never looks like a finished zip.
    partial = path.with_suffix(".part")
    with httpx.stream("GET", url, timeout=120) as response:
        response.raise_for_status()
        with partial.open("wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)

    partial.rename(path)
    return path
