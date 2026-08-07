---
name: courts-setup
description: >-
  Set up access to the reputation.ru court service — connect the MCP server or
  configure the REST API key. Run this FIRST if court-search, court-deep-analysis,
  or court-document report missing tools, or return 401/403/"unauthorized". Also
  bundles a dependency-free REST client (court_client.py) for agents without MCP.
user-invocable: true
version: 0.1.0
requires:
  env:
    - REPUTATION_API_KEY
primaryEnv: REPUTATION_API_KEY
metadata:
  author: reputation
  openclaw:
    envVars:
      - name: REPUTATION_API_KEY
        required: true
        description: >-
          API key for the reputation.ru court service — a PAID third-party API.
          Requires a reputation.ru account (get a key at
          https://reputation.ru/account/api). Calls are billed per the service
          tariff.
---

# Court service setup (reputation.ru)

> **Paid service.** reputation.ru is a paid court API — you need an account and API key, and calls are billed per the service tariff.

Connect an agent to the reputation.ru court service. There are two ways in — the
**MCP server** (preferred) or the **REST API** directly. Either way you need an
API key.

## 1. Get an API key

Create one at https://reputation.ru/account/api ("Создать API ключ"). It goes in
an `Authorization` header on every request.

## 2a. Connect via MCP (preferred)

Add the reputation MCP server to your agent's MCP config
(`.claude/mcp.json`, `~/.cursor/mcp.json`, Claude Desktop config, or your
runtime's equivalent), then restart the client:

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

This exposes the tools the court-* skills use:
`search_arbitration_cases`, `search_general_court_cases`, `search_vsrf_documents`,
`deep_research_request` / `deep_research_status` / `deep_research_result`,
`get_general_court_document`, `get_arbitration_document`.

## 2b. Use the REST API (no MCP)

Base URL `https://api.reputation.ru`; send `Authorization: <api-key>` on every
call. Endpoints are documented inside each court-* skill. A ready client that
handles requests, JSON, and the async analysis polling loop is bundled here:

```bash
export REPUTATION_API_KEY=<your-api-key>
# optional: export REPUTATION_BASE_URL=https://api.reputation.ru

python scripts/court_client.py search general "взыскание процентов по ст. 395 ГК РФ"
python scripts/court_client.py analyze "как суды взыскивают неустойку по ДДУ"
python scripts/court_client.py doc arbitr <DocId>
```

`court_client.py` uses only the Python standard library — no install needed.

## 3. Verify

Run a cheap search (`court-search`) — e.g. `search_vsrf_documents("обзор
судебной практики")` or `court_client.py search vsrf "обзор судебной практики"`.
A non-empty result confirms the key and connection.

## Troubleshooting

- `401` — missing/invalid API key. Check the `Authorization` header / `REPUTATION_API_KEY`.
- `403` — the key lacks access to that endpoint.
- `429` — rate limit; back off and retry.
- MCP tools not appearing — re-check the config path and restart the client;
  some clients cache the tool list.

## Court systems (routing quick reference)

- **Arbitration** (`search_arbitration_cases`) — org-vs-org: debt, bankruptcy,
  tax, corporate, contracts, IP, state bodies. Case no. `А40-12345/2024`; docs → `DocId`.
- **General jurisdiction / СОЮ** (`search_general_court_cases`) — individuals:
  family, labour, consumer, criminal, administrative, housing. Case no.
  `2-1700/2025`; docs → `FileId`.
- **Supreme Court / ВС РФ** (`search_vsrf_documents`) — Пленум resolutions,
  practice reviews, Президиум — legal positions, not individual cases.

## Billing (so skills can warn the user)

- Each **search** call = one billed request.
- **Deep analysis** = one billed request at `deep_research_request`; status &
  result are free.
- **Document text** retrieval is billed per the service's tariff.
