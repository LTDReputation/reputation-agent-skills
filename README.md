# agent-skills

Portable [Agent Skills](https://agentskills.io) for the **reputation.ru** court
service — search and analyze Russian court practice (судебная практика РФ) from
any skills-compatible AI agent (Claude / Claude Code, Cursor, Gemini CLI,
OpenCode, Goose, Codex, OpenClaw, and others).

The skill is a self-contained folder with a `SKILL.md`. Agents load only its name
and description until a task matches, then read the full instructions — so it costs
little context until actually used.

## Skill

A single skill, [`court-practice`](skills/court-practice/), covering the whole court
service:

| Capability | Use it for | Typical time |
|---|---|---|
| **Search** | **Default.** Find relevant court cases (арбитраж / СОЮ / ВС РФ) by a legal question. | 10–45s |
| **Deep analysis** | A synthesized analytical report across practice («сложившаяся практика по…»). Asynchronous: start, then poll. | 30–240s |
| **Document text** | Fetch the full text of a specific case document (by `FileId`/`DocId` from search). | seconds |
| **Setup** | Connect the service — MCP (account sign-in or API key) or REST API key. Do first. Bundles a zero-dependency REST client. | — |

The skill is built around the reputation **MCP server** (`https://api.reputation.ru/mcp`,
the tool layer); when MCP isn't connected it falls back to the **REST API** via the
bundled `court_client.py`.

> **Paid service.** Requests are billed to your reputation.ru account per the service
> tariff, whichever way you authorize.

## Authorization

There are two ways to authorize. Pick by what your client supports and whether a person
is at the keyboard:

| | Use when | How |
|---|---|---|
| **Account sign-in (OAuth)** | MCP client with OAuth support, interactive session | Add the MCP server with **no headers**; the client opens a browser, you sign in and approve access. The client stores and refreshes the token itself. |
| **API key** | Any client, headless runs, REST, CI | Create a key at https://reputation.ru/account/api and send it in the `Authorization` header. |

### Account sign-in (OAuth)

Point your client at the server without any `headers`:

```json
{
  "mcpServers": {
    "reputation-court-search": {
      "url": "https://api.reputation.ru/mcp"
    }
  }
}
```

In Claude Code you can add it from the CLI and then authorize via `/mcp`:

```bash
claude mcp add --transport http reputation-court-search https://api.reputation.ru/mcp
```

Notes:

- **Do not add `headers.Authorization`.** Most clients skip the sign-in flow when a
  static header is present and send its value as an API key instead.
- Sign-in needs a person in a browser — an agent running non-interactively can't complete
  it. For headless hosts use the client's own manual fallback (e.g. OpenClaw's
  `openclaw mcp login <name>` with `--code`) or switch to an API key.
- The connected assistant shows up at https://reputation.ru/account/api under
  «Подключённые AI-ассистенты», where you can revoke access.
- Account sign-in applies to the **MCP endpoint only**; the REST API uses a key (or an
  OAuth access token, see below).

### API key

```json
{
  "mcpServers": {
    "reputation-court-search": {
      "url": "https://api.reputation.ru/mcp",
      "headers": { "Authorization": "<your-api-key>" }
    }
  }
}
```

## Requirements

- A reputation.ru account — either sign in through MCP (OAuth) or create an API key at
  https://reputation.ru/account/api.
- Either the reputation MCP server connected, or the ability to call the REST API
  (the bundled `court_client.py` uses only the Python standard library).

## Install

**As a Claude Code plugin (recommended).** This repo is a Claude Code plugin
marketplace. Add it, then install the `courts` plugin — you get the skill as a
slash command (`/courts:court-practice`) and the reputation MCP server wired from
[`.mcp.json`](.mcp.json):

```
/plugin marketplace add LTDReputation/reputation-agent-skills
/plugin install courts@reputation-agent-skills
```

The bundled [`.mcp.json`](.mcp.json) authenticates with an **API key**, so set it before
starting Claude Code:

```bash
export REPUTATION_API_KEY=<your-api-key>   # from https://reputation.ru/account/api
```

Prefer account sign-in? Because the bundled config sends a static `Authorization` header
(which disables OAuth), add the server yourself without headers as shown in
[Account sign-in (OAuth)](#account-sign-in-oauth) and authorize it via `/mcp`.

**As a Codex plugin.** A Codex manifest is provided at
[`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) and a Codex marketplace entry at
[`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json) (same skill) —
install via the Codex skill installer pointing at this repo.

**Manual (any skills-compatible agent).** Copy the skill folder into your
agent's skills directory:

```bash
mkdir -p .claude/skills
cp -r skills/* .claude/skills/
```

The skill's **Setup** section connects the MCP server (or sets an API key); do that
first, then use it for everyday lookups. The `SKILL.md` format is the same across
runtimes — consult your agent's docs for its exact skills path.

## REST client

When MCP isn't available, [`court_client.py`](skills/court-practice/scripts/court_client.py)
calls the REST API directly (Python standard library only — no install):

```bash
export REPUTATION_API_KEY=<your-api-key>

python skills/court-practice/scripts/court_client.py search general "взыскание процентов по ст. 395 ГК РФ"
python skills/court-practice/scripts/court_client.py analyze "как суды взыскивают неустойку по ДДУ"
python skills/court-practice/scripts/court_client.py doc arbitr <DocId>
```

| Variable | Purpose |
|---|---|
| `REPUTATION_API_KEY` | API key, sent as `Authorization: <key>`. |
| `REPUTATION_ACCESS_TOKEN` | OAuth access token, sent as `Authorization: Bearer <token>`. Takes precedence over the key when both are set. |
| `REPUTATION_HTTP_TIMEOUT` | HTTP timeout in seconds. Default `90`; keep it ≥ 60. |
| `REPUTATION_BASE_URL` | API base URL. Default `https://api.reputation.ru`. |

## Timeouts

The search and analysis pipelines run live AI, so a slow response is normal, not a
failure:

- Use a client timeout of **≥ 60s** for search; deep analysis is asynchronous (start, then
  poll) and usually finishes in 30–240s.
- Don't apply a generic "no response in 10–15s → give up" rule — it kills live requests.
- An **empty result after ~45s** is almost always a timeout, not "nothing found". Raise
  the timeout and retry before concluding there is no practice.

`SKILL.md` has the full guidance, including an ordered self-check (reachable →
authorized → end-to-end) and a symptom → cause table for `401` / `403` / `429`,
`invalid_token`, and missing MCP tools.

## Layout

```
agent-skills/
├── .agents/plugins/marketplace.json  # Codex plugin marketplace descriptor
├── .claude-plugin/
│   ├── marketplace.json          # Claude Code plugin marketplace descriptor
│   └── plugin.json               # the `courts` plugin (→ ./skills, → ./.mcp.json)
├── .codex-plugin/plugin.json     # Codex plugin manifest
├── .mcp.json                     # bundled reputation MCP server (API key via ${REPUTATION_API_KEY})
└── skills/
    └── court-practice/
        ├── SKILL.md
        └── scripts/court_client.py   # zero-dependency REST client + analysis polling
```

## Contributing

Keep `SKILL.md` focused; the description must say **when** to use the skill — that's
what the agent matches on. Put endpoints, tool names, and routing in the section that
owns them (Search / Deep analysis / Document text / Setup).
