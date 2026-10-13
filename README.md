# AI Support API

Async customer-support agent built with **FastAPI**, **Redis**, and **OpenRouter**.

External systems submit a support ticket, receive a `job_id` immediately, then poll until the agent finishes (`DONE` / `WAITING` / `PASS` / `ERR`).

> **Warning — do not trust the AI for access control.**  
> Authorization must be enforced by **your tool APIs**, not by model behavior or prompts.  
> Every tool request from this service forwards `SUPPORT_TOOL_KEY` (also sent as `Support-Tool-Key`). Your backends must validate that key, bind each call to the authenticated subject (e.g. the real `user_id` from your session/token — not values invented in chat), and reject cross-account or privileged reads/writes. The model can choose tool ids and arguments, including wrong `user_id`s; treat that as untrusted input.

## Features

- Single async submit endpoint + poll endpoint
- Structured OpenRouter decisions via Pydantic / JSON Schema
- Multi-round tool calling (max 3 AI rounds; final round cannot call tools)
- Concurrent HTTPS tool execution with `SUPPORT_TOOL_KEY` header forwarding
- Redis-backed job state (default TTL 1 hour)
- SSRF-hardened tool URL validation (HTTPS only, no localhost/private IPs)
- Prompt-injection guards on user `q`
- Token cost aggregation from fixed OpenRouter price table

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: API_KEY, OPENROUTER_API_KEY, REDIS_URL
```

Redis must be running and reachable via `REDIS_URL`.

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Docs: `http://localhost:8000/docs`

## Deploy (Docker)

One container: Nginx on `:80` → Uvicorn. Redis is external (set `REDIS_URL` in `.env`).

```bash
cp .env.example .env
# set API_KEY, OPENROUTER_API_KEY, REDIS_URL
docker build -t ai-support:latest .
docker run -d --name ai-support -p 80:80 --env-file .env ai-support:latest
```

- Health: `GET /health`
- Mirrors: `mirror-docker.runflare.com`, `mirror-pypi.runflare.com`, `mirror-linux.runflare.com`

## Endpoints

### `POST /support` → `202`

Headers:

| Header | Description |
|--------|-------------|
| `API_KEY` | Shared secret (`API_KEY` env) |
| `SUPPORT_TOOL_KEY` | Forwarded as header on every tool HTTP call |
| `AI_MODEL` | OpenRouter model id, e.g. `google/gemini-2.5-flash` |

Body:

```json
{
  "q": "لینک من خرابه",
  "initial_data": {"user_id": 125},
  "system_data": {
    "note_prompt": "",
    "knowledge": "…",
    "tools": [
      {
        "id": 1,
        "title": "Check link",
        "endpoint": "https://api.example.com/links/check",
        "usecase": "Validate download link",
        "method": "POST",
        "act": "READ",
        "body_params": [
          {
            "param": "url",
            "usecase": "Broken link",
            "type": "STR",
            "limits": "max length 2048",
            "required": true
          }
        ],
        "sensitivity_level": 1,
        "developer_message": ""
      }
    ]
  },
  "history": [
    {"role": "user", "message": "لینک من خرابه"},
    {
      "role": "bot",
      "response": {
        "support_state": "WAITING",
        "message_for_user": "لطفا لینک خراب را ارسال کنید.",
        "message_for_admin": null,
        "report_for_system": "Asked user for the broken link.",
        "tools_usage": [],
        "cost_in_usd": 0.001
      }
    }
  ]
}
```

Response:

```json
{ "job_id": "uuid" }
```

### `GET /support/{job_id}`

Same `API_KEY` header.

Pending:

```json
{ "status": "PENDING", "job_id": "uuid" }
```

Done:

```json
{
  "status": "DONE",
  "job_id": "uuid",
  "result": {
    "support_state": "DONE",
    "message_for_user": "…",
    "message_for_admin": null,
    "report_for_system": "…",
    "tools_usage": [1, 2, 1],
    "cost_in_usd": 0.0123
  }
}
```

## Agent loop

1. Build trusted system prompt (`note_prompt`, `knowledge`, tools catalog without endpoints).
2. Wrap `q` + `initial_data` as untrusted data fences.
3. Ask OpenRouter for a structured decision.
4. If `TOOL_CALLS` → execute tools concurrently → append results → repeat (max 3 AI rounds).
5. On round 3, only `WAITING` / `DONE` / `PASS` are accepted.
6. Persist final `SupportResponse` in Redis.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | required | Shared inbound API key |
| `OPENROUTER_API_KEY` | required | OpenRouter bearer token |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `JOB_TTL_SECONDS` | `3600` | Job + payload TTL |
| `TOOL_HTTP_TIMEOUT_SECONDS` | `15` | Per-tool HTTP timeout |

## Project layout

```
app/
  api/support.py          # POST/GET /support
  schemas/                # Pydantic request/response/AI schemas
  security/               # auth, URL SSRF checks, prompt-injection
  services/               # agent, OpenRouter, tools, Redis, cost
  constants.py            # pricing + limits
  config.py               # env settings
  main.py                 # FastAPI app
```
