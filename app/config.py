"""
Application configuration using Pydantic Settings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Cognigate Engine"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # API
    api_prefix: str = "/v1"
    api_key_header: str = "X-API-Key"

    # Security
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_expire_minutes: int = 30
    admin_api_key: str = "CHANGE_ME_IN_PRODUCTION"  # API key for admin endpoints

    # Trust Engine
    default_trust_level: int = 1
    trust_decay_rate: float = 0.01

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Gateway / Upstream
    agentanchor_api_url: str = "https://app.agentanchorai.com/api"
    gateway_timeout_ms: int = 30000
    gateway_circuit_breaker_threshold: int = 5

    # Critic Pattern - AI Provider Configuration
    # Supported: "anthropic" (Claude), "openai" (GPT), "google" (Gemini), "xai" (Grok)
    critic_provider: str = "xai"  # Default to Grok

    # API Keys (set the one matching your provider)
    anthropic_api_key: str = ""  # Claude
    openai_api_key: str = ""     # GPT
    google_api_key: str = ""     # Gemini
    xai_api_key: str = ""        # Grok

    # Model settings per provider
    critic_model_anthropic: str = "claude-3-5-sonnet-20241022"
    critic_model_openai: str = "gpt-4o-mini"
    critic_model_google: str = "gemini-1.5-flash"
    critic_model_xai: str = "grok-2-latest"

    critic_temperature: float = 0.3
    critic_enabled: bool = True

    # External Services
    database_url: str = "sqlite+aiosqlite:///./cognigate.db"
    redis_url: str = "redis://localhost:6379"
    redis_enabled: bool = False  # Disabled by default, graceful degradation

    # Signature System
    signature_enabled: bool = True
    signature_private_key: str = ""  # Base64-encoded PEM private key (optional)
    signature_key_path: str = ""     # Path to PEM private key file (optional)

    # Cache TTLs (seconds)
    cache_ttl_policy_results: int = 60        # Policy evaluation results
    cache_ttl_trust_scores: int = 300         # Trust scores
    cache_ttl_velocity_state: int = 0         # Velocity state (no expiry)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
