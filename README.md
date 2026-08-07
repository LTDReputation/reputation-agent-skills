# agent-skills

Portable [Agent Skills](https://agentskills.io) for the **reputation.ru** court
service — search and analyze Russian court practice (судебная практика РФ) from
any skills-compatible AI agent (Claude / Claude Code, Cursor, Gemini CLI,
OpenCode, Goose, Codex, and others).

Each skill is a self-contained folder with a `SKILL.md`. Agents load only the
name and description until a task matches, then read the full instructions —
so many skills cost little context.

## Skills

| Skill | Use it for |
|---|---|
| [`court-search`](skills/court-search/) | **Default.** Find relevant court cases (арбитраж / СОЮ / ВС РФ) by a legal question — fast, seconds. |
| [`court-deep-analysis`](skills/court-deep-analysis/) | A synthesized analytical report across practice («сложившаяся практика по…»). Asynchronous, ~30–120s. |
| [`court-document`](skills/court-document/) | Fetch the full text of a specific case document (by `FileId`/`DocId` from search). |
| [`courts-setup`](skills/courts-setup/) | Connect the service — MCP server or REST API key. Run first. Bundles a zero-dependency REST client. |

The skills are built around the reputation **MCP server** (the tool layer); when
MCP isn't connected they fall back to the **REST API** via the bundled
`court_client.py`.

## Requirements

- An API key from https://reputation.ru/account/api.
- Either the reputation MCP server connected, or the ability to call the REST API
  (the bundled `court_client.py` uses only the Python standard library).

## Install

**As a Claude Code plugin (recommended).** This repo is a Claude Code plugin
marketplace. Add it, then install the `courts` plugin — you get the four skills
as slash commands (`/courts:court-search`, `/courts:court-deep-analysis`, …) and
the reputation MCP server auto-wired from [`.mcp.json`](.mcp.json):

```
/plugin marketplace add LTDReputation/reputation-agent-skills
/plugin install courts@reputation-agent-skills
```

Then set your key so the bundled MCP can authenticate:

```bash
export REPUTATION_API_KEY=<your-api-key>   # from https://reputation.ru/account/api
```

**As a Codex plugin.** A Codex manifest is provided at
[`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) (same skills) — install
via the Codex skill installer pointing at this repo.

**Manual (any skills-compatible agent).** Copy the skill folders into your
agent's skills directory:

```bash
mkdir -p .claude/skills
cp -r skills/* .claude/skills/
```

Either way, run **`courts-setup`** first to connect the MCP server (or set an API
key), then use `court-search` for everyday lookups. The `SKILL.md` format is the
same across runtimes — consult your agent's docs for its exact skills path.

## Layout

```
agent-skills/
├── .claude-plugin/
│   ├── marketplace.json          # Claude Code plugin marketplace descriptor
│   └── plugin.json               # the `courts` plugin (→ ./skills, → ./.mcp.json)
├── .codex-plugin/plugin.json     # Codex plugin manifest
├── .mcp.json                     # bundled reputation MCP server (key via ${REPUTATION_API_KEY})
└── skills/
    ├── court-search/SKILL.md
    ├── court-deep-analysis/SKILL.md
    ├── court-document/SKILL.md
    └── courts-setup/
        ├── SKILL.md
        └── scripts/court_client.py   # zero-dependency REST client + SOD polling
```

## Contributing

Keep each `SKILL.md` focused and short; put endpoints, tool names, and routing in
the skill that owns them. Descriptions must say **when** to use a skill (and when
to use a sibling instead) — that's what the agent matches on.
