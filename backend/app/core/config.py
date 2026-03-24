from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "DocQA"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/docqa.db"

    # File storage
    upload_dir: str = "./uploads"
    vector_store_dir: str = "./data/chroma"
    max_upload_size_mb: int = 50
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 6
    retrieval_candidate_multiplier: int = 2
    retrieval_vector_weight: float = 0.65
    retrieval_keyword_weight: float = 0.35
    conversation_recent_messages: int = 8
    conversation_summary_chars: int = 1200
    conversation_history_char_budget: int = 3000

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def vector_store_path(self) -> Path:
        p = Path(self.vector_store_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
