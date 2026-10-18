# Security phase 2: credential activation plan (prepared 2026-10-18, NOT executed)

This plan is meant to run **after** the phase-1 deployment of the validated candidate images: backend
`7bef874d`, bridge `517755a5`, with all keys left unset. It complements `docs/SECURITY_DEPLOYMENT_GUIDE.md`
and `docs/N8N_SECURITY_INTEGRATION.md`. Every step needs the owner's explicit approval. No value is ever
written in Git, in workflow JSON, in logs or in chat.

## 0. Verified starting point (read-only audit, 2026-10-18)

| Item | Fact |
|---|---|
| Production backend `8adaf99` | **No authentication on `/ingestion/run` and `/index/run`**. The container still receives `TELEGRAM_BOT_TOKEN` and `N8N_ENCRYPTION_KEY`. |
| Candidate backend `7bef874d` (= commit `12828f3`) | Admin endpoints: 403 without `ADMIN_API_KEY`, 401 with a wrong key. Agent endpoints: open until `AGENT_API_KEY` is set. The key comparison is constant-time. Bodies over 15 MB get 413. |
| `.env` | `ADMIN_API_KEY`, `AGENT_API_KEY` and `ASSISTANT_WEBHOOK_KEY` are absent (names checked only) |
| n8n | 0 credentials. No HTTP node sends a header. The webhooks `assistant` and `retrieve` use `authentication: none`. |
| Workflow 03 | Six HTTP nodes use `onError: continueErrorOutput` and lead to "Respond: agent error" (HTTP 503), so **a 401 looks like an outage** |
| Network | Every port is bound to 127.0.0.1. Ollama listens on loopback only. The Telegram bridge uses outbound long polling. |

## 1. Credentials required

| Secret | Stored in | Used by |
|---|---|---|
| `AGENT_API_KEY` | `.env` → backend; n8n Header Auth credential "TNAA Backend Agent" (header `X-Agent-Key`) | wf 02 node "RAG Retriever (backend)"; wf 03 nodes Intent Router, RAG Retriever, Checklist Builder, Grounded Answer, Form-Filling Helper, Dossier Validator (**7 nodes**) |
| `ASSISTANT_WEBHOOK_KEY` | `.env` → telegram-bridge; host shell for the web proxy and CLI; n8n Header Auth credential "TNAA Assistant Entry" (header `X-Assistant-Key`) | Webhook nodes `POST /webhook/assistant` (wf 03) and `POST /webhook/retrieve` (wf 02) |
| `ADMIN_API_KEY` | `.env` → backend; n8n credential "TNAA Backend Admin" (header `X-Admin-Key`) | wf 01 nodes "Download official documents" and "Build chunks and index". **Set this only when a re-ingestion is actually planned.** |

Generate each value locally: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## 2. Activation order (callers first, enforcement last)

| # | Action | Expected effect | Smoke test (no Telegram message, no ingestion) |
|---|---|---|---|
| 1 | Back up: n8n CLI export of the 3 workflows, a copy of the n8n database, and the current `.env` (privately) | none | export files exist; checksums recorded |
| 2 | Create the "TNAA Backend Agent" credential in n8n. Attach it to the 7 nodes through the verified API update procedure (`docs/N8N_AUTHENTICATED_API_UPDATE.md`). Publish wf 02 and 03. | Headers are sent but ignored (key still unset) | `scripts/defect_probes.py http://127.0.0.1:5678/webhook/assistant <out>` gives 16/16; n8n executions succeed |
| 3 | Set `AGENT_API_KEY` in `.env`. Run `docker compose up -d --no-deps --no-build --pull never backend`. | Direct backend calls without the header get 401; n8n calls succeed | `curl -X POST 127.0.0.1:8000/agents/route` with no header → 401. The probes through the webhook give 16/16 again. |
| 4 | Set `ASSISTANT_WEBHOOK_KEY` in `.env`. Run `docker compose --profile telegram up -d --no-deps --no-build --pull never telegram-bridge`. Export the key in the web-proxy and CLI shells. | Clients send `X-Assistant-Key`; n8n still accepts requests without it | Bridge healthy; one owner-sent Telegram text answered |
| 5 | Create "TNAA Assistant Entry". Set `authentication: headerAuth` on both webhook nodes and publish. | Requests without the key are rejected by n8n | Webhook POST without the header → 401/403; with the header → 200. Then an owner-sent Telegram text. |
| 6 | Only when re-ingestion is planned: set `ADMIN_API_KEY`, recreate the backend, attach "TNAA Backend Admin" to wf 01 (it stays inactive) | Admin endpoints accept the key | No admin POST as a test. Verify the dependency through `tests/test_api_security.py` instead. |

## 3. Failure recovery

| Symptom | Likely cause | Recovery |
|---|---|---|
| Every assistant reply is the 503 "agent error" after step 3 | A node is missing the agent credential, or the key differs | Remove `AGENT_API_KEY` from `.env`, recreate the backend (enforcement is now off), fix the credential, then retry step 3 |
| Bridge gets 401/403 after step 5 | The bridge key differs from the n8n credential | Set wf 03's webhook back to `authentication: none` from the step-1 export; fix `.env`; recreate the bridge |
| Backend unhealthy after recreation | Configuration error | `docker compose logs backend`; restore the previous `.env` line; recreate |
| Ingestion or indexing needed during the activation | – | Postpone. Never test with a production admin POST. |

## 4. Rollback (one coordinated state)
1. Restore workflows 02 and 03 from the step-1 exports through the same verified API procedure (draft →
   verify → publish the exact version). Workflow 01 stays inactive.
2. Remove the three key lines from `.env`. Recreate the backend, then the bridge (`--no-deps --no-build`).
3. Run the read-only health checks (backend `/health`, n8n `/healthz`, bridge health), the probes 16/16 and an
   owner-sent Telegram text.

**Never** remove a caller's header while enforcement is still on.
