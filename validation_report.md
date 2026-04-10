# RAG Validation Report

**Generated:** 2026-04-10 18:30:41

## Collection Statistics

- api_methods: 2,231 chunks
- spatial: 863 chunks
- game_data: 27,205 chunks

## RAG vs Legacy Comparison

- Top-1 class match rate: 9/15 (60%)
- Top-3 class presence rate: 10/15 (67%)

**Top-1 Mismatches:**
  - `Inventory.isFull`: legacy=`Inventory` rag=`Equipment`
  - `Inventory.contains`: legacy=`Inventory` rag=`Equipment`
  - `Inventory.getCount`: legacy=`Inventory` rag=`Menu`
  - `GameObjects.closest`: legacy=`GameObjects` rag=`GraphicsObjects`
  - `Sleep.sleep`: legacy=`Sleepable` rag=`Sleep`
  - `Skills.getRealLevel`: legacy=`Skills` rag=`Character`

**Top-3 Mismatches (not found in any of top-3):**
  - `Inventory.isFull`: expected=`Inventory` got=['DepositBox', 'Equipment']
  - `Inventory.contains`: expected=`Inventory` got=['Bank', 'DepositBox', 'Equipment']
  - `Inventory.getCount`: expected=`Inventory` got=['ItemProcessing', 'Menu', 'Mouse']
  - `GameObjects.closest`: expected=`GameObjects` got=['GameObject', 'GraphicsObjects']
  - `Skills.getRealLevel`: expected=`Skills` got=['Character', 'ExperienceListener', 'GameObject']

## Live JavaDocs Coverage

| Class | Live Methods | In ChromaDB | Coverage | Status |
|-------|-------------|-------------|----------|--------|
| Bank | 144 | 144 | 100% | OK |
| Inventory | 119 | 2 | 2% | CRITICAL |
| Walking | 44 | 5 | 11% | CRITICAL |
| NPCs | 17 | 17 | 100% | OK |
| GameObjects | 13 | 1 | 8% | CRITICAL |
| Players | 15 | 15 | 100% | OK |
| Sleep | 13 | 0 | 0% | CRITICAL |
| Skills | 13 | 1 | 8% | CRITICAL |

## New Tools Validation

- Items: 5/5 queries returned results
- NPCs: 5/5 queries returned results
- Locations: 5/5 queries returned results

## Java Syntax

- Valid identifiers: 99.6%
- Valid return types: 99.6%
- Deprecated patterns: none found

## Key Findings

- ChromaDB holds 2,231 API method chunks, 863 spatial chunks, and 27,205 game data chunks.
- RAG top-1 class match rate is 60% vs legacy keyword engine (expected — semantic similarity vs exact keyword match).
- RAG top-3 class presence rate is 67% — the correct class appears within the top-3 results for 10/15 queries.
- Classes with full (>=90%) JavaDocs coverage: Bank, NPCs, Players.
- Classes with critically low (<50%) coverage: Inventory, Walking, GameObjects, Sleep, Skills. API v4 Downloader likely missed most methods — re-download recommended.
- New tools validation: items 5/5, NPCs 5/5, locations 5/5 queries returned results.
- Java syntax: 99.6% valid identifiers, 99.6% valid return types, deprecated patterns: none found.


## Recommendations

- **Re-run API v4 Downloader** for low-coverage classes: Inventory, Walking, GameObjects, Sleep, Skills. These classes have <50% method coverage, indicating the downloader missed pages. Check pagination or class name matching in the downloader.
- **RAG top-3 presence is 67%** (target ≥80%). Consider increasing embedding model quality or chunk overlap for api_methods collection.
- All new tool queries (items, NPCs, locations) returned results — Phase 3 tool integration can proceed.
- Before Phase 3: resolve CRITICAL coverage classes and confirm top-3 presence ≥80%.
