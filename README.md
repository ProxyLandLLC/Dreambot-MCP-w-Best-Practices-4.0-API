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

Hit this button:  [Interactive Documentation](https://proxylandllc.github.io/Dreambot-MCP-w-Best-Practices-4.0-API/)  to see the interactive browser! Shows you
multiple different things such as how to set it up, and different usages! Enjoy!

---

## Testing

Two-layer automated test harness under `tests/`:

- **`tests/protocol/`** — fast pytest suite that drives `server.py` over stdio via the official MCP Python client. Asserts on tool responses directly, no LLM. Run:

  ```
  pytest tests/protocol/
  ```

- **`tests/scenarios/`** — Claude Agent SDK harness that runs 31 YAML scenarios through a live Claude session with the `dreambot-scripting` skill and the MCP server. Requires `ANTHROPIC_API_KEY` in the environment. Run:

  ```
  python -m tests.scenarios.runner                 # all, parallel (4 workers)
  python -m tests.scenarios.runner --sequential    # serial, easier to debug
  python -m tests.scenarios.runner -k tile         # filter by id substring
  python -m tests.scenarios.runner --workers 8     # custom pool size
  python -m tests.scenarios.runner --no-judge      # skip LLM judge entirely
  ```

  Reports land in `tests/scenarios/reports/<timestamp>/` (gitignored). Each
  run writes a `summary.md` plus a per-scenario JSON file with the full
  transcript, tool calls, assertion results, and (where enabled) the Sonnet
  4.6 judge verdict.

Design doc: `docs/superpowers/specs/2026-04-10-scenario-test-harness-design.md`
Plan: `docs/superpowers/plans/2026-04-10-scenario-test-harness.md`
