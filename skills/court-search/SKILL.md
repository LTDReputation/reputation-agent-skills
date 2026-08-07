---
name: court-search
description: >-
  DEFAULT for finding Russian court cases (судебная практика РФ) by a legal
  question — arbitration (арбитраж), general jurisdiction (СОЮ), and the Supreme
  Court (ВС РФ). Returns a relevant list of cases in seconds. Use
  court-deep-analysis instead only when the user wants a synthesized report on
  how courts decide a topic; use court-document to fetch a case's full text. If
  tools are missing or you get 401/403, run courts-setup first.
user-invocable: true
argument-hint: <запрос на русском, напр. «взыскание процентов по ст. 395 ГК РФ»>
metadata:
  author: reputation
---

# Court search (fast, reputation.ru)

Natural-language search over Russian court practice. One tool/endpoint per court
system — **route by the nature of the dispute**, then pass the user's question
in Russian.

## Route to the right system

- **Arbitration** — disputes between organizations/entrepreneurs: debt between
  companies, bankruptcy of ООО/ИП, corporate conflicts, contracts (поставка,
  подряд, аренда), tax (ФНС), IP/trademarks, state bodies (ФАС).
- **General jurisdiction (СОЮ)** — disputes involving individuals: family
  (развод, алименты), inheritance, labour, consumer protection, insurance
  (ОСАГО/КАСКО), **criminal**, administrative (КоАП), housing.
- **Supreme Court (ВС РФ)** — high-court legal positions: постановления Пленума,
  обзоры практики, Президиум. For "what's the established position on…", not for
  individual cases.

If the question spans systems, search the two most likely — or use
**court-deep-analysis**, which covers all three.

## Run the search

**If the reputation MCP is connected**, call the matching tool with `query`:

| System | Tool |
|---|---|
| Arbitration | `search_arbitration_cases(query)` |
| General jurisdiction | `search_general_court_cases(query)` |
| Supreme Court | `search_vsrf_documents(query)` |

**Otherwise (REST)** — `Authorization: <api-key>`, base `https://api.reputation.ru`:

| System | `POST` path |
|---|---|
| Arbitration | `/api/v2/arbitr/ai-search` |
| General jurisdiction | `/api/v2/general-jurisdiction-courts/ai-search` |
| Supreme Court | `/api/v1/vsrf/ai-search` |

Body: `{ "Query": "<вопрос на русском>" }`. Or use `court_client.py search
{arbitr|general|vsrf} "<query>"` from **courts-setup**.

## Query tips

- Write the query **in Russian**, describing the situation and naming the norm
  when relevant (`банкротство ООО по заявлению кредитора`).
- **Each search call is billed as one request** — refine deliberately, don't
  spam near-duplicates.

## Presenting results

- Always cite the **case number** and its link (`WebsiteUrl`) so the user can
  open the card.
- An empty result may mean "nothing found" **or** a search timeout — if empty,
  note that simplifying the query may help.
- Don't fabricate case numbers, parties, or outcomes — state only what the
  returned cases support.

## Next steps

- Full text of a specific document → **court-document** (use its `FileId`/`DocId`).
- A synthesized answer across practice → **court-deep-analysis**.
