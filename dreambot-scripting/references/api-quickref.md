# DreamBot API 4.0 — Quick Reference

All classes below use **static methods** (no instance needed). Import each class explicitly.

---

## Bank

**Import:** `org.dreambot.api.methods.container.impl.bank.Bank`

### State
```java
Bank.isOpen()                    // boolean — is bank interface open?
Bank.isLoaded()                  // boolean — are contents loaded?
Bank.isFull()                    // boolean
Bank.isEmpty()                   // boolean
Bank.capacity()                  // int — max bank slots
```

### Open / Close
```java
Bank.open()                      // boolean — opens nearest bank
Bank.open(BankLocation bank)     // boolean — opens specific bank
Bank.close()                     // boolean
Bank.getClosestBankLocation()    // BankLocation
```

### Withdraw
```java
Bank.withdraw(int id)                    // boolean — withdraws 1
Bank.withdraw(String name)               // boolean — withdraws 1
Bank.withdraw(int id, int amount)        // boolean
Bank.withdraw(String name, int amount)   // boolean
Bank.withdrawAll(int id)                 // boolean
Bank.withdrawAll(String name)            // boolean
```

### Deposit
```java
Bank.deposit(int id)                     // boolean
Bank.deposit(String name)                // boolean
Bank.deposit(int id, int amount)         // boolean
Bank.depositAll(int id)                  // boolean
Bank.depositAllItems()                   // boolean — deposits entire inventory
Bank.depositAllEquipment()               // boolean
Bank.depositAllExcept(Integer... ids)    // boolean
```

### Query
```java
Bank.all()                          // List<Item>
Bank.all(Filter<Item> filter)       // List<Item>
Bank.get(int id)                    // Item (or null)
Bank.get(String name)               // Item (or null)
Bank.contains(int id)               // boolean (ignores placeholders)
Bank.contains(String name)          // boolean
Bank.containsAll(Integer... ids)    // boolean
Bank.count(int id)                  // int
Bank.count(String name)             // int
Bank.getItemInSlot(int slot)        // Item
```

### Tabs
```java
Bank.openTab(int tab)               // boolean (0-based index)
Bank.getCurrentTab()                // int
Bank.availableTabs()                // int
```

### Mode / Settings
```java
Bank.setWithdrawMode(BankMode.NOTE)       // withdraw as notes
Bank.setWithdrawMode(BankMode.ITEM)       // withdraw as items
Bank.getWithdrawMode()                    // BankMode
Bank.setDefaultQuantity(BankQuantitySelection.ONE)   // ONE/FIVE/TEN/ALL/X
Bank.togglePlaceholders()                // boolean
Bank.placeHoldersEnabled()               // boolean
```

---

## Inventory

**Import:** `org.dreambot.api.methods.container.impl.Inventory`

```java
Inventory.all()                          // List<Item>
Inventory.all(Filter<Item> filter)       // List<Item>
Inventory.get(int id)                    // Item
Inventory.get(String name)               // Item
Inventory.contains(int id)              // boolean
Inventory.contains(String name)         // boolean
Inventory.contains(Integer... ids)      // boolean — has any of these
Inventory.count(int id)                 // int
Inventory.count(String name)            // int
Inventory.isFull()                      // boolean (28 items)
Inventory.isEmpty()                     // boolean
Inventory.getFirstEmptySlot()           // int (-1 if full)
Inventory.interact(int id, String action)      // boolean
Inventory.interact(String name, String action) // boolean
Inventory.interact(String name)                // boolean (default action)
Inventory.drop(int id)                  // boolean
Inventory.dropAll(Filter<Item> filter)  // boolean
Inventory.drag(int itemId, int toSlot)  // boolean
Inventory.swap(int fromSlot, int toSlot)// boolean
Inventory.combine(Item primary, Item secondary) // boolean
Inventory.slot(int id)                  // int — slot index of item
Inventory.isSlotEmpty(int slot)         // boolean
```

---

## Walking

**Import:** `org.dreambot.api.methods.walking.impl.Walking`

```java
Walking.walk(Tile tile)              // boolean — web + local pathfinding
Walking.walk(Entity entity)          // boolean
Walking.walk(int x, int y)           // boolean
Walking.walk(int x, int y, int z)    // boolean (z = plane)
Walking.walkExact(Tile tile)         // boolean — aims for exact tile
Walking.walkOnScreen(Tile tile)      // boolean — clicks tile on viewport
Walking.shouldWalk()                 // boolean — > 5 tiles from dest
Walking.shouldWalk(int distance)     // boolean — > N tiles from dest
Walking.canWalk(Tile tile)           // boolean — pathfindable?
Walking.isRunEnabled()               // boolean
Walking.toggleRun()                  // boolean
Walking.getRunEnergy()               // int (0–100)
Walking.getRunThreshold()            // int
Walking.setRunThreshold(int energy)  // auto-enable run above this energy
Walking.getDestination()             // Tile (or null)
Walking.getDestinationDistance()     // int
```

---

## NPCs

**Import:** `org.dreambot.api.methods.interactive.NPCs`

```java
NPCs.all()                           // List<NPC>
NPCs.all(String... names)            // List<NPC>
NPCs.all(Integer... ids)             // List<NPC>
NPCs.all(Filter<NPC> filter)         // List<NPC>
NPCs.closest(String... names)        // NPC (nearest by distance)
NPCs.closest(Integer... ids)         // NPC
NPCs.closest(Filter<NPC> filter)     // NPC
NPCs.setIgnoreHealth(boolean)        // include 0-health NPCs
NPCs.setIncludeNullNames(boolean)    // include unnamed NPCs
```

**NPC wrapper** (`org.dreambot.api.wrappers.interactive.NPC`):
```java
npc.getName()           // String
npc.getId()             // int
npc.interact(String)    // boolean
npc.isInCombat()        // boolean
npc.isAnimating()       // boolean
npc.getAnimation()      // int (-1 = idle)
npc.getHealthPercent()  // int (0–100)
npc.distance()          // double — to local player
npc.getTile()           // Tile
npc.hasAction(String)   // boolean
```

---

## GameObjects

**Import:** `org.dreambot.api.methods.interactive.GameObjects`

```java
GameObjects.all()                          // List<GameObject>
GameObjects.all(String... names)           // List<GameObject>
GameObjects.all(Integer... ids)            // List<GameObject>
GameObjects.all(Filter<GameObject> filter) // List<GameObject>
GameObjects.closest(String... names)       // GameObject
GameObjects.closest(Integer... ids)        // GameObject
GameObjects.closest(Filter<GameObject> filter) // GameObject
GameObjects.getObjectsOnTile(Tile tile)    // List<GameObject>
GameObjects.getTopObjectOnTile(Tile tile)  // GameObject
```

**GameObject wrapper** (`org.dreambot.api.wrappers.interactive.GameObject`):
```java
obj.getName()           // String
obj.getId()             // int
obj.interact(String)    // boolean
obj.getTile()           // Tile
obj.distance()          // double
obj.hasAction(String)   // boolean
obj.isOnScreen()        // boolean
```

---

## Players

**Import:** `org.dreambot.api.methods.interactive.Players`

```java
Players.localPlayer()                      // Player — the logged-in player
Players.all()                              // List<Player>
Players.closest(Filter<Player> filter)     // Player
```

**Player wrapper** (`org.dreambot.api.wrappers.interactive.Player`):
```java
player.isAnimating()          // boolean
player.isMoving()             // boolean
player.getAnimation()         // int
player.getName()              // String
player.getTile()              // Tile
player.distance(Tile tile)    // double
player.isInCombat()           // boolean
player.getSkillLevel(Skill)   // int — boosted level
```

---

## Tile

**Import:** `org.dreambot.api.wrappers.map.Tile`

```java
new Tile(int x, int y)           // plane 0 (surface)
new Tile(int x, int y, int plane) // plane 0=surface, 1=first floor
tile.distance(Locatable other)   // double — Chebyshev distance
tile.isOnScreen()                // boolean
tile.canReach()                  // boolean — pathfindable from player
tile.getX()                      // int
tile.getY()                      // int
tile.getZ()                      // int (plane)
```

---

## Calculations

**Import:** `org.dreambot.api.methods.Calculations`

```java
Calculations.random(int min, int max)        // random int (inclusive)
Calculations.random(double min, double max)  // random double
Calculations.distanceBetween(Tile a, Tile b) // double
```

---

## Skills

**Import:** `org.dreambot.api.methods.skills.Skills` and `org.dreambot.api.methods.skills.Skill`

```java
Skills.getRealLevel(Skill.WOODCUTTING)          // int — base level
Skills.getBoostedLevel(Skill.WOODCUTTING)       // int — with boosts
Skills.getExperience(Skill.WOODCUTTING)         // int — total XP
Skills.getExperienceToLevel(Skill.WOODCUTTING)  // int — XP to next level
Skills.getPercentToNextLevel(Skill.WOODCUTTING) // double (0.0–1.0)
```

**Skill enum values** (common ones):
`ATTACK, STRENGTH, DEFENCE, RANGED, PRAYER, MAGIC, RUNECRAFTING, HITPOINTS,
CRAFTING, MINING, SMITHING, FISHING, COOKING, FIREMAKING, WOODCUTTING,
AGILITY, HERBLORE, THIEVING, FLETCHING, SLAYER, FARMING, CONSTRUCTION, HUNTER`

---

## TaskScript / Task

**Imports:**
```java
import org.dreambot.api.script.TaskScript;   // main script base class
import org.dreambot.api.script.Task;         // individual task base class — NOT TaskNode
```

> Individual task classes extend `Task`, not `TaskNode`. `TaskNode` is an outdated internal name.

```java
// In main script onStart():
setTasks(new TaskA(), new TaskB(), new TaskC());

// Each Task class:
public class TaskA extends Task {
    @Override public boolean validate() { /* when to run */ return true; }
    @Override public int execute()      { /* what to do */ return 600; }
}
```
