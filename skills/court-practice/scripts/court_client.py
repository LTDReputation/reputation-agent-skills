#!/usr/bin/env python3
"""
Minimal, dependency-free client for the reputation.ru court API.

For agents that can run code but don't have the reputation MCP connected. Uses
only the Python standard library.

Auth: set REPUTATION_API_KEY (get a key at https://reputation.ru/account/api).
Base URL overridable via REPUTATION_BASE_URL (default https://api.reputation.ru).

CLI:
    python court_client.py search {arbitr|general|vsrf} "запрос на русском"
    python court_client.py analyze "тема для глубокого анализа"
    python court_client.py doc {arbitr|general} <document-id>
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("REPUTATION_BASE_URL", "https://api.reputation.ru").rstrip("/")
API_KEY = os.environ.get("REPUTATION_API_KEY", "")

SEARCH_ENDPOINTS = {
    "arbitr": "/api/v2/arbitr/ai-search",
    "general": "/api/v3/general-jurisdiction-courts/ai-search",
    "vsrf": "/api/v1/vsrf/ai-search",
}
# (endpoint, id query-param name)
DOCUMENT_ENDPOINTS = {
    "arbitr": ("/api/v1/arbitr/document/text", "docId"),
    "general": ("/api/v3/general-jurisdiction-courts/documents/text", "id"),
}
ANALYSIS = {
    "request": "/api/v1/ai-analysis/request",
    "status": "/api/v1/ai-analysis/status",
    "result": "/api/v1/ai-analysis/result",
}


class CourtApiError(Exception):
    pass


def _request(method, path, *, params=None, body=None, expect="json", timeout=60):
    if not API_KEY:
        raise CourtApiError("REPUTATION_API_KEY is not set")
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": API_KEY}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.status == 204:
                return None
            if expect == "text":
                return raw.decode("utf-8", "replace")
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise CourtApiError(f"HTTP {e.code} on {method} {path}: {detail}") from None


def search(system, query):
    """Fast AI search in one court system. Returns the paginated collection dict."""
    if system not in SEARCH_ENDPOINTS:
        raise CourtApiError(f"unknown system {system!r}; use one of {list(SEARCH_ENDPOINTS)}")
    return _request("POST", SEARCH_ENDPOINTS[system], body={"Query": query})


def document_text(system, doc_id):
    """Full text of a case document by its id (FileId for general, DocId for arbitr).

    Returns the text, or None if the document has no indexed text (204/404)."""
    if system not in DOCUMENT_ENDPOINTS:
        raise CourtApiError(f"unknown system {system!r}; use one of {list(DOCUMENT_ENDPOINTS)}")
    endpoint, id_param = DOCUMENT_ENDPOINTS[system]
    try:
        return _request("GET", endpoint, params={id_param: doc_id}, expect="text")
    except CourtApiError as e:
        if "HTTP 404" in str(e):
            return None
        raise


def analyze(query, poll_interval=12, timeout=300):
    """Run the full async deep-research flow: request -> poll -> result.

    Returns {"Report": ..., "CaseIds": [...]}. Raises on failure/timeout."""
    created = _request("POST", ANALYSIS["request"], body={"Query": query})
    request_id = created.get("RequestId") or created.get("requestId")
    if not request_id:
        raise CourtApiError("analysis request did not return a RequestId")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = _request("GET", ANALYSIS["status"], params={"RequestId": request_id})
        state = (status.get("Status") or status.get("status") or "").strip()
        if state == "Done":
            return _request("GET", ANALYSIS["result"], params={"RequestId": request_id})
        if state == "Failed":
            raise CourtApiError(f"analysis {request_id} failed")
        time.sleep(poll_interval)
    raise CourtApiError(f"analysis {request_id} did not finish within {timeout}s")


def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "search" and len(argv) >= 4:
        print(json.dumps(search(argv[2], argv[3]), ensure_ascii=False, indent=2))
    elif cmd == "analyze" and len(argv) >= 3:
        print(json.dumps(analyze(argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "doc" and len(argv) >= 4:
        text = document_text(argv[2], argv[3])
        print(text if text is not None else "(no indexed text for this document)")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
