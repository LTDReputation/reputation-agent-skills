---
name: court-deep-analysis
description: >-
  Use for a synthesized analytical report on Russian court practice — questions
  like «сложившаяся практика по…», «как суды решают…», «обзор практики». It
  searches all court systems (арбитраж, СОЮ, ВС РФ), filters by relevance, and
  writes a report with the cases it cites. Asynchronous, ~30–120s. For a simple
  list of cases use court-search instead. If tools are missing or you get
  401/403, run courts-setup first.
user-invocable: true
argument-hint: <тема анализа, напр. «как суды взыскивают неустойку по ДДУ»>
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

# Court deep analysis (reputation.ru)

> **Paid service.** Uses the reputation.ru court API — a paid third-party service that needs a reputation.ru account and API key (`REPUTATION_API_KEY`; get one at https://reputation.ru/account/api). Calls are billed per the service tariff. New here? Run **courts-setup** first.

Deep research: one asynchronous job searches all three court systems, filters by
relevance, and returns an analytical **report** (Markdown, with embedded case
links) plus the ids of the cases it cites. Use it when the user wants a
*synthesized answer across practice*, not just a case list.

## The async flow — the agent drives it

**Start → poll → fetch.** Do not block on a single call.

1. **Start** (billed once, here):
   - MCP: `deep_research_request(query)` → `request_id`
   - REST: `POST /api/v1/ai-analysis/request` `{ "Query": "…" }` → `{ "RequestId": "…" }`
2. **Poll status** (not billed) — every ~10–15s:
   - MCP: `deep_research_status(request_id)` → `InProcess` | `Done` | `Failed`
   - REST: `GET /api/v1/ai-analysis/status?RequestId=<id>` → `{ "Status": "…" }`
3. **Fetch result** when `Done` (not billed):
   - MCP: `deep_research_result(request_id)`
   - REST: `GET /api/v1/ai-analysis/result?RequestId=<id>` → `{ "Report": "…", "CaseIds": [ … ] }`

Rules:
- Usually `Done` in ~30–120s. If it exceeds a few minutes without `Done`/`Failed`,
  stop and tell the user rather than polling forever.
- `Failed` → the job errored; you may start a new request.
- One-shot alternative: `court_client.py analyze "<тема>"` from **courts-setup**
  runs the whole loop and returns the report.

## Presenting the report

- Return the report as-is — **keep its embedded case links**; don't rewrite them.
- You may append the cited `CaseIds` as a short reference list.
- Only claim what the report supports; don't add cases or conclusions it doesn't.

## When NOT to use this

If the user just wants relevant cases on a concrete question, use **court-search**
(faster and cheaper). Deep analysis is for synthesis across practice.
