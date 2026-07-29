"""
Penalty Context

A PenaltyContext is created once per request from RedisRepository.
It contains every piece of information required by the policy
pipeline.

RedisRepository
        │
        ▼
PenaltyContext
        │
 ┌──────┼────────┐
 ▼      ▼        ▼
Trust  Policy  Recovery
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class PenaltyContext:
    """
    Complete state of an identity at the time of evaluation.

    This object is immutable during policy execution.
    Engines should NEVER modify it.
    """

    # ==========================================================
    # Identity - REQUIRED (no defaults)
    # ==========================================================

    client_id: int | None

    identity_id: str

    ip_address: str

    fingerprint: str

    user_agent: str

    # ==========================================================
    # Current Request - REQUIRED (no defaults)
    # ==========================================================

    risk_score: float

    request_count: int

    error_count: int

    violation_count: int

    unique_ip_count: int

    # ==========================================================
    # Reputation - REQUIRED (no defaults)
    # ==========================================================

    ip_reputation: float

    identity_reputation: float

    fingerprint_reputation: float

    # ==========================================================
    # Current State - REQUIRED (no defaults)
    # ==========================================================

    is_blocked: bool

    ip_blocked: bool

    fingerprint_blocked: bool

    is_throttled: bool

    # ==========================================================
    # Adaptive Thresholds - REQUIRED (no defaults)
    # MOVED HERE BEFORE any fields with defaults
    # ==========================================================

    allow_threshold: float

    throttle_threshold: float

    block_threshold: float

    # ==========================================================
    # Historical Behavior (EWMA) - END USER LEVEL
    # NOW HAS A DEFAULT - this is fine because all required fields
    # are above this point
    # ==========================================================

    historical_suspicion: float = 0.0
    """
    EWMA of this END USER's recent suspicious behavior.
    
    Tracks the user (identity_id), not the client application.
    Updated every request with learn_baseline=True.
    Used to detect gradual behavior degradation.
    """

    # ==========================================================
    # Derived Values - ALL HAVE DEFAULTS
    # Filled by TrustEngine / RecoveryEngine
    # ==========================================================

    trust_score: float = 0.0

    recovery_score: float = 0.0

    combined_reputation: float = 0.0

    adjusted_risk: float = 0.0

    # ==========================================================
    # Optional Metadata - HAS DEFAULT
    # ==========================================================

    metadata: dict = field(default_factory=dict)

    # ==========================================================
    # Convenience Properties
    # ==========================================================

    @property
    def has_reputation(self) -> bool:
        return (
            self.ip_reputation > 0
            or self.identity_reputation > 0
            or self.fingerprint_reputation > 0
        )

    @property
    def has_violations(self) -> bool:
        return self.violation_count > 0

    @property
    def is_ip_rotating(self) -> bool:
        return self.unique_ip_count > 1

    @property
    def severe_ip_rotation(self) -> bool:
        return self.unique_ip_count >= 5

    @property
    def moderate_ip_rotation(self) -> bool:
        return self.unique_ip_count >= 3

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def is_high_request_volume(self) -> bool:
        return self.request_count >= 100

    @property
    def is_clean(self) -> bool:
        """
        User has behaved well recently.
        Used by RecoveryEngine.
        """
        return (
            self.violation_count == 0
            and self.error_count == 0
            and self.unique_ip_count <= 1
            and self.request_count < 40
        )

    @property
    def reputation_average(self) -> float:
        return (
            self.ip_reputation * 0.5
            + self.identity_reputation * 0.3
            + self.fingerprint_reputation * 0.2
        )

    # ==========================================================
    # Serialization
    # ==========================================================

    def as_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "identity_id": self.identity_id,
            "ip_address": self.ip_address,
            "fingerprint": self.fingerprint,
            "risk_score": self.risk_score,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "violation_count": self.violation_count,
            "unique_ip_count": self.unique_ip_count,
            "ip_reputation": self.ip_reputation,
            "identity_reputation": self.identity_reputation,
            "fingerprint_reputation": self.fingerprint_reputation,
            "combined_reputation": self.combined_reputation,
            "trust_score": self.trust_score,
            "recovery_score": self.recovery_score,
            "adjusted_risk": self.adjusted_risk,
            "is_blocked": self.is_blocked,
            "ip_blocked": self.ip_blocked,
            "fingerprint_blocked": self.fingerprint_blocked,
            "is_throttled": self.is_throttled,
            "allow_threshold": self.allow_threshold,
            "throttle_threshold": self.throttle_threshold,
            "block_threshold": self.block_threshold,
            "historical_suspicion": self.historical_suspicion,
            "metadata": self.metadata,
        }