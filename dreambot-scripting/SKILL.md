---
name: dreambot-scripting
description: >
  DreamBot OSRS script development with API 4.0. Always use this skill whenever the user mentions DreamBot, OSRS scripting, RuneScape botting, bot scripts, or any DreamBot-related code — even if they just ask to "write a script" in a DreamBot project context. Covers script structure, the 4.0 static-method API pattern, banking, walking, inventory, NPC and GameObject interaction, state machines, anti-ban, and when to use the JavaDocs MCP tools. If the user is building or debugging a DreamBot script, invoke this skill immediately.
---

# DreamBot Scripting — API 4.0

## What you need to know first

DreamBot is an OSRS botting client. Scripts are Java classes. The client calls `onLoop()` in a loop; you return the milliseconds to wait before the next call. Everything in the API is accessed via **static methods** — there is no `getBank()` or `getInventory()` inheritance from 3.x.

**The single most important 4.0 change**: `MethodProvider` is deprecated. Do not extend it, do not call methods inherited from it. Use the static utility classes directly.

---

## Script skeleton

Every script needs `@ScriptManifest` and must extend `AbstractScript`:

```java
import org.dreambot.api.script.AbstractScript;
import org.dreambot.api.script.Category;
import org.dreambot.api.script.ScriptManifest;

@ScriptManifest(
    name    = "My Script",
    description = "Does something useful",
    author  = "YourName",
    version = 1.0,
    category = Category.MISC
)
public class MyScript extends AbstractScript {

    @Override
    public void onStart() {
        log("Script started!");
    }

    @Override
    public int onLoop() {
        // Return ms to sleep before next call — aim for 600-1200 (human-like)
        return 600;
    }

    @Override
    public void onExit() {
        log("Script stopped.");
    }
}
```

---

## API 4.0 access pattern — static methods

Import classes directly and call static methods. No instance or getter needed.

```java
// Banking
import org.dreambot.api.methods.container.impl.bank.Bank;
Bank.isOpen();
Bank.open();
Bank.withdraw("Logs", 28);
Bank.depositAllItems();
Bank.close();

// Inventory
import org.dreambot.api.methods.container.impl.Inventory;
Inventory.contains("Logs");
Inventory.isFull();
Inventory.interact("Logs", "Use");

// Walking
import org.dreambot.api.methods.walking.impl.Walking;
import org.dreambot.api.wrappers.map.Tile;
Walking.walk(new Tile(3166, 3487));
Walking.shouldWalk(7);   // true if > 7 tiles from destination
Walking.isRunEnabled();
Walking.toggleRun();

// NPCs
import org.dreambot.api.methods.interactive.NPCs;
import org.dreambot.api.wrappers.interactive.NPC;
NPC goblin = NPCs.closest("Goblin");
if (goblin != null) goblin.interact("Attack");

// GameObjects
import org.dreambot.api.methods.interactive.GameObjects;
import org.dreambot.api.wrappers.interactive.GameObject;
GameObject tree = GameObjects.closest("Oak tree");
if (tree != null) tree.interact("Chop down");

// Local player
import org.dreambot.api.methods.interactive.Players;
Players.localPlayer().isAnimating();
Players.localPlayer().isMoving();
Players.localPlayer().getTile();
```

---

## State machine (recommended structure)

Keep `onLoop()` clean by delegating to a state enum:

```java
private enum State { BANKING, WALKING, SKILLING }

private State getState() {
    if (Inventory.isFull())   return State.BANKING;
    if (!atSkillArea())       return State.WALKING;
    return State.SKILLING;
}

@Override
public int onLoop() {
    switch (getState()) {
        case BANKING:  handleBanking();  break;
        case WALKING:  handleWalking();  break;
        case SKILLING: handleSkilling(); break;
    }
    return Calculations.random(600, 1200);
}
```

---

## Banking pattern

```java
private void handleBanking() {
    if (!Bank.isOpen()) {
        Bank.open();
        Sleep.sleepUntil(Bank::isOpen, 5000);
        return;
    }
    Bank.depositAllItems();
    Bank.withdraw("Required Item", 28);
    Sleep.sleepUntil(() -> Inventory.contains("Required Item"), 3000);
    Bank.close();
    Sleep.sleepUntil(() -> !Bank.isOpen(), 2000);
}
```

---

## Walking pattern

```java
private static final Tile SKILL_TILE = new Tile(3166, 3487, 0);

private boolean atSkillArea() {
    return Players.localPlayer().getTile().distance(SKILL_TILE) < 5;
}

private void handleWalking() {
    if (Walking.shouldWalk(7)) {
        Walking.walk(SKILL_TILE);
    }
}
```

---

## Interaction with NPC/object

Always null-check. Use `sleepUntil` after clicking instead of fixed delays:

```java
private void handleSkilling() {
    if (Players.localPlayer().isAnimating()) return;

    NPC target = NPCs.closest(n ->
        "Goblin".equals(n.getName()) && !n.isInCombat()
    );
    if (target == null) return;

    if (target.interact("Attack")) {
        // Wait for animating OR in combat — the player may move toward the target
        // first (taking 1–2 game ticks = 600–1200ms) before the attack animation starts
        Sleep.sleepUntil(() ->
            Players.localPlayer().isAnimating() || Players.localPlayer().isInCombat(), 3000);
    }
}
```

---

## Sleep utilities

Use `Sleep` static methods everywhere — including helper classes that don't extend `AbstractScript`. The inherited `sleep()` methods from `AbstractScript` are only available inside the script class itself and will cause scope errors if used in separate helper/task classes.

```java
import org.dreambot.api.utilities.Sleep;

Sleep.sleep(600);                                              // fixed ms
Sleep.sleep(600, 1200);                                        // random range
Sleep.sleepUntil(() -> Bank.isOpen(), 5000);                   // wait up to 5s
Sleep.sleepUntil(() -> !Bank.isOpen(), 2000);
Sleep.sleepWhile(() -> Players.localPlayer().isMoving(), 10000); // wait while condition is true
```

---

## Anti-ban: timing variation

DreamBot handles human-like mouse movement and click patterns natively — do not implement custom mouse spline calculations, random off-screen mouse moves, or manual input simulation. That work is done for you.

What you *should* vary is timing and interaction order:

```java
import org.dreambot.api.methods.Calculations;
import org.dreambot.api.utilities.Sleep;

return Calculations.random(600, 1200);   // vary onLoop() return value

// Occasional idle break (~3% chance)
if (Calculations.random(0, 100) < 3) {
    Sleep.sleep(Calculations.random(2000, 6000));
}
```

---

## Logging

```java
log("message");    // info — visible in DreamBot's script logger
error("oops");     // error level
```

---

## When to use the JavaDocs MCP tools

Use the MCP tools when you need a method signature, return type, or overloads not covered here:

| Goal | Tool | Example arguments |
|------|------|-------------------|
| List all packages | `dreambot_overview` | (none) |
| List classes in a package | `dreambot_package` | `package="org.dreambot.api.methods.container.impl.bank"` |
| Get all methods for a class | `dreambot_member` | `package="org.dreambot.api.methods.container.impl.bank"`, `href="Bank.html"` |

**Key packages:**

| Package | What's in it |
|---------|-------------|
| `org.dreambot.api.script` | AbstractScript, ScriptManifest, Category |
| `org.dreambot.api.methods.container.impl.bank` | Bank, BankLocation, BankMode, BankTab |
| `org.dreambot.api.methods.container.impl` | Inventory, Shop, DropPattern |
| `org.dreambot.api.methods.walking.impl` | Walking |
| `org.dreambot.api.methods.interactive` | NPCs, GameObjects, Players |
| `org.dreambot.api.wrappers.interactive` | NPC, GameObject, Player, Entity |
| `org.dreambot.api.wrappers.items` | Item |
| `org.dreambot.api.wrappers.map` | Tile |
| `org.dreambot.api.methods` | Calculations, Animations |
| `org.dreambot.api.methods.skills` | Skills, Skill (enum) |
| `org.dreambot.api.methods.dialogues` | Dialogues |
| `org.dreambot.api.methods.magic` | Magic, Spells |
| `org.dreambot.api.methods.prayer` | Prayer, Prayers |

---

## Important 4.0 rules

- `MethodProvider` is **deprecated** — never extend it or call its methods
- `onLoop()` returns an `int` (ms). Return at least 100ms; 600+ is human-like
- Lambda filters: `NPCs.closest(n -> n.getName().equals("X") && n.getHealthPercent() > 50)`
- `Tile(x, y)` defaults to plane 0 (surface). Use `Tile(x, y, 1)` for first floor
- Always null-check entity results before calling `.interact()`
- Use `sleepUntil` after every interaction — don't assume instant success

---

## Reference files

Read these when you need full method signatures or less common patterns:

- `references/api-quickref.md` — Full signatures: Bank, Inventory, Walking, NPCs, GameObjects, Players, Skills
- `references/patterns.md` — GE trading, magic, prayer, dialogue, world hop, equipment, camera
