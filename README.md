# Dreambot Scripting MCP

Write DreamBot OSRS scripts. Let AI know the API.

A Model Context Protocol server paired with a Claude Code skill that gives Claude real-time access to the DreamBot API 4.0 JavaDocs — so you can say "write a woodcutting bot" and get correct, API-4.0-compliant Java instead of hallucinated 3.x patterns.

---

## What's included

| Component | What it does |
|---|---|
| `dreambot_search` | Keyword + semantic API search |
| `dreambot_overview` | Lists all API packages |
| `dreambot_package` | Lists classes in a package |
| `dreambot_member` | Full method signatures for a class |
| `dreambot_tile` | Map URL to Tile code |
| `dreambot-scripting` skill | Teaches Claude API 4.0 patterns |

---

**Requires Python 3.9+.** On macOS/Linux use `pip3` and `python3` where commands below say `pip`/`python`.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Register the MCP server

Add this block to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dreambot-scripting": {
      "command": "python",
      "args": ["C:/absolute/path/to/Dreambot-Scripting-MCP-main/server.py"]
    }
  }
}
```

> Replace the path with the absolute path to `server.py` on your machine. The `API v4` folder must be present in the same directory as `server.py`.
> 
> On Windows, `"command": "python"` is correct. On macOS/Linux, change it to `"python3"`.

### 3. Install the skill

Copy `dreambot-scripting.skill` (repo root) into your Claude Code plugins directory, then restart Claude Code.

> The skill teaches Claude the API 4.0 static-method pattern, state machine structure, anti-ban timing, and when to call each MCP tool — automatically, every time you work on a DreamBot script.

---

## What just happened?

The **MCP server** runs locally alongside Claude Code. When Claude needs to look up a method signature, it calls one of the five tools — which either search the local API index or scrape the live JavaDocs. The **skill** fires automatically whenever you mention DreamBot or OSRS scripting, priming Claude with correct API 4.0 patterns before a single line of code is written.

---

## Tool reference

| Tool | Input | When to use |
|---|---|---|
| `dreambot_search` | `query` (string), `top_k` (int, default 8) | First stop — natural language or keyword |
| `dreambot_overview` | — | Browse all available packages |
| `dreambot_package` | `package` (dot-separated string) | List classes in a known package |
| `dreambot_member` | `package` + `href` (e.g. `Bank.html`) | Full method list with signatures |
| `dreambot_tile` | Explv `url` or raw `x`, `y`, `z` integers | Convert map coordinates to code |

### Typical workflow

```
1. dreambot_search("check if bank is open")
   → identifies Bank class, returns package and href

2. dreambot_member(package="org.dreambot.api.methods.container.impl.bank", href="Bank.html")
   → full method list: isOpen(), open(), withdraw(), depositAllItems(), close() ...
```

---

## Interactive docs

Open [`index.html`](index.html) in your browser for the full documentation with live tool examples and copy-paste code blocks.
