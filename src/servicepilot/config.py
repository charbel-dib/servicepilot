import json
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEMO_IDENTITIES = {
    "demo-alice-token": {"user_id": "alice", "services": ["atlas", "nova", "vpn"]},
    "demo-bob-token": {"user_id": "bob", "services": ["atlas", "nova", "orion", "vpn"]},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SERVICEPILOT_", env_file=".env", extra="ignore")

    environment: str = "demo"
    provider: str = "offline"
    model: str = "gpt-4.1-mini"
    api_key: SecretStr | None = None
    data_dir: Path = Path(".servicepilot")
    procedures_dir: Path = Path(__file__).parent / "data" / "procedures"
    status_url: str = "http://127.0.0.1:8001"
    status_timeout: float = Field(default=3.0, gt=0, le=30)
    max_tool_calls: int = Field(default=6, ge=1, le=12)
    approval_ttl_seconds: int = Field(default=900, ge=1, le=86400)
    identities_json: SecretStr | None = None
    embedding_backend: str = "hashing"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.environment not in {"demo", "production"}:
            raise ValueError("environment must be demo or production")
        if self.provider not in {"offline", "openai"}:
            raise ValueError("provider must be offline or openai")
        if self.embedding_backend not in {"hashing", "sentence-transformers"}:
            raise ValueError("unsupported embedding backend")
        if self.provider == "openai" and (not self.api_key or not self.api_key.get_secret_value()):
            raise ValueError("SERVICEPILOT_API_KEY is required for openai mode")
        identities = self.identities
        if not identities:
            raise ValueError("at least one identity is required")
        if self.environment == "production":
            if not self.identities_json or not self.identities_json.get_secret_value():
                raise ValueError("explicit identities are required outside demo mode")
            if any(len(key) < 32 or key.startswith("demo-") for key in identities):
                raise ValueError("production tokens must be random and at least 32 characters")
        return self

    @property
    def identities(self) -> dict:
        value = (
            json.loads(self.identities_json.get_secret_value())
            if self.identities_json and self.identities_json.get_secret_value()
            else DEMO_IDENTITIES
        )
        for token, identity in value.items():
            if (
                not token
                or not identity.get("user_id")
                or not isinstance(identity.get("services"), list)
            ):
                raise ValueError("invalid identity configuration")
        return value
