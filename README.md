# agent-skills

Portable [Agent Skills](https://agentskills.io) for **reputation.ru** — search and
analyze Russian court practice (судебная практика РФ) and review contracts under
Russian law (проверка договора) from any skills-compatible AI agent (Claude / Claude Code, Cursor, Gemini CLI,
OpenCode, Goose, Codex, and others).

Each skill is a self-contained folder with a `SKILL.md`. Agents load only its name
and description until a task matches, then read the full instructions — so it costs
little context until actually used.

## Skills

| Plugin | Skill | What it does |
|---|---|---|
| `courts` | [`court-practice`](plugins/courts/skills/court-practice/) | Court practice search, deep analysis, document text |
| `contracts` | [`contract-review-ru`](plugins/contracts/skills/contract-review-ru/) | Contract review for lawyers: counterparty + signatory check, risks, redlines, PDF conclusion |

### court-practice

One skill, [`court-practice`](plugins/courts/skills/court-practice/), covering the whole court
service:

| Capability | Use it for |
|---|---|
| **Search** | **Default.** Find relevant court cases (арбитраж / СОЮ / ВС РФ) by a legal question — fast, seconds. |
| **Deep analysis** | A synthesized analytical report across practice («сложившаяся практика по…»). Asynchronous, ~30–120s. |
| **Document text** | Fetch the full text of a specific case document (by `FileId`/`DocId` from search). |
| **Setup** | Connect the service — MCP server or REST API key. Do first. Bundles a zero-dependency REST client. |

The skill is built around the reputation **MCP server** (the tool layer); when MCP
isn't connected it falls back to the **REST API** via the bundled `court_client.py`.

### contract-review-ru

A lawyer's assistant for contract review under Russian law. It reads the contract for
the side you represent and works through a fixed methodology: counterparty check,
signatory authority, technical check, validity, clause-by-clause risks, missing terms,
how counterparty findings change the contract, and legal verification of each risk.
It returns a **PDF conclusion** with ready-to-insert clause wording, plus an editable
**DOCX** protocol of disagreements on request.

| Uses | For |
|---|---|
| `reputation-company` MCP — `resolve_company` → **`get_risk_report`** + `get_company_profile`, targeted deep-dives (`get_court_cases`, `get_debts`, `get_registries`, …) | counterparty (company or ИП) and signatory checks |
| `reputation-ai-search` MCP — `search_legal_norms` / `get_legal_norm_text`, `search_vsrf_documents`, `search_arbitration_cases` | current wording of norms and court practice behind each risk |
| bundled [`render_report.py`](plugins/contracts/skills/contract-review-ru/scripts/render_report.py) | Markdown → PDF (weasyprint or headless Chrome/Edge) and DOCX (no dependencies), colour-and-word risk badges, page numbers, Cyrillic check |

Both MCP servers authorize with a reputation.ru **API key** from `REPUTATION_API_KEY`,
sent as the `Authorization` header. The servers also support account sign-in (OAuth);
see the skill's [setup notes](plugins/contracts/skills/contract-review-ru/references/setup.md).

> The `contracts` plugin currently points at **staging**:
> `https://api-staging.reputation.ru/mcp/companies` (company data) and
> `https://api-staging.reputation.ru/mcp` (norms and court practice). Staging may be
> reachable only from allowed networks. Switch
> [`plugins/contracts/.mcp.json`](plugins/contracts/.mcp.json) and
> [`references/setup.md`](plugins/contracts/skills/contract-review-ru/references/setup.md)
> to production URLs once mcp-company is published.

## Requirements

- A reputation.ru account: sign in via OAuth from the assistant, or an API key from
  https://reputation.ru/account/api.
- `courts`: either the reputation MCP server connected, or the ability to call the REST API
  (the bundled `court_client.py` uses only the Python standard library).
- `contracts`: Python 3 and, for PDF, either weasyprint or Chrome / Chromium / Edge.

## Install

**As a Claude Code plugin (recommended).** This repo is a Claude Code plugin
marketplace. Add it, then install the `courts` plugin — you get the skill as a
slash command (`/courts:court-practice`) and the reputation MCP server auto-wired
from [`plugins/courts/.mcp.json`](plugins/courts/.mcp.json):

```
/plugin marketplace add LTDReputation/reputation-agent-skills
/plugin install courts@reputation-agent-skills
```

Then set your key so the bundled MCP can authenticate:

```bash
export REPUTATION_API_KEY=<your-api-key>   # from https://reputation.ru/account/api
```

For contract review, install the `contracts` plugin (`/contracts:contract-review-ru`).
Its two MCP servers are wired from
[`plugins/contracts/.mcp.json`](plugins/contracts/.mcp.json) and read the same
`REPUTATION_API_KEY` (use a staging key while the plugin points at staging):

```
/plugin install contracts@reputation-agent-skills
```

**As a Codex plugin.** A Codex manifest is provided at
[`plugins/courts/.codex-plugin/plugin.json`](plugins/courts/.codex-plugin/plugin.json) (courts) and
[`plugins/contracts/.codex-plugin/plugin.json`](plugins/contracts/.codex-plugin/plugin.json)
(contracts) — install
via the Codex skill installer pointing at this repo.

**Manual (any skills-compatible agent).** Copy the skill folder into your
agent's skills directory:

```bash
mkdir -p .claude/skills
cp -r plugins/courts/skills/* .claude/skills/
cp -r plugins/contracts/skills/* .claude/skills/
```

Each skill's setup section connects the MCP server (or sets an API key); do that
first, then use it for everyday lookups. The `SKILL.md` format is the same across
runtimes — consult your agent's docs for its exact skills path.

## Layout

```
reputation-agent-skills/
├── .claude-plugin/marketplace.json   # Claude Code marketplace — lists both plugins
├── .agents/plugins/marketplace.json  # Codex marketplace — lists both plugins
├── README.md
└── plugins/
    ├── courts/                       # the `courts` plugin
    │   ├── .claude-plugin/plugin.json
    │   ├── .codex-plugin/plugin.json
    │   ├── .mcp.json                 # reputation-court-search (key via ${REPUTATION_API_KEY})
    │   └── skills/court-practice/
    │       ├── SKILL.md
    │       └── scripts/court_client.py   # zero-dependency REST client + SOD polling
    └── contracts/                    # the `contracts` plugin
        ├── .claude-plugin/plugin.json
        ├── .codex-plugin/plugin.json
        ├── .mcp.json                 # reputation-company + reputation-ai-search (key via ${REPUTATION_API_KEY})
        └── skills/contract-review-ru/
            ├── SKILL.md              # the review methodology + tool routing
            ├── references/           # setup.md, contract-types.md
            └── scripts/render_report.py  # Markdown → PDF / DOCX
```

Each plugin is self-contained under `plugins/<name>/`; the repo root holds only the
marketplace catalogs. To add a plugin, create `plugins/<name>/` with the same shape and
list it in both marketplace files.

## Contributing

Keep `SKILL.md` focused; the description must say **when** to use the skill — that's
what the agent matches on. Put endpoints, tool names, and routing in the section that
owns them (Search / Deep analysis / Document text / Setup; for contracts — «Инструменты Репутации»).
