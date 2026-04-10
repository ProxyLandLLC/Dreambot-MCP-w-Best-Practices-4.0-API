"""
Game data chunker — transforms osrs-db items.g.json and npcs.g.json
into item chunks and NPC data chunks for the game_data collection.

Data source: wvanderp/osrs-db npm package (arrays of cache-extracted objects).
"""


def chunk_items(items_data: list) -> list[dict]:
    """
    Parse osrs-db items.g.json into item chunks.
    Input is an array of item objects from the OSRS cache.
    """
    chunks = []

    for item in items_data:
        item_id = item.get("id")
        if item_id is None:
            continue

        name = item.get("name", "").strip()
        if not name or name == "null" or name == "Null":
            continue

        examine = item.get("examine", "")
        tradeable = item.get("isTradeable", False)
        members = item.get("members", False)
        cost = item.get("cost", 0)
        stackable = item.get("stackable", 0)

        # Determine if equipable from interfaceOptions containing "Wield"/"Wear"
        interface_opts = item.get("interfaceOptions", [])
        equipable = any(
            opt in ("Wield", "Wear", "Equip")
            for opt in (interface_opts or [])
            if opt
        )

        # Build document text
        parts = [f"{name}"]
        if examine:
            parts[0] += f" — {examine}"
        parts.append(f"Item ID: {item_id}.")

        if tradeable:
            parts.append(f"Tradeable. Value: {cost} gp.")
        else:
            parts.append(f"Not tradeable. Value: {cost} gp.")

        if equipable:
            parts.append("Equipable.")
        if stackable:
            parts.append("Stackable.")
        if members:
            parts.append("Members only.")

        # Weight (stored in grams in osrs-db)
        weight = item.get("weight", 0)
        if weight and weight > 0:
            parts.append(f"Weight: {weight / 1000:.2f} kg.")

        doc_text = " ".join(parts)

        # Determine slot from wearPos1
        slot = ""
        wear_pos = item.get("wearPos1", -1)
        slot_map = {
            0: "head", 1: "cape", 2: "neck", 3: "weapon",
            4: "body", 5: "shield", 7: "legs", 9: "hands",
            10: "feet", 12: "ring", 13: "ammo",
        }
        if wear_pos in slot_map:
            slot = slot_map[wear_pos]

        chunks.append({
            "id": f"item:{item_id}",
            "document": doc_text,
            "metadata": {
                "chunk_type": "item",
                "item_id": item_id,
                "name": name,
                "tradeable": bool(tradeable),
                "equipable": equipable,
                "slot": slot,
                "members": bool(members),
                "quest_req": "",
            },
        })

    return chunks


def chunk_npcs(npcs_data: list) -> list[dict]:
    """
    Parse osrs-db npcs.g.json into NPC data chunks (stats/actions).
    Input is an array of NPC objects from the OSRS cache.
    """
    chunks = []
    seen_ids: set[str] = set()

    for npc in npcs_data:
        npc_id = npc.get("id")
        if npc_id is None:
            continue

        name = npc.get("name", "").strip()
        if not name or name == "null" or name == "Null":
            continue

        combat_level = npc.get("combatLevel", 0)
        actions = npc.get("actions", [])
        members = npc.get("members", False)
        stats = npc.get("stats", {})

        # Extract HP from stats if available
        hitpoints = 0
        if isinstance(stats, dict):
            hitpoints = stats.get("hitpoints", stats.get("hp", 0))
        elif isinstance(stats, list) and len(stats) > 3:
            hitpoints = stats[3] if stats[3] else 0

        # Filter null actions
        action_list = [a for a in (actions or []) if a]
        actions_str = ", ".join(action_list)

        parts = [f"{name}"]
        if combat_level:
            parts[0] += f" — Level {combat_level} NPC."
        else:
            parts[0] += " — Non-combat NPC."

        if hitpoints:
            parts.append(f"HP: {hitpoints}.")
        if actions_str:
            parts.append(f"Actions: {actions_str}.")
        if members:
            parts.append("Members only.")

        doc_text = " ".join(parts)

        # Deduplicate NPC IDs (some NPCs have multiple cache entries)
        chunk_id = f"npc:{npc_id}"
        if chunk_id in seen_ids:
            continue
        seen_ids.add(chunk_id)

        chunks.append({
            "id": chunk_id,
            "document": doc_text,
            "metadata": {
                "chunk_type": "npc",
                "npc_id": npc_id,
                "name": name,
                "combat_level": combat_level or 0,
                "hitpoints": hitpoints or 0,
                "members": bool(members),
            },
        })

    return chunks
