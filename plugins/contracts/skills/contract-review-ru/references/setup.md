# Подключение MCP-серверов reputation.ru

Нужно один раз. Пропусти, если инструменты `resolve_company`, `get_risk_report`, `search_legal_norms` уже доступны.

Скилл работает с двумя серверами:

| Имя в конфиге | URL | Что даёт |
|---|---|---|
| `reputation-company` | `https://api-staging.reputation.ru/mcp/companies` | проверка контрагента |
| `reputation-ai-search` | `https://api-staging.reputation.ru/mcp` | нормы права и судебная практика |

При установке плагина `contracts` оба сервера подключаются автоматически из его `.mcp.json` — с API-ключом из переменной окружения `REPUTATION_API_KEY`.

## API-ключ — основной способ

Пользователь создаёт ключ на https://reputation.ru/account/api («Создать API ключ») и задаёт его в окружении **до запуска клиента**:

```bash
export REPUTATION_API_KEY=<ключ>
```

Ключ передаётся как есть, без `Bearer`, в заголовке `Authorization`:

```json
{
  "mcpServers": {
    "reputation-company": {
      "type": "http",
      "url": "https://api-staging.reputation.ru/mcp/companies",
      "headers": { "Authorization": "${REPUTATION_API_KEY}" }
    },
    "reputation-ai-search": {
      "type": "http",
      "url": "https://api-staging.reputation.ru/mcp",
      "headers": { "Authorization": "${REPUTATION_API_KEY}" }
    }
  }
}
```

То же из командной строки Claude Code:

```bash
claude mcp add --transport http reputation-company https://api-staging.reputation.ru/mcp/companies --header "Authorization: $REPUTATION_API_KEY"
claude mcp add --transport http reputation-ai-search https://api-staging.reputation.ru/mcp --header "Authorization: $REPUTATION_API_KEY"
```

Ключ даёт пользователь — сам его не придумывай и не выводи в чат, отчёт или логи. Если переменная не задана, попроси пользователя задать её и перезапустить клиент. Вызовы списываются со счёта пользователя по тарифу сервиса.

## Вход через аккаунт (OAuth) — альтернатива

Серверы поддерживают и вход через аккаунт reputation.ru. Для этого сервер указывается **без `headers`** — со статическим `Authorization` клиент вход не предложит. При первом обращении клиент получает `401` с `WWW-Authenticate`, находит сервер авторизации (`https://reputation.ru`) и открывает браузер для входа.

Пройти этот вход сам ты не можешь — нужен человек в браузере (Claude Code: `/mcp` → сервер → Authenticate). Никогда не проси прислать код авторизации, токен или callback-URL.

## Симптом → причина

| Симптом | Причина / что делать |
|---|---|
| инструментов нет в списке | сервер не подключён, не задан `REPUTATION_API_KEY` или клиент закэшировал список — проверь конфиг и переменную, перезапусти клиент |
| `401` | ключ не передан или неверен — проверь `REPUTATION_API_KEY` (ключ должен быть от того же окружения, что и сервер: staging или prod) |
| `401` + `WWW-Authenticate: Bearer … resource_metadata=…` | заголовок `Authorization` не дошёл — переменная пустая или конфиг без `headers` |
| ответ «ПРОВЕРКА НЕ ВЫПОЛНЕНА…» | данные не получены (ошибка API, нет прав) — в отчёте пиши «не проверено», не «рисков нет» |
| `403 Forbidden` от nginx или таймаут к `api-staging.reputation.ru` | staging открыт не из всех сетей — нужен разрешённый IP / VPN |
| пустой поиск практики через ~45 с | таймаут, а не «ничего не найдено» — упрости запрос, повтори |
| `429` | лимит запросов — подожди и повтори |

Если сервер так и не подключился — проводи проверку договора без него, а в отчёте (разделы «Контрагент и подписант» и «Что перепроверить юристу») прямо укажи, какие проверки не выполнены и что для них нужно.
