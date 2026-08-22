# backend/ai_integration/registry.py
"""
Rakshak AI Integration — Provider Registry
==============================================
Singleton registry that manages AI provider instances.

Reads provider configuration from Django settings (RAKSHAK_AI)
and lazy-loads providers on first access.

RESPONSIBILITY:
    - Load provider configuration from settings.py
    - Instantiate provider classes lazily
    - Select the default provider
    - Allow runtime provider registration (for testing)
    - Provide a single get_provider() entry point

WHO SHOULD USE THIS:
    - PredictionService (ai_integration/prediction_service.py)
    - Tests (to register mock providers)

WHO SHOULD NEVER USE THIS:
    - Views (they go through PredictionService)
    - Agents (they go through PredictionService)
    - Templates

DESIGN DECISION: WHY A REGISTRY?
    The registry pattern allows:
    1. Multiple providers to coexist (local + cloud + LLM)
    2. Runtime swapping for A/B testing
    3. Fallback chains (try cloud → fallback to local)
    4. Testing with mock providers without changing settings
    5. Future multi-model ensemble support

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module has ZERO database interaction.
# It manages Python objects in memory.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

import importlib
import logging
import threading
from typing import Any, Dict, Optional

from ai_integration.providers import BaseAIProvider

logger = logging.getLogger("rakshak.ai_integration.registry")


class AIProviderRegistry:
    """
    Singleton registry for AI provider instances.

    Thread-safe. Uses a lock to prevent duplicate initialization
    when multiple Django request threads access the registry
    simultaneously.

    Usage:
        from ai_integration.registry import ai_provider_registry

        # Get the default provider
        provider = ai_provider_registry.get_provider()
        response = provider.predict(request)

        # Get a specific provider
        cloud_provider = ai_provider_registry.get_provider("cloud")

        # Register a mock provider (testing)
        ai_provider_registry.register_provider("mock", MockProvider())
    """

    def __init__(self):
        self._providers: Dict[str, BaseAIProvider] = {}
        self._default_name: Optional[str] = None
        self._config_loaded = False
        self._lock = threading.Lock()

    def _load_config(self):
        """
        Load provider configuration from Django settings.

        Reads the RAKSHAK_AI dict from settings.py and registers
        configured providers. Does NOT instantiate providers — that
        happens lazily in get_provider().

        Settings shape:
            RAKSHAK_AI = {
                'DEFAULT_PROVIDER': 'local',
                'PROVIDERS': {
                    'local': {
                        'CLASS': 'ai_integration.local_provider.LocalPickleProvider',
                        'MODEL_DIR': '...',
                        'WINDOW_SIZE': 64,
                    },
                },
            }
        """
        if self._config_loaded:
            return

        with self._lock:
            if self._config_loaded:
                return

            try:
                from django.conf import settings

                config = getattr(settings, "RAKSHAK_AI", {})
                self._default_name = config.get("DEFAULT_PROVIDER", "local")
                self._provider_configs = config.get("PROVIDERS", {})
                self._config_loaded = True

                logger.info(
                    f"AIProviderRegistry: Loaded config — "
                    f"default={self._default_name}, "
                    f"providers={list(self._provider_configs.keys())}"
                )

            except Exception as e:
                logger.error(f"AIProviderRegistry: Failed to load config: {e}")
                self._config_loaded = True  # Don't retry on every request
                self._provider_configs = {}

    def _instantiate_provider(self, name: str) -> Optional[BaseAIProvider]:
        """
        Instantiate a provider from its configuration.

        Reads the CLASS path from the provider config, dynamically
        imports it, and creates an instance with the remaining
        config values as constructor kwargs.

        Args:
            name: Provider name (key in RAKSHAK_AI['PROVIDERS']).

        Returns:
            Provider instance, or None on failure.
        """
        config = self._provider_configs.get(name)
        if not config:
            logger.error(
                f"AIProviderRegistry: No config for provider '{name}'. "
                f"Available: {list(self._provider_configs.keys())}"
            )
            return None

        class_path = config.get("CLASS")
        if not class_path:
            logger.error(
                f"AIProviderRegistry: Provider '{name}' has no CLASS configured."
            )
            return None

        try:
            # Dynamic import: "ai_integration.local_provider.LocalPickleProvider"
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)

            # Pass remaining config as kwargs (exclude CLASS)
            kwargs = {k.lower(): v for k, v in config.items() if k != "CLASS"}

            provider = provider_class(**kwargs)

            if not isinstance(provider, BaseAIProvider):
                logger.error(
                    f"AIProviderRegistry: {class_path} does not implement "
                    f"BaseAIProvider interface."
                )
                return None

            logger.info(
                f"AIProviderRegistry: Instantiated provider '{name}' "
                f"({class_path})"
            )
            return provider

        except ImportError as e:
            logger.error(
                f"AIProviderRegistry: Failed to import {class_path}: {e}"
            )
            return None

        except TypeError as e:
            logger.error(
                f"AIProviderRegistry: Failed to instantiate {class_path} — "
                f"constructor kwargs mismatch: {e}"
            )
            return None

        except Exception as e:
            logger.error(
                f"AIProviderRegistry: Failed to create provider '{name}': {e}",
                exc_info=True,
            )
            return None

    def get_provider(self, name: Optional[str] = None) -> Optional[BaseAIProvider]:
        """
        Get a provider instance by name.

        If no name is given, returns the default provider.
        Providers are lazy-loaded on first access and cached.

        Args:
            name: Provider name. None = use default.

        Returns:
            BaseAIProvider instance, or None if not available.

        FUTURE MULTI-MODEL NOTE:
            To use multiple providers simultaneously:
                local = registry.get_provider("local")
                cloud = registry.get_provider("cloud")
                # Run both, compare, or ensemble
        """
        self._load_config()

        provider_name = name or self._default_name
        if not provider_name:
            logger.error("AIProviderRegistry: No provider name and no default set.")
            return None

        # Check cache first
        if provider_name in self._providers:
            return self._providers[provider_name]

        # Instantiate and cache (thread-safe)
        with self._lock:
            # Double-check after acquiring lock
            if provider_name in self._providers:
                return self._providers[provider_name]

            provider = self._instantiate_provider(provider_name)
            if provider:
                self._providers[provider_name] = provider

            return provider

    def register_provider(self, name: str, provider: BaseAIProvider):
        """
        Manually register a provider instance.

        Used for:
            - Testing (register a mock provider)
            - Runtime hot-swapping
            - Custom provider injection

        Args:
            name:     Provider identifier.
            provider: Provider instance implementing BaseAIProvider.
        """
        if not isinstance(provider, BaseAIProvider):
            raise TypeError(
                f"Provider must implement BaseAIProvider. "
                f"Got: {type(provider).__name__}"
            )

        with self._lock:
            self._providers[name] = provider

        logger.info(
            f"AIProviderRegistry: Registered provider '{name}' "
            f"({type(provider).__name__})"
        )

    def unregister_provider(self, name: str):
        """Remove a provider from the registry."""
        with self._lock:
            self._providers.pop(name, None)
        logger.info(f"AIProviderRegistry: Unregistered provider '{name}'")

    def list_providers(self) -> Dict[str, str]:
        """
        List all registered and configured providers.

        Returns:
            Dict mapping provider name → status.
            Status is "loaded" (instantiated) or "configured" (not yet loaded).
        """
        self._load_config()

        result = {}

        # Loaded providers
        for name, provider in self._providers.items():
            result[name] = f"loaded ({provider.get_provider_name()})"

        # Configured but not yet loaded
        for name in self._provider_configs:
            if name not in result:
                result[name] = "configured (not loaded)"

        return result

    def health_check(self) -> Dict[str, Any]:
        """
        Run health checks on all loaded providers.

        Returns:
            Dict with overall status and per-provider health.
        """
        self._load_config()

        provider_health = {}
        all_healthy = True

        for name, provider in self._providers.items():
            try:
                health = provider.health_check()
                provider_health[name] = health
                if health.get("status") != "healthy":
                    all_healthy = False
            except Exception as e:
                provider_health[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                all_healthy = False

        return {
            "status": "healthy" if all_healthy else "degraded",
            "default_provider": self._default_name,
            "providers": provider_health,
            "configured": list(self._provider_configs.keys()),
        }

    def reset(self):
        """
        Clear all cached providers. Forces reload on next access.

        Use after:
            - Changing settings.RAKSHAK_AI at runtime
            - Deploying new model files
            - Running tests with different configurations
        """
        with self._lock:
            self._providers.clear()
            self._config_loaded = False

        logger.info("AIProviderRegistry: Reset — all providers cleared")


# ===================================================================
# MODULE-LEVEL SINGLETON
# ===================================================================
# This is the global registry instance. Import and use this.
#
# Usage:
#     from ai_integration.registry import ai_provider_registry
#     provider = ai_provider_registry.get_provider()
#
# Why a singleton?
#     - Provider instances are expensive to create (model loading)
#     - Multiple Django threads should share the same providers
#     - Testing can override via register_provider()
# ===================================================================

ai_provider_registry = AIProviderRegistry()
