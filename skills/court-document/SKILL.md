---
name: court-document
description: >-
  Fetch the full text of one Russian court-case document by its id, using an id
  that came from court-search results (FileId for general jurisdiction, DocId
  for arbitration). Use after court-search when the user needs the actual
  document text — not to search for cases. If tools are missing or you get
  401/403, run courts-setup first.
user-invocable: true
argument-hint: <document id from search results>
metadata:
  author: reputation
---

# Court document text (reputation.ru)

Retrieve the full plain text of a specific case document. You need an id from a
prior **court-search** result — this skill does not search for cases.

## Which id

- **General jurisdiction (СОЮ)** — the document's **`FileId`**.
- **Arbitration** — the document's **`DocId`**.

(The Supreme Court / ВС РФ has no separate document-text endpoint; its search
results already carry the relevant text.)

## Fetch it

**If the reputation MCP is connected:**

| System | Tool |
|---|---|
| General jurisdiction | `get_general_court_document(file_id=<FileId>)` |
| Arbitration | `get_arbitration_document(doc_id=<DocId>)` |

**Otherwise (REST)** — `Authorization: <api-key>`, base `https://api.reputation.ru`,
returns `text/plain`:

| System | `GET` path | Id param | Empty-text status |
|---|---|---|---|
| General jurisdiction | `/api/v2/general-jurisdiction-courts/documents/text` | `id` = `FileId` | `204` |
| Arbitration | `/api/v1/arbitr/document/text` | `docId` = `DocId` | `404` |

Or: `court_client.py doc {general|arbitr} <id>` from **courts-setup**.

## Handling the result

- A `204`/`404` (or empty text) means the document has **no indexed text** — tell
  the user that; do not fabricate document content.
- Missing id param → `400`.
- Quote or summarize only what the returned text actually contains.
