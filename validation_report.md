# RAG Validation Report

**Generated:** 2026-04-10 18:43:01

## Collection Statistics

- api_methods: 5,334 chunks
- spatial: 863 chunks
- game_data: 27,205 chunks

## RAG vs Legacy Comparison

- Top-1 class match rate: 14/15 (93%)
- Top-3 class presence rate: 15/15 (100%)

**Top-1 Mismatches:**
  - `Bank.isOpen`: legacy=`Bank` rag=`BankTab`

## Live JavaDocs Coverage

| Class | Live Methods | In ChromaDB | Coverage | Status |
|-------|-------------|-------------|----------|--------|
| Bank | 144 | 144 | 100% | OK |
| Inventory | 119 | 117 | 98% | OK |
| Walking | 44 | 39 | 89% | WARNING |
| NPCs | 17 | 17 | 100% | OK |
| GameObjects | 13 | 12 | 92% | OK |
| Players | 15 | 15 | 100% | OK |
| Sleep | 13 | 13 | 100% | OK |
| Skills | 13 | 12 | 92% | OK |

## New Tools Validation

- Items: 5/5 queries returned results
- NPCs: 5/5 queries returned results
- Locations: 5/5 queries returned results

## Java Syntax

- Valid identifiers: 100.0%
- Valid return types: 99.6%
- Deprecated patterns: none found

## Key Findings

- ChromaDB holds 5,334 API method chunks, 863 spatial chunks, and 27,205 game data chunks.
- RAG top-1 class match rate is 93% vs legacy keyword engine (expected — semantic similarity vs exact keyword match).
- RAG top-3 class presence rate is 100% — the correct class appears within the top-3 results for 15/15 queries.
- Classes with full (>=90%) JavaDocs coverage: Bank, Inventory, NPCs, GameObjects, Players, Sleep, Skills.
- Classes with partial (50–89%) coverage: Walking.
- New tools validation: items 5/5, NPCs 5/5, locations 5/5 queries returned results.
- Java syntax: 100.0% valid identifiers, 99.6% valid return types, deprecated patterns: none found.


## Recommendations

- **Investigate partial coverage** for: Walking. Some methods may be inherited from parent classes or defined in superclasses not currently indexed.
- RAG top-3 presence at 100% — no tuning needed for retrieval accuracy.
- All new tool queries (items, NPCs, locations) returned results — Phase 3 tool integration can proceed.
- Before Phase 3: resolve CRITICAL coverage classes and confirm top-3 presence ≥80%.
