"""
Spatial chunker — transforms map_labels.json, osrs-db NPC locations,
and osrs-db object locations into chunks for the spatial collection.
"""

import hashlib
import json
import re


# Region boundaries (rough OSRS coordinate ranges)
_REGIONS = [
    ("Misthalin", 3136, 3200, 3392, 3520),
    ("Asgarnia", 2880, 2944, 3200, 3392),
    ("Kandarin", 2560, 2624, 3200, 3520),
    ("Morytania", 3392, 3456, 3200, 3520),
    ("Karamja", 2816, 2880, 2944, 3200),
    ("Tirannwn", 2176, 2240, 3136, 3392),
    ("Fremennik", 2624, 2688, 3584, 3840),
    ("Wilderness", 2944, 3008, 3520, 3968),
    ("Kharidian Desert", 3200, 3264, 2816, 3136),
    ("Zeah", 1536, 1600, 3456, 3840),
]


def _classify_region(x: int, y: int) -> str:
    """Classify a tile coordinate into a rough OSRS region."""
    for name, x_min, _, x_max, _ in _REGIONS:
        # Use wider ranges for broader matching
        if x_min - 200 <= x <= x_max + 200:
            for rname, _, y_min, _, y_max in _REGIONS:
                if rname == name and y_min - 200 <= y <= y_max + 200:
                    return name
    return "Unknown"


def chunk_map_labels(labels_data: list[dict]) -> list[dict]:
    """
    Parse map_labels.json into named_location chunks.
    Supports both formats:
      - {name, worldX, worldY, plane} (current Explv format)
      - {name, position: {x, y, z}}  (legacy format)
    """
    chunks = []
    for entry in labels_data:
        name = entry.get("name", "").strip()
        if not name:
            continue

        # Clean HTML tags from name
        name = re.sub(r"<[^>]+>", "", name).strip()
        if not name:
            continue

        # Support both formats
        if "worldX" in entry:
            x = entry.get("worldX", 0)
            y = entry.get("worldY", 0)
            z = entry.get("plane", 0)
        else:
            pos = entry.get("position", {})
            x = pos.get("x", 0)
            y = pos.get("y", 0)
            z = pos.get("z", 0)

        if x == 0 and y == 0:
            continue

        region = _classify_region(x, y)

        doc_text = (
            f"{name} — Location in {region}. "
            f"Coordinates: ({x}, {y}, {z}). Plane: {'surface' if z == 0 else f'level {z}'}. "
            f"DreamBot: new Tile({x}, {y}, {z})"
        )

        chunks.append({
            "id": f"location:{name}:{x}:{y}:{z}",
            "document": doc_text,
            "metadata": {
                "chunk_type": "named_location",
                "name": name,
                "world_x": x,
                "world_y": y,
                "plane": z,
                "region": region,
            },
        })

    return chunks


def chunk_npc_locations(npcs_data) -> list[dict]:
    """
    Parse osrs-db npcs.g.json into npc_location chunks.
    Only NPCs with known coordinates are included.

    Accepts either a dict {id: npc_data} or list [{npc_data}, ...].
    Note: The wvanderp/osrs-db npm package typically does NOT include
    NPC coordinates. This function will return 0 chunks in that case.
    """
    chunks = []

    # Normalize to iterable of (npc_id, npc_dict) pairs
    if isinstance(npcs_data, dict):
        items_iter = ((k, v) for k, v in npcs_data.items())
    elif isinstance(npcs_data, list):
        items_iter = ((npc.get("id", i), npc) for i, npc in enumerate(npcs_data))
    else:
        return chunks

    for npc_id_raw, npc in items_iter:
        try:
            npc_id = int(npc_id_raw)
        except (ValueError, TypeError):
            continue

        name = npc.get("name", "").strip()
        if not name or name == "null":
            continue

        # Try all known coordinate field patterns
        coords = npc.get("coords", [])
        if not coords:
            coords = npc.get("locations", [])
        if not coords:
            # Check for direct x/y fields
            if "worldX" in npc and npc["worldX"]:
                coords = [{"x": npc["worldX"], "y": npc["worldY"], "plane": npc.get("plane", 0)}]

        if not coords:
            continue

        # Take first known coordinate
        first = coords[0]
        if isinstance(first, dict):
            x = first.get("x", first.get("worldX", 0))
            y = first.get("y", first.get("worldY", 0))
            z = first.get("plane", first.get("z", 0))
        elif isinstance(first, (list, tuple)):
            x, y = first[0], first[1]
            z = first[2] if len(first) > 2 else 0
        else:
            continue

        if x == 0 and y == 0:
            continue

        combat_level = npc.get("combatLevel", npc.get("combat_level", 0))
        interactions = npc.get("actions", npc.get("interactions", []))
        if isinstance(interactions, list):
            interactions = ",".join(str(a) for a in interactions if a)

        doc_text = (
            f"{name} — NPC located near ({x}, {y}, {z}). "
            f"Combat level: {combat_level}."
        )
        if interactions:
            doc_text += f" Interactions: {interactions}."

        chunks.append({
            "id": f"npc_loc:{npc_id}:{x}:{y}",
            "document": doc_text,
            "metadata": {
                "chunk_type": "npc_location",
                "name": name,
                "npc_id": npc_id,
                "world_x": x,
                "world_y": y,
                "plane": z,
                "interactions": interactions or "",
                "combat_level": combat_level or 0,
            },
        })

    return chunks


def chunk_object_locations(objects_data) -> list[dict]:
    """
    Parse osrs-db object data into object_location chunks.
    Clusters by object type + approximate region to avoid hundreds of
    individual "Oak tree" chunks.

    Accepts either a dict {id: obj_data} or list [{obj_data}, ...].
    Note: The wvanderp/osrs-db npm package typically does NOT include
    object coordinates. This function will return 0 chunks in that case.
    """
    # Group coordinates by object name + rounded centroid
    clusters: dict[str, dict] = {}

    # Normalize to iterable of (obj_id, obj_dict) pairs
    if isinstance(objects_data, dict):
        items_iter = objects_data.items()
    elif isinstance(objects_data, list):
        items_iter = ((obj.get("id", i), obj) for i, obj in enumerate(objects_data))
    else:
        return []

    for obj_id_raw, obj in items_iter:
        try:
            obj_id = int(obj_id_raw)
        except (ValueError, TypeError):
            continue

        name = obj.get("name", "").strip()
        if not name or name == "null":
            continue

        coords = obj.get("coords", [])
        if not coords:
            continue

        # Normalize coordinates
        parsed_coords = []
        for c in coords:
            if isinstance(c, dict):
                cx, cy = c.get("x", 0), c.get("y", 0)
            elif isinstance(c, (list, tuple)):
                cx, cy = c[0], c[1]
            else:
                continue
            if cx > 0 and cy > 0:
                parsed_coords.append((cx, cy))

        if not parsed_coords:
            continue

        # Compute centroid
        cx = sum(p[0] for p in parsed_coords) // len(parsed_coords)
        cy = sum(p[1] for p in parsed_coords) // len(parsed_coords)

        # Round centroid to ~128-tile grid for clustering
        rounded_x = (cx // 128) * 128
        rounded_y = (cy // 128) * 128
        cluster_key = f"{obj_id}:{rounded_x}:{rounded_y}"

        actions = obj.get("actions", [])
        if isinstance(actions, list):
            actions = ",".join(str(a) for a in actions if a)

        if cluster_key not in clusters:
            clusters[cluster_key] = {
                "obj_id": obj_id,
                "name": name,
                "centroid_x": cx,
                "centroid_y": cy,
                "actions": actions or "",
                "coords": parsed_coords,
            }
        else:
            clusters[cluster_key]["coords"].extend(parsed_coords)

    chunks = []
    for cluster_key, cluster in clusters.items():
        name = cluster["name"]
        obj_id = cluster["obj_id"]
        cx = cluster["centroid_x"]
        cy = cluster["centroid_y"]
        actions = cluster["actions"]
        all_coords = cluster["coords"][:20]  # Cap at 20 per cluster

        coord_list = [[c[0], c[1]] for c in all_coords]
        coord_str = json.dumps(coord_list)

        # Hash for stable ID
        hash_input = f"{obj_id}:{cx // 128}:{cy // 128}"
        id_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]

        doc_text = f"{name} — Found near ({cx}, {cy}, 0)."
        if actions:
            doc_text += f" Actions: {actions}."
        doc_text += f" {len(all_coords)} known positions."

        chunks.append({
            "id": f"obj_loc:{obj_id}:{id_hash}",
            "document": doc_text,
            "metadata": {
                "chunk_type": "object_location",
                "name": name,
                "object_id": obj_id,
                "world_x": cx,
                "world_y": cy,
                "plane": 0,
                "actions": actions,
                "coordinates": coord_str,
            },
        })

    return chunks
