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
    Each entry has: name, position {x, y, z}
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


def chunk_npc_locations(npcs_data: dict) -> list[dict]:
    """
    Parse osrs-db npcs.g.json into npc_location chunks.
    Only NPCs with known coordinates are included.
    """
    chunks = []
    for npc_id_str, npc in npcs_data.items():
        try:
            npc_id = int(npc_id_str)
        except (ValueError, TypeError):
            continue

        name = npc.get("name", "").strip()
        if not name:
            continue

        # osrs-db stores locations differently depending on version
        # Try common field names
        coords = npc.get("coords", [])
        if not coords:
            # Some versions use 'locations' or nested coordinate fields
            locations = npc.get("locations", [])
            if locations and isinstance(locations[0], dict):
                coords = [(loc.get("x", 0), loc.get("y", 0), loc.get("plane", 0))
                          for loc in locations if loc.get("x")]

        if not coords:
            continue

        # Take first known coordinate
        if isinstance(coords[0], dict):
            x = coords[0].get("x", 0)
            y = coords[0].get("y", 0)
            z = coords[0].get("plane", coords[0].get("z", 0))
        elif isinstance(coords[0], (list, tuple)):
            x, y = coords[0][0], coords[0][1]
            z = coords[0][2] if len(coords[0]) > 2 else 0
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


def chunk_object_locations(objects_data: dict) -> list[dict]:
    """
    Parse osrs-db object data into object_location chunks.
    Clusters by object type + approximate region to avoid hundreds of
    individual "Oak tree" chunks.
    """
    # Group coordinates by object name + rounded centroid
    clusters: dict[str, dict] = {}

    for obj_id_str, obj in objects_data.items():
        try:
            obj_id = int(obj_id_str)
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
