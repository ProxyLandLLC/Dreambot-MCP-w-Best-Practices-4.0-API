"""
Game data chunker — transforms osrs-db items.g.json and npcs.g.json
into item chunks and NPC data chunks for the game_data collection.
"""


def chunk_items(items_data: dict) -> list[dict]:
    """
    Parse osrs-db items.g.json into item chunks.
    Each item gets base info, trade info, equipment stats, and requirements.
    """
    chunks = []

    for item_id_str, item in items_data.items():
        try:
            item_id = int(item_id_str)
        except (ValueError, TypeError):
            continue

        name = item.get("name", "").strip()
        if not name or name == "null" or name == "Null":
            continue

        # Base info
        examine = item.get("examine", item.get("description", ""))
        tradeable = item.get("tradeable", item.get("tradeable_on_ge", False))
        members = item.get("members", False)
        equipable = item.get("equipable", item.get("equipable_by_player", False))

        # Build document text
        parts = [f"{name}"]
        if examine:
            parts[0] += f" — {examine}"
        parts.append(f"Item ID: {item_id}.")

        if tradeable:
            buy_limit = item.get("buy_limit", "")
            high_alch = item.get("highalch", item.get("high_alch", ""))
            low_alch = item.get("lowalch", item.get("low_alch", ""))
            trade_parts = ["Tradeable on GE."]
            if buy_limit:
                trade_parts.append(f"Buy limit: {buy_limit}.")
            if high_alch:
                trade_parts.append(f"High alch: {high_alch}.")
            parts.append(" ".join(trade_parts))
        else:
            parts.append("Not tradeable.")

        # Equipment stats
        slot = ""
        if equipable:
            equipment = item.get("equipment", {})
            slot = equipment.get("slot", "")
            attack_speed = item.get("weapon", {}).get("attack_speed", "")

            equip_parts = []
            if slot:
                equip_parts.append(f"Equip slot: {slot}.")
            if attack_speed:
                equip_parts.append(f"Attack speed: {attack_speed}.")

            # Attack bonuses
            for bonus_name in ["attack_stab", "attack_slash", "attack_crush",
                               "attack_magic", "attack_ranged"]:
                val = equipment.get(bonus_name, 0)
                if val and val != 0:
                    label = bonus_name.replace("attack_", "")
                    equip_parts.append(f"+{val} {label}.")

            # Strength bonuses
            for bonus_name in ["melee_strength", "ranged_strength", "magic_damage"]:
                val = equipment.get(bonus_name, 0)
                if val and val != 0:
                    label = bonus_name.replace("_", " ")
                    equip_parts.append(f"+{val} {label}.")

            if equip_parts:
                parts.append(" ".join(equip_parts))

        # Requirements
        requirements = item.get("equipment", {}).get("requirements", {})
        quest_reqs = item.get("quest_requirements", [])
        if requirements:
            req_parts = [f"{skill} {level}" for skill, level in requirements.items()]
            parts.append(f"Requirements: {', '.join(req_parts)}.")
        if quest_reqs:
            if isinstance(quest_reqs, list):
                quest_str = ";".join(str(q) for q in quest_reqs)
            else:
                quest_str = str(quest_reqs)
            parts.append(f"Quests: {quest_str}.")

        if members:
            parts.append("Members only.")

        doc_text = " ".join(parts)

        chunks.append({
            "id": f"item:{item_id}",
            "document": doc_text,
            "metadata": {
                "chunk_type": "item",
                "item_id": item_id,
                "name": name,
                "tradeable": bool(tradeable),
                "equipable": bool(equipable),
                "slot": slot or "",
                "members": bool(members),
                "quest_req": ";".join(str(q) for q in quest_reqs) if isinstance(quest_reqs, list) else str(quest_reqs or ""),
            },
        })

    return chunks


def chunk_npcs(npcs_data: dict) -> list[dict]:
    """
    Parse osrs-db npcs.g.json into NPC data chunks (stats/drops).
    Location data is handled separately by the spatial chunker.
    """
    chunks = []

    for npc_id_str, npc in npcs_data.items():
        try:
            npc_id = int(npc_id_str)
        except (ValueError, TypeError):
            continue

        name = npc.get("name", "").strip()
        if not name or name == "null" or name == "Null":
            continue

        combat_level = npc.get("combatLevel", npc.get("combat_level", 0))
        hitpoints = npc.get("hitpoints", 0)
        max_hit = npc.get("maxHit", npc.get("max_hit", 0))
        attack_type = npc.get("attackType", npc.get("attack_type", ""))
        members = npc.get("members", False)

        parts = [f"{name} — Level {combat_level} NPC."]
        if hitpoints:
            parts.append(f"HP: {hitpoints}.")
        if max_hit:
            parts.append(f"Max hit: {max_hit}.")
        if attack_type:
            if isinstance(attack_type, list):
                attack_type = ", ".join(str(a) for a in attack_type)
            parts.append(f"Attack style: {attack_type}.")

        # Notable drops
        drops = npc.get("drops", [])
        if drops and isinstance(drops, list):
            notable = []
            for drop in drops[:10]:
                if isinstance(drop, dict):
                    drop_name = drop.get("name", drop.get("item", ""))
                    rarity = drop.get("rarity", drop.get("rate", ""))
                    if drop_name:
                        entry = str(drop_name)
                        if rarity:
                            entry += f" ({rarity})"
                        notable.append(entry)
            if notable:
                parts.append(f"Drops: {', '.join(notable)}.")

        if members:
            parts.append("Members only.")

        doc_text = " ".join(parts)

        chunks.append({
            "id": f"npc:{npc_id}",
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
