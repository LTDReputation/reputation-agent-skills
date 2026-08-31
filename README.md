# agent-skills

Portable [Agent Skills](https://agentskills.io) for the **reputation.ru** court
service — search and analyze Russian court practice (судебная практика РФ) from
any skills-compatible AI agent (Claude / Claude Code, Cursor, Gemini CLI,
OpenCode, Goose, Codex, and others).

The skill is a self-contained folder with a `SKILL.md`. Agents load only its name
and description until a task matches, then read the full instructions — so it costs
little context until actually used.

## Skill

A single skill, [`court-practice`](skills/court-practice/), covering the whole court
service:

| Capability | Use it for |
|---|---|
| **Search** | **Default.** Find relevant court cases (арбитраж / СОЮ / ВС РФ) by a legal question — fast, seconds. |
| **Deep analysis** | A synthesized analytical report across practice («сложившаяся практика по…»). Asynchronous, ~30–120s. |
| **Document text** | Fetch the full text of a specific case document (by `FileId`/`DocId` from search). |
| **Setup** | Connect the service — MCP server or REST API key. Do first. Bundles a zero-dependency REST client. |

The skill is built around the reputation **MCP server** (the tool layer); when MCP
isn't connected it falls back to the **REST API** via the bundled `court_client.py`.

## Requirements

- An API key from https://reputation.ru/account/api.
- Either the reputation MCP server connected, or the ability to call the REST API
  (the bundled `court_client.py` uses only the Python standard library).

## Install

**As a Claude Code plugin (recommended).** This repo is a Claude Code plugin
marketplace. Add it, then install the `courts` plugin — you get the skill as a
slash command (`/courts:court-practice`) and the reputation MCP server auto-wired
from [`.mcp.json`](.mcp.json):

```
/plugin marketplace add LTDReputation/reputation-agent-skills
/plugin install courts@reputation-agent-skills
```

Then set your key so the bundled MCP can authenticate:

```bash
export REPUTATION_API_KEY=<your-api-key>   # from https://reputation.ru/account/api
```

**As a Codex plugin.** A Codex manifest is provided at
[`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) (same skill) — install
via the Codex skill installer pointing at this repo.

**Manual (any skills-compatible agent).** Copy the skill folder into your
agent's skills directory:

```bash
mkdir -p .claude/skills
cp -r skills/* .claude/skills/
```

The skill's **Setup** section connects the MCP server (or sets an API key); do that
first, then use it for everyday lookups. The `SKILL.md` format is the same across
runtimes — consult your agent's docs for its exact skills path.

## Layout

```
agent-skills/
├── .claude-plugin/
│   ├── marketplace.json          # Claude Code plugin marketplace descriptor
│   └── plugin.json               # the `courts` plugin (→ ./skills, → ./.mcp.json)
├── .codex-plugin/plugin.json     # Codex plugin manifest
├── .mcp.json                     # bundled reputation MCP server (key via ${REPUTATION_API_KEY})
└── skills/
    └── court-practice/
        ├── SKILL.md
        └── scripts/court_client.py   # zero-dependency REST client + SOD polling
```

## Contributing

Keep `SKILL.md` focused; the description must say **when** to use the skill — that's
what the agent matches on. Put endpoints, tool names, and routing in the section that
owns them (Search / Deep analysis / Document text / Setup).
