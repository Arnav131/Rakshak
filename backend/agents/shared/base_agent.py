"""
Rakshak Agent System — Base Agent
====================================
Abstract base class that all agents inherit from.
Provides lifecycle management, logging, and event emission.
"""

import logging
import time
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.utils import timezone


logger = logging.getLogger("rakshak.agents")


class AgentStatus:
    """Agent health status constants."""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


class BaseAgent(ABC):
    """
    Abstract base class for all Rakshak agents.

    Provides:
    - Lifecycle management (start, stop, health check)
    - Structured logging
    - Processing time tracking
    - Error handling with circuit breaker semantics
    - Event emission to Django models
    """

    # Override in subclasses
    AGENT_NAME: str = "base_agent"
    AGENT_VERSION: str = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self._error_count = 0
        self._max_errors = self.config.get("max_consecutive_errors", 5)
        self._total_processed = 0
        self._total_errors = 0
        self._last_run_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._processing_times: List[float] = []

        logger.info(f"[{self.AGENT_NAME}] Initialized (v{self.AGENT_VERSION})")

    @abstractmethod
    def process(self, data: Any) -> Dict:
        """
        Core processing logic — must be implemented by each agent.

        Args:
            data: Input data (format depends on agent type)

        Returns:
            Dict with processing results
        """
        pass

    def run(self, data: Any) -> Dict:
        """
        Execute the agent's processing with error handling and metrics.

        This is the public entry point. Wraps process() with:
        - Status tracking
        - Timing
        - Error handling with circuit breaker
        - Structured result format

        Args:
            data: Input data for processing

        Returns:
            Dict with keys: success, result, processing_time_ms, agent, error
        """
        if self.status == AgentStatus.DISABLED:
            return {
                "success": False,
                "error": f"Agent {self.AGENT_NAME} is disabled (too many errors)",
                "agent": self.AGENT_NAME,
            }

        self.status = AgentStatus.RUNNING
        t0 = time.time()

        try:
            result = self.process(data)
            elapsed_ms = (time.time() - t0) * 1000

            self._error_count = 0  # Reset on success
            self._total_processed += 1
            self._last_run_at = timezone.now()
            self._processing_times.append(elapsed_ms)

            # Keep only last 100 times for avg calculation
            if len(self._processing_times) > 100:
                self._processing_times = self._processing_times[-100:]

            self.status = AgentStatus.IDLE

            return {
                "success": True,
                "result": result,
                "processing_time_ms": round(elapsed_ms, 2),
                "agent": self.AGENT_NAME,
            }

        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            self._error_count += 1
            self._total_errors += 1
            self._last_error = str(e)

            logger.error(
                f"[{self.AGENT_NAME}] Error ({self._error_count}/{self._max_errors}): {e}",
                exc_info=True,
            )

            # Circuit breaker: disable after too many consecutive errors
            if self._error_count >= self._max_errors:
                self.status = AgentStatus.DISABLED
                logger.critical(
                    f"[{self.AGENT_NAME}] DISABLED — {self._max_errors} consecutive errors"
                )
            else:
                self.status = AgentStatus.ERROR

            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "processing_time_ms": round(elapsed_ms, 2),
                "agent": self.AGENT_NAME,
            }

    def health_check(self) -> Dict:
        """Return agent health status."""
        avg_time = (
            sum(self._processing_times) / len(self._processing_times)
            if self._processing_times else 0
        )

        return {
            "agent": self.AGENT_NAME,
            "version": self.AGENT_VERSION,
            "status": self.status,
            "total_processed": self._total_processed,
            "total_errors": self._total_errors,
            "consecutive_errors": self._error_count,
            "avg_processing_time_ms": round(avg_time, 2),
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "last_error": self._last_error,
        }

    def reset(self):
        """Reset the agent (clears error state)."""
        self._error_count = 0
        self.status = AgentStatus.IDLE
        logger.info(f"[{self.AGENT_NAME}] Reset")

    def log_event(self, event_type: str, entity_type: str, entity_id: int, description: str = ""):
        """
        Write to Django AuditLog.

        Args:
            event_type: AuditLog.EventType value
            entity_type: Model name (e.g., 'alert', 'ticket')
            entity_id: Primary key of the affected entity
            description: Human-readable description
        """
        try:
            from railway.models import AuditLog
            AuditLog.objects.create(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_type=AuditLog.ActorType.ML_PIPELINE,
                actor_identifier=self.AGENT_NAME,
                description=description,
            )
        except Exception as e:
            logger.warning(f"[{self.AGENT_NAME}] Failed to write audit log: {e}")
