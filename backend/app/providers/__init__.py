from ..services.settings_service import get_runtime_settings
from .base import AIProvider, ProviderError
from .ollama import OllamaProvider
from .openai_compat import OpenRouterProvider, OpenAICompatProvider

_REGISTRY: dict[str, type] = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatProvider,
    "openrouter": OpenRouterProvider,
}

_instances: dict[str, AIProvider] = {}


def refresh_providers() -> None:
    _instances.clear()


def get_provider(name: str | None = None) -> AIProvider:
    settings = get_runtime_settings()
    provider_name = (name or settings.ai_provider).lower()
    if provider_name not in _REGISTRY:
        raise ProviderError(f"Unknown AI provider '{provider_name}'. Available: {list(_REGISTRY)}")
    key = provider_name
    if key in _instances:
        return _instances[key]
    cls = _REGISTRY[key]
    if provider_name == "ollama":
        provider = cls(base_url=settings.ollama_base_url, auto_pull=settings.ollama_auto_pull)
    elif provider_name == "openrouter":
        provider = cls(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            default_model=settings.openrouter_model,
        )
    elif provider_name == "openai":
        provider = cls(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            default_model=settings.openai_model,
        )
    else:
        raise ProviderError(f"Unsupported provider: {provider_name}")
    _instances[key] = provider
    return provider


def list_providers() -> list[dict]:
    return [
        {
            "id": "ollama",
            "name": "Ollama (local)",
            "description": "Local models served by Ollama. Auto-downloads missing models.",
        },
        {
            "id": "openai",
            "name": "OpenAI-compatible API",
            "description": "Any OpenAI-compatible endpoint (OpenAI, LM Studio, vLLM, Groq, ...).",
        },
        {
            "id": "openrouter",
            "name": "OpenRouter",
            "description": "Hundreds of hosted models through one API.",
        },
    ]
