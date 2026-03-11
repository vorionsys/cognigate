# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Application configuration using Pydantic Settings.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

# Auto-detect Vercel serverless environment
_IS_VERCEL = bool(os.environ.get("VERCEL"))

# Production: Use DATABASE_URL env var (Neon PostgreSQL) if set.
# Development: Fall back to local SQLite.
# Vercel: Previously used ephemeral /tmp SQLite — now requires DATABASE_URL for persistence.
_DEFAULT_DB_URL = (
    os.environ.get("DATABASE_URL")
    or ("sqlite+aiosqlite:////tmp/cognigate.db" if _IS_VERCEL else "sqlite+aiosqlite:///./cognigate.db")
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Cognigate Engine"
    app_version: str = "0.2.0"
    debug: bool = False
    environment: str = "development"

    # API
    api_prefix: str = "/v1"
    api_key_header: str = "X-API-Key"

    # Security
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_expire_minutes: int = 30
    admin_api_key: str = "CHANGE_ME_IN_PRODUCTION"  # API key for admin endpoints
    api_key: str = "CHANGE_ME_IN_PRODUCTION"  # API key for pipeline endpoints

    # MFA Configuration
    mfa_enabled: bool = False  # Enable TOTP MFA for admin endpoints
    mfa_totp_secret: str = ""  # Base32-encoded TOTP secret (generate with pyotp.random_base32())
    mfa_totp_issuer: str = "Cognigate"
    mfa_totp_window: int = 1  # Accept codes ±1 time step (30-second window)

    # Trust Engine
    default_trust_level: int = 1
    trust_decay_rate: float = 0.01
    trust_decay_half_life_days: int = 182  # 182-day half-life for inactivity decay
    trust_decay_floor: float = 0.50        # 50% floor — score doesn't decay below this fraction

    # Deep Space Modules
    # TMR Consensus — fault-tolerant multi-model redundancy
    tmr_consensus_risk_threshold: int = 80   # Min risk ρ to trigger voting
    tmr_divergence_threshold: float = 10.0   # Trust-point divergence threshold
    tmr_min_replicas: int = 3                # Minimum replicas required
    # Monte Carlo — predictive horizon risk forecasting
    mc_default_epsilon: float = 0.05         # Per-step failure rate
    mc_default_horizon_hours: int = 24       # Default forecast horizon
    mc_default_trials: int = 2000            # Monte Carlo trial count
    mc_risk_threshold: int = 60              # Min risk ρ to trigger forecasting
    # Self-Healing — evolutionary parameter optimization
    evolution_target_ratio: float = 10.0     # Target r_l/r_g asymmetry ratio
    evolution_batch_hours: int = 168          # 7-day batch frequency
    evolution_generations: int = 25           # GA generations per run
    evolution_population: int = 20            # GA population size

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Gateway / Upstream
    vorion_api_url: str = "https://app.vorion.org/api"
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
    database_url: str = _DEFAULT_DB_URL
    redis_url: str = "redis://localhost:6379"
    redis_enabled: bool = False  # Disabled by default, graceful degradation

    # Federation Configuration — IA-8(1), IA-8(2) [PLANNED]
    # OIDC federation for accepting external identity assertions
    oidc_enabled: bool = False
    oidc_issuer_url: str = ""       # e.g., "https://login.gov" or "https://accounts.google.com"
    oidc_client_id: str = ""        # OIDC client/application ID
    oidc_audience: str = ""         # Expected audience claim in ID tokens

    # SAML federation for accepting government IdP assertions
    saml_enabled: bool = False
    saml_idp_metadata_url: str = ""  # e.g., "https://idp.agency.gov/metadata.xml"

    # Signature System
    signature_enabled: bool = True
    signature_private_key: str = ""  # Base64-encoded PEM private key (optional)
    signature_key_path: str = ""     # Path to PEM private key file (optional)

    # Cache TTLs (seconds)
    cache_ttl_policy_results: int = 60        # Policy evaluation results
    cache_ttl_trust_scores: int = 300         # Trust scores
    cache_ttl_velocity_state: int = 0         # Velocity state (no expiry)

    def validate_secrets(self) -> list[str]:
        """
        Validate that default/placeholder secrets are not used in production.

        Returns list of validation errors. Empty list means all secrets are valid.
        Raises RuntimeError in production if default secrets are detected.
        """
        errors = []
        _FORBIDDEN_DEFAULTS = {"CHANGE_ME_IN_PRODUCTION", "", "changeme", "secret", "password"}

        if self.secret_key in _FORBIDDEN_DEFAULTS:
            errors.append("secret_key is using a default/placeholder value")
        if self.admin_api_key in _FORBIDDEN_DEFAULTS:
            errors.append("admin_api_key is using a default/placeholder value")
        if self.api_key in _FORBIDDEN_DEFAULTS:
            errors.append("api_key is using a default/placeholder value")

        if errors and self.environment == "production":
            raise RuntimeError(
                f"FATAL: Default secrets detected in production environment. "
                f"Refusing to start. Issues: {'; '.join(errors)}"
            )

        return errors


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
