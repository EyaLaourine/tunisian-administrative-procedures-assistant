"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    data_dir: Path = Path("data")
    sources_registry: Path = Path("config/sources.yaml")

    qdrant_url: str = "http://localhost:6343"
    qdrant_api_key: str | None = None
    qdrant_collection_prefix: str = "official_docs"

    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024
    llm_model: str = "mistral:latest"

    http_user_agent: str = "TunisianAdminAssistant-Research/0.1 (academic project)"
    http_timeout_seconds: float = 60.0
    max_download_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    default_crawl_delay_seconds: float = Field(default=2.0, ge=0)
    # Extra *intermediate* CA certificates (PEM) for official servers that send incomplete
    # chains. Verification still requires a chain to a standard trusted root.
    extra_ca_dir: Path = Path("config/certs")

    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

    # --- Phase 2: agents ---
    prompts_dir: Path = Path("prompts")
    # Model used for item translation (EN answers). Falls back to llm_model when empty.
    translation_model: str = "translategemma:4b"
    llm_timeout_seconds: float = 300.0
    # Ask the LLM to classify a query when the deterministic rules find no procedure.
    intent_llm_fallback: bool = True
    # Passages below this cosine similarity are not used as evidence.
    retrieval_min_score: float = Field(default=0.45, ge=-1.0, le=1.0)
    ocr_languages: str = "ara+fra"
    # Retrieval used by /agents/retrieve: "agent" (dense, routed expansion) or "hybrid"
    # (raw + expanded dense + BM25 with reciprocal rank fusion; see docs/EVALUATION.md).
    retrieval_mode: str = Field(default="hybrid", pattern="^(agent|hybrid)$")
    # Hybrid mode: at most this share of the results may come from one document (min. 2).
    retrieval_max_per_doc_ratio: float = Field(default=0.4, gt=0, le=1)
    # Evidence verifier (topic consistency + numerical claims, agents/verification.py).
    evidence_verification: bool = True
    # Topic-consistency part of the verifier: OFF by default. It removes the known topic-confusion failures
    # (regression set) but on the two independent test sets it did not reduce false acceptance and added
    # false refusals (docs/EVALUATION.md section 7). Kept for experiments: EVIDENCE_TOPIC_CHECK=true.
    evidence_topic_check: bool = False

    # Shared secret for the privileged, state-changing endpoints (/ingestion/run, /index/run). Fail closed: when
    # it is not configured these endpoints are disabled (HTTP 403); when configured, callers send X-Admin-Key.
    admin_api_key: str | None = Field(default=None, repr=False)
    # Optional shared secret for the agent API (/agents/*, /retrieve). When set, every caller (the n8n HTTP nodes)
    # must send X-Agent-Key, so the assistant webhook cannot be bypassed by calling the backend directly.
    # Unset by default so that the current n8n workflows keep working until they send the header.
    agent_api_key: str | None = Field(default=None, repr=False)
    # Upper bound for any request body (base64 uploads are ~4/3 of the file size plus JSON overhead).
    max_request_bytes: int = Field(default=15 * 1024 * 1024, gt=0)

    # --- Telegram bridge (long polling; the token is only read from the environment / .env) ---
    telegram_bot_token: str | None = Field(default=None, repr=False)
    assistant_webhook_url: str = "http://localhost:5678/webhook/assistant"
    # Optional key sent as X-Assistant-Key to the n8n assistant webhook (enable Header Auth on the webhook first).
    assistant_webhook_key: str | None = Field(default=None, repr=False)

    def resolve(self, path: Path) -> Path:
        """Resolve a configured path relative to the repository root."""
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def raw_dir(self) -> Path:
        return self.resolve(self.data_dir) / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.resolve(self.data_dir) / "processed"

    @property
    def registry_path(self) -> Path:
        return self.resolve(self.sources_registry)

    @property
    def prompts_path(self) -> Path:
        return self.resolve(self.prompts_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
