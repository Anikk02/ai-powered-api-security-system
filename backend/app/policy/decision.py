# app/policy/decision.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import Action, BlockSeverity


@dataclass(slots=True)
class PenaltyDecision:
    """
    Final decision returned by PolicyEngine.

    This object contains ONLY business decisions.
    RedisRepository is responsible for persisting them.
    """

    # ==========================================================
    # Decision
    # ==========================================================

    action: Action
    reason: str

    # ==========================================================
    # Scores
    # ==========================================================

    risk_score: float
    trust_score: float
    reputation: float

    # ==========================================================
    # Reputation update
    # ==========================================================

    reputation_delta: float = 0.0

    # ==========================================================
    # Recovery
    # ==========================================================

    should_recover: bool = False
    recovery_delta: float = 0.0

    # ==========================================================
    # Violation handling
    # ==========================================================

    increment_violation: bool = False

    # ==========================================================
    # Block
    # ==========================================================

    should_block: bool = False
    block_severity: BlockSeverity | None = None
    block_duration: int = 0

    # ==========================================================
    # Throttle
    # ==========================================================

    should_throttle: bool = False
    throttle_duration: int = 0

    # ==========================================================
    # Adaptive Baseline Learning
    # ==========================================================

    learn_baseline: bool = False  # <-- ADD THIS FIELD

    # ==========================================================
    # Logging / Explainability
    # ==========================================================

    explanation: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)

    # ==========================================================
    # Helpers
    # ==========================================================

    @property
    def is_allowed(self) -> bool:
        return self.action == "allow"

    @property
    def is_blocked(self) -> bool:
        return self.action == "block"

    @property
    def is_throttled(self) -> bool:
        return self.action == "throttle"

    @property
    def needs_reputation_update(self) -> bool:
        return (
            self.reputation_delta != 0.0
            or self.recovery_delta != 0.0
        )

    @property
    def final_reputation_delta(self) -> float:
        """
        Final reputation delta applied to Redis.

        Positive  -> increase reputation (more suspicious)

        Negative  -> recovery (become more trusted)
        """
        return self.reputation_delta + self.recovery_delta

    @property
    def needs_redis_update(self) -> bool:
        """
        Repository can skip unnecessary writes.
        """
        return (
            self.should_block
            or self.should_throttle
            or self.increment_violation
            or self.needs_reputation_update
        )

    # ==========================================================
    # Serialization
    # ==========================================================

    def to_metadata(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,

            "risk_score": round(self.risk_score, 4),
            "trust_score": round(self.trust_score, 4),
            "reputation": round(self.reputation, 4),

            "reputation_delta": round(self.reputation_delta, 4),
            "recovery_delta": round(self.recovery_delta, 4),
            "final_reputation_delta": round(
                self.final_reputation_delta,
                4,
            ),

            "block": self.should_block,
            "block_duration": self.block_duration,
            "block_severity": self.block_severity,

            "throttle": self.should_throttle,
            "throttle_duration": self.throttle_duration,

            "increment_violation": self.increment_violation,
            "recovered": self.should_recover,

            "learn_baseline": self.learn_baseline,  # <-- ADD THIS

            "metadata": self.metadata,
        }