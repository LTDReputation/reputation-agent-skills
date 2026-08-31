---
name: court-practice
description: >-
  Russian court practice (судебная практика РФ) via reputation.ru — find cases,
  get a synthesized analysis report, or fetch a document's full text across
  arbitration (арбитраж), general jurisdiction (СОЮ), and the Supreme Court
  (ВС РФ). Use for «найди практику по…», «как суды решают…», «обзор практики»,
  «полный текст решения». Paid service — needs REPUTATION_API_KEY; if tools are
  missing or you get 401/403, do the Setup section first.
user-invocable: true
argument-hint: <вопрос на русском, напр. «взыскание неустойки по ДДУ»>
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

# Russian court practice (reputation.ru)

> **Paid service.** Uses the reputation.ru court API — a paid third-party service that needs a reputation.ru account and API key (`REPUTATION_API_KEY`; get one at https://reputation.ru/account/api). Calls are billed per the service tariff.

One skill covering Russian court practice, with three capabilities plus setup:

- **Search** — a fast, relevant list of cases (the default).
- **Deep analysis** — an asynchronous synthesized report across all court systems.
- **Document text** — the full text of one document by its id.

Work through the MCP tools when the reputation MCP is connected; otherwise use the
REST API (or the bundled `scripts/court_client.py`). If tools are missing or a call
returns `401`/`403`, do **Setup** first.

---

## Setup

Needed once — skip if the reputation MCP tools already work.

### 1. Get an API key

Create one at https://reputation.ru/account/api ("Создать API ключ"). It goes in an
`Authorization` header on every request.

### 2a. Connect via MCP (preferred)

Add the reputation MCP server to your agent's MCP config (`.claude/mcp.json`,
`~/.cursor/mcp.json`, Claude Desktop config, or your runtime's equivalent), then
restart the client:

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

This exposes: `search_arbitration_cases`, `search_general_court_cases`,
`search_vsrf_documents`, `deep_research_request` / `deep_research_status` /
`deep_research_result`, `get_general_court_document`, `get_arbitration_document`.

### 2b. Use the REST API (no MCP)

Base URL `https://api.reputation.ru`; send `Authorization: <api-key>` on every call.
A ready client that handles requests, JSON, and the async analysis polling loop is
bundled here (Python stdlib only — no install):

```bash
export REPUTATION_API_KEY=<your-api-key>
# optional: export REPUTATION_BASE_URL=https://api.reputation.ru

python scripts/court_client.py search general "взыскание процентов по ст. 395 ГК РФ"
python scripts/court_client.py analyze "как суды взыскивают неустойку по ДДУ"
python scripts/court_client.py doc arbitr <DocId>
```

### 3. Verify

Run a cheap search — e.g. `search_vsrf_documents("обзор судебной практики")` or
`court_client.py search vsrf "обзор судебной практики"`. A non-empty result confirms
the key and connection.

---

## Route to the right court system

- **Arbitration** (арбитраж) — disputes between organizations/entrepreneurs: debt
  between companies, bankruptcy of ООО/ИП, corporate conflicts, contracts (поставка,
  подряд, аренда), tax (ФНС), IP/trademarks, state bodies (ФАС). Case no.
  `А40-12345/2024`; document id → **`DocId`**.
- **General jurisdiction** (СОЮ) — disputes involving individuals: family (развод,
  алименты), inheritance, labour, consumer protection, insurance (ОСАГО/КАСКО),
  **criminal**, administrative (КоАП), housing. Case no. `2-1700/2025`; document id
  → **`FileId`**.
- **Supreme Court** (ВС РФ) — high-court legal positions: постановления Пленума,
  обзоры практики, Президиум. For "what's the established position on…", not for
  individual cases. (No separate document-text endpoint — its search results already
  carry the text.)

If a question spans systems, search the two most likely — or use **Deep analysis**,
which covers all three.

---

## 1. Search (fast — the default)

**MCP** — call the matching tool with `query`:

| System | Tool |
|---|---|
| Arbitration | `search_arbitration_cases(query)` |
| General jurisdiction | `search_general_court_cases(query)` |
| Supreme Court | `search_vsrf_documents(query)` |

**REST** — `Authorization: <api-key>`, base `https://api.reputation.ru`,
body `{ "Query": "<вопрос на русском>" }`:

| System | `POST` path |
|---|---|
| Arbitration | `/api/v2/arbitr/ai-search` |
| General jurisdiction | `/api/v3/general-jurisdiction-courts/ai-search` |
| Supreme Court | `/api/v1/vsrf/ai-search` |

Or `court_client.py search {arbitr|general|vsrf} "<query>"`.

**Tips:** write the query **in Russian**, describing the situation and naming the
norm when relevant (`банкротство ООО по заявлению кредитора`). **Each search call is
billed as one request** — refine deliberately, don't spam near-duplicates.

---

## 2. Deep analysis (async synthesized report)

Use when the user wants a *synthesized answer across practice* («сложившаяся практика
по…», «как суды решают…», «обзор практики»), not just a case list. One async job
searches all three systems, filters by relevance, and returns a Markdown **report**
with embedded case links plus the ids of the cases it cites.

**Start → poll → fetch** — don't block on a single call:

1. **Start** (billed once, here):
   - MCP: `deep_research_request(query)` → `request_id`
   - REST: `POST /api/v1/ai-analysis/request` `{ "Query": "…" }` → `{ "RequestId": "…" }`
2. **Poll status** (not billed) — every ~10–15s:
   - MCP: `deep_research_status(request_id)` → `InProcess` | `Done` | `Failed`
   - REST: `GET /api/v1/ai-analysis/status?RequestId=<id>` → `{ "Status": "…" }`
3. **Fetch result** when `Done` (not billed):
   - MCP: `deep_research_result(request_id)`
   - REST: `GET /api/v1/ai-analysis/result?RequestId=<id>` → `{ "Report": "…", "CaseIds": [ … ] }`

Rules: usually `Done` in ~30–120s. If it exceeds a few minutes without `Done`/`Failed`,
stop and tell the user rather than polling forever. `Failed` → the job errored; you
may start a new request. One-shot alternative: `court_client.py analyze "<тема>"` runs
the whole loop and returns the report. Return the report as-is — **keep its embedded
case links**; you may append the cited `CaseIds` as a short reference list.

---

## 3. Document text

Retrieve the full plain text of a specific document. You need an id from a prior
**search** result — this does not search for cases.

**MCP:**

| System | Tool |
|---|---|
| General jurisdiction | `get_general_court_document(file_id=<FileId>)` |
| Arbitration | `get_arbitration_document(doc_id=<DocId>)` |

**REST** — `Authorization: <api-key>`, base `https://api.reputation.ru`, returns
`text/plain`:

| System | `GET` path | Id param | Empty-text status |
|---|---|---|---|
| General jurisdiction | `/api/v3/general-jurisdiction-courts/documents/text` | `id` = `FileId` | `204` |
| Arbitration | `/api/v1/arbitr/document/text` | `docId` = `DocId` | `404` |

Or `court_client.py doc {general|arbitr} <id>`. A `204`/`404` (or empty text) means
the document has **no indexed text** — tell the user; don't fabricate content.

---

## Presenting results

- Always cite the **case number** and its link (`WebsiteUrl`) so the user can open the
  card.
- An empty search result may mean "nothing found" **or** a timeout — if empty, note
  that simplifying the query may help.
- Quote or summarize only what the returned cases/text actually support — don't
  fabricate case numbers, parties, outcomes, or document content.

## Billing (so you can warn the user)

- Each **search** call = one billed request.
- **Deep analysis** = one billed request at start (`deep_research_request`); status &
  result are free.
- **Document text** retrieval is billed per the service tariff.

## Troubleshooting

- `401` — missing/invalid API key. Check the `Authorization` header / `REPUTATION_API_KEY`.
- `403` — the key lacks access to that endpoint.
- `429` — rate limit; back off and retry.
- `400` on document text — missing id param.
- MCP tools not appearing — re-check the config path and restart the client; some
  clients cache the tool list.
