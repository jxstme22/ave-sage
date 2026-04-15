"""
AVE SAGE — Config
Loads configuration from config.yaml + environment variable overrides.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class AveConfig:
    api_key: str = ""
    api_plan: str = "free"
    secret_key: str = ""
    chains: list = field(default_factory=lambda: ["solana", "bsc"])


@dataclass
class CollectionConfig:
    significance_threshold: float = 0.6
    price_change_min: float = 0.03
    volume_spike_multiplier: float = 2.5
    max_events_per_hour: int = 500
    poll_interval_seconds: int = 60
    signal_window_seconds: int = 900


@dataclass
class MemoryConfig:
    vector_db: str = "chromadb"
    embedding_provider: str = "sentence_transformer"
    embedding_model: str = "all-MiniLM-L6-v2"
    collection_name: str = "ave_sage_memory"
    persist_dir: str = "./data/chroma"
    max_context_chunks: int = 8
    similarity_threshold: float = 0.60
    lookback_hours: int = 168


@dataclass
class AgentConfig:
    llm_provider: str = "openrouter"
    reasoning_model: str = "anthropic/claude-sonnet-4-20250514"
    trade_confidence_min: float = 0.70
    dry_run: bool = True
    max_position_usd: float = 50.0
    take_profit_pct: float = 0.08
    stop_loss_pct: float = 0.04
    risk_warn_threshold: float = 0.65
    assets_id: str = ""           # AVE proxy wallet assetsId for live trading


@dataclass
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    enable_websocket: bool = True


@dataclass
class TelegramConfig:
    bot_token: str = ""
    admin_chat_ids: list = field(default_factory=list)


@dataclass
class Settings:
    ave: AveConfig = field(default_factory=AveConfig)
    collection: CollectionConfig = field(default_factory=CollectionConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    openrouter_api_key: str = ""
    openai_api_key: str = ""


def _load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _merge(dataclass_instance, cfg_dict: dict):
    """Merge dict values into a dataclass instance."""
    for k, v in cfg_dict.items():
        if hasattr(dataclass_instance, k):
            setattr(dataclass_instance, k, v)


def load_settings(config_path: str = None) -> Settings:
    if config_path is None:
        # Resolve relative to this file so it works from any working directory
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    raw = _load_yaml(config_path)
    s = Settings()

    _merge(s.ave, raw.get("ave", {}))
    _merge(s.collection, raw.get("collection", {}))
    _merge(s.memory, raw.get("memory", {}))
    _merge(s.agent, raw.get("agent", {}))
    _merge(s.dashboard, raw.get("dashboard", {}))
    _merge(s.telegram, raw.get("telegram", {}))

    # Environment variable overrides (highest priority)
    s.ave.api_key = os.getenv("AVE_API_KEY", s.ave.api_key)
    s.ave.secret_key = os.getenv("AVE_SECRET_KEY", s.ave.secret_key)
    s.ave.api_plan = os.getenv("API_PLAN", s.ave.api_plan)
    s.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", s.openrouter_api_key)
    s.openai_api_key = os.getenv("OPENAI_API_KEY", s.openai_api_key)
    s.telegram.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", s.telegram.bot_token)

    # TELEGRAM_ADMIN_ID — comma-separated user IDs, e.g. "123456789,987654321"
    admin_env = os.getenv("TELEGRAM_ADMIN_ID", "")
    if admin_env:
        ids = [i.strip() for i in admin_env.split(",") if i.strip()]
        parsed = []
        for i in ids:
            try:
                parsed.append(int(i))
            except ValueError:
                pass
        if parsed:
            s.telegram.admin_chat_ids = parsed

    # OPENROUTER_MODEL — override the reasoning model at runtime
    model_env = os.getenv("OPENROUTER_MODEL", "")
    if model_env:
        s.agent.reasoning_model = model_env

    # PROXY_ASSETS_ID — AVE proxy wallet assetsId for live trading
    assets_id_env = os.getenv("PROXY_ASSETS_ID", "")
    if assets_id_env:
        s.agent.assets_id = assets_id_env

    # Ensure env vars are set for the official ave-cloud-skill SDK
    # (SDK reads AVE_API_KEY, AVE_SECRET_KEY, API_PLAN from os.environ)
    if s.ave.api_key:
        os.environ.setdefault("AVE_API_KEY", s.ave.api_key)
    if s.ave.secret_key:
        os.environ.setdefault("AVE_SECRET_KEY", s.ave.secret_key)
    if s.ave.api_plan:
        os.environ.setdefault("API_PLAN", s.ave.api_plan)

    return s


settings = load_settings()
