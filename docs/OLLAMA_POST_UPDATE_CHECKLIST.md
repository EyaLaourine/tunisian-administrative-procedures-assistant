# Ollama post-update checklist (pending v0.40.6)

Background:
- Since 2026-10-17, Ollama runs **local-only**: the app setting "Expose Ollama to the network" is off and the
  server listens on `127.0.0.1:11434`.
- The two Public-profile `ollama.exe` firewall rules are disabled.
- The desktop app installs a downloaded update the next time it starts (for example after a reboot).

Run these checks right after the update. All of them are read-only.

```powershell
# 1. Version and loopback-only binding: expect a new version, and 127.0.0.1 only (no 0.0.0.0, no ::)
curl.exe -s http://127.0.0.1:11434/api/version
Get-NetTCPConnection -LocalPort 11434 -State Listen | Select-Object LocalAddress, OwningProcess

# 2. Not reachable through the Wi-Fi address: expect a connection failure
curl.exe -s -m 5 http://192.168.1.16:11434/api/version

# 3. Firewall: the Public ollama.exe rules are still disabled. An installer may add new rules,
#    so check for any NEW enabled Public rule too.
Get-NetFirewallRule -DisplayName 'ollama.exe' | Select-Object Name, Profile, Enabled

# 4. Models: expect bge-m3:latest, mistral:latest and translategemma:4b
curl.exe -s http://127.0.0.1:11434/api/tags
```

```bash
# 5. Container-to-host connectivity from the real production backend: expect 3 model names
docker exec tunisian-admin-assistant-backend-1 python -c "import urllib.request,json;print([m['name'] for m in json.load(urllib.request.urlopen('http://host.docker.internal:11434/api/tags',timeout=5))['models']])"

# 6. Backend health: expect "ollama": true
curl -s http://127.0.0.1:8000/health

# 7. Host-side embedding through the project settings (OLLAMA_URL from .env = http://127.0.0.1:11434)
.venv/Scripts/python -m pytest -q tests/test_integration_services.py::test_ollama_bge_m3_embedding_shape
```

**If check 1 shows `0.0.0.0` or `::`:** the update re-enabled network exposure. Turn "Expose Ollama to the
network" off again in the Ollama Settings, then repeat checks 1–2.

**If check 3 shows an enabled Public rule:** disable it (elevated):
`Disable-NetFirewallRule -Name '<rule name>'`.

**If check 4 is missing a model:** do **not** re-pull or re-index anything. Check that the app's model location
is still `C:\Users\Eya Laourine` (`OLLAMA_MODELS:` line in `%LOCALAPPDATA%\Ollama\server.log`).

Background record and rollback: `rag-finance-pipeline/docs/OLLAMA_LOCAL_ONLY.md` and
`rag-finance-pipeline/deployment/ollama_hardening/ROLLBACK.md`.
