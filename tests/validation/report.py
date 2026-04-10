"""
Phase 2 RAG Validation Report Generator.

Run with:
    python -m tests.validation.report

Outputs validation_report.md in the project root.
"""

import asyncio
import datetime
import re
import sys
import os

# Ensure project root is on sys.path when run as module
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import requests
from bs4 import BeautifulSoup

from tools.search_engine import SearchEngine
from tools.index_builder import load_index
from rag.retriever import Retriever
from rag.store import ChromaStore, sentinel_exists
from tests.validation.conftest import (
    API_EXACT_QUERIES,
    NATURAL_LANGUAGE_QUERIES,
    ITEM_QUERIES,
    NPC_QUERIES,
    SPATIAL_QUERIES,
    LIVE_VERIFY_CLASSES,
)
from tests.validation.test_live_javadocs import _scrape_method_summary, _get_chromadb_methods


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JAVA_IDENT = re.compile(r"^[a-zA-Z_$][a-zA-Z0-9_$]*$")
PRIMITIVES = {"void", "int", "long", "double", "float", "boolean", "byte", "char", "short"}
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
# Section helpers
# ---------------------------------------------------------------------------

def _section_collection_stats(store: ChromaStore) -> tuple[str, dict]:
    counts = {}
    for name in ("api_methods", "spatial", "game_data"):
        counts[name] = store.collection_count(name)

    lines = [
        "## Collection Statistics",
        "",
        f"- api_methods: {counts['api_methods']:,} chunks",
        f"- spatial: {counts['spatial']:,} chunks",
        f"- game_data: {counts['game_data']:,} chunks",
        "",
    ]
    return "\n".join(lines), counts


async def _section_rag_vs_legacy(retriever: Retriever) -> tuple[str, dict]:
    print("  Computing RAG vs Legacy comparison...", flush=True)
    methods = load_index()
    legacy_engine = SearchEngine(methods)

    top1_matches = 0
    top3_found = 0
    top1_mismatches = []
    top3_mismatches = []

    total = len(API_EXACT_QUERIES)
    for query in API_EXACT_QUERIES:
        legacy_results = legacy_engine.search(query, top_k=1)
        legacy_class = legacy_results[0]["class_name"] if legacy_results else None

        # Top-1
        rag_ctx = await retriever.retrieve(query, force_collections=["api_methods"], top_k=1)
        rag_class = rag_ctx.chunks[0].metadata.get("class_name") if rag_ctx.chunks else None

        if legacy_class and rag_class and legacy_class == rag_class:
            top1_matches += 1
        else:
            top1_mismatches.append(
                f"`{query}`: legacy=`{legacy_class}` rag=`{rag_class}`"
            )

        # Top-3
        if legacy_class:
            rag_ctx3 = await retriever.retrieve(query, force_collections=["api_methods"], top_k=3)
            rag_classes = {c.metadata.get("class_name", "") for c in rag_ctx3.chunks}
            if legacy_class in rag_classes:
                top3_found += 1
            else:
                top3_mismatches.append(
                    f"`{query}`: expected=`{legacy_class}` got={sorted(rag_classes)}"
                )

    top1_pct = top1_matches / total * 100 if total else 0
    top3_pct = top3_found / total * 100 if total else 0

    lines = [
        "## RAG vs Legacy Comparison",
        "",
        f"- Top-1 class match rate: {top1_matches}/{total} ({top1_pct:.0f}%)",
        f"- Top-3 class presence rate: {top3_found}/{total} ({top3_pct:.0f}%)",
    ]
    if top1_mismatches:
        lines.append("")
        lines.append("**Top-1 Mismatches:**")
        for m in top1_mismatches:
            lines.append(f"  - {m}")
    if top3_mismatches:
        lines.append("")
        lines.append("**Top-3 Mismatches (not found in any of top-3):**")
        for m in top3_mismatches:
            lines.append(f"  - {m}")
    lines.append("")

    stats = {
        "top1_matches": top1_matches,
        "top3_found": top3_found,
        "total": total,
        "top1_pct": top1_pct,
        "top3_pct": top3_pct,
        "top1_mismatches": top1_mismatches,
        "top3_mismatches": top3_mismatches,
    }
    return "\n".join(lines), stats


def _section_javadocs_coverage(store: ChromaStore) -> tuple[str, dict]:
    print("  Scraping live JavaDocs for coverage stats...", flush=True)
    rows = []
    coverage_data = {}

    for package, href, class_name in LIVE_VERIFY_CLASSES:
        try:
            live_methods = _scrape_method_summary(package, href)
        except Exception as exc:
            rows.append(
                f"| {class_name} | ERROR | - | - | CRITICAL |"
            )
            coverage_data[class_name] = {"error": str(exc)}
            continue

        if not live_methods:
            rows.append(f"| {class_name} | 0 | - | - | WARNING |")
            coverage_data[class_name] = {"live": 0, "in_db": 0, "coverage": 0.0}
            continue

        db_methods = _get_chromadb_methods(store, class_name)
        db_names = {m["name"] for m in db_methods}
        live_names = [m["method_name"] for m in live_methods]
        covered = [n for n in live_names if n in db_names]
        total = len(live_names)
        coverage = len(covered) / total if total else 1.0

        if coverage >= 0.90:
            status = "OK"
        elif coverage >= 0.50:
            status = "WARNING"
        else:
            status = "CRITICAL"

        rows.append(
            f"| {class_name} | {total} | {len(covered)} | {coverage:.0%} | {status} |"
        )
        coverage_data[class_name] = {
            "live": total,
            "in_db": len(covered),
            "coverage": coverage,
            "status": status,
        }

    lines = [
        "## Live JavaDocs Coverage",
        "",
        "| Class | Live Methods | In ChromaDB | Coverage | Status |",
        "|-------|-------------|-------------|----------|--------|",
    ] + rows + [""]

    return "\n".join(lines), coverage_data


async def _section_new_tools(retriever: Retriever) -> tuple[str, dict]:
    print("  Validating new tools (items, NPCs, locations)...", flush=True)

    async def _count_returning(queries, force_coll, extra_filters=None):
        ok = 0
        for query in queries:
            ctx = await retriever.retrieve(
                query,
                force_collections=force_coll,
                extra_filters=extra_filters or {},
                top_k=5,
            )
            if ctx.chunks:
                ok += 1
        return ok

    item_ok = await _count_returning(
        ITEM_QUERIES, ["game_data"],
        extra_filters={"game_data": {"chunk_type": "item"}},
    )
    npc_ok = await _count_returning(
        NPC_QUERIES, ["game_data"],
        extra_filters={"game_data": {"chunk_type": "npc"}},
    )
    spatial_ok = await _count_returning(SPATIAL_QUERIES, ["spatial"])

    lines = [
        "## New Tools Validation",
        "",
        f"- Items: {item_ok}/{len(ITEM_QUERIES)} queries returned results",
        f"- NPCs: {npc_ok}/{len(NPC_QUERIES)} queries returned results",
        f"- Locations: {spatial_ok}/{len(SPATIAL_QUERIES)} queries returned results",
        "",
    ]
    stats = {
        "items": (item_ok, len(ITEM_QUERIES)),
        "npcs": (npc_ok, len(NPC_QUERIES)),
        "spatial": (spatial_ok, len(SPATIAL_QUERIES)),
    }
    return "\n".join(lines), stats


def _section_java_syntax(store: ChromaStore) -> tuple[str, dict]:
    print("  Checking Java syntax in ChromaDB...", flush=True)

    result = store.get_collection("api_methods").get(
        where={"chunk_type": "method"},
        limit=500,
    )
    metadatas = result.get("metadatas", [])
    documents = result.get("documents", [])
    total = len(metadatas)

    # Valid identifiers
    invalid_ids = []
    for meta in metadatas:
        name = meta.get("method_name", "")
        if not name or not JAVA_IDENT.match(name):
            invalid_ids.append(f"{meta.get('class_name', '?')}.{name!r}")
    valid_id_pct = (1 - len(invalid_ids) / total) * 100 if total else 0

    # Valid return types
    unusual_types = []
    for meta in metadatas:
        return_type = meta.get("return_type", "").strip()
        if not return_type:
            unusual_types.append(return_type)
            continue
        base = re.sub(r"<.*>", "", return_type).replace("[]", "").strip()
        if base not in PRIMITIVES and not re.match(r"^(?:[a-z][a-z0-9]*\.)*[A-Z][a-zA-Z0-9_$]*$", base):
            unusual_types.append(return_type)
    valid_type_pct = (1 - len(unusual_types) / total) * 100 if total else 0

    # Deprecated patterns
    dep_violations = []
    for i, doc in enumerate(documents):
        for pattern, description in DEPRECATED_PATTERNS:
            if pattern.search(doc):
                dep_violations.append(description)

    dep_summary = "none found" if not dep_violations else f"{len(dep_violations)} found"

    lines = [
        "## Java Syntax",
        "",
        f"- Valid identifiers: {valid_id_pct:.1f}%",
        f"- Valid return types: {valid_type_pct:.1f}%",
        f"- Deprecated patterns: {dep_summary}",
        "",
    ]
    stats = {
        "valid_id_pct": valid_id_pct,
        "valid_type_pct": valid_type_pct,
        "dep_violations": dep_violations,
        "total_checked": total,
    }
    return "\n".join(lines), stats


def _section_key_findings(
    collection_counts: dict,
    rag_stats: dict,
    coverage_data: dict,
    tools_stats: dict,
    syntax_stats: dict,
) -> str:
    findings = []

    # Collection sizes
    findings.append(
        f"ChromaDB holds {collection_counts.get('api_methods', 0):,} API method chunks, "
        f"{collection_counts.get('spatial', 0):,} spatial chunks, and "
        f"{collection_counts.get('game_data', 0):,} game data chunks."
    )

    # RAG vs Legacy
    findings.append(
        f"RAG top-1 class match rate is {rag_stats['top1_pct']:.0f}% vs legacy keyword engine "
        f"(expected — semantic similarity vs exact keyword match)."
    )
    findings.append(
        f"RAG top-3 class presence rate is {rag_stats['top3_pct']:.0f}% — the correct class "
        f"appears within the top-3 results for {rag_stats['top3_found']}/{rag_stats['total']} queries."
    )

    # Coverage: classify classes
    ok_classes = [cls for cls, d in coverage_data.items() if isinstance(d, dict) and d.get("status") == "OK"]
    warn_classes = [cls for cls, d in coverage_data.items() if isinstance(d, dict) and d.get("status") == "WARNING"]
    critical_classes = [cls for cls, d in coverage_data.items() if isinstance(d, dict) and d.get("status") == "CRITICAL"]

    if ok_classes:
        findings.append(f"Classes with full (>=90%) JavaDocs coverage: {', '.join(ok_classes)}.")
    if warn_classes:
        findings.append(f"Classes with partial (50–89%) coverage: {', '.join(warn_classes)}.")
    if critical_classes:
        findings.append(
            f"Classes with critically low (<50%) coverage: {', '.join(critical_classes)}. "
            f"API v4 Downloader likely missed most methods — re-download recommended."
        )

    # New tools
    i_ok, i_total = tools_stats["items"]
    n_ok, n_total = tools_stats["npcs"]
    s_ok, s_total = tools_stats["spatial"]
    findings.append(
        f"New tools validation: items {i_ok}/{i_total}, NPCs {n_ok}/{n_total}, "
        f"locations {s_ok}/{s_total} queries returned results."
    )

    # Syntax
    findings.append(
        f"Java syntax: {syntax_stats['valid_id_pct']:.1f}% valid identifiers, "
        f"{syntax_stats['valid_type_pct']:.1f}% valid return types, "
        f"deprecated patterns: {'none' if not syntax_stats['dep_violations'] else len(syntax_stats['dep_violations'])} found."
    )

    return "## Key Findings\n\n" + "\n".join(f"- {f}" for f in findings) + "\n"


def _section_recommendations(
    coverage_data: dict,
    rag_stats: dict,
    tools_stats: dict,
) -> str:
    recs = []

    critical_classes = [cls for cls, d in coverage_data.items() if isinstance(d, dict) and d.get("status") == "CRITICAL"]
    warn_classes = [cls for cls, d in coverage_data.items() if isinstance(d, dict) and d.get("status") == "WARNING"]

    if critical_classes:
        recs.append(
            f"**Re-run API v4 Downloader** for low-coverage classes: {', '.join(critical_classes)}. "
            f"These classes have <50% method coverage, indicating the downloader missed pages. "
            f"Check pagination or class name matching in the downloader."
        )
    if warn_classes:
        recs.append(
            f"**Investigate partial coverage** for: {', '.join(warn_classes)}. "
            f"Some methods may be inherited from parent classes or defined in superclasses "
            f"not currently indexed."
        )

    if rag_stats["top3_pct"] < 80:
        recs.append(
            f"**RAG top-3 presence is {rag_stats['top3_pct']:.0f}%** (target ≥80%). "
            f"Consider increasing embedding model quality or chunk overlap for api_methods collection."
        )
    else:
        recs.append(
            f"RAG top-3 presence at {rag_stats['top3_pct']:.0f}% — no tuning needed for retrieval accuracy."
        )

    i_ok, i_total = tools_stats["items"]
    n_ok, n_total = tools_stats["npcs"]
    s_ok, s_total = tools_stats["spatial"]
    if i_ok < i_total or n_ok < n_total or s_ok < s_total:
        recs.append(
            "**Some new-tool queries returned no results.** Verify game_data ingest completed "
            "correctly and all item/NPC data was indexed."
        )
    else:
        recs.append(
            "All new tool queries (items, NPCs, locations) returned results — Phase 3 tool "
            "integration can proceed."
        )

    recs.append(
        "Before Phase 3: resolve CRITICAL coverage classes and confirm top-3 presence ≥80%."
    )

    return "## Recommendations\n\n" + "\n".join(f"- {r}" for r in recs) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def generate_report() -> str:
    print("Generating Phase 2 RAG Validation Report...", flush=True)

    if not sentinel_exists():
        print("ERROR: RAG not initialized — run ingest first.", file=sys.stderr)
        sys.exit(1)

    store = ChromaStore()
    retriever = Retriever(store=store)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("[1/5] Collection statistics...", flush=True)
    stats_section, collection_counts = _section_collection_stats(store)

    print("[2/5] RAG vs Legacy comparison...", flush=True)
    rag_section, rag_stats = await _section_rag_vs_legacy(retriever)

    print("[3/5] Live JavaDocs coverage...", flush=True)
    coverage_section, coverage_data = _section_javadocs_coverage(store)

    print("[4/5] New tools validation...", flush=True)
    tools_section, tools_stats = await _section_new_tools(retriever)

    print("[5/5] Java syntax checks...", flush=True)
    syntax_section, syntax_stats = _section_java_syntax(store)

    findings_section = _section_key_findings(
        collection_counts, rag_stats, coverage_data, tools_stats, syntax_stats
    )
    recs_section = _section_recommendations(coverage_data, rag_stats, tools_stats)

    report = "\n".join([
        "# RAG Validation Report",
        "",
        f"**Generated:** {now}",
        "",
        stats_section,
        rag_section,
        coverage_section,
        tools_section,
        syntax_section,
        findings_section,
        "",
        recs_section,
    ])

    return report


def main():
    report = asyncio.run(generate_report())

    output_path = os.path.join(_PROJECT_ROOT, "validation_report.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport written to: {output_path}", flush=True)

    # Print a brief summary to stdout (encode-safe for Windows console)
    print("\n--- Summary ---", flush=True)
    for line in report.splitlines():
        if line.startswith("- ") or line.startswith("**") or line.startswith("## ") or line.startswith("| "):
            safe_line = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            )
            print(safe_line, flush=True)


if __name__ == "__main__":
    main()
