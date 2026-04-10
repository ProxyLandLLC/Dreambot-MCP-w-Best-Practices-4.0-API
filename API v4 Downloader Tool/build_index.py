#!/usr/bin/env python3
"""
build_index.py — Parses JavaDoc HTML into RAG-optimized Markdown, index.json, and methods.json.

No external tools required (no Pandoc). Uses BeautifulSoup to extract rich class/method
data from the HTML method-detail sections, producing output optimized for the Dreambot
MCP Server's search and retrieval pipeline.

Usage:
    python build_index.py --html-dir "path/to/html files"
                          --out-dir  "path/to/output"
"""

import argparse
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup, Tag

# ──────────────────────────────────────────────
# HTML Parsing — extract rich class metadata
# ──────────────────────────────────────────────

_ZWS = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def _clean(text: str) -> str:
    """Strip zero-width chars, collapse whitespace, strip outer whitespace."""
    text = _ZWS.sub("", text)
    return " ".join(text.split()).strip()


def _parse_signature(signature: str) -> dict:
    """
    Parse a Java method signature into structured components.
    E.g. "public static boolean open()" ->
         {modifiers: "public static", return_type: "boolean", params: "", param_count: 0}
    E.g. "public static void withdraw(String name, int amount)" ->
         {modifiers: "public static", return_type: "void", params: "String name, int amount", param_count: 2}
    """
    sig = signature.strip()
    result = {"modifiers": "", "return_type": "", "params": "", "param_count": 0}

    # Extract params from parentheses
    paren_match = re.search(r"\(([^)]*)\)", sig)
    if paren_match:
        params_str = paren_match.group(1).strip()
        result["params"] = params_str
        if params_str:
            # Count parameters by splitting on commas, accounting for generics like Map<K,V>
            depth = 0
            count = 1
            for ch in params_str:
                if ch in "<(":
                    depth += 1
                elif ch in ">)":
                    depth -= 1
                elif ch == "," and depth == 0:
                    count += 1
            result["param_count"] = count
        sig_before_params = sig[:paren_match.start()].strip()
    else:
        sig_before_params = sig

    # Split the pre-params part into tokens
    # E.g. "public static @NonNull boolean" -> ["public", "static", "@NonNull", "boolean"]
    tokens = sig_before_params.split()

    # Known Java modifiers
    java_modifiers = {
        "public", "private", "protected", "static", "final", "abstract",
        "synchronized", "native", "default", "strictfp",
    }

    mod_tokens = []
    remaining = []
    for token in tokens:
        if token.lower() in java_modifiers:
            mod_tokens.append(token)
        elif token.startswith("@"):
            # Annotations like @NonNull, @Nullable — skip, not modifiers
            continue
        else:
            remaining.append(token)

    result["modifiers"] = " ".join(mod_tokens)

    # Last remaining token is the method name, everything before is return type
    if len(remaining) >= 2:
        result["return_type"] = " ".join(remaining[:-1])
    elif len(remaining) == 1:
        # Could be just the method name (constructors) or just return type
        result["return_type"] = remaining[0]

    return result


def _extract_type_kind(soup: BeautifulSoup) -> str:
    """Determine if this is a class, interface, enum, or annotation."""
    pre = soup.find("pre")
    if not pre:
        return "class"
    text = pre.get_text(" ", strip=True).lower()
    if "interface" in text:
        return "interface"
    if "enum" in text:
        return "enum"
    if "@interface" in text or "annotation" in text:
        return "annotation"
    return "class"


def _extract_inheritance(soup: BeautifulSoup) -> list[str]:
    """Extract the inheritance chain from the nested ul.inheritance tree.

    JavaDoc nests these as:
      <ul class="inheritance">
        <li>java.lang.Object</li>
        <li><ul class="inheritance">
          <li>MiddleClass</li>
          <li><ul class="inheritance"><li>ThisClass</li></ul></li>
        </ul></li>
      </ul>

    We walk the nesting top-down collecting the first leaf <li> at each level.
    """
    chain = []
    current_ul = soup.find("ul", {"class": "inheritance"})
    while current_ul:
        # At each ul level, the first <li> without a nested ul is the class name
        next_ul = None
        for li in current_ul.find_all("li", recursive=False):
            nested = li.find("ul", {"class": "inheritance"})
            if nested:
                next_ul = nested
            else:
                text = _clean(li.get_text())
                if text:
                    chain.append(text)
        current_ul = next_ul

    return chain


def _extract_interfaces(soup: BeautifulSoup) -> list[str]:
    """Extract implemented/extended interfaces from the description block."""
    interfaces = []
    for dt in soup.find_all("dt"):
        label = dt.get_text(strip=True).lower()
        if "implements" in label or "superinterfaces" in label:
            dd = dt.find_next_sibling("dd")
            if dd:
                for a in dd.find_all("a"):
                    interfaces.append(_clean(a.get_text()))
    return interfaces


def _extract_class_description(soup: BeautifulSoup) -> str:
    """Extract the class-level description text."""
    desc_div = soup.find("div", {"class": "description"})
    if not desc_div:
        return ""
    block = desc_div.find("div", {"class": "block"})
    if block:
        return _clean(block.get_text())
    return ""


def _parse_dl_docs(dl: Tag | None) -> dict:
    """Parse a <dl> tag containing param/return/throws documentation."""
    docs = {"params": {}, "returns": "", "throws": {}, "since": "", "see": []}
    if not dl:
        return docs

    current_label = ""
    for child in dl.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "dt":
            text = child.get_text(strip=True).lower()
            if "param" in text:
                current_label = "params"
            elif "return" in text:
                current_label = "returns"
            elif "throws" in text or "exception" in text:
                current_label = "throws"
            elif "since" in text:
                current_label = "since"
            elif "see" in text:
                current_label = "see"
            else:
                current_label = ""
        elif child.name == "dd":
            val = _clean(child.get_text())
            if current_label == "params":
                # Format: "paramName - description"
                parts = val.split(" - ", 1)
                if len(parts) == 2:
                    docs["params"][parts[0].strip()] = parts[1].strip()
                else:
                    # Sometimes just "paramName description"
                    parts = val.split(" ", 1)
                    if len(parts) == 2:
                        docs["params"][parts[0].strip()] = parts[1].strip()
            elif current_label == "returns":
                docs["returns"] = val
            elif current_label == "throws":
                parts = val.split(" - ", 1)
                if len(parts) == 2:
                    docs["throws"][parts[0].strip()] = parts[1].strip()
                else:
                    docs["throws"][val] = ""
            elif current_label == "since":
                docs["since"] = val
            elif current_label == "see":
                docs["see"].append(val)
    return docs


def _extract_method_details(soup: BeautifulSoup) -> dict[str, dict]:
    """
    Parse the method.detail section for full method docs.
    Returns {method_anchor: {signature, description, params, returns, throws}}.
    """
    details = {}

    # Find the method.detail anchor
    detail_anchor = soup.find("a", {"id": "method.detail"})
    if not detail_anchor:
        return details

    # Walk the blockList items after the anchor
    container = detail_anchor.find_parent("li") or detail_anchor.find_parent("section")
    if not container:
        return details

    for block in container.find_all("ul", {"class": "blockList"}, recursive=False):
        for li in block.find_all("li", {"class": "blockList"}, recursive=False):
            h4 = li.find("h4")
            if not h4:
                continue
            method_name = _clean(h4.get_text())

            sig_pre = li.find("pre", {"class": "methodSignature"})
            signature = _clean(sig_pre.get_text()) if sig_pre else ""

            desc_block = li.find("div", {"class": "block"})
            description = _clean(desc_block.get_text()) if desc_block else ""

            dl = li.find("dl")
            dl_docs = _parse_dl_docs(dl)

            # Build a key from method name (may have overloads, we'll key by signature)
            details[signature or method_name] = {
                "name": method_name,
                "signature": signature,
                "description": description,
                **dl_docs,
            }

    return details


def _extract_summary_methods(soup: BeautifulSoup) -> list[dict]:
    """
    Extract methods from the memberSummary table (summary section).
    Returns list of {modifier, signature_text, summary}.
    """
    methods = []
    # Find the method summary table specifically — some classes have multiple
    # memberSummary tables (Constructor Summary, Method Summary, etc.)
    method_table = None
    for table in soup.find_all("table", {"class": "memberSummary"}):
        caption = table.find("caption")
        if caption and "Method" in caption.get_text(strip=True):
            method_table = caption.find_parent("table")
            break
    if not method_table:
        # Fallback: try the first memberSummary table
        method_table = soup.find("table", {"class": "memberSummary"})
    if not method_table:
        return methods

    for row in method_table.find_all("tr"):
        modifier_td = row.find("td", {"class": "colFirst"})
        name_th = row.find("th", {"class": "colSecond"})
        desc_td = row.find("td", {"class": "colLast"})

        if not (modifier_td and name_th):
            continue

        modifier = _clean(modifier_td.get_text())
        sig_el = name_th.find("code")
        if not sig_el:
            continue
        sig_text = _clean(sig_el.get_text())

        summary = ""
        if desc_td:
            block = desc_td.find("div", {"class": "block"})
            if block:
                summary = _clean(block.get_text())

        methods.append({
            "modifier": modifier,
            "signature_text": sig_text,
            "summary": summary,
        })

    return methods


def _extract_enum_constants(soup: BeautifulSoup) -> list[dict]:
    """Extract enum constant names and descriptions."""
    constants = []
    # Look for enum constant summary table
    for table in soup.find_all("table", {"class": "memberSummary"}):
        caption = table.find("caption")
        if caption and "enum" in caption.get_text(strip=True).lower():
            for row in table.find_all("tr"):
                name_th = row.find("th", {"class": "colSecond"})
                desc_td = row.find("td", {"class": "colLast"})
                if not name_th:
                    continue
                code = name_th.find("code")
                name = _clean(code.get_text()) if code else _clean(name_th.get_text())
                desc = ""
                if desc_td:
                    block = desc_td.find("div", {"class": "block"})
                    desc = _clean(block.get_text()) if block else ""
                constants.append({"name": name, "description": desc})
    return constants


def _extract_fields(soup: BeautifulSoup) -> list[dict]:
    """Extract field summary entries."""
    fields = []
    for table in soup.find_all("table", {"class": "memberSummary"}):
        caption = table.find("caption")
        if not caption:
            continue
        cap_text = caption.get_text(strip=True).lower()
        if "field" not in cap_text:
            continue
        for row in table.find_all("tr"):
            type_td = row.find("td", {"class": "colFirst"})
            name_th = row.find("th", {"class": "colSecond"})
            desc_td = row.find("td", {"class": "colLast"})
            if not (type_td and name_th):
                continue
            field_type = _clean(type_td.get_text())
            code = name_th.find("code")
            field_name = _clean(code.get_text()) if code else _clean(name_th.get_text())
            desc = ""
            if desc_td:
                block = desc_td.find("div", {"class": "block"})
                desc = _clean(block.get_text()) if block else ""
            fields.append({"name": field_name, "type": field_type, "description": desc})
    return fields


def parse_class_html(html_path: Path) -> dict | None:
    """
    Parse a JavaDoc HTML file and extract all available class metadata.
    Returns a rich dict or None if not a valid class page.
    """
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find(["h1", "h2"], {"class": "title"})
    if not title_el:
        return None

    raw_title = _clean(title_el.get_text())
    # Strip "Class ", "Interface ", "Enum ", "Annotation Type " prefixes
    title_text = re.sub(
        r"^(Class|Interface|Enum|Annotation\s+Type)\s+", "", raw_title
    )

    # Package
    package = ""
    subtitle = soup.find("div", {"class": "subTitle"})
    if subtitle:
        # Find the <a> tag inside (cleaner) or fall back to text
        pkg_link = subtitle.find("a")
        if pkg_link:
            package = _clean(pkg_link.get_text())
        else:
            raw = _clean(subtitle.get_text())
            # Strip leading "Package" label
            package = raw[len("Package"):].strip() if raw.startswith("Package") else raw

    type_kind = _extract_type_kind(soup)
    inheritance = _extract_inheritance(soup)
    interfaces = _extract_interfaces(soup)
    class_desc = _extract_class_description(soup)

    # Method summary (quick signatures + one-line descriptions)
    summary_methods = _extract_summary_methods(soup)

    # Method details (full docs: params, returns, throws)
    method_details = _extract_method_details(soup)

    # Merge summary + detail into rich method entries.
    # Track which detail entries have been consumed to avoid duplicate matches.
    methods = []
    consumed_detail_keys: set[str] = set()

    for sm in summary_methods:
        modifier = sm["modifier"]
        sig_text = sm["signature_text"]
        full_sig = f"{modifier} {sig_text}".strip()

        # Extract method name from summary signature
        name_match = re.search(r"(\w+)\s*[(\u200b]", sig_text)
        method_name = name_match.group(1) if name_match else sig_text.split("(")[0].strip()

        # Try to match with a detail entry (exact overload first, then loose)
        matched_detail = None
        matched_key = None

        # Pass 1: match by name + param count
        for detail_key, detail in method_details.items():
            if detail_key in consumed_detail_keys:
                continue
            if detail["name"] == method_name and _sig_matches(sig_text, detail["signature"]):
                matched_detail = detail
                matched_key = detail_key
                break

        # Pass 2: match by name only (first unconsumed)
        if not matched_detail:
            for detail_key, detail in method_details.items():
                if detail_key in consumed_detail_keys:
                    continue
                if detail["name"] == method_name:
                    matched_detail = detail
                    matched_key = detail_key
                    break

        if matched_key:
            consumed_detail_keys.add(matched_key)

        final_sig = matched_detail["signature"] if matched_detail else full_sig
        parsed = _parse_signature(final_sig)

        entry = {
            "name": method_name,
            "signature": final_sig,
            "modifiers": parsed["modifiers"],
            "return_type": parsed["return_type"],
            "params_str": parsed["params"],
            "param_count": parsed["param_count"],
            "summary": sm["summary"],
            "description": matched_detail["description"] if matched_detail else sm["summary"],
            "param_docs": matched_detail["params"] if matched_detail else {},
            "returns": matched_detail["returns"] if matched_detail else "",
            "throws": matched_detail["throws"] if matched_detail else {},
        }
        methods.append(entry)

    # Enum constants
    enum_constants = _extract_enum_constants(soup) if type_kind == "enum" else []

    # Fields
    fields = _extract_fields(soup)

    return {
        "title": title_text,
        "package": package,
        "type": type_kind,
        "inheritance": inheritance,
        "interfaces": interfaces,
        "description": class_desc,
        "methods": methods,
        "enum_constants": enum_constants,
        "fields": fields,
    }


def _sig_matches(summary_sig: str, detail_sig: str) -> bool:
    """Rough check if two signatures refer to the same overload."""
    # Count commas as a proxy for parameter count
    s_commas = summary_sig.count(",")
    d_commas = detail_sig.count(",")
    if s_commas != d_commas:
        return False
    # Check if both have no params
    if "()" in summary_sig and "()" in detail_sig:
        return True
    return s_commas == d_commas


# ──────────────────────────────────────────────
# Markdown Generation — RAG-optimized output
# ──────────────────────────────────────────────

def generate_markdown(class_data: dict) -> str:
    """Generate a RAG-optimized Markdown document for a single class."""
    lines = []

    # Inheritance: last item is the class itself, parents are everything before it
    parents = class_data["inheritance"][:-1] if len(class_data["inheritance"]) > 1 else []
    direct_parent = parents[-1] if parents else ""

    # YAML frontmatter
    lines.append("---")
    lines.append(f"class: {class_data['title']}")
    lines.append(f"package: {class_data['package']}")
    lines.append(f"type: {class_data['type']}")
    if direct_parent:
        lines.append(f"extends: {direct_parent}")
    if class_data["interfaces"]:
        lines.append(f"implements: [{', '.join(class_data['interfaces'])}]")
    lines.append("---")
    lines.append("")

    # Title and metadata
    lines.append(f"# {class_data['title']}")
    lines.append("")
    lines.append(f"**Package:** `{class_data['package']}`")
    if parents:
        lines.append(f"**Extends:** `{' > '.join(parents)}`")
    if class_data["interfaces"]:
        lines.append(f"**Implements:** {', '.join(f'`{i}`' for i in class_data['interfaces'])}")
    lines.append("")

    if class_data["description"]:
        lines.append(class_data["description"])
        lines.append("")

    # Enum constants
    if class_data.get("enum_constants"):
        lines.append("## Enum Constants")
        lines.append("")
        for const in class_data["enum_constants"]:
            lines.append(f"### {const['name']}")
            if const["description"]:
                lines.append(f"{const['description']}")
            lines.append("")

    # Fields
    if class_data.get("fields"):
        lines.append("## Fields")
        lines.append("")
        for field in class_data["fields"]:
            lines.append(f"- `{field['type']}` **{field['name']}** — {field['description']}")
        lines.append("")

    # Methods
    if class_data["methods"]:
        lines.append("## Methods")
        lines.append("")
        for method in class_data["methods"]:
            lines.append(f"### {method['name']}")
            lines.append("")
            lines.append("```java")
            lines.append(method["signature"])
            lines.append("```")
            lines.append("")

            if method["description"]:
                lines.append(method["description"])
                lines.append("")

            if method.get("param_docs"):
                lines.append("**Parameters:**")
                for pname, pdesc in method["param_docs"].items():
                    lines.append(f"- `{pname}` — {pdesc}")
                lines.append("")

            if method["returns"]:
                lines.append(f"**Returns:** {method['returns']}")
                lines.append("")

            if method["throws"]:
                lines.append("**Throws:**")
                for tname, tdesc in method["throws"].items():
                    line = f"- `{tname}`"
                    if tdesc:
                        line += f" — {tdesc}"
                    lines.append(line)
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# Index Generation — JSON outputs for MCP
# ──────────────────────────────────────────────

def build_index_json(all_classes: dict[str, dict]) -> dict:
    """
    Build the enhanced index.json with full class metadata.
    Structure: {file_key: {package, type, description, inheritance, interfaces, methods, ...}}
    """
    return all_classes


def build_methods_json(all_classes: dict[str, dict]) -> list[dict]:
    """
    Build the flat methods.json for the MCP search engine and ChromaDB ingest pipeline.

    Each method entry includes chunker-ready metadata fields matching the ChromaDB
    api_methods collection schema from the RAG architecture spec:
      id, class_name, method_name, package, href, method_signature,
      modifiers, return_type, params, param_count, description, full_text
    """
    methods = []
    for file_key, class_data in all_classes.items():
        package = class_data["package"]
        title = class_data["title"]
        class_name = title.split()[-1] if " " in title else title
        href = class_name + ".html"

        for method in class_data["methods"]:
            sig = method["signature"]
            desc = method["description"] or method["summary"]

            # Build rich full_text for semantic/keyword search
            param_doc_text = " ".join(
                f"{k} {v}" for k, v in method.get("param_docs", {}).items()
            )
            returns_text = method.get("returns", "")
            full_text = f"{class_name} {sig} {desc} {param_doc_text} {returns_text}".strip()

            entry = {
                # Identity
                "id": f"{class_name}.{method['name']}",
                "class_name": class_name,
                "method_name": method["name"],
                "package": package,
                "href": href,
                # Signature (raw + parsed components for ChromaDB metadata)
                "method_signature": sig,
                "modifiers": method.get("modifiers", ""),
                "return_type": method.get("return_type", ""),
                "params": method.get("params_str", ""),
                "param_count": method.get("param_count", 0),
                # Content
                "description": desc,
                "full_text": full_text,
            }
            methods.append(entry)

        # Also index enum constants for search
        for const in class_data.get("enum_constants", []):
            full_text = f"{class_name} {const['name']} {const['description']}".strip()
            methods.append({
                "id": f"{class_name}.{const['name']}",
                "class_name": class_name,
                "method_name": const["name"],
                "package": package,
                "href": href,
                "method_signature": const["name"],
                "modifiers": "",
                "return_type": "",
                "params": "",
                "param_count": 0,
                "description": const["description"],
                "full_text": full_text,
            })

    return methods


def build_class_overviews_json(all_classes: dict[str, dict]) -> list[dict]:
    """
    Build class overview entries for the ChromaDB api_methods collection.

    Each entry matches the class_overview chunk schema from the RAG architecture spec:
      class_name, package, extends, implements, method_count, href, description, key_methods
    """
    overviews = []
    for file_key, class_data in all_classes.items():
        title = class_data["title"]
        class_name = title.split()[-1] if " " in title else title
        package = class_data["package"]

        parents = class_data["inheritance"][:-1] if len(class_data["inheritance"]) > 1 else []
        direct_parent = parents[-1] if parents else ""

        method_names = [m["name"] for m in class_data["methods"]]
        # Deduplicate while preserving order (overloads → one mention)
        seen = set()
        unique_methods = []
        for name in method_names:
            if name not in seen:
                seen.add(name)
                unique_methods.append(name)

        key_methods = ", ".join(unique_methods[:15])
        if len(unique_methods) > 15:
            key_methods += f", ... ({len(unique_methods)} total)"

        desc = class_data.get("description", "")
        overview_text = (
            f"{class_name} — {desc}" if desc
            else f"{class_name} — {class_data['type'].capitalize()} in {package}."
        )
        overview_text += f" Package: {package}."
        if direct_parent and direct_parent != "java.lang.Object":
            overview_text += f" Extends: {direct_parent}."
        if class_data["interfaces"]:
            overview_text += f" Implements: {', '.join(class_data['interfaces'])}."
        if key_methods:
            overview_text += f" Key methods: {key_methods}."

        overviews.append({
            "id": f"class:{package}.{class_name}",
            "class_name": class_name,
            "package": package,
            "type": class_data["type"],
            "extends": direct_parent,
            "implements": ", ".join(class_data["interfaces"]),
            "method_count": len(class_data["methods"]),
            "href": class_name + ".html",
            "description": overview_text,
        })

    return overviews


def build_packages_json(all_classes: dict[str, dict]) -> dict[str, list[str]]:
    """Build a package -> [class_names] mapping."""
    packages: dict[str, list[str]] = {}
    for file_key, class_data in all_classes.items():
        pkg = class_data["package"]
        title = class_data["title"]
        class_name = title.split()[-1] if " " in title else title
        packages.setdefault(pkg, []).append(class_name)
    for pkg in packages:
        packages[pkg].sort()
    return dict(sorted(packages.items()))


# ──────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────

def build_all(html_dir: Path, out_dir: Path):
    """
    Full pipeline:
      1. Parse every .html in html_dir
      2. Generate RAG Markdown in out_dir/markdown/
      3. Generate index.json in out_dir/json/           (full class metadata)
      4. Generate methods.json in out_dir/json/          (flat, ChromaDB-ready method chunks)
      5. Generate class_overviews.json in out_dir/json/  (ChromaDB-ready class overview chunks)
      6. Generate packages.json in out_dir/json/         (package → class mapping)
    """
    html_dir = Path(html_dir)
    out_dir = Path(out_dir)

    html_files = sorted(html_dir.glob("*.html"))
    total = len(html_files)

    if total == 0:
        print("No HTML files found. Run downloader.py first.")
        return

    md_dir = out_dir / "markdown"
    json_dir = out_dir / "json"

    for d in [md_dir, json_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    # Phase 1: Parse all HTML
    print(f"\nPhase 1: Parsing {total} HTML files...")
    all_classes: dict[str, dict] = {}
    skipped = 0
    for i, html_path in enumerate(html_files, 1):
        print(f"  [{i}/{total}] Parsing {html_path.name}...")
        class_data = parse_class_html(html_path)
        if class_data:
            all_classes[html_path.stem] = class_data
        else:
            skipped += 1

    parsed = len(all_classes)
    print(f"  Parsed {parsed} classes ({skipped} non-class files skipped).")

    # Phase 2: Generate Markdown
    print(f"\nPhase 2: Generating {parsed} RAG Markdown files...")
    for file_key, class_data in all_classes.items():
        md_content = generate_markdown(class_data)
        md_path = md_dir / f"{file_key}.md"
        md_path.write_text(md_content, encoding="utf-8")

    # Phase 3: Generate JSON indexes
    print("\nPhase 3: Building JSON indexes...")

    index_path = json_dir / "index.json"
    index_path.write_text(
        json.dumps(build_index_json(all_classes), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  index.json: {parsed} classes")

    methods = build_methods_json(all_classes)
    methods_path = json_dir / "methods.json"
    methods_path.write_text(
        json.dumps(methods, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  methods.json: {len(methods)} searchable entries")

    overviews = build_class_overviews_json(all_classes)
    overviews_path = json_dir / "class_overviews.json"
    overviews_path.write_text(
        json.dumps(overviews, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  class_overviews.json: {len(overviews)} class overview chunks")

    packages = build_packages_json(all_classes)
    packages_path = json_dir / "packages.json"
    packages_path.write_text(
        json.dumps(packages, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  packages.json: {len(packages)} packages")

    print(f"\nDone. Output: {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse JavaDoc HTML into RAG-optimized Markdown + JSON indexes."
    )
    parser.add_argument("--html-dir", required=True, help="Source .html directory")
    parser.add_argument("--out-dir", required=True, help="Output root directory")
    args = parser.parse_args()
    build_all(Path(args.html_dir), Path(args.out_dir))
