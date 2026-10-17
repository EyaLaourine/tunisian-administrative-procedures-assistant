# Security deployment guide (final candidate, 2026-10-17)

This guide describes how to activate the security controls of the final candidate **without breaking Telegram,
n8n or the web/CLI fallbacks**. Nothing here has been applied to production. Every step marked **[approval]**
changes live containers, workflows or credentials and requires the project owner's explicit approval.

## 1. Trust boundaries and entry points

| Entry point | Who calls it | Exposure | Protection in the candidate |
|---|---|---|---|
| Telegram Bot API (long polling) | Bridge → Telegram (outbound only) | No inbound port | Token only in the bridge environment; never logged |
| n8n `POST /webhook/assistant` | Bridge (internal network), web proxy and CLI (host loopback) | 127.0.0.1:5678 | Optional **Header Auth** (`X-Assistant-Key`); all three clients already send the header when `ASSISTANT_WEBHOOK_KEY` is set |
| n8n retrieval webhook (workflow 02) | Not used by workflow 03 | 127.0.0.1:5678 | Same Header Auth recommendation |
| Backend `/agents/*`, `/retrieve` (public assistant functions) | n8n HTTP nodes (internal network) | 127.0.0.1:8000 and the Docker network | Optional `AGENT_API_KEY` → `X-Agent-Key` required (prevents bypassing the webhook through direct backend access) |
| Backend `/ingestion/run`, `/index/run` (**privileged**, write data and Qdrant) | Operator or n8n workflow 01 (inactive) | Same | **Fail closed**: HTTP 403 unless `ADMIN_API_KEY` is configured; then `X-Admin-Key` is required (constant-time comparison) |
| Backend `/health`, `/sources`, `/manifest` | Monitoring, demo UI | Same | Public, read-only; no secret in responses |
| Qdrant (project) | Backend (internal network) | 127.0.0.1:6343 | No API key yet; see §5 |
| Web demo proxy | Browser on the same machine | 127.0.0.1:8090 | Input validation; optional `ASSISTANT_WEBHOOK_KEY` |

**Request limits:**
- The backend rejects bodies larger than `MAX_REQUEST_BYTES` (default 15 MB) with HTTP 413 before parsing.
- Uploads are additionally checked for type, signature and the 10 MB limit by the bridge, the web proxy and the
  agents.
- Rate limiting: the bridge allows one in-flight request per user and two globally. The HTTP entry points have
  no rate limiter; that is acceptable only while they are bound to loopback.

## 2. Environment variables (names only; never commit values)

| Variable | Container | Purpose | Default |
|---|---|---|---|
| `ADMIN_API_KEY` | backend | Enables privileged endpoints and requires `X-Admin-Key` | empty → privileged endpoints **disabled** |
| `AGENT_API_KEY` | backend | Requires `X-Agent-Key` on `/agents/*` and `/retrieve` | empty → open (current behaviour) |
| `MAX_REQUEST_BYTES` | backend | Request body limit | 15 MB |
| `ASSISTANT_WEBHOOK_KEY` | telegram-bridge; host shell for the web proxy and CLI | Value sent as `X-Assistant-Key` | empty → not sent |
| `QDRANT_API_KEY` | backend | Key for an authenticated Qdrant | empty |
| `QDRANT__SERVICE__API_KEY` | qdrant | Enables Qdrant authentication | empty |
| `TELEGRAM_BOT_TOKEN` | telegram-bridge only | Bot token | – |
| `N8N_ENCRYPTION_KEY` | n8n only | n8n credential encryption | – |

**Least privilege (candidate `docker-compose.yml`):**
- The backend no longer uses `env_file: .env`: it receives an explicit list without `TELEGRAM_BOT_TOKEN` or
  `N8N_ENCRYPTION_KEY`.
- The bridge receives only its token, the webhook URL and key, the upload limit and the log level.
- Verified with `docker compose config --format json`, by variable names only.

Generate keys locally, never in chat or logs (PowerShell):
```powershell
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```
Then put each value on its own line in `.env`.

## 3. Activation plan (ordered; each step reversible)

| Step | Action | Breaks anything? | Approval |
|---|---|---|---|
| 1 | Deploy the final-candidate backend and bridge images with the new Compose file (`docker compose up -d --no-deps backend`, then the bridge). With no new key set, behaviour is identical, except that `/ingestion/run` and `/index/run` return 403. | Only manual re-ingestion through HTTP, which is reactivated by step 2. The CLI (`python -m ingestion`) is unaffected. | **[approval]** |
| 2 | Set `ADMIN_API_KEY` in `.env` and recreate the backend. Workflow 01 must send `X-Admin-Key` (contract change, §4). | No | **[approval]** |
| 3 | Set `ASSISTANT_WEBHOOK_KEY` in `.env`. Recreate the bridge. Restart the web proxy and set it in the CLI shell. Clients now send the header, and n8n still accepts requests without auth. | No | **[approval]** |
| 4 | In n8n, create a *Header Auth* credential (name `X-Assistant-Key`, value = the key). Set `authentication: headerAuth` on the `POST /webhook/assistant` node of workflow 03 and re-publish. | Only clients without the key (intended) | **[approval]** (live workflow change) |
| 5 | Set `AGENT_API_KEY`. Add the header `X-Agent-Key` to the 6 HTTP nodes of workflow 03 (and to workflow 02 if used), using an n8n credential. Recreate the backend. | Direct backend calls without the key (intended) | **[approval]** (live workflow change) |
| 6 | Qdrant authentication (§5). | No, if done in order | **[approval]** |

**Verification after each step:**
- the smoke tests of `RELEASE_READINESS_CHECKLIST.md` §4;
- `curl` without a key → 401/403; with the key → 200;
- the bridge log shows `telegram_message_answered`;
- no key appears in any log.

**Rollback:** remove the variable or credential and recreate the container, or re-publish the previous workflow
version. Image rollback: retag `:post-audit-before` (see the checklist).

## 4. Contract changes for the n8n workflows (for synchronisation by Codex)

No workflow ID, webhook path or response format changes. When the corresponding step is approved:

1. **Workflow 03:**
   - Optionally, Header Auth on `POST /webhook/assistant` (step 4).
   - Header `X-Agent-Key` on the 6 HTTP nodes (step 5).
   - The repository definition already contains the error outputs on all agent nodes, returning a structured 503.
2. **Workflow 02** (retrieval API): header `X-Agent-Key` on its `/retrieve` call (step 5).
3. **Workflow 01** (ingest and index, inactive): header `X-Admin-Key` on `/ingestion/run` and `/index/run`
   (step 2). Without it, these calls now return 403.

## 5. Qdrant

| Container | Project | Network | Published | Auth | Data |
|---|---|---|---|---|---|
| `tunisian-admin-assistant-qdrant-1` | this project | `tunisian-admin-assistant_internal` | **127.0.0.1:6343** only | none | volume `tunisian-admin-assistant_qdrant_data` (272 + 174 points) |
| `qdrant` | **`rag-finance-pipeline` (unrelated)** | `rag-finance-pipeline_default` (not shared with this project) | **0.0.0.0:6333–6334, IPv4 and IPv6: reachable from the LAN** | **none** (unauthenticated `GET /collections` → 200) | volume `qdrant_storage`, collection `documents` |

**The project's backend reaches the right instance.** The backend resolves `qdrant` on its own Compose network
to `tunisian-admin-assistant-qdrant-1`. The unrelated container is on another network. The candidate's health
check and all 728 replay cases used collections `official_docs_*`, which exist only in the project instance.

**Recommendations (not executed):**
1. **Unrelated container [approval of its owner]:**
   - If it is not needed, stop it: `docker stop qdrant` (data stays in volume `qdrant_storage`).
   - If it is needed, recreate it from its own Compose project with `127.0.0.1:` port bindings and
     `QDRANT__SERVICE__API_KEY`.
   - Do not delete the volume.
2. **Project instance [approval]:**
   - Keep the loopback binding (needed by tests and the CLI). Remove the host port entirely if host access is
     not needed: the backend only needs the internal network.
   - To enable authentication, set `QDRANT__SERVICE__API_KEY` and the same value in `QDRANT_API_KEY`, then
     recreate `qdrant` and then `backend`.
   - Volumes and collections are untouched by a recreate. Take a snapshot first; Codex's snapshots are in
     `data/evaluation/post_audit_backup/qdrant/`.
3. **Remote access** is not required by this project. If ever needed: an API key, TLS, a firewall rule limited
   to known hosts, and never `0.0.0.0` without authentication.

## 6. Logs and secrets

- **Bridge:** silences `httpx`/`httpcore` logging (Telegram URLs contain the token) and logs exception types only.
- **Backend:** logs routing metadata only. A live test with `AGENT_API_KEY` set found 0 occurrences of the key
  in the container log.
- **Settings:** secrets are `repr=False` (unit test).
- **Repository:** `.env` is git-ignored. Workflow JSON files contain no credentials (unit test). Never print
  `docker compose config` without `--quiet` or `--format json` piped to a name-only filter.
