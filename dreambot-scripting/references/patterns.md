# DreamBot Scripting — Advanced Patterns

## TaskScript pattern (task-based scripts)

Use `TaskScript` as the main class and individual `Task` subclasses for each state.

> **IMPORTANT:** The individual task class extends `Task` — NOT `TaskNode`.
> `TaskNode` is an old/internal name. The correct import is `org.dreambot.api.script.Task`.

**Main script class:**
```java
import org.dreambot.api.script.TaskScript;
import org.dreambot.api.script.ScriptManifest;
import org.dreambot.api.script.Category;

@ScriptManifest(name = "My Script", version = 1.0, description = "", author = "", category = Category.MISC)
public class MyScript extends TaskScript {
    @Override
    public void onStart() {
        setTasks(
            new BankTask(),
            new WalkTask(),
            new DoActionTask()
        );
    }
}
```

**Individual task class:**
```java
import org.dreambot.api.script.Task;   // ← correct import, NOT TaskNode

public class BankTask extends Task {

    @Override
    public boolean validate() {
        // return true when this task should run
        return !Bank.isOpen() && Inventory.isFull();
    }

    @Override
    public int execute() {
        Bank.open();
        Sleep.sleepUntil(Bank::isOpen, 5000);
        Bank.depositAllItems();
        Sleep.sleepUntil(Inventory::isEmpty, 3000);
        return 600;
    }
}
```

`TaskScript.setTasks(Task...)` evaluates each task in order — the first one whose `validate()` returns `true` has its `execute()` called.

---

## Dialogue handling

```java
import org.dreambot.api.methods.dialogues.Dialogues;

@Override
public int onLoop() {
    // Always handle dialogues at the top of onLoop
    if (Dialogues.canContinue()) {
        Dialogues.continueDialogue();
        Sleep.sleepUntil(() -> !Dialogues.canContinue(), 3000);
        return 300;
    }
    if (Dialogues.inDialogue()) {
        Dialogues.chooseOption("Option text");
        return 600;
    }
    // ... rest of logic
    return 600;
}
```

---

## Equipment

**Import:** `org.dreambot.api.methods.container.impl.equipment.Equipment`

```java
import org.dreambot.api.methods.container.impl.equipment.Equipment;
import org.dreambot.api.methods.container.impl.equipment.EquipmentSlot;

Equipment.isSlotEmpty(EquipmentSlot.WEAPON)   // boolean
Equipment.contains("Rune axe")                // boolean
Equipment.all()                               // List<Item>
Equipment.get(EquipmentSlot.WEAPON)           // Item
Equipment.interact(EquipmentSlot.WEAPON, "Remove") // boolean
Equipment.getDefenseBonus()                   // int
```

**EquipmentSlot enum:** `HEAD, CAPE, AMULET, WEAPON, CHEST, SHIELD, LEGS, GLOVES, BOOTS, RING, AMMO`

---

## Magic

**Import:** `org.dreambot.api.methods.magic.Magic`

```java
import org.dreambot.api.methods.magic.Magic;
import org.dreambot.api.methods.magic.Spells;

Magic.castSpell(Spells.STANDARD.HIGH_LEVEL_ALCHEMY)  // boolean
Magic.isSpellSelected(Spells.STANDARD.HIGH_LEVEL_ALCHEMY) // boolean
Magic.getBook()                                           // Spellbook enum

// Cast on an item in inventory:
if (Magic.castSpell(Spells.STANDARD.HIGH_LEVEL_ALCHEMY)) {
    Sleep.sleepUntil(() -> Magic.isSpellSelected(Spells.STANDARD.HIGH_LEVEL_ALCHEMY), 2000);
    Inventory.interact("Dragon bones", "Cast");
}
```

**Common spells:** `Spells.STANDARD.TELEGRAB`, `Spells.STANDARD.SUPERHEAT_ITEM`,
`Spells.STANDARD.VARROCK_TELEPORT`, `Spells.LUNAR.HUMIDIFY`, etc.

---

## Prayer

**Import:** `org.dreambot.api.methods.prayer.Prayer`

```java
import org.dreambot.api.methods.prayer.Prayer;
import org.dreambot.api.methods.prayer.Prayers;

Prayer.toggle(Prayers.PROTECT_FROM_MELEE, true)   // activate
Prayer.toggle(Prayers.PROTECT_FROM_MELEE, false)  // deactivate
Prayer.isActive(Prayers.PROTECT_FROM_MELEE)        // boolean
Prayer.getPoints()                                  // int — current prayer points
Prayer.deactivateAll()                              // turn off all prayers
```

---

## Grand Exchange

**Import:** `org.dreambot.api.methods.grandexchange.GrandExchange`

```java
import org.dreambot.api.methods.grandexchange.GrandExchange;

GrandExchange.isOpen()                              // boolean
GrandExchange.open()                                // boolean
GrandExchange.close()                               // boolean

GrandExchange.buyItem("Coal", 100, 200)             // boolean (name, qty, price)
GrandExchange.sellItem("Logs", 100, 80)             // boolean

GrandExchange.collectAll()                          // collect completed offers
GrandExchange.getFirstOpenSlot()                    // int (-1 if none)
```

---

## World hopping

**Import:** `org.dreambot.api.methods.world.Worlds`

```java
import org.dreambot.api.methods.world.World;
import org.dreambot.api.methods.world.Worlds;

// Find a world matching criteria
World target = Worlds.getFirst(w ->
    w.isMembers() && w.getPlayerCount() < 500 && !w.isPVP()
);
if (target != null) {
    target.hop();
    Sleep.sleepUntil(() -> Login.isLoggedIn(), 10000);
}

Worlds.getCurrentWorld()   // int — current world number
```

---

## Tabs / UI navigation

```java
import org.dreambot.api.methods.tabs.Tab;
import org.dreambot.api.methods.tabs.Tabs;

Tabs.open(Tab.INVENTORY)     // boolean
Tabs.open(Tab.COMBAT)
Tabs.open(Tab.SKILLS)
Tabs.isOpen(Tab.INVENTORY)   // boolean
```

**Tab enum values:** `COMBAT, SKILLS, QUESTS, INVENTORY, EQUIPMENT, PRAYER, MAGIC,
CLAN, FRIENDS, IGNORES, LOGOUT, OPTIONS, EMOTES, MUSIC`

---

## Camera

```java
import org.dreambot.api.methods.input.Camera;

Camera.toEntity(gameObject)    // rotate camera toward entity
Camera.toTile(tile)            // rotate toward tile
Camera.setPitch(100)           // 0-100; higher = looking more downward
Camera.setZoom(128)            // zoom level
Camera.getYaw()                // int — current compass bearing
Camera.getPitch()              // int
```

---

## Login state check

```java
import org.dreambot.api.methods.login.Login;
import org.dreambot.api.methods.login.LoginState;

Login.isLoggedIn()             // boolean
Login.getState()               // LoginState enum
```

---

## Widgets (advanced — use when MCP tools needed)

Widgets let you interact with arbitrary game UI elements. Use `dreambot_member` with
package=`org.dreambot.api.methods.widget` to look up the Widget API when needed.

```java
import org.dreambot.api.methods.widget.Widgets;
import org.dreambot.api.wrappers.widgets.WidgetChild;

WidgetChild widget = Widgets.getWidget(parentId, childId);
if (widget != null && widget.isVisible()) {
    widget.interact("Continue");
}
```

---

## Paint (HUD overlay)

Override `onPaint(Graphics2D g)` to draw on screen:

```java
import java.awt.Graphics2D;
import java.awt.Color;
import java.awt.Font;

@Override
public void onPaint(Graphics2D g) {
    g.setColor(Color.WHITE);
    g.setFont(new Font("Arial", Font.BOLD, 12));
    g.drawString("Script running", 10, 30);
    g.drawString("XP/hr: " + xpPerHour, 10, 50);
}
```

---

## Filter lambda patterns

Filters are functional interfaces — use lambdas:

```java
// NPC: alive goblin not in combat
NPCs.closest(n ->
    "Goblin".equals(n.getName()) &&
    n.getHealthPercent() > 0 &&
    !n.isInCombat()
);

// GameObject: tree that has the chop action
GameObjects.closest(obj ->
    "Oak tree".equals(obj.getName()) && obj.hasAction("Chop down")
);

// Inventory: all noted items
Inventory.all(item -> item.isNoted());

// Bank: items below a stack threshold
Bank.all(item -> "Coal".equals(item.getName()) && item.getAmount() < 100);
```

---

## Script timer / XP tracking

```java
private long startTime = System.currentTimeMillis();
private int startXp;

@Override
public void onStart() {
    startXp = Skills.getExperience(Skill.WOODCUTTING);
}

// In onPaint:
long elapsed = System.currentTimeMillis() - startTime;
double hours = elapsed / 3600000.0;
int xpGained = Skills.getExperience(Skill.WOODCUTTING) - startXp;
int xpPerHour = (int)(xpGained / hours);
```
