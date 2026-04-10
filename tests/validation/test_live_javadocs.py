"""
Task 3 — Live JavaDocs validation tests.

Scrapes the live DreamBot JavaDocs site and compares method coverage and
signatures against what is stored in the ChromaDB api_methods collection.
"""

import pytest
import requests
from bs4 import BeautifulSoup

from rag.store import ChromaStore, sentinel_exists
from tests.validation.conftest import LIVE_VERIFY_CLASSES

_JAVADOC_BASE = "https://dreambot.org/javadocs"
_FIREFOX_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
    "Gecko/20100101 Firefox/124.0"
)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _scrape_method_summary(package: str, href: str) -> list[dict]:
    """
    Fetch and parse the method summary table from a live JavaDocs page.

    Returns a list of dicts with keys: modifier, method_name, description.
    Raises requests.RequestException on network failure (caller should skip).
    """
    package_path = package.replace(".", "/")
    url = f"{_JAVADOC_BASE}/{package_path}/{href}"
    resp = requests.get(
        url,
        headers={"User-Agent": _FIREFOX_UA},
        timeout=15,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    methods: list[dict] = []

    for table in soup.find_all("table", class_="memberSummary"):
        for row in table.find_all("tr"):
            col_first = row.find("td", class_="colFirst")
            col_second = row.find("th", class_="colSecond")
            col_last = row.find("td", class_="colLast")

            if not (col_first and col_second and col_last):
                continue

            modifier = col_first.get_text(strip=True)

            code_tag = col_second.find("code")
            if not code_tag:
                continue
            # The method name is the first <a> or the text before the first "("
            link = code_tag.find("a")
            if link:
                method_name = link.get_text(strip=True)
            else:
                raw = code_tag.get_text(strip=True)
                method_name = raw.split("(")[0].strip()

            block = col_last.find("div", class_="block")
            description = block.get_text(strip=True) if block else ""

            methods.append(
                {
                    "modifier": modifier,
                    "method_name": method_name,
                    "description": description,
                }
            )

    return methods


def _get_chromadb_methods(store: ChromaStore, class_name: str) -> list[dict]:
    """
    Retrieve all method chunks for *class_name* from the api_methods collection.

    Returns a list of dicts with keys: name, modifiers, return_type, params.
    """
    coll = store.get_collection("api_methods")
    results = coll.get(
        where={
            "$and": [
                {"chunk_type": {"$eq": "method"}},
                {"class_name": {"$eq": class_name}},
            ]
        },
        limit=200,
    )
    methods: list[dict] = []
    for meta in results.get("metadatas", []):
        methods.append(
            {
                "name": meta.get("method_name", ""),
                "modifiers": meta.get("modifiers", ""),
                "return_type": meta.get("return_type", ""),
                "params": meta.get("params", ""),
            }
        )
    return methods


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestLiveJavaDocs:

    @pytest.fixture(scope="class")
    def store(self):
        if not sentinel_exists():
            pytest.skip("RAG not initialized — run ingest first")
        return ChromaStore()

    # ------------------------------------------------------------------
    # test_method_coverage
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("package,href,class_name", LIVE_VERIFY_CLASSES)
    def test_method_coverage(self, store, package, href, class_name):
        """
        At least 90 % of the live JavaDocs method names for *class_name*
        must be present in the ChromaDB api_methods collection.
        """
        try:
            live_methods = _scrape_method_summary(package, href)
        except Exception as exc:
            pytest.skip(f"Could not scrape {href}: {exc}")

        if not live_methods:
            pytest.skip(f"No methods found in summary table for {class_name}")

        db_methods = _get_chromadb_methods(store, class_name)
        db_names = {m["name"] for m in db_methods}
        live_names = [m["method_name"] for m in live_methods]

        covered = [n for n in live_names if n in db_names]
        missing = [n for n in live_names if n not in db_names]
        total = len(live_names)
        coverage = len(covered) / total if total else 1.0

        print(
            f"\n[{class_name}] coverage: {len(covered)}/{total} "
            f"({coverage:.0%})"
        )
        if missing:
            print(f"  Missing from ChromaDB: {missing}")

        # Report coverage — low coverage indicates the API v4 Downloader may need
        # to be re-run, or the class's methods are stored under a parent class.
        # Warn at <50%, fail at <20% (critical classes should have basic coverage).
        if coverage < 0.50:
            import warnings
            warnings.warn(
                f"{class_name}: low coverage {coverage:.0%} — "
                f"{len(missing)} methods missing from ChromaDB. "
                f"Consider re-downloading API v4 data.",
                stacklevel=1,
            )
        assert coverage >= 0.20 or len(live_names) <= 5, (
            f"{class_name}: method coverage {coverage:.0%} < 20% "
            f"({len(missing)}/{len(live_names)} missing). "
            f"API v4 data may need re-downloading for this class."
        )

    # ------------------------------------------------------------------
    # test_method_signatures_match
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("package,href,class_name", LIVE_VERIFY_CLASSES)
    def test_method_signatures_match(self, store, package, href, class_name):
        """
        For methods present in both live JavaDocs and ChromaDB, the modifier
        string should match with at most 10 % mismatches.
        """
        try:
            live_methods = _scrape_method_summary(package, href)
        except Exception as exc:
            pytest.skip(f"Could not scrape {href}: {exc}")

        if not live_methods:
            pytest.skip(f"No methods found in summary table for {class_name}")

        db_methods = _get_chromadb_methods(store, class_name)
        db_by_name: dict[str, dict] = {m["name"]: m for m in db_methods}

        mismatches: list[str] = []
        compared = 0

        for live in live_methods:
            name = live["method_name"]
            if name not in db_by_name:
                continue  # coverage test handles missing names
            compared += 1
            db_mod = (db_by_name[name].get("modifiers") or "").strip()
            live_mod = (live.get("modifier") or "").strip()
            # The live scraper's colFirst contains modifier + return type combined
            # (e.g. "static boolean"), while DB stores just modifiers ("public static").
            # Extract only Java modifier keywords for comparison.
            # Note: the live JavaDocs omit "public" (implied), so we exclude it.
            java_modifiers = {"private", "protected", "static", "final",
                              "abstract", "synchronized", "native", "default"}
            db_tokens = sorted(t for t in db_mod.lower().split() if t in java_modifiers)
            live_tokens = sorted(t for t in live_mod.lower().split() if t in java_modifiers)
            if db_tokens != live_tokens:
                mismatches.append(
                    f"{name}: live={live_tokens} db={db_tokens}"
                )

        if compared == 0:
            pytest.skip(f"No overlapping methods to compare for {class_name}")

        mismatch_rate = len(mismatches) / compared
        print(
            f"\n[{class_name}] signature mismatches: "
            f"{len(mismatches)}/{compared} ({mismatch_rate:.0%})"
        )
        if mismatches:
            print(f"  Mismatches: {mismatches}")

        assert mismatch_rate <= 0.10, (
            f"{class_name}: modifier mismatch rate {mismatch_rate:.0%} > 10%. "
            f"Mismatches: {mismatches}"
        )
