"""
Java syntax validation tests for DreamBot MCP Server's RAG system.

Validates that:
- Method names are valid Java identifiers
- Return types are valid Java types
- No deprecated 3.x API patterns exist in documents
- The dreambot_tile tool generates syntactically correct Java code
"""

import re
import pytest
import pytest_asyncio

from rag.store import ChromaStore, sentinel_exists
from tools.dreambot_tile import handle_dreambot_tile_tool


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

JAVA_IDENT = re.compile(r"^[a-zA-Z_$][a-zA-Z0-9_$]*$")

DEPRECATED_PATTERNS = [
    (re.compile(r"extends\s+MethodProvider"), "extends MethodProvider"),
    (re.compile(r"getBank\(\)"), "getBank()"),
    (re.compile(r"getInventory\(\)"), "getInventory()"),
    (re.compile(r"getWalking\(\)"), "getWalking()"),
    (re.compile(r"getNpcs\(\)"), "getNpcs()"),
    (re.compile(r"getPlayers\(\)\.getLocal\(\)"), "getPlayers().getLocal()"),
    (re.compile(r"Players\.getLocal\(\)"), "Players.getLocal()"),
]


# ---------------------------------------------------------------------------
# TestJavaSyntaxInChromaDB
# ---------------------------------------------------------------------------

class TestJavaSyntaxInChromaDB:
    """Validates Java syntax accuracy of method data stored in ChromaDB."""

    @pytest.fixture(scope="class")
    def store(self):
        if not sentinel_exists():
            pytest.skip("RAG not initialized — run ingest first")
        return ChromaStore()

    def test_method_names_are_valid_identifiers(self, store):
        """All method_name values must be valid Java identifiers."""
        result = store.get_collection("api_methods").get(
            where={"chunk_type": "method"},
            limit=500,
        )
        metadatas = result.get("metadatas", [])
        assert metadatas, "No method metadata returned from ChromaDB"

        invalid = []
        for meta in metadatas:
            name = meta.get("method_name", "")
            if not name or not JAVA_IDENT.match(name):
                invalid.append(name)

        assert not invalid, (
            f"Found {len(invalid)} invalid Java identifiers: {invalid[:10]}"
        )

    def test_return_types_are_valid(self, store):
        """Return types should be void, primitives, or UpperCamelCase class names. Allow up to 5% unusual."""
        result = store.get_collection("api_methods").get(
            where={"chunk_type": "method"},
            limit=500,
        )
        metadatas = result.get("metadatas", [])
        assert metadatas, "No method metadata returned from ChromaDB"

        # Valid Java primitives and void
        primitives = {"void", "int", "long", "double", "float", "boolean", "byte", "char", "short"}

        # Pattern for valid Java return type: primitives, UpperCamelCase, or generic/array variants
        valid_type_pattern = re.compile(
            r"^(void|int|long|double|float|boolean|byte|char|short"
            r"|[A-Z][a-zA-Z0-9_$]*"           # UpperCamelCase class
            r"(?:<[^>]+>)?"                    # optional generic
            r"(?:\[\])*"                       # optional array brackets
            r"|[a-z][a-zA-Z0-9_$]*(?:\[\])*)$"  # lowercase (primitives already covered, but for arrays)
        )

        unusual = []
        for meta in metadatas:
            return_type = meta.get("return_type", "").strip()
            if not return_type:
                unusual.append(return_type)
                continue
            # Strip array suffixes and generics for base check
            base = re.sub(r"<.*>", "", return_type).replace("[]", "").strip()
            if base not in primitives and not re.match(r"^[A-Z][a-zA-Z0-9_$]*$", base):
                unusual.append(return_type)

        total = len(metadatas)
        unusual_pct = len(unusual) / total if total > 0 else 0
        assert unusual_pct <= 0.05, (
            f"{len(unusual)}/{total} ({unusual_pct:.1%}) return types are unusual — exceeds 5% threshold. "
            f"Examples: {unusual[:10]}"
        )

    def test_no_deprecated_patterns_in_documents(self, store):
        """No method documents should contain deprecated DreamBot 3.x API patterns."""
        result = store.get_collection("api_methods").get(
            where={"chunk_type": "method"},
            limit=500,
        )
        documents = result.get("documents", [])
        assert documents, "No documents returned from ChromaDB"

        violations = []
        for i, doc in enumerate(documents):
            for pattern, description in DEPRECATED_PATTERNS:
                if pattern.search(doc):
                    violations.append({
                        "doc_index": i,
                        "deprecated_pattern": description,
                        "snippet": doc[:120],
                    })

        assert not violations, (
            f"Found {len(violations)} deprecated 3.x pattern(s) in documents: "
            f"{violations[:5]}"
        )


# ---------------------------------------------------------------------------
# TestTileOutputSyntax
# ---------------------------------------------------------------------------

class TestTileOutputSyntax:
    """Validates that the dreambot_tile tool generates correct Java code."""

    @pytest.mark.asyncio
    async def test_tile_url_output_syntax(self):
        """Tile tool output for known coordinates should contain correct Java snippets."""
        result = await handle_dreambot_tile_tool({"x": 3222, "y": 3218, "z": 0})
        assert result and len(result) == 1, "Expected exactly one TextContent result"
        text = result[0].text

        # Assert required Java snippets are present
        assert "new Tile(3222, 3218, 0)" in text, "Missing: new Tile(3222, 3218, 0)"
        assert "new Area(" in text, "Missing: new Area("
        assert "Walking.walk(new Tile(" in text, "Missing: Walking.walk(new Tile("
        assert "Sleep.sleepUntil(() ->" in text, "Missing: Sleep.sleepUntil(() ->"
        assert "Players.localPlayer()" in text, "Missing: Players.localPlayer()"

        # Assert no deprecated 3.x patterns
        for pattern, description in DEPRECATED_PATTERNS:
            assert not pattern.search(text), (
                f"Output contains deprecated pattern '{description}'"
            )

    @pytest.mark.asyncio
    async def test_tile_area_syntax_correct(self):
        """Area coordinates should be center ±15 tiles."""
        result = await handle_dreambot_tile_tool({"x": 3000, "y": 3000, "z": 0})
        assert result and len(result) == 1, "Expected exactly one TextContent result"
        text = result[0].text

        # x=3000, y=3000, r=15 => Area(2985, 2985, 3015, 3015)
        assert "new Area(2985, 2985, 3015, 3015)" in text, (
            f"Expected 'new Area(2985, 2985, 3015, 3015)' in output.\nActual output:\n{text}"
        )
