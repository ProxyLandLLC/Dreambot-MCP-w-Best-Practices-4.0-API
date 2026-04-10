"""
API chunker — reads pre-built RAG-ready JSON from the API v4 Downloader Tool.

The downloader produces:
  - json/methods.json       — flat array of method entries (ChromaDB-ready)
  - json/class_overviews.json — flat array of class overview entries (ChromaDB-ready)

This chunker simply maps those entries into the ChromaDB chunk format,
handling overload deduplication for IDs.
"""

import json
import os
import re


def _find_json_dir(api_v4_dir: str) -> str:
    """Locate the json/ directory within the API v4 folder structure."""
    # New format: API v4/API v4/json/
    nested = os.path.join(api_v4_dir, "API v4", "json")
    if os.path.isdir(nested):
        return nested

    # Direct: API v4/json/
    direct = os.path.join(api_v4_dir, "json")
    if os.path.isdir(direct):
        return direct

    # Legacy fallback: API v4/json files/
    legacy = os.path.join(api_v4_dir, "json files")
    if os.path.isdir(legacy):
        return legacy

    raise FileNotFoundError(
        f"No json directory found in {api_v4_dir}. "
        "Expected 'API v4/json/' or 'API v4/API v4/json/'."
    )


def chunk_api_docs(api_v4_dir: str) -> tuple[list[dict], list[dict]]:
    """
    Load pre-built RAG-ready JSON and convert to ChromaDB chunk format.

    Returns (method_chunks, class_chunks) where each chunk is:
      {"id": str, "document": str, "metadata": dict}
    """
    json_dir = _find_json_dir(api_v4_dir)

    # Load pre-built data
    methods_path = os.path.join(json_dir, "methods.json")
    overviews_path = os.path.join(json_dir, "class_overviews.json")

    if not os.path.exists(methods_path):
        raise FileNotFoundError(
            f"methods.json not found at {methods_path}. "
            "Run the API v4 Downloader Tool first."
        )

    with open(methods_path, encoding="utf-8") as f:
        methods_data = json.load(f)

    class_chunks = []
    if os.path.exists(overviews_path):
        with open(overviews_path, encoding="utf-8") as f:
            overviews_data = json.load(f)
        class_chunks = _build_class_chunks(overviews_data)

    method_chunks = _build_method_chunks(methods_data)

    return method_chunks, class_chunks


def _build_class_chunks(overviews_data: list[dict]) -> list[dict]:
    """Convert class_overviews.json entries into ChromaDB chunks."""
    chunks = []
    seen_ids: set[str] = set()
    for entry in overviews_data:
        chunk_id = entry.get("id", f"class:{entry.get('package', '')}.{entry.get('class_name', '')}")
        description = entry.get("description", "")
        class_name = entry.get("class_name", "")
        package = entry.get("package", "")

        # Deduplicate class IDs (generics can cause collisions)
        if chunk_id in seen_ids:
            counter = 2
            while f"{chunk_id}_{counter}" in seen_ids:
                counter += 1
            chunk_id = f"{chunk_id}_{counter}"
        seen_ids.add(chunk_id)

        chunks.append({
            "id": chunk_id,
            "document": description,
            "metadata": {
                "chunk_type": "class_overview",
                "class_name": class_name,
                "package": package,
                "extends": entry.get("extends", ""),
                "implements": entry.get("implements", ""),
                "method_count": entry.get("method_count", 0),
                "href": entry.get("href", f"{class_name}.html"),
            },
        })

    return chunks


def _build_method_chunks(methods_data: list[dict]) -> list[dict]:
    """Convert methods.json entries into ChromaDB chunks, deduplicating overload IDs."""
    chunks = []
    seen_ids: set[str] = set()

    for entry in methods_data:
        class_name = entry.get("class_name", "")
        method_name = entry.get("method_name", "")
        package = entry.get("package", "")
        params = entry.get("params", "")
        description = entry.get("description", "")
        full_text = entry.get("full_text", "")

        # Build document text: use full_text if available, else construct it
        if full_text:
            doc_text = full_text
        elif description:
            doc_text = f"{class_name}.{method_name}({params}) — {description}"
        else:
            doc_text = f"{class_name}.{method_name}({params})"

        # Build unique ID using package + class + method + param types
        param_types = _extract_param_types(params)
        method_id = f"method:{package}.{class_name}.{method_name}({param_types})"

        # Handle duplicate IDs (method overloads with same param types)
        if method_id in seen_ids:
            counter = 2
            while f"{method_id}_{counter}" in seen_ids:
                counter += 1
            method_id = f"{method_id}_{counter}"
        seen_ids.add(method_id)

        chunks.append({
            "id": method_id,
            "document": doc_text,
            "metadata": {
                "chunk_type": "method",
                "class_name": class_name,
                "method_name": method_name,
                "package": package,
                "return_type": entry.get("return_type", ""),
                "modifiers": entry.get("modifiers", ""),
                "params": params,
                "param_count": entry.get("param_count", 0),
                "href": entry.get("href", f"{class_name}.html"),
            },
        })

    return chunks


def _extract_param_types(params_str: str) -> str:
    """Extract just the type names from a parameter string for ID uniqueness."""
    if not params_str.strip():
        return ""
    parts = []
    for param in params_str.split(","):
        param = param.strip()
        # Remove annotations like @NonNull
        param = re.sub(r"@\w+\s*", "", param).strip()
        # Take the type (first token)
        tokens = param.split()
        if tokens:
            parts.append(tokens[0])
    return ",".join(parts)
