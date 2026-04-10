"""
RAG vs Legacy SearchEngine comparison tests.

Validates that the new RAG Retriever is at least as capable as the legacy
keyword/semantic SearchEngine across exact API queries and natural language
queries.
"""

import pytest
import pytest_asyncio

from tests.validation.conftest import API_EXACT_QUERIES, NATURAL_LANGUAGE_QUERIES
from tools.search_engine import SearchEngine
from rag.retriever import Retriever


# ---------------------------------------------------------------------------
# Exact API query comparison tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRagVsLegacyExact:
    """Compare legacy engine vs RAG retriever on exact Class.method queries."""

    async def test_exact_queries_top_class_match(self, legacy_engine: SearchEngine, retriever: Retriever):
        """
        For each API_EXACT_QUERIES entry, compare the top-1 class_name returned
        by legacy vs RAG. Assert that at least 80% of queries agree on class.
        """
        matches = 0
        mismatches = []

        for query in API_EXACT_QUERIES:
            # Legacy: sync search, top-1
            legacy_results = legacy_engine.search(query, top_k=1)
            legacy_class = legacy_results[0]["class_name"] if legacy_results else None

            # RAG: async retrieve, forced to api_methods collection, top-1
            rag_ctx = await retriever.retrieve(query, force_collections=["api_methods"], top_k=1)
            rag_class = rag_ctx.chunks[0].metadata.get("class_name") if rag_ctx.chunks else None

            if legacy_class and rag_class and legacy_class == rag_class:
                matches += 1
            else:
                mismatches.append({
                    "query": query,
                    "legacy_class": legacy_class,
                    "rag_class": rag_class,
                })

        total = len(API_EXACT_QUERIES)
        match_rate = matches / total if total > 0 else 0.0

        print(f"\nExact query class match rate: {matches}/{total} ({match_rate:.1%})")
        if mismatches:
            print("Mismatches:")
            for m in mismatches:
                print(f"  [{m['query']}] legacy={m['legacy_class']!r}  rag={m['rag_class']!r}")

        assert match_rate >= 0.80, (
            f"Top-1 class match rate {match_rate:.1%} is below the 80% threshold. "
            f"Mismatches: {mismatches}"
        )

    async def test_no_empty_rag_results(self, legacy_engine: SearchEngine, retriever: Retriever):
        """
        For every query in API_EXACT_QUERIES + NATURAL_LANGUAGE_QUERIES, if the
        legacy engine returns results then RAG must also return at least 1 result.
        """
        all_queries = API_EXACT_QUERIES + NATURAL_LANGUAGE_QUERIES
        failures = []

        for query in all_queries:
            legacy_results = legacy_engine.search(query, top_k=5)
            if not legacy_results:
                # Legacy has nothing — nothing to compare against
                continue

            rag_ctx = await retriever.retrieve(query, force_collections=["api_methods"], top_k=5)
            if len(rag_ctx.chunks) == 0:
                failures.append(query)

        assert not failures, (
            f"RAG returned 0 results for {len(failures)} queries where legacy had results: "
            f"{failures}"
        )


# ---------------------------------------------------------------------------
# Natural language query tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRagVsLegacyNaturalLanguage:
    """Validate RAG retriever behaviour on natural language queries."""

    async def test_natural_language_returns_results(self, retriever: Retriever):
        """Every natural language query must return at least 1 chunk from RAG."""
        empty_queries = []

        for query in NATURAL_LANGUAGE_QUERIES:
            rag_ctx = await retriever.retrieve(query, force_collections=["api_methods"], top_k=5)
            if len(rag_ctx.chunks) == 0:
                empty_queries.append(query)

        assert not empty_queries, (
            f"RAG returned 0 results for {len(empty_queries)} NL queries: {empty_queries}"
        )

    async def test_bank_queries_return_bank_class(self, retriever: Retriever):
        """
        Bank-related natural language queries should surface at least one result
        whose class_name contains 'Bank'.
        """
        bank_queries = [q for q in NATURAL_LANGUAGE_QUERIES if "bank" in q.lower()]
        assert bank_queries, "No bank-related queries found in NATURAL_LANGUAGE_QUERIES"

        failures = []
        for query in bank_queries:
            rag_ctx = await retriever.retrieve(query, force_collections=["api_methods"], top_k=8)
            classes = [
                chunk.metadata.get("class_name", "")
                for chunk in rag_ctx.chunks
            ]
            if not any("Bank" in cls for cls in classes):
                failures.append({"query": query, "classes_returned": classes})

        assert not failures, (
            f"Bank-related queries did not surface any 'Bank' class results: {failures}"
        )

    async def test_walking_queries_return_walking_class(self, retriever: Retriever):
        """
        Walking/movement natural language queries should surface at least one
        result whose class_name contains 'Walking', 'Map', or 'Locatable'.
        """
        walking_queries = [q for q in NATURAL_LANGUAGE_QUERIES if "walk" in q.lower()]
        assert walking_queries, "No walking-related queries found in NATURAL_LANGUAGE_QUERIES"

        walking_classes = {"Walking", "Map", "Locatable"}
        failures = []

        for query in walking_queries:
            rag_ctx = await retriever.retrieve(query, force_collections=["api_methods"], top_k=8)
            classes = {
                chunk.metadata.get("class_name", "")
                for chunk in rag_ctx.chunks
            }
            if not classes.intersection(walking_classes):
                failures.append({"query": query, "classes_returned": sorted(classes)})

        assert not failures, (
            f"Walking queries did not surface Walking/Map/Locatable class results: {failures}"
        )
