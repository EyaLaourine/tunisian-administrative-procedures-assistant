# GitHub release readiness

Date: 2026-10-19. Scope: `release/github-ready`, release checkout only. No deployment, production restart, ingestion, production indexing, Telegram message, merge or history rewrite was performed.

## Completed before this continuation

Claude prepared configuration cleanup, a public TLS intermediate certificate, an offline corpus builder, a disposable `fresh-*` stack and fresh-install evaluation. Prior production Phase F/G results remain historical evidence, not tests rerun by this release task.

## Verified in this continuation

| Check | Observed result |
|---|---|
| Offline reconstruction in release checkout and separate temporary export | 14 documents; 286 structure / 186 recursive chunks; image-only decree skipped |
| Official original SHA-256 checks | 15/15 matched manifest |
| Unit suite in release checkout | 1399 passed, 7 skipped, 41 deselected |
| Unit suite in separate export | 1399 passed, 7 skipped, 41 deselected; 6 dependency deprecation warnings |
| Dependency consistency | `pip check`: no broken requirements in available Python environment |
| Backend and bridge Docker builds from separate export | Passed; dependency layers reused Docker cache |
| Compose configuration with public example placeholders | Passed (`config --quiet`) |
| Disposable backend health | `ok`, Qdrant/Ollama true, 15 manifest records |
| Disposable vector collections | 286 structure / 186 recursive points |
| Disposable n8n export | Workflow 01 inactive (5 executable + 6 notes); 02 published (3+4); 03 published (17+10); retrieve/assistant paths |
| Disposable assistant webhook | HTTP 200; SARL fee request routed to checklist builder with RNE C 012 and official RNE source |
| Credential-pattern scan | No matches in 636 reachable history blobs or reviewed tracked worktree files |
| Sensitive-path history check | No tracked real `.env`, DPAPI store, private-key path, upload directory or virtual environment found |

Unit tests used an already available Python environment, without modifying its packages. Docker builds validate container dependency installation/buildability with cached layers; this is not a new Windows VM or an uncached package-download experiment. The isolated stack was created earlier; its existing health, collections, imported workflows and one webhook were verified here. Full benchmarks were not repeated.

## Documentation and release contents

- README introduces Telegram as frontend and includes the professor installation/test checklist.
- `docs/INSTALLATION.md` gives ordered PowerShell commands, models, configuration, offline preparation, new-install-only indexing, n8n import/publication and BotFather steps.
- `output/pdf/Professor_Installation_Guide.pdf` is the printable guide; includes the assigned private repository URL.
- `.env.example` documents defaults and distinguishes host options from Compose forwarding.
- `.dockerignore` excludes credentials, source-control metadata, caches and disposable state while keeping required official originals.
- Public CA certificate is tracked; no private key is included.
- Generated LaTeX build intermediates are untracked; published report PDFs and archived academic evidence remain.
- Two historical Qdrant `.snapshot` archives are untracked from the release tree but retained locally. They remain in prior history; no history was rewritten. They are official-corpus runtime snapshots, not required for installation.
- Existing evidence was preserved; pending replacements of personal paths/hostnames with generic forms were retained. These changes do not represent new test runs.

## Reproducibility boundaries

Historical production has 12 indexed documents and 272/174 points. Fresh preparation includes the two Interior forms: 14 indexed documents and 286/186 chunks. Manifest size is 15 because an image-only document is skipped. Do not reindex production to make these counts match.

Professors must install Docker/Python/Ollama, download models, configure their own private secrets, initialize a new empty vector database, publish workflows and create their own Telegram bot. The fixed Compose project/container names and hard-coded integration-test ports require a dedicated machine or reviewed isolation override. The installation guide explicitly warns about this.

## Security and remaining acceptance

Scanning is a finite check, not proof that arbitrary data can never contain sensitive content. Reviewed original documents have the recorded official hashes; tests use fixture material. No real Telegram authentication or message exchange was performed by this continuation. Manual four-language, PDF/image and dossier acceptance with a new bot remains required. OCR may reject poor images; dossier output cannot certify legal completeness. Model tags are mutable: record digests when reproducing measurements.

The repository must remain private initially. GitHub CLI authorization was completed by the owner as EyaLaourine. The new private repository is `EyaLaourine/tunisian-administrative-procedures-assistant`. A local clone of the committed release passed essential-file presence checks. Professors require an invitation before accessing the private repository. Publication URL, pushed SHA, default branch and remote verification must be reported only after successful authenticated creation/push. No credentials may be stored in this report.
