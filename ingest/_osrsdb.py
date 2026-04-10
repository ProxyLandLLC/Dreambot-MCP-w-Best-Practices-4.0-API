"""
Shared osrs-db download helper.

Downloads the osrs-db npm package tarball and extracts the JSON data files.
The npm package contains the actual JSON (not Git LFS pointers).
"""

import os
import tarfile
import tempfile

import requests

from rag.store import get_cache_path

OSRSDB_NPM_URL = "https://registry.npmjs.org/osrs-db/latest"


def _get_tarball_url() -> str:
    """Fetch the latest tarball URL from npm registry."""
    resp = requests.get(OSRSDB_NPM_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["dist"]["tarball"]


def ensure_osrsdb_cached(force: bool = False) -> str:
    """
    Download and extract osrs-db data files if not already cached.
    Returns the path to the cache directory containing the JSON files.
    """
    cache_dir = os.path.join(get_cache_path(), "osrs-db")
    os.makedirs(cache_dir, exist_ok=True)

    # Check if already extracted
    marker = os.path.join(cache_dir, "items.g.json")
    if os.path.exists(marker) and not force:
        print(f"  Using cached osrs-db: {cache_dir}")
        return cache_dir

    # Download tarball
    print("  Fetching osrs-db package info from npm...")
    tarball_url = _get_tarball_url()
    print(f"  Downloading: {tarball_url}")

    tgz_path = os.path.join(cache_dir, "osrs-db.tgz")
    resp = requests.get(tarball_url, timeout=120, stream=True)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    with open(tgz_path, "wb") as f:
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r  Downloaded: {downloaded // 1024}KB / {total // 1024}KB ({pct}%)", end="")
    print()

    # Extract data/*.json files
    print("  Extracting JSON data files...")
    with tarfile.open(tgz_path, "r:gz") as tar:
        for member in tar.getmembers():
            # Only extract data/*.g.json files
            if member.name.startswith("package/data/") and member.name.endswith(".json"):
                # Extract to cache_dir with flattened path
                filename = os.path.basename(member.name)
                member.name = filename
                tar.extract(member, cache_dir)
                print(f"    Extracted: {filename}")

    # Clean up tarball
    try:
        os.remove(tgz_path)
    except OSError:
        pass

    print(f"  osrs-db cached at: {cache_dir}")
    return cache_dir
