"""
Rakshak Agent System — Package Init & Agent Registry
======================================================
Phase 1 compatible agent layer that integrates the AI Engine
models with the existing Django backend.

Usage:
    from agents import get_agent_registry
    registry = get_agent_registry()
    anomaly_agent = registry.get('anomaly_detection')
"""

from typing import Dict, Optional

# Lazy-loaded registry singleton
_registry: Optional["AgentRegistry"] = None


class AgentRegistry:
    """Central registry for all agents. Lazy-initializes on first access."""

    def __init__(self):
        self._agents: Dict[str, object] = {}
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        # Import agents lazily to avoid circular imports
        from agents.shared.base_agent import BaseAgent
        self._initialized = True

    def register(self, name: str, agent):
        """Register an agent instance."""
        self._agents[name] = agent

    def get(self, name: str):
        """Get a registered agent by name."""
        self._ensure_initialized()
        return self._agents.get(name)

    def list_agents(self) -> Dict[str, str]:
        """List all registered agents and their status."""
        return {
            name: type(agent).__name__
            for name, agent in self._agents.items()
        }


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry singleton."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
