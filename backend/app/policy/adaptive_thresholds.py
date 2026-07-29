# adaptive_thresholds.py - Truly adaptive, no hard caps

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Optional

from app.policy.constants import (
    EWMA_ALPHA,
    HIGH_PERCENTILE,
    MEDIUM_PERCENTILE,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    THRESHOLD_HISTORY,
    MIN_SAMPLES,
    MIN_HIGH_THRESHOLD,
    MAX_HIGH_THRESHOLD,
    MIN_MEDIUM_THRESHOLD,
    MAX_MEDIUM_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AdaptiveThresholds:
    high: float
    medium: float
    high_percentile: float
    medium_percentile: float
    sample_count: int
    mean: float
    std_dev: float


class AdaptiveThresholdEngine:
    """
    Computes truly adaptive thresholds from historical risk scores.
    
    No hard caps - thresholds are purely data-driven based on
    each client's actual traffic patterns.
    
    This allows the system to:
    - Learn what's "normal" for each client
    - Adapt to different traffic patterns
    - Handle seasonal variations
    - Scale with client growth
    """
    
    def __init__(self) -> None:
        # Per-client rolling history
        self._history: dict[int | None, list[float]] = {}
        self._cache: dict[int | None, AdaptiveThresholds] = {}
        
        # Statistics per client
        self._stats: dict[int | None, dict] = {}
        
        logger.info("AdaptiveThresholdEngine initialized (truly adaptive)")

    def update(self, client_id: int | None, value: float) -> None:
        """
        Record a new observation for this client.
        This is called after EVERY request.
        """
        if client_id is None:
            client_id = 0
        
        history = self._history.setdefault(client_id, [])
        history.append(value)

        logger.info(
            "History stats: "
            f"min={min(history):.3f}, "
            f"max={max(history):.3f}, "
            f"avg={sum(history)/len(history):.3f}, "
            f"count_1={sum(x >= 0.99 for x in history)}, "
            f"count_09={sum(x >= 0.90 for x in history)}, "
            f"count_08={sum(x >= 0.80 for x in history)}"
        )
        
        # Keep history bounded
        if len(history) > THRESHOLD_HISTORY:
            del history[:len(history) - THRESHOLD_HISTORY]
        
        # Recompute thresholds for this client
        previous = self._cache.get(client_id)
        self._cache[client_id] = self.compute(
            history,
            previous_high=previous.high if previous else None,
            previous_medium=previous.medium if previous else None,
        )
        
        # Log threshold changes periodically
        if len(history) % 100 == 0:
            current = self._cache[client_id]
            logger.info(
                f"[Adaptive] client={client_id}, "
                f"samples={len(history)}, "
                f"high={current.high:.3f}, "
                f"medium={current.medium:.3f}, "
                f"mean={current.mean:.3f}, "
                f"std={current.std_dev:.3f}"
            )

    def thresholds(self, client_id: int | None) -> tuple[float, float]:
        """
        Return the current thresholds for this client.
        """
        if client_id is None:
            client_id = 0
        
        cached = self._cache.get(client_id)
        
        if cached is None:
            return DEFAULT_HIGH_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD
        
        return cached.high, cached.medium

    def get_stats(self, client_id: int | None) -> dict:
        """
        Get statistical summary for a client.
        Useful for debugging and monitoring.
        """
        if client_id is None:
            client_id = 0
        
        cached = self._cache.get(client_id)
        if cached is None:
            return {
                "samples": 0,
                "high_threshold": DEFAULT_HIGH_THRESHOLD,
                "medium_threshold": DEFAULT_MEDIUM_THRESHOLD,
                "mean": 0.0,
                "std_dev": 0.0,
            }
        
        return {
            "samples": cached.sample_count,
            "high_threshold": cached.high,
            "medium_threshold": cached.medium,
            "high_percentile": cached.high_percentile,
            "medium_percentile": cached.medium_percentile,
            "mean": cached.mean,
            "std_dev": cached.std_dev,
        }

    def compute(
        self,
        history: list[float],
        previous_high: float | None = None,
        previous_medium: float | None = None,
    ) -> AdaptiveThresholds:
        """
        Compute truly adaptive thresholds from history.
        
        No hard caps - purely data-driven.
        """
        sample_count = len(history)


        
        # Not enough samples - use defaults
        if sample_count < MIN_SAMPLES:
            return AdaptiveThresholds(
                high=DEFAULT_HIGH_THRESHOLD,
                medium=DEFAULT_MEDIUM_THRESHOLD,
                high_percentile=0.0,
                medium_percentile=0.0,
                sample_count=sample_count,
                mean=0.0,
                std_dev=0.0,
            )
        
        sorted_history = sorted(history)
        logger.info(
            f"Top20={sorted_history[-20:]}"
        )
        
        # Calculate percentiles
        high_percentile = self._percentile(sorted_history, HIGH_PERCENTILE)
        medium_percentile = self._percentile(sorted_history, MEDIUM_PERCENTILE)

        high = high_percentile
        medium = medium_percentile
        
        # Calculate statistics
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std_dev = variance ** 0.5
        
        # Smooth with previous values if available
        if previous_high is not None:
            high = self._ewma(previous_high, high)
        if previous_medium is not None:
            medium = self._ewma(previous_medium, medium)

        # Keep adaptive thresholds within safe operating ranges.
        high = max(MIN_HIGH_THRESHOLD, min(high, MAX_HIGH_THRESHOLD))
        medium = max(MIN_MEDIUM_THRESHOLD, min(medium, MAX_MEDIUM_THRESHOLD))
        
        # Ensure thresholds are in logical order
        # High should always be >= medium
        if high < medium:
            high, medium = medium, high

        logger.info(
            f"p65={medium_percentile:.3f}, "
            f"p85={high_percentile:.3f}, "
            f"mean={mean:.3f}, "
            f"std={std_dev:.3f}"
        )
        
        
        return AdaptiveThresholds(
            high=round(high, 4),
            medium=round(medium, 4),
            high_percentile=round(high_percentile, 4),
            medium_percentile=round(medium_percentile, 4),
            sample_count=sample_count,
            mean=round(mean, 4),
            std_dev=round(std_dev, 4),
        )

    @staticmethod
    def _percentile(values: list[float], p: int) -> float:
        """Calculate percentile of sorted values."""
        if not values:
            return 0.0
        
        k = int((len(values) - 1) * p / 100)
        return values[k]

    @staticmethod
    def _ewma(old: float, new: float) -> float:
        """Exponentially weighted moving average for smoothing."""
        return (1 - EWMA_ALPHA) * old + EWMA_ALPHA * new


# Singleton instance
adaptive_thresholds = AdaptiveThresholdEngine()