import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_MCP_ROOT = os.path.dirname(_HERE)
LOCAL_INDEX = os.path.join(_MCP_ROOT, "API v4", "json files", "index.json")
METHODS_FILE = os.path.join(_MCP_ROOT, "index", "methods.json")


def _parse_class_and_href(key: str, package: str) -> tuple:
    pkg_prefix = package.replace(".", "_")
    if key.startswith(pkg_prefix + "_"):
        class_name = key[len(pkg_prefix) + 1:]
    else:
        class_name = key.split("_")[-1]
    return class_name, class_name + ".html"


def parse_local_index() -> list:
    """Parse the local API v4 index.json and return a flat list of method dicts."""
    if not os.path.exists(LOCAL_INDEX):
        raise FileNotFoundError(
            f"API v4 not found. Place the 'API v4' folder in the MCP server root: {_MCP_ROOT}"
        )

    with open(LOCAL_INDEX, encoding="utf-8") as f:
        data = json.load(f)

    methods = []
    for key, class_data in data.items():
        raw_package = class_data.get("package", "")
        # Strip "Package" prefix
        package = raw_package[len("Package"):] if raw_package.startswith("Package") else raw_package

        class_name, href = _parse_class_and_href(key, package)

        for method in class_data.get("methods", []):
            raw_sig = method.get("signature", "")
            raw_desc = method.get("summary", "")

            # Strip zero-width spaces and other unicode artifacts
            sig = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", raw_sig).strip()

            # Collapse newlines in description
            desc = " ".join(raw_desc.split())

            # Extract method name from signature
            match = re.search(r"(\w+)\s*\(", sig)
            if not match:
                continue  # skip fields and non-method entries
            method_name = match.group(1)

            entry = {
                "id": f"{class_name}.{method_name}",
                "class_name": class_name,
                "package": package,
                "href": href,
                "method_signature": sig,
                "description": desc,
                "full_text": f"{class_name} {sig} {desc}",
            }
            methods.append(entry)

    return methods


def build_index() -> list:
    """Parse local index and save to METHODS_FILE. Returns the list of method dicts."""
    methods = parse_local_index()

    os.makedirs(os.path.dirname(METHODS_FILE), exist_ok=True)
    with open(METHODS_FILE, "w", encoding="utf-8") as f:
        json.dump(methods, f, indent=2)

    return methods


def load_index() -> list:
    """Load methods from cache file, building it first if it doesn't exist."""
    if os.path.exists(METHODS_FILE):
        with open(METHODS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return build_index()
